"""Application settings, loaded from environment variables and the .env file."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


SSL_MODES = ("DISABLED", "PREFERRED", "REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY")
# URL prefixes that mean "MySQL" but would select a driver this app does not install.
_OTHER_MYSQL_PREFIXES = ("mysql://", "mysql+mysqldb://", "mysql+mysqlconnector://")


def normalise_database_url(url: str) -> tuple[str, str | None]:
    """Accept a MySQL URL as hosting providers show it, e.g. Aiven's
    ``mysql://user:pw@host:port/db?ssl-mode=REQUIRED``.

    - ``mysql://`` would make SQLAlchemy load the mysqlclient driver ("No module named
      'MySQLdb'"); this app uses PyMySQL, so the prefix becomes ``mysql+pymysql://``.
    - ``ssl-mode`` is a MySQL client option PyMySQL does not understand; it is removed
      from the URL and returned separately, to configure TLS in ``connect_args``.
    """
    url = url.strip()
    for prefix in _OTHER_MYSQL_PREFIXES:
        if url.startswith(prefix):
            url = "mysql+pymysql://" + url[len(prefix) :]
            break
    parts = urlsplit(url)
    ssl_mode = None
    kept = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower().replace("_", "-") in ("ssl-mode", "sslmode"):
            ssl_mode = value.strip().upper()
        else:
            kept.append((key, value))
    return urlunsplit(parts._replace(query=urlencode(kept))), ssl_mode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = Field(min_length=16)
    session_max_age_seconds: int = 8 * 60 * 60
    log_level: str = "INFO"

    database_url: str
    test_database_url: str | None = None
    # TLS for a hosted MySQL (e.g. Aiven). Give the CA certificate in ONE of two ways:
    # - DATABASE_SSL_CA: path to the file (on Render: a Secret File, /etc/secrets/ca.pem)
    # - DATABASE_SSL_CA_PEM: the certificate text itself, pasted into the variable
    # Neither set = no TLS (local development).
    database_ssl_ca: str | None = None
    database_ssl_ca_pem: str | None = None
    # REQUIRED = encrypted even without a CA (not verified); taken from "?ssl-mode=" in the
    # URL when present. A CA certificate always gives full verification.
    database_ssl_mode: str | None = None

    @model_validator(mode="after")
    def clean_database_url(self) -> "Settings":
        self.database_url, mode_in_url = normalise_database_url(self.database_url)
        if self.test_database_url:
            self.test_database_url, _ = normalise_database_url(self.test_database_url)
        self.database_ssl_mode = (self.database_ssl_mode or mode_in_url or "").upper() or None
        if self.database_ssl_mode and self.database_ssl_mode not in SSL_MODES:
            raise ValueError(
                f"DATABASE_SSL_MODE '{self.database_ssl_mode}' is not valid. "
                f"Use one of: {', '.join(SSL_MODES)}."
            )
        has_ca = bool(self.database_ssl_ca or self.database_ssl_ca_pem)
        if self.database_ssl_mode in ("VERIFY_CA", "VERIFY_IDENTITY") and not has_ca:
            raise ValueError(
                f"ssl-mode {self.database_ssl_mode} needs the database's CA certificate: set "
                "DATABASE_SSL_CA (a file) or DATABASE_SSL_CA_PEM (the certificate text)."
            )
        return self

    @model_validator(mode="after")
    def certificate_must_exist(self) -> "Settings":
        if self.database_ssl_ca_pem:
            if "BEGIN CERTIFICATE" not in self.database_ssl_ca_pem:
                raise ValueError(
                    "DATABASE_SSL_CA_PEM must contain the whole certificate, including the "
                    "'-----BEGIN CERTIFICATE-----' and '-----END CERTIFICATE-----' lines."
                )
        elif self.database_ssl_ca and not Path(self.database_ssl_ca).is_file():
            raise ValueError(
                f"DATABASE_SSL_CA points to '{self.database_ssl_ca}', but no file exists there. "
                "On Render: open the service -> Environment -> Secret Files and add a file named "
                "'ca.pem' containing the database's CA certificate (or paste the certificate into "
                "DATABASE_SSL_CA_PEM instead), then redeploy."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings. Fails fast at startup if required values are missing."""
    return Settings()
