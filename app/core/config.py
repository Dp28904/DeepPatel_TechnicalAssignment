"""Application settings, loaded from environment variables and the .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = Field(min_length=16)
    session_max_age_seconds: int = 8 * 60 * 60
    log_level: str = "INFO"

    database_url: str
    test_database_url: str | None = None
    # Path to the CA certificate of a hosted MySQL that requires TLS (e.g. Aiven on
    # Render: upload ca.pem as a Secret File, then set /etc/secrets/ca.pem). Unset = no TLS.
    database_ssl_ca: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings. Fails fast at startup if required values are missing."""
    return Settings()
