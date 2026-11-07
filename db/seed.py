"""Load sample data for local development and the demo.

    python -m db.seed           # add sample data; existing rows are left alone
    python -m db.seed --reset   # empty every table first, then load sample data

Sample account emails and passwords come from .env (SEED_* variables), so no
credentials are stored in the repository.
"""

import argparse
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.enums import Role
from app.models import Base
from app.modules.users import repository as user_repository
from app.modules.users import service as user_service
from app.modules.users.schemas import UserCreate


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str
    seed_sales1_email: str = "sales1@example.com"
    seed_sales1_password: str
    seed_sales2_email: str = "sales2@example.com"
    seed_sales2_password: str


def reset_database() -> None:
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f"TRUNCATE TABLE `{table.name}`"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    print("All tables emptied.")


def seed_users(db: Session, settings: SeedSettings) -> None:
    accounts = [
        ("Asha Admin", settings.seed_admin_email, settings.seed_admin_password, Role.ADMIN),
        ("Ravi Sales", settings.seed_sales1_email, settings.seed_sales1_password, Role.SALES),
        ("Meera Sales", settings.seed_sales2_email, settings.seed_sales2_password, Role.SALES),
    ]
    for name, email, password, role in accounts:
        if user_repository.get_by_email(db, email):
            print(f"  user exists, skipped: {email}")
            continue
        user_service.create_user(
            db, UserCreate(name=name, email=email, password=password, role=role)
        )
        print(f"  created {role.value:<5} {email}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m db.seed")
    parser.add_argument("--reset", action="store_true", help="empty all tables before seeding")
    args = parser.parse_args(argv)

    settings = SeedSettings()
    if args.reset:
        reset_database()

    with SessionLocal() as db:
        print("Seeding users...")
        seed_users(db, settings)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
