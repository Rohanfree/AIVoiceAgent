"""
config.py - Application configuration using Pydantic Settings.
Reads environment variables from .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables or .env file."""

    # Path to Firebase service account credentials JSON
    firebase_credential_path: str = "./firebase-service-account.json"

    # Default business client ID — used as fallback when Vapi doesn't pass assistantId
    client_id: str = "default-client"

    # Application environment: "development" enables debug logging
    app_env: str = "production"

    # Server binding
    host: str = "0.0.0.0"
    port: int = 8090

    # ── JWT Authentication ──────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-to-a-64-char-random-hex-string"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ── Admin Credentials ───────────────────────────────────────────────────
    admin_username: str = "automite_admin"
    admin_password: str = "Aut0m!te@Secure#2026"

    # ── Vapi AI ─────────────────────────────────────────────────────────────
    vapi_api_key: str = ""
    vapi_template_assistant_id: str = "e8595039-80c0-4c78-a84c-8aff64d40407"

    # ── Google OAuth2 (Calendar Integration) ────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── Google GenAI ────────────────────────────────────────────────────────
    gemini_api_key: str = ""

    # ── Encryption ──────────────────────────────────────────────────────────
    secret_key: str = ""

    # ── Public base URL ─────────────────────────────────────────────────────
    base_url: str = "http://localhost:8090"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def debug(self) -> bool:
        """Returns True when running in development mode."""
        return self.app_env.lower() == "development"


# Singleton instance used across the app
settings = Settings()

