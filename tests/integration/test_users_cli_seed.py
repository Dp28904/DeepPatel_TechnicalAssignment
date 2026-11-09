"""Account creation: the service, the create-user CLI and the seed script."""

import pytest
from sqlalchemy import func, select

from app import cli
from app.core.enums import Role
from app.core.exceptions import Conflict
from app.models import User
from app.modules.users import service as user_service
from app.modules.users.schemas import UserCreate
from db import seed


def _user_count(db) -> int:
    return db.scalar(select(func.count()).select_from(User))


def test_create_user_rejects_duplicate_email_case_insensitively(db_session, admin_user):
    with pytest.raises(Conflict):
        user_service.create_user(
            db_session,
            UserCreate(
                name="X", email="ADMIN@example.com", password="long-enough", role=Role.SALES
            ),
        )


def test_user_schema_rejects_short_password():
    with pytest.raises(ValueError):
        UserCreate(name="X", email="x@example.com", password="short", role=Role.SALES)


def test_cli_creates_user(db_session, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "cli-password-1")
    code = cli.main(
        ["create-user", "--name", "Cli User", "--email", "cli@example.com", "--role", "SALES"]
    )
    assert code == 0
    assert "Created SALES user" in capsys.readouterr().out
    user = db_session.scalar(select(User).where(User.email == "cli@example.com"))
    assert user is not None and user.role is Role.SALES


def test_cli_rejects_mismatched_passwords(db_session, monkeypatch, capsys):
    answers = iter(["first-password", "second-password"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    code = cli.main(["create-user", "--name", "X", "--email", "x@example.com", "--role", "ADMIN"])
    assert code == 1
    assert "do not match" in capsys.readouterr().err
    assert _user_count(db_session) == 0


def test_cli_reports_validation_errors(db_session, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "short")
    code = cli.main(["create-user", "--name", "X", "--email", "bad-email", "--role", "ADMIN"])
    assert code == 1
    err = capsys.readouterr().err
    assert "email" in err and "password" in err


@pytest.fixture
def seed_env(monkeypatch):
    for key, value in {
        "SEED_ADMIN_EMAIL": "seed.admin@example.com",
        "SEED_ADMIN_PASSWORD": "seed-admin-pw",
        "SEED_SALES1_EMAIL": "seed.sales1@example.com",
        "SEED_SALES1_PASSWORD": "seed-sales1-pw",
        "SEED_SALES2_EMAIL": "seed.sales2@example.com",
        "SEED_SALES2_PASSWORD": "seed-sales2-pw",
    }.items():
        monkeypatch.setenv(key, value)


def test_seed_creates_sample_accounts_and_is_idempotent(db_session, seed_env, client):
    assert seed.main([]) == 0
    assert seed.main([]) == 0  # second run must not duplicate anything
    assert _user_count(db_session) == 3

    response = client.post(
        "/api/auth/login", json={"email": "seed.sales1@example.com", "password": "seed-sales1-pw"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "SALES"


def test_seed_reset_empties_tables_first(db_session, seed_env, admin_user):
    assert seed.main(["--reset"]) == 0
    db_session.expire_all()
    emails = set(db_session.scalars(select(User.email)))
    assert "admin@example.com" not in emails  # removed by --reset
    assert len(emails) == 3
