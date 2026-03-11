"""
dependencies.py — FastAPI Depends() callables for authentication and authorization.

Usage in routes:
    @router.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        ...

    @router.get("/admin-only")
    async def admin_only(user: dict = Depends(require_admin)):
        ...
"""

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_handler import verify_token

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    Extract and validate the current user from the Authorization header.

    Raises 401 if no token or token is invalid/expired.
    Returns the decoded JWT payload dict.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """
    Ensure the authenticated user has admin privileges.

    Raises 403 if the user's scope is not 'admin:all'.
    """
    scope = user.get("scope", "")
    if scope != "admin:all":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


def require_scope(required_scope: str):
    """
    Factory that returns a dependency requiring a specific token scope.

    Usage:
        @router.get("/tool-only", dependencies=[Depends(require_scope("tool"))])
    """

    async def _check_scope(user: dict = Depends(get_current_user)) -> dict:
        scope = user.get("scope", "")
        if scope != required_scope and scope != "admin:all":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{required_scope}' is required.",
            )
        return user

    return _check_scope
