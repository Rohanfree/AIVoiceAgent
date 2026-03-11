"""
jwt_handler.py — JWT token creation and verification with dual-scope support.

Scopes:
  - 'dashboard'   → short-lived (15 min) for human interactive sessions
  - 'tool'        → long-lived (7 days) for M2M AI tool communication
  - 'admin:all'   → admin scope (inherits dashboard lifespan)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


def create_access_token(
    data: dict[str, Any],
    scope: str = "dashboard",
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Payload dict (must include 'sub' with user identifier).
        scope: Token scope — 'dashboard', 'tool', or 'admin:all'.
        expires_delta: Custom expiry. Defaults to config-based lifespan.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    now = datetime.now(tz=timezone.utc)

    if expires_delta is None:
        if scope == "tool":
            expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)
        else:
            expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({
        "exp": now + expires_delta,
        "iat": now,
        "scope": scope,
    })

    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    Create a long-lived refresh token for token rotation.

    Args:
        data: Payload dict (must include 'sub').

    Returns:
        Encoded JWT refresh token string.
    """
    to_encode = data.copy()
    now = datetime.now(tz=timezone.utc)
    expires = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode.update({
        "exp": expires,
        "iat": now,
        "scope": "refresh",
    })

    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    """
    Decode and validate a JWT token.

    Returns:
        Token payload dict if valid, None if expired/invalid.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        logger.debug("JWT verification failed: %s", exc)
        return None
