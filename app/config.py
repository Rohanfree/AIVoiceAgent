"""
config.py - Application configuration using Pydantic Settings.
Reads environment variables from .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables or .env file."""

    # Path to Firebase service account credentials JSON
    firebase_credential_path: str = "./firebase-service-account.json"

    # Default business client ID — used as fallback in agent tools
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

    # ── Google OAuth2 (Calendar Integration) ────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── Google Sheets Integration ────────────────────────────────────────────
    google_sheet_id: str = ""           # Spreadsheet ID from the sheet URL
    google_sheet_tab: str = "Call Logs" # Worksheet / tab name to append rows into

    # ── Google GenAI ────────────────────────────────────────────────────────
    gemini_api_key: str = ""

    # ── Encryption ──────────────────────────────────────────────────────────
    secret_key: str = ""

    # ── Public base URL ─────────────────────────────────────────────────────
    base_url: str = "http://localhost:8090"

    # ── WhatsApp Cloud API ──────────────────────────────────────────────────
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""

    # ── Contact Form Email (Gmail SMTP) ─────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""          # The Gmail address used to SEND (needs an App Password)
    smtp_password: str = ""      # Google App Password (16 chars), NOT your Gmail password
    contact_email: str = "aiautomite@gmail.com"  # Where contact submissions are received

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

