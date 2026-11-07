"""Shared pytest fixtures.

Safe defaults are set before the app is imported, so the unit tests run without a .env file.
Values from the real environment or .env still take precedence.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault(
    "DATABASE_URL", "mysql+pymysql://sales_app:sales_app_pw@127.0.0.1:3306/sales_test"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)
