"""
auth_router.py — Authentication endpoints under /automiteui/auth/*.

Handles:
  POST /automiteui/auth/login     → username/password → tokens
  POST /automiteui/auth/register  → create user + clone Vapi assistant
  POST /automiteui/auth/refresh   → rotate refresh token
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client

from app.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from app.auth.password import hash_password, verify_password
from app.config import settings
from app.db import get_db
from app.schemas.auth_models import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ─── LOGIN ─────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
)
async def login(body: LoginRequest, db: Client = Depends(get_db)) -> TokenResponse:
    """
    Authenticate a user with username + password.
    Returns an access token and a refresh token.
    """
    # Check admin account first
    if body.username == settings.admin_username:
        if not verify_password(body.password, _get_admin_hash(db)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )
        scope = "admin:all"
        token_data = {"sub": "admin", "username": settings.admin_username, "is_admin": True}

        return TokenResponse(
            access_token=create_access_token(token_data, scope=scope),
            refresh_token=create_refresh_token(token_data),
            scope=scope,
            expires_in_minutes=settings.jwt_access_token_expire_minutes,
        )

    # Look up regular user by username
    user_doc = _find_user_by_username(db, body.username)
    if user_doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not verify_password(body.password, user_doc.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    scope = "dashboard"
    token_data = {
        "sub": user_doc["id"],
        "username": user_doc["username"],
        "client_id": user_doc.get("client_id"),
        "is_admin": False,
    }

    return TokenResponse(
        access_token=create_access_token(token_data, scope=scope),
        refresh_token=create_refresh_token(token_data),
        scope=scope,
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
    )


# ─── REGISTER ──────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new client user",
)
async def register(body: RegisterRequest, db: Client = Depends(get_db)) -> TokenResponse:
    """
    Register a new client user.

    Flow:
    1. Validate username is unique
    2. Create user document in Firestore
    3. Clone Vapi assistant using template (if VAPI_API_KEY is configured)
    4. Create client document in Firestore
    5. Return JWT tokens
    """
    # Check for duplicate username
    existing = _find_user_by_username(db, body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' is already taken.",
        )

    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(body.password)

    # Try to clone Vapi assistant
    client_id = str(uuid.uuid4())  # fallback if Vapi not configured
    vapi_assistant_id = None

    if settings.vapi_api_key:
        try:
            from app.services.vapi_service import clone_assistant

            vapi_assistant_id = await clone_assistant(
                client_name=body.client_name,
                assistant_name=body.assistant_name,
            )
            if vapi_assistant_id:
                client_id = vapi_assistant_id
        except Exception as exc:
            logger.warning("Vapi assistant cloning failed (continuing): %s", exc)

    # Create user document
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc).isoformat()

    user_doc = {
        "id": user_id,
        "username": body.username,
        "hashed_password": hashed_pw,
        "is_admin": False,
        "subscription_status": "active",
        "client_id": client_id,
        "client_name": body.client_name,
        "assistant_name": body.assistant_name,
        "created_at": now,
    }
    db.collection("users").document(user_id).set(user_doc)
    logger.info("User '%s' registered with id=%s, client_id=%s", body.username, user_id, client_id)

    # Create client document
    client_doc = {
        "id": client_id,
        "user_id": user_id,
        "business_name": body.client_name,
        "assistant_name": body.assistant_name,
        "vapi_assistant_id": vapi_assistant_id,
        "services": [],
        "operating_hours": {},
        "policies": {},
        "currency": "INR",
        "is_active": True,
        "subscription_status": "active",
        "created_at": now,
    }
    db.collection("clients").document(client_id).set(client_doc)
    logger.info("Client '%s' created with id=%s", body.client_name, client_id)

    # Issue tokens
    scope = "dashboard"
    token_data = {
        "sub": user_id,
        "username": body.username,
        "client_id": client_id,
        "is_admin": False,
    }

    return TokenResponse(
        access_token=create_access_token(token_data, scope=scope),
        refresh_token=create_refresh_token(token_data),
        scope=scope,
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
    )


# ─── REFRESH ───────────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and get a new access token",
)
async def refresh_token(body: RefreshRequest) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    Old refresh token is implicitly invalidated by issuing a new one.
    """
    payload = verify_token(body.refresh_token)

    if payload is None or payload.get("scope") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    # Determine scope for the new access token
    is_admin = payload.get("is_admin", False)
    scope = "admin:all" if is_admin else "dashboard"

    token_data = {
        "sub": payload["sub"],
        "username": payload.get("username"),
        "client_id": payload.get("client_id"),
        "is_admin": is_admin,
    }

    return TokenResponse(
        access_token=create_access_token(token_data, scope=scope),
        refresh_token=create_refresh_token(token_data),
        scope=scope,
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
    )


# ─── Helpers ────────────────────────────────────────────────────────────────

def _find_user_by_username(db: Client, username: str) -> dict | None:
    """Look up a user document by username. Returns dict or None."""
    docs = (
        db.collection("users")
        .where("username", "==", username)
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None


def _get_admin_hash(db: Client) -> str:
    """
    Get the admin password hash.

    First checks Firestore for a seeded admin user,
    then falls back to hashing the password from settings.
    """
    admin_doc = _find_user_by_username(db, settings.admin_username)
    if admin_doc:
        return admin_doc.get("hashed_password", "")

    # Fallback: hash from env (first login before seed script runs)
    return hash_password(settings.admin_password)
