"""
google_auth_router.py — Handles Google OAuth2 flow for Calendar access.
Endpoints:
  - POST /client/auth/google/start: Starts OAuth flow (Bearer auth, returns authorization_url).
  - GET /client/auth/google/login: Header-authenticated redirect variant of /start.
  - GET /client/auth/google/debug: Admin-only diagnostics.
  - GET /client/auth/google/callback: Finishes OAuth flow and stores tokens.
"""

import hashlib
import hmac
import logging
import os
import re
import secrets
import urllib.parse
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests as http_requests
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from app.config import settings
from app.db import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.services.sheets_service import create_client_sheet
from app.services.token_crypto import firestore_token_write
from google.api_core.exceptions import AlreadyExists
from jose import JWTError, jwt

# Allow insecure transport when base_url uses http (local dev or http-only deployments)
if settings.base_url.startswith("http://"):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/client/auth/google",
    tags=["Google OAuth"],
)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

OAUTH_STATE_TTL_SECONDS = 600
_STATE_TYPE = "google_oauth_state"
_STATE_COLLECTION = "oauth_states_used"
_DEFAULT_RETURN_PATH = "/automiteui/pages/dashboard"
_CONTROL_CHARS = re.compile(r"[\x00-\x20\x7f\\]")


def _callback_uri() -> str:
    # Built from base_url so the scheme matches what is registered in Google Cloud Console.
    return settings.base_url.rstrip("/") + "/automiteaiapplication/client/auth/google/callback"


def _origin(url: str) -> str | None:
    parts = urllib.parse.urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def _allowed_origins() -> set[str]:
    origins = {_origin(settings.base_url), _origin(settings.public_site_url)}
    origins.update(_origin(o) for o in settings.cors_origins)
    return {o for o in origins if o}


def validate_return_to(return_to: str | None) -> str | None:
    """Return a safe return_to or None if absent; raise ValueError if off-list.

    Accepts a same-origin absolute path ("/x") or an absolute http(s) URL whose
    origin is base_url, public_site_url or a configured CORS origin.
    """
    if not return_to:
        return None
    if len(return_to) > 2048 or _CONTROL_CHARS.search(return_to):
        raise ValueError("return_to is not allowed")
    if return_to.startswith("/"):
        if return_to.startswith("//"):
            raise ValueError("return_to is not allowed")
        return return_to
    parts = urllib.parse.urlsplit(return_to)
    if (
        parts.scheme not in ("http", "https")
        or parts.username is not None
        or parts.password is not None
        or _origin(return_to) not in _allowed_origins()
    ):
        raise ValueError("return_to is not allowed")
    return return_to


def _state_key() -> str:
    # Derived key: a state token can never verify as an access token, or vice versa.
    return hmac.new(
        settings.jwt_secret_key.encode(), b"google-oauth-state-v1", hashlib.sha256
    ).hexdigest()


def create_oauth_state(client_id: str, return_to: str | None) -> str:
    """Signed, short-lived state carrying only the client id, return_to and a nonce."""
    now = datetime.now(tz=timezone.utc)
    claims = {
        "typ": _STATE_TYPE,
        "cid": client_id,
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(seconds=OAUTH_STATE_TTL_SECONDS),
    }
    if return_to:
        claims["r"] = return_to
    return jwt.encode(claims, _state_key(), algorithm="HS256")


def verify_oauth_state(state: str) -> dict:
    """Verify signature, expiry and type. Raises ValueError otherwise."""
    try:
        claims = jwt.decode(state, _state_key(), algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Invalid or expired state") from exc
    if claims.get("typ") != _STATE_TYPE or not claims.get("cid") or not claims.get("jti"):
        raise ValueError("Invalid state")
    return claims


def consume_oauth_state(db, claims: dict) -> None:
    """Mark the state nonce used; atomic create() fails if it was already consumed."""
    try:
        db.collection(_STATE_COLLECTION).document(claims["jti"]).create({
            "client_id": claims["cid"],
            "used_at": datetime.now(tz=timezone.utc),
            "expires_at": datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
        })
    except AlreadyExists as exc:
        raise ValueError("State already used") from exc


def _build_authorization_url(user: dict, return_to: str | None) -> str:
    client_id = user.get("client_id")
    if user.get("scope") == "tool" or not isinstance(client_id, str) or not client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A client session is required.")
    try:
        safe_return_to = validate_return_to(return_to)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="return_to is not allowed.")

    flow = Flow.from_client_config(get_client_config(), scopes=SCOPES, redirect_uri=_callback_uri())
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=create_oauth_state(client_id, safe_return_to),
        prompt="consent",
    )
    return authorization_url


def _with_params(url: str, params: dict) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.urlencode(params)
    query = f"{parts.query}&{query}" if parts.query else query
    return urllib.parse.urlunsplit(parts._replace(query=query))


def _result_redirect(return_to: str | None, **params) -> RedirectResponse:
    target = return_to
    if target:
        try:
            target = validate_return_to(target)
        except ValueError:
            target = None
    if not target:
        target = settings.base_url.rstrip("/") + _DEFAULT_RETURN_PATH
    return RedirectResponse(url=_with_params(target, params))


def get_client_config():
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth credentials are not configured in .env",
        )
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        }
    }

