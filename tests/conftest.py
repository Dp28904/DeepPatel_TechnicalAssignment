"""Shared pytest fixtures.

The test suite always runs against the separate ``sales_test`` database, never the
development database. Before the app is imported, ``DATABASE_URL`` is overridden
with ``TEST_DATABASE_URL`` (from the environment or .env), and a guard refuses to
run if the database name does not end in ``_test``, because tests truncate tables.
"""

import os

from dotenv import dotenv_values

DEFAULT_TEST_DATABASE_URL = "mysql+pymysql://sales_app:sales_app_pw@127.0.0.1:3306/sales_test"

_dotenv = dotenv_values(".env")
TEST_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or _dotenv.get("TEST_DATABASE_URL")
    or DEFAULT_TEST_DATABASE_URL
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import make_url, text  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402

if not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
    raise RuntimeError(
        f"Refusing to run tests: database name in TEST_DATABASE_URL must end with '_test' "
        f"(got {make_url(TEST_DATABASE_URL).database!r})."
    )


def _alembic_config() -> Config:
    config = Config("alembic.ini")
    # '%' must be escaped because Alembic's config uses ConfigParser interpolation.
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def migrated_database():
    """Rebuild the test schema once per run from the real migrations.

    Going down to base and back up also proves the migration's downgrade works.
    """
    config = _alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


def _truncate_all_tables() -> None:
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f"TRUNCATE TABLE `{table.name}`"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def db_session(migrated_database):
    """A database session for one test. Every table is emptied afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        _truncate_all_tables()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)
