"""Database queries for users. No business rules here."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import User


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def add(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user


def list_all(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.role, User.name, User.id)))
