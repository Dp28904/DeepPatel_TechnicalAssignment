"""A real connection with ssl-mode REQUIRED is encrypted (MySQL 8.4 supports TLS out of the box)."""

from sqlalchemy import create_engine, text

from app.core import database
from app.core.config import Settings
from tests.conftest import TEST_DATABASE_URL


def test_required_mode_gives_an_encrypted_connection(monkeypatch, migrated_database):
    aiven_style = TEST_DATABASE_URL.replace("mysql+pymysql://", "mysql://") + "?ssl-mode=REQUIRED"
    settings = Settings(database_url=aiven_style, secret_key="k" * 16)
    monkeypatch.setattr(database, "get_settings", lambda: settings)

    engine = create_engine(settings.database_url, connect_args=database.connect_args())
    with engine.connect() as connection:
        cipher = connection.execute(text("SHOW SESSION STATUS LIKE 'Ssl_cipher'")).one()[1]
    engine.dispose()
    assert cipher  # e.g. TLS_AES_256_GCM_SHA384: the connection is encrypted
