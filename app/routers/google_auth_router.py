"""
google_auth_router.py — Handles Google OAuth2 flow for Calendar access.
Endpoints:
  - GET /client/auth/google/login: Starts OAuth flow.
  - GET /client/auth/google/callback: Finishes OAuth flow and stores tokens.
"""

import logging
import json
import os
import urllib.parse
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from app.config import settings
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.services.sheets_service import create_client_sheet
from jose import jwt

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
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# We use the user's JWT as the state to identify them in the callback
# and prevent CSRF.

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
async def google_debug(request: Request):
    """Debug info for OAuth."""
    base = settings.base_url.rstrip("/")
    redirect_uri = f"{base}/automiteaiapplication/client/auth/google/callback"
    return {
        "base_url_settings": settings.base_url,
        "computed_redirect_uri": redirect_uri,
        "request_url_host": request.url.netloc,
        "client_id_present": bool(settings.google_client_id),
        "client_secret_present": bool(settings.google_client_secret),
        "insecure_transport_env": os.environ.get('OAUTHLIB_INSECURE_TRANSPORT'),
    }

@router.get("/login")
async def google_login(request: Request, token: str, return_to: str = None):
    """
    Start Google OAuth flow.
    Expects 'token' (the app's JWT) to be passed in query params.
    Optional 'return_to' is the URL to redirect back to after OAuth completes.
    """
    try:
        # Validate token first
        jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])

        client_config = get_client_config()

        # Build redirect URI from base_url so the scheme (http/https) matches
        # what is registered in Google Cloud Console, regardless of proxy termination.
        redirect_uri = settings.base_url.rstrip("/") + "/automiteaiapplication/client/auth/google/callback"

        logger.info("Generating Google OAuth URL. Computed redirect_uri: %s", redirect_uri)

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )

        # Encode token and return_to URL into state so both survive the OAuth round-trip
        state_data = {"t": token}
        if return_to:
            state_data["r"] = return_to
        state = json.dumps(state_data)

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=state,
            prompt="consent"
        )
        
        logger.info("Redirecting user to: %s", authorization_url)
        return RedirectResponse(authorization_url)
    except Exception as e:
        logger.error("Error starting Google OAuth: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/callback", name="google_callback")
async def google_callback(request: Request, code: str, state: str):
    """
    OAuth callback. Uses 'state' (JWT) to identify the client.
    """
    try:
        # 1. Parse state: JSON {"t": jwt, "r": return_to} or legacy raw JWT
        return_to = None
        try:
            state_data = json.loads(state)
            token = state_data["t"]
            return_to = state_data.get("r")
        except (json.JSONDecodeError, KeyError):
            token = state  # backward compat: state was the raw JWT

        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        client_id = payload.get("client_id")
        if not client_id:
            raise Exception("Invalid state: no client_id")

        # 2. Exchange code for tokens
        client_config = get_client_config()
        redirect_uri = settings.base_url.rstrip("/") + "/automiteaiapplication/client/auth/google/callback"

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # 3. Save to Firestore
        db = get_db()
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }

        logger.info("Attempting to save tokens to Firestore for client: %s", client_id)
        db.collection("clients").document(client_id).set({
            "google_calendar_linked": True,
            "google_calendar_tokens": token_data,
        }, merge=True)
        logger.info("Successfully updated Firestore document for client: %s", client_id)

        # 4. Create a Google Sheet in the client's own Drive
        try:
            client_doc = db.collection("clients").document(client_id).get()
            business_name = (client_doc.to_dict() or {}).get("business_name", "Client")
            sheet_id = create_client_sheet(client_id, business_name, token_data)
            if sheet_id:
                db.collection("clients").document(client_id).set(
                    {"google_sheet_id": sheet_id}, merge=True
                )
                logger.info("Google Sheet saved to Firestore | client=%s | sheet_id=%s", client_id, sheet_id)
        except Exception as sheet_exc:
            logger.error("Sheet creation failed for client %s (non-fatal): %s", client_id, sheet_exc)

        # 5. Redirect back to the originating page (or fallback to dashboard)
        base = settings.base_url.rstrip("/")
        if return_to:
            sep = "&" if "?" in return_to else "?"
            success_url = f"{return_to}{sep}google_linked=success"
        else:
            success_url = f"{base}/automiteui/pages/dashboard?google_linked=success"
        return RedirectResponse(url=success_url)

    except Exception as e:
        logger.exception("CRITICAL ERROR in Google OAuth callback")
        base = settings.base_url.rstrip("/")
        error_msg = urllib.parse.quote(str(e))
        if return_to:
            sep = "&" if "?" in return_to else "?"
            error_url = f"{return_to}{sep}google_linked=error&detail={error_msg}"
        else:
            error_url = f"{base}/automiteui/pages/dashboard?google_linked=error&detail={error_msg}"
        return RedirectResponse(url=error_url)
