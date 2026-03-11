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
    assistant_name: str = Field(..., min_length=1, max_length=100, description="Name for the Vapi AI assistant")


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
