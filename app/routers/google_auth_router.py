"""
google_auth_router.py — Handles Google OAuth2 flow for Calendar access.
Endpoints:
  - GET /client/auth/google/login: Starts OAuth flow.
  - GET /client/auth/google/callback: Finishes OAuth flow and stores tokens.
"""

import logging
import json
import os
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from app.config import settings
from app.db import get_db
from app.auth.dependencies import get_current_user
from jose import jwt

# Allow insecure transport for local development (http instead of https)
if settings.debug:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/client/auth/google",
    tags=["Google OAuth"],
)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
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
    redirect_uri = f"{base}/client/auth/google/callback"
    return {
        "base_url_settings": settings.base_url,
        "computed_redirect_uri": redirect_uri,
        "request_url_host": request.url.netloc,
        "client_id_present": bool(settings.google_client_id),
        "client_secret_present": bool(settings.google_client_secret),
        "insecure_transport_env": os.environ.get('OAUTHLIB_INSECURE_TRANSPORT'),
    }

@router.get("/login")
async def google_login(request: Request, token: str):
    """
    Start Google OAuth flow. 
    Expects 'token' (the app's JWT) to be passed in query params.
    """
    try:
        # Validate token first
        jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        
        client_config = get_client_config()
        
        # Use url_for for the callback to ensure it matches the current request host/port
        redirect_uri = str(request.url_for("google_callback"))
        
        # Ensure it's http if insecure transport is allowed
        if os.environ.get('OAUTHLIB_INSECURE_TRANSPORT') == '1':
            redirect_uri = redirect_uri.replace("https://", "http://")
        
        logger.info("Generating Google OAuth URL. Computed redirect_uri: %s", redirect_uri)

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=token,  # Pass the JWT as state
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
        # 1. Validate the JWT from state
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=["HS256"])
        client_id = payload.get("client_id")
        if not client_id:
            raise Exception("Invalid state: no client_id")

        # 2. Exchange code for tokens
        client_config = get_client_config()
        redirect_uri = str(request.url_for("google_callback"))
        if os.environ.get('OAUTHLIB_INSECURE_TRANSPORT') == '1':
            redirect_uri = redirect_uri.replace("https://", "http://")

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
            "scopes": credentials.scopes,
        }
        
        logger.info("Attempting to save tokens to Firestore for client: %s", client_id)
        db.collection("clients").document(client_id).set({
            "google_calendar_linked": True,
            "google_calendar_tokens": token_data,
        }, merge=True)
        logger.info("Successfully updated Firestore document for client: %s", client_id)

        # 4. Redirect back to dashboard (always uses the UI prefix)
        base = settings.base_url.rstrip("/")
        return RedirectResponse(url=f"{base}/automiteui/pages/dashboard?google_linked=success")

    except Exception as e:
        logger.exception("CRITICAL ERROR in Google OAuth callback")
        base = settings.base_url.rstrip("/")
        # Return the error message in the URL for better user feedback during debug
        error_msg = str(e).replace(" ", "_")
        return RedirectResponse(url=f"{base}/automiteui/pages/dashboard?google_linked=error&detail={error_msg}")
