"""
refresh_store.py — server-side record of issued refresh tokens (rotation + revocation).

Each refresh token carries a unique `jti`. A Firestore document keyed by that
jti in `refresh_tokens` tracks user/client binding, expiry and used/revoked
state. Raw tokens are never stored. Rotation runs in a single Firestore
transaction: the old record is marked used and the new record is created
atomically, so a token can be redeemed at most once.

Replaying an already-used token is treated as theft: every token in its
family (the chain of rotations descending from one login) is revoked.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from jose import jwt

from app.auth.jwt_handler import create_refresh_token, verify_token

logger = logging.getLogger(__name__)

COLLECTION = "refresh_tokens"

# Indirection so tests can run the transaction body against a fake database.
transactional = firestore.transactional


class RefreshTokenInvalid(Exception):
    """Token is expired, tampered, replayed, revoked, wrong scope or unbound."""


class RefreshStoreUnavailable(Exception):
    """Database missing or failing; refresh must fail closed."""


def _issue(token_data: dict[str, Any], family_id: str) -> tuple[str, str, dict[str, Any]]:
    """Mint a refresh token and build its tracking record. Returns (token, jti, record)."""
    jti = uuid.uuid4().hex
    token = create_refresh_token(token_data, jti=jti)
    claims = jwt.get_unverified_claims(token)
    record = {
        "jti": jti,
        "family_id": family_id,
        "user_id": token_data["sub"],
        "client_id": token_data.get("client_id"),
        "is_admin": bool(token_data.get("is_admin", False)),
        "scope": "refresh",
        "issued_at": datetime.fromtimestamp(claims["iat"], tz=timezone.utc),
        "expires_at": datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
        "used": False,
        "revoked": False,
        "replaced_by": None,
    }
    return token, jti, record


def issue_refresh_token(db: Any, token_data: dict[str, Any]) -> str:
    """Create a refresh token for a fresh login and persist its record."""
    if db is None:
        raise RefreshStoreUnavailable("database unavailable")
    token, jti, record = _issue(token_data, family_id=uuid.uuid4().hex)
    try:
        db.collection(COLLECTION).document(jti).set(record)
    except Exception as exc:
        logger.error("Failed to store refresh token record: %s", type(exc).__name__)
        raise RefreshStoreUnavailable("database error") from exc
    return token


def rotate_refresh_token(db: Any, presented_token: str) -> tuple[dict[str, Any], str]:
    """
    Redeem a refresh token exactly once.

    Returns (token_data, new_refresh_token) where token_data holds the bound
    sub/username/client_id/is_admin for minting the matching access token.
    Raises RefreshTokenInvalid or RefreshStoreUnavailable.
    """
    payload = verify_token(presented_token)
    if payload is None or payload.get("scope") != "refresh":
        raise RefreshTokenInvalid("bad signature, expiry or scope")
    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti or not payload.get("sub"):
        raise RefreshTokenInvalid("missing jti/sub")
    if db is None:
        raise RefreshStoreUnavailable("database unavailable")

    token_data = {
        "sub": payload["sub"],
        "username": payload.get("username"),
        "client_id": payload.get("client_id"),
        "is_admin": bool(payload.get("is_admin", False)),
    }
    old_ref = db.collection(COLLECTION).document(jti)
    now = datetime.now(tz=timezone.utc)

    def _redeem(transaction):
        snap = old_ref.get(transaction=transaction)
        if not snap.exists:
            return "invalid", None, None
        rec = snap.to_dict() or {}
        if rec.get("used"):
            return "replay", rec.get("family_id"), None
        if rec.get("revoked"):
            return "invalid", None, None
        expires_at = rec.get("expires_at")
        if expires_at is None or expires_at <= now:
            return "invalid", None, None
        if (
            rec.get("user_id") != token_data["sub"]
            or rec.get("client_id") != token_data["client_id"]
            or bool(rec.get("is_admin")) != token_data["is_admin"]
        ):
            return "invalid", None, None
        new_token, new_jti, new_rec = _issue(token_data, rec["family_id"])
        transaction.update(old_ref, {"used": True, "used_at": now, "replaced_by": new_jti})
        transaction.set(db.collection(COLLECTION).document(new_jti), new_rec)
        return "ok", None, new_token

    try:
        outcome, family_id, new_token = transactional(_redeem)(db.transaction())
    except Exception as exc:
        logger.error("Refresh rotation failed: %s", type(exc).__name__)
        raise RefreshStoreUnavailable("database error") from exc

    if outcome == "replay":
        logger.warning("Refresh token replay detected; revoking family for user %s", token_data["sub"])
        _revoke_family(db, family_id)
        raise RefreshTokenInvalid("replayed")
    if outcome != "ok":
        raise RefreshTokenInvalid("not redeemable")
    return token_data, new_token


def _revoke_family(db: Any, family_id: str | None) -> None:
    """Best-effort revocation of every record in a rotation family."""
    if not family_id:
        return
    try:
        docs = db.collection(COLLECTION).where(filter=FieldFilter("family_id", "==", family_id)).stream()
        for doc in docs:
            doc.reference.update({"revoked": True})
    except Exception as exc:
        logger.error("Failed to revoke refresh family: %s", type(exc).__name__)
