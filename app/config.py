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
