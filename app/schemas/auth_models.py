"""
auth_models.py — Pydantic schemas for authentication endpoints.
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request body for POST /automiteui/auth/login"""

    username: str = Field(..., min_length=3, description="Account username")
    password: str = Field(..., min_length=6, description="Account password")


class RegisterRequest(BaseModel):
    """Request body for POST /automiteui/auth/register"""

    username: str = Field(..., min_length=3, max_length=50, description="Desired username")
    password: str = Field(..., min_length=8, description="Strong password (min 8 chars)")
    client_name: str = Field(..., min_length=1, max_length=100, description="Business/client display name")
    email: str = Field(..., min_length=5, max_length=200, description="Client email address for notifications")
    timezone: str = Field(default="Asia/Kolkata", max_length=100, description="Client IANA timezone (e.g. Asia/Kolkata)")
    elevenlabs_agent_id: str = Field(..., min_length=1, max_length=200, description="ElevenLabs Conversational AI agent ID")
    business_info: str = Field(default="", description="Client-specific business info: booking slots, working days, policies")
    first_message: str = Field(default="", description="Agent's opening message spoken at the start of every call")


class TokenResponse(BaseModel):
    """Returned after successful login or token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    scope: str = Field(default="dashboard", description="Token scope")
    expires_in_minutes: int = Field(default=15, description="Access token lifespan")


class RefreshRequest(BaseModel):
    """Request body for POST /automiteui/auth/refresh"""

    refresh_token: str = Field(..., description="Current refresh token")


class UserProfile(BaseModel):
    """Lightweight user profile returned in authenticated responses."""

    user_id: str
    username: str
    client_id: str | None = None
    client_name: str | None = None
    is_admin: bool = False
    subscription_status: str = "active"
