"""
auth_router.py — Authentication endpoints under /automiteui/auth/*.

Handles:
  POST /automiteui/auth/login     → username/password → tokens
  POST /automiteui/auth/register  → create user + client record
  POST /automiteui/auth/refresh   → rotate refresh token
"""

import logging
import smtplib
import uuid
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client, FieldFilter

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


# ─── CHECK AGENT ───────────────────────────────────────────────────────────

@router.get("/check-agent", summary="Check if an ElevenLabs agent ID is already registered")
async def check_agent(agent_id: str, db: Client = Depends(get_db)):
    """Returns {taken, client_name, first_message} for the given agent ID."""
    from app.services.elevenlabs_service import get_agent as el_get_agent

    docs = (
        db.collection("users")
        .where(filter=FieldFilter("elevenlabs_agent_id", "==", agent_id))
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        return {"taken": True, "client_name": data.get("client_name", "another client"), "first_message": ""}

    # Not taken — fetch first_message from ElevenLabs
    first_message = ""
    try:
        agent_data = await el_get_agent(agent_id)
        if agent_data:
            first_message = (
                agent_data
                .get("conversation_config", {})
                .get("agent", {})
                .get("first_message", "")
            ) or ""
    except Exception:
        pass

    return {"taken": False, "first_message": first_message}


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
    3. Create client document in Firestore
    4. Return JWT tokens
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
    client_id = str(uuid.uuid4())

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
        "email": body.email,
        "elevenlabs_agent_id": body.elevenlabs_agent_id,
        "created_at": now,
    }
    db.collection("users").document(user_id).set(user_doc)
    logger.info("User '%s' registered with id=%s, client_id=%s", body.username, user_id, client_id)

    # Generate a long-lived tool token (embedded in ElevenLabs agent tool headers)
    tool_token = create_access_token(
        {"sub": client_id, "client_id": client_id},
        scope="tool",
        expires_delta=timedelta(days=365),
    )

    # Create client document
    client_doc = {
        "id": client_id,
        "user_id": user_id,
        "business_name": body.client_name,
        "email": body.email,
        "timezone": body.timezone,
        "elevenlabs_agent_id": body.elevenlabs_agent_id,
        "tool_token": tool_token,
        "services": [],
        "operating_hours": {},
        "policies": {},
        "currency": "INR",
        "knowledge_base_text": body.business_info.strip(),
        "is_active": True,
        "subscription_status": "active",
        "created_at": now,
    }
    db.collection("clients").document(client_id).set(client_doc)
    logger.info("Client '%s' created with id=%s", body.client_name, client_id)

    # Send welcome email to the registered email address
    _send_welcome_email(body.email, body.client_name)

    from app.services.elevenlabs_service import setup_agent_tools, patch_agent_tools, inject_client_context_into_prompt, patch_agent_first_message

    # Step 1: Resolve tool IDs (creates missing tools, no agent PATCH yet)
    try:
        tool_ids = await setup_agent_tools(
            agent_id=body.elevenlabs_agent_id,
            client_id=client_id,
        )
        if tool_ids is None:
            raise RuntimeError("setup_agent_tools returned None")
    except Exception as exc:
        logger.error("setup_agent_tools failed during registration — rolling back: %s", exc)
        db.collection("users").document(user_id).delete()
        db.collection("clients").document(client_id).delete()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to configure ElevenLabs agent tools. Please verify your Agent ID and try again.",
        )

    # Step 2: PATCH agent with tool_ids only (no KB)
    try:
        patch_ok = await patch_agent_tools(
            agent_id=body.elevenlabs_agent_id,
            tool_ids=tool_ids,
        )
        if not patch_ok:
            logger.error("patch_agent_tools failed for client %s — tools may not be attached", client_id)
    except Exception as exc:
        logger.error("patch_agent_tools error for client %s: %s", client_id, exc)

    # Step 3: Inject client_id + business_info directly into the agent's system prompt
    try:
        await inject_client_context_into_prompt(
            agent_id=body.elevenlabs_agent_id,
            client_id=client_id,
            business_info=body.business_info,
        )
    except Exception as exc:
        logger.error("inject_client_context_into_prompt failed for client %s: %s", client_id, exc)

    # Step 4: Update agent's first message if provided
    if body.first_message.strip():
        try:
            await patch_agent_first_message(
                agent_id=body.elevenlabs_agent_id,
                first_message=body.first_message.strip(),
            )
        except Exception as exc:
            logger.error("patch_agent_first_message failed for client %s: %s", client_id, exc)

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

def _send_welcome_email(client_email: str, business_name: str) -> None:
    """Send a welcome email to the newly registered client."""
    try:
        if not settings.smtp_user or not settings.smtp_password:
            logger.warning("SMTP not configured — skipping welcome email for %s", client_email)
            return

        dashboard_url = settings.base_url.rstrip("/") + "/automiteui/pages/dashboard"
        html_body = f"""
        <html><body style="font-family:'Helvetica Neue',Arial,sans-serif;color:#111;max-width:600px;margin:0 auto;">
          <div style="background:#1A4D3A;padding:24px 32px;border-radius:12px 12px 0 0;">
            <h1 style="margin:0;color:#fff;font-size:22px;">Welcome to Automite AI!</h1>
          </div>
          <div style="background:#f9f9f9;padding:32px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 12px 12px;">
            <p>Hi <strong>{business_name}</strong>,</p>
            <p>Your Automite AI account has been created successfully. Your AI voice assistant is ready to be configured.</p>
            <p><a href="{dashboard_url}" style="background:#1A4D3A;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;">Go to Dashboard</a></p>
            <p style="margin-top:24px;font-size:13px;color:#666;">
              Next step: Connect your Google Calendar from the dashboard to enable automated call log sheets and appointment booking.
            </p>
          </div>
          <p style="font-size:12px;color:#999;text-align:center;margin-top:16px;">Sent by Automite AI</p>
        </body></html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Welcome to Automite AI — {business_name}"
        msg["From"] = f"Automite AI <{settings.smtp_user}>"
        msg["To"] = client_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, client_email, msg.as_string())

        logger.info("Welcome email sent to %s for business '%s'", client_email, business_name)
    except Exception as exc:
        logger.error("Failed to send welcome email to %s: %s", client_email, exc)


def _find_user_by_username(db: Client, username: str) -> dict | None:
    """Look up a user document by username. Returns dict or None."""
    docs = (
        db.collection("users")
        .where(filter=FieldFilter("username", "==", username))
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