@router.get("/debug")
async def google_debug(request: Request, user: dict = Depends(require_admin)):
    """Admin-only OAuth configuration diagnostics (never exposes secret values)."""
    return {
        "base_url_settings": settings.base_url,
        "computed_redirect_uri": _callback_uri(),
        "request_url_host": request.url.netloc,
        "client_id_present": bool(settings.google_client_id),
        "client_secret_present": bool(settings.google_client_secret),
        "insecure_transport_env": os.environ.get('OAUTHLIB_INSECURE_TRANSPORT'),
    }

@router.post("/start")
async def google_start(return_to: str | None = None, user: dict = Depends(get_current_user)):
    """Start Google OAuth. The app JWT travels in the Authorization header, never the URL.

    Returns {"authorization_url": ...} for the browser to navigate to.
    """
    return {"authorization_url": _build_authorization_url(user, return_to)}

@router.get("/login")
async def google_login(return_to: str | None = None, user: dict = Depends(get_current_user)):
    """Header-authenticated variant of /start that responds with a redirect.

    The former ``?token=`` query parameter is no longer accepted.
    """
    return RedirectResponse(_build_authorization_url(user, return_to))

@router.get("/callback", name="google_callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """OAuth callback. Verifies the signed single-use state to identify the client."""
    return_to = None
    try:
        # 1. Verify and consume state before doing anything else
        if not state:
            raise ValueError("Missing state")
        claims = verify_oauth_state(state)
        return_to = claims.get("r")
        client_id = claims["cid"]
        db = get_db()
        consume_oauth_state(db, claims)

        if error or not code:
            logger.warning("Google OAuth returned an error for client %s: %s", client_id, error)
            return _result_redirect(return_to, google_linked="error", detail="access_denied" if error == "access_denied" else "google_error")

        # 2. Exchange code for tokens
        client_config = get_client_config()
        redirect_uri = _callback_uri()

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # 3. Save to Firestore
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }

        logger.info("Attempting to save tokens to Firestore for client: %s", client_id)
        write = firestore_token_write(token_data, client_id)
        db.collection("clients").document(client_id).set(write["data"], merge=write["merge"])
        logger.info("Successfully updated Firestore document for client: %s", client_id)

        # 4. Create a Google Sheet — only if one hasn't been created yet
        try:
            client_doc = db.collection("clients").document(client_id).get()
            client_data = client_doc.to_dict() or {}
            existing_sheet_id = client_data.get("google_sheet_id")

            business_name = client_data.get("business_name", "Client")
            if existing_sheet_id:
                logger.info("Sheet already exists for client %s — re-sending notification", client_id)
                _send_sheet_notification(credentials, client_id, business_name, existing_sheet_id, db)
            else:
                sheet_id = create_client_sheet(client_id, business_name, token_data)
                if sheet_id:
                    db.collection("clients").document(client_id).set(
                        {"google_sheet_id": sheet_id}, merge=True
                    )
                    logger.info("Google Sheet saved to Firestore | client=%s | sheet_id=%s", client_id, sheet_id)
                    _send_sheet_notification(credentials, client_id, business_name, sheet_id, db)
        except Exception as sheet_exc:
            logger.error("Sheet creation failed for client %s (non-fatal): %s", client_id, sheet_exc)

        # 5. Redirect back to the originating page (or fallback to dashboard)
        return _result_redirect(return_to, google_linked="success")

    except Exception as e:
        logger.exception("Google OAuth callback failed")
        detail = "invalid_state" if isinstance(e, ValueError) else "callback_failed"
        return _result_redirect(return_to, google_linked="error", detail=detail)


def _send_sheet_notification(credentials, client_id: str, business_name: str, sheet_id: str, db) -> None:
    """Fetch client's Google email via userinfo API and send a sheet-created notification."""
    try:
        resp = http_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=10,
        )
        resp.raise_for_status()
        client_email = resp.json().get("email")
        if not client_email:
            logger.warning("Could not retrieve Google email for client %s", client_id)
            return

        db.collection("clients").document(client_id).set(
            {"google_user_email": client_email}, merge=True
        )

        if not settings.smtp_user or not settings.smtp_password:
            logger.warning("SMTP not configured — skipping sheet notification email")
            return

        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        html_body = f"""
        <html><body style="font-family:'Helvetica Neue',Arial,sans-serif;color:#111;max-width:600px;margin:0 auto;">
          <div style="background:#1A4D3A;padding:24px 32px;border-radius:12px 12px 0 0;">
            <h1 style="margin:0;color:#fff;font-size:22px;">Your Call Log Sheet is Ready</h1>
          </div>
          <div style="background:#f9f9f9;padding:32px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 12px 12px;">
            <p>Hi <strong>{business_name}</strong>,</p>
            <p>Your Google Sheet for call logs has been created successfully in your Google Drive.</p>
            <p><a href="{sheet_url}" style="background:#1A4D3A;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;">Open Your Sheet</a></p>
            <p style="margin-top:24px;font-size:13px;color:#666;">This sheet will automatically receive call log entries from your Automite AI assistant.</p>
          </div>
          <p style="font-size:12px;color:#999;text-align:center;margin-top:16px;">Sent by Automite AI</p>
        </body></html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your Automite AI Call Log Sheet is Ready — {business_name}"
        msg["From"] = f"Automite AI <{settings.smtp_user}>"
        msg["To"] = client_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, client_email, msg.as_string())

        logger.info("Sheet notification email sent to %s for client %s", client_email, client_id)

    except Exception as exc:
        logger.error("Failed to send sheet notification email for client %s: %s", client_id, exc)
