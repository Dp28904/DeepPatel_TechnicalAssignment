"""Hosting settings: TLS to a hosted MySQL is opt-in through DATABASE_SSL_CA."""

from app.core import database
from app.core.config import Settings


def test_no_tls_options_by_default(monkeypatch):
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: Settings(database_url="mysql+pymysql://x", secret_key="k" * 16),
    )
    assert database.connect_args() == {}


def test_tls_with_certificate_verification_when_ca_is_set(monkeypatch):
    settings = Settings(
        database_url="mysql+pymysql://x", secret_key="k" * 16, database_ssl_ca="/etc/secrets/ca.pem"
    )
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    assert database.connect_args() == {"ssl": {"ca": "/etc/secrets/ca.pem"}}


def test_production_mode_is_read_from_app_env():
    assert Settings(database_url="x", secret_key="k" * 16, app_env="production").is_production
    assert not Settings(database_url="x", secret_key="k" * 16, app_env="development").is_production
