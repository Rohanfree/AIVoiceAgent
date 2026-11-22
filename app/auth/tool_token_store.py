"""
tool_token_store.py — server-side record of issued ElevenLabs tool tokens (rotation + revocation).

Each tool token is a JWT (scope="tool") carrying a unique `jti` and the
`client_id` it was issued for. A Firestore document keyed by that jti in
`tool_tokens` tracks client binding, expiry and revoked/superseded state. Raw
tokens are never stored or logged. A token authenticates only while its record
exists, is unrevoked, unexpired and bound to the same client_id as the claim,
so a revoked, superseded or never-issued (e.g. legacy jti-less) token is
rejected even if its signature is valid.

Rotation issues the new record first, then revokes every other active record
for the client, so a client never has two live tokens once rotation returns.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud.firestore import FieldFilter
from jose import jwt

from app.auth.jwt_handler import create_access_token, verify_token

logger = logging.getLogger(__name__)

COLLECTION = "tool_tokens"

# Matches the lifetime previously used for tool tokens issued at registration.
TOOL_TOKEN_TTL = timedelta(days=365)


class ToolTokenInvalid(Exception):
    """Token is expired, tampered, revoked, superseded, unknown or unbound."""


class ToolTokenStoreUnavailable(Exception):
    """Database missing or failing; tool auth must fail closed."""


def _mint(client_id: str) -> tuple[str, dict[str, Any]]:
    """Mint a tool token and build its tracking record. Returns (token, record)."""
    jti = uuid.uuid4().hex
    token = create_access_token(
        {"sub": client_id, "client_id": client_id, "jti": jti},
        scope="tool",
        expires_delta=TOOL_TOKEN_TTL,
    )
    claims = jwt.get_unverified_claims(token)
    record = {
        "jti": jti,
        "client_id": client_id,
        "scope": "tool",
        "issued_at": datetime.fromtimestamp(claims["iat"], tz=timezone.utc),
        "expires_at": datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
        "revoked": False,
        "revoked_at": None,
        "replaced_by": None,
    }
    return token, record


def issue_tool_token(db: Any, client_id: str) -> tuple[str, str]:
    """Create a tool token for a client and persist its record. Returns (token, jti)."""
    if db is None:
        raise ToolTokenStoreUnavailable("database unavailable")
    if not isinstance(client_id, str) or not client_id:
        raise ValueError("client_id is required")
    token, record = _mint(client_id)
    try:
        db.collection(COLLECTION).document(record["jti"]).set(record)
    except Exception as exc:
        logger.error("Failed to store tool token record: %s", type(exc).__name__)
        raise ToolTokenStoreUnavailable("database error") from exc
    return token, record["jti"]


def revoke_client_tool_tokens(db: Any, client_id: str, replaced_by: str | None = None,
                              keep_jti: str | None = None) -> int:
    """Revoke every active tool token record for a client (except keep_jti). Returns count."""
    if db is None:
        raise ToolTokenStoreUnavailable("database unavailable")
    now = datetime.now(tz=timezone.utc)
    count = 0
    try:
        docs = db.collection(COLLECTION).where(filter=FieldFilter("client_id", "==", client_id)).stream()
        for doc in docs:
            rec = doc.to_dict() or {}
            if rec.get("revoked") or rec.get("jti") == keep_jti:
                continue
            doc.reference.update({"revoked": True, "revoked_at": now, "replaced_by": replaced_by})
            count += 1
    except Exception as exc:
        logger.error("Failed to revoke tool tokens: %s", type(exc).__name__)
        raise ToolTokenStoreUnavailable("database error") from exc
    return count


def rotate_tool_token(db: Any, client_id: str) -> tuple[str, str]:
    """Issue a fresh tool token and revoke all older ones. Returns (token, jti)."""
    token, jti = issue_tool_token(db, client_id)
    try:
        revoke_client_tool_tokens(db, client_id, replaced_by=jti, keep_jti=jti)
    except ToolTokenStoreUnavailable:
        try:
            db.collection(COLLECTION).document(jti).update({
                "revoked": True,
                "revoked_at": datetime.now(tz=timezone.utc),
            })
        except Exception as exc:
            logger.error("Failed to roll back rotated tool token: %s", type(exc).__name__)
        raise
    return token, jti


def verify_tool_token(db: Any, token: str) -> dict[str, Any]:
    """
    Validate a tool JWT against its server-side record.

    Returns the decoded payload. Raises ToolTokenInvalid or ToolTokenStoreUnavailable.
    """
    payload = verify_token(token)
    if payload is None or payload.get("scope") != "tool":
        raise ToolTokenInvalid("bad signature, expiry or scope")
    jti = payload.get("jti")
    client_id = payload.get("client_id")
    if not isinstance(jti, str) or not jti or not isinstance(client_id, str) or not client_id:
        raise ToolTokenInvalid("missing jti/client_id")
    if db is None:
        raise ToolTokenStoreUnavailable("database unavailable")
    try:
        snap = db.collection(COLLECTION).document(jti).get()
        rec = snap.to_dict() if snap.exists else None
    except Exception as exc:
        logger.error("Tool token lookup failed: %s", type(exc).__name__)
        raise ToolTokenStoreUnavailable("database error") from exc
    if not rec or rec.get("revoked"):
        raise ToolTokenInvalid("unknown or revoked")
    expires_at = rec.get("expires_at")
    if expires_at is None or expires_at <= datetime.now(tz=timezone.utc):
        raise ToolTokenInvalid("record expired")
    if rec.get("client_id") != client_id:
        raise ToolTokenInvalid("client mismatch")
    return payload
