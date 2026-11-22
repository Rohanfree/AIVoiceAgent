"""
config.py - Application configuration using Pydantic Settings.
Reads environment variables from .env file.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Environments where insecure placeholder secrets are tolerated. Anything else
# (including the default "production" and typos) is treated as production.
_LENIENT_ENVS = {"development", "test"}

# Published placeholder/default values that must never secure a real deployment.
_KNOWN_DEFAULT_JWT_SECRETS = {"change-me-to-a-64-char-random-hex-string"}
_KNOWN_DEFAULT_ADMIN_PASSWORDS = {"Aut0m!te@Secure#2026"}

MIN_JWT_SECRET_LENGTH = 32
MIN_ADMIN_PASSWORD_LENGTH = 12
MIN_SECRET_KEY_LENGTH = 32


def _is_weak_secret(value: str, defaults: set[str], min_length: int) -> bool:
    """True if value is blank, a known default, too short, or a single repeated char."""
    value = value.strip()
    return (
        len(value) < min_length
        or value in defaults
        or len(set(value)) < 4
    )


class Settings(BaseSettings):
    """Central configuration loaded from environment variables or .env file."""

    # Path to Firebase service account credentials JSON
    firebase_credential_path: str = "./firebase-service-account.json"

    # Default business client ID — used as fallback in agent tools
    client_id: str = "default-client"

    # Application environment: "development" enables debug logging
    app_env: str = "production"

    # Enable request/response debug logging for ElevenLabs agent tool calls
    agent_tools_debug: bool = False

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

    # ── Auth Rate Limiting ──────────────────────────────────────────────────
    # Per client address, per endpoint (login / register / check-agent).
    # In-memory and per-process: not valid across multiple workers/instances.
    auth_rate_limit_max_requests: int = 10
    auth_rate_limit_window_seconds: int = 60

    # ── CORS ────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed browser origins (env: CORS_ALLOWED_ORIGINS).
    # The default only covers local development; set explicit origins in production.
    cors_allowed_origins: str = "http://localhost:8090,http://127.0.0.1:8090"

    # ── Google OAuth2 (Calendar Integration) ────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── Google Sheets Integration ────────────────────────────────────────────
    google_sheet_id: str = ""           # Spreadsheet ID from the sheet URL
    google_sheet_tab: str = "Call Logs" # Worksheet / tab name to append rows into

    # ── Google GenAI ────────────────────────────────────────────────────────
    gemini_api_key: str = ""

    # ── Encryption ──────────────────────────────────────────────────────────
    # Master secret for encrypting Google OAuth tokens at rest (HKDF -> AES-256-GCM).
    # Required (>= 32 chars) outside development/test. Changing it makes stored tokens unreadable.
    secret_key: str = ""

    # ── Public base URL ─────────────────────────────────────────────────────
    base_url: str = "http://localhost:8090"

    # ── Public site URL (canonical origin for SEO surfaces) ─────────────────
    # Separate from base_url, which stays the internal/provider-facing URL.
    public_site_url: str = "https://auto-mite.com"

    # ── WhatsApp Cloud API ──────────────────────────────────────────────────
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""

    # ── ElevenLabs Conversational AI ────────────────────────────────────────
    elevenlabs_api_key: str = ""

    # ── VAPI AI Integration (LEGACY — disabled) ─────────────────────────────
    # Set vapi_enabled=true in .env only if re-activating the Vapi integration.
    vapi_enabled: bool = False
    vapi_api_key: str = ""
    vapi_template_assistant_id: str = ""

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
        hide_input_in_errors=True,  # keep secret values out of validation errors
    )

    @model_validator(mode="after")
    def _require_strong_secrets_in_production(self) -> "Settings":
        """Refuse to start outside development/test with missing or weak secrets.

        Error text names only the offending settings, never their values.
        """
        if self.app_env.strip().lower() in _LENIENT_ENVS:
            return self
        problems = []
        origins = self.cors_origins
        if not origins:
            problems.append("CORS_ALLOWED_ORIGINS must list at least one origin")
        elif "*" in origins:
            problems.append("CORS_ALLOWED_ORIGINS must not contain '*' (credentials are enabled)")
        if _is_weak_secret(self.jwt_secret_key, _KNOWN_DEFAULT_JWT_SECRETS, MIN_JWT_SECRET_LENGTH):
            problems.append(
                f"JWT_SECRET_KEY must be set to a non-default value of at least "
                f"{MIN_JWT_SECRET_LENGTH} characters"
            )
        if _is_weak_secret(self.admin_password, _KNOWN_DEFAULT_ADMIN_PASSWORDS, MIN_ADMIN_PASSWORD_LENGTH):
            problems.append(
                f"ADMIN_PASSWORD must be set to a non-default value of at least "
                f"{MIN_ADMIN_PASSWORD_LENGTH} characters"
            )
        if _is_weak_secret(self.secret_key, set(), MIN_SECRET_KEY_LENGTH):
            problems.append(
                f"SECRET_KEY (encrypts Google OAuth tokens at rest) must be set to a "
                f"value of at least {MIN_SECRET_KEY_LENGTH} characters"
            )
        if problems:
            raise ValueError("Insecure production configuration: " + "; ".join(problems))
        return self

    @property
    def cors_origins(self) -> list[str]:
        """Parsed CORS_ALLOWED_ORIGINS: stripped, de-blanked, trailing slashes removed."""
        return [o.strip().rstrip("/") for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def debug(self) -> bool:
        """Returns True when running in development mode."""
        return self.app_env.lower() == "development"


# Singleton instance used across the app
settings = Settings()

