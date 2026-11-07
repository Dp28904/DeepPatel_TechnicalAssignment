"""User business rules: creation and credential checks."""

from sqlalchemy.orm import Session

from app.core.exceptions import Conflict
from app.core.security import hash_password, verify_password
from app.modules.users import repository
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate


def create_user(db: Session, data: UserCreate) -> User:
    if repository.get_by_email(db, data.email):
        raise Conflict(f"A user with email '{data.email}' already exists.", code="email_taken")
    user = repository.add(
        db,
        User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
            is_active=True,
        ),
    )
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user if the email/password pair is valid and the account is active."""
    user = repository.get_by_email(db, email)
    if not verify_password(password, user.password_hash if user else None):
        return None
    if not user.is_active:
        return None
    return user


def get_active_user(db: Session, user_id: int) -> User | None:
    user = repository.get_by_id(db, user_id)
    return user if user and user.is_active else None
