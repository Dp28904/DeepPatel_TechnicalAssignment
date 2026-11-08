"""User business rules: creation, credential checks and account management."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.exceptions import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.security import hash_password, verify_password
from app.modules.users import repository
from app.modules.users.models import User
from app.modules.users.schemas import (
    PasswordChange,
    PasswordReset,
    UserCreate,
    UserListOut,
    UserProfileUpdate,
)


def create_user(db: Session, data: UserCreate) -> User:
    if repository.get_by_email(db, data.email):
        message = f"The email '{data.email}' is already used by another account."
        raise Conflict(
            message, code="email_taken", details=[{"field": "email", "message": message}]
        )
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


# --- Account management -----------------------------------------------------------
# Rules (enforced here, on the server):
# - An Admin may edit the name/email of any Sales User and of themselves.
# - An Admin may set a new password for a Sales User (no old password needed).
# - An Admin changes their OWN password only with their current password.
# - Nobody may edit another Admin. Sales Users cannot change accounts at all,
#   including their own password: they ask an Admin.
def can_edit_profile(actor: User, target: User) -> bool:
    return actor.is_admin and (target.id == actor.id or target.role == Role.SALES)


def can_reset_password(actor: User, target: User) -> bool:
    return actor.is_admin and target.role == Role.SALES


def _to_list_item(actor: User, user: User) -> UserListOut:
    return UserListOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        can_edit_profile=can_edit_profile(actor, user),
        can_reset_password=can_reset_password(actor, user),
    )


def list_users(db: Session, actor: User) -> list[UserListOut]:
    return [_to_list_item(actor, user) for user in repository.list_all(db)]


def get_user(db: Session, actor: User, user_id: int) -> UserListOut:
    user = repository.get_by_id(db, user_id)
    if user is None:
        raise NotFound(f"User {user_id} was not found.")
    return _to_list_item(actor, user)


def _get_or_404(db: Session, user_id: int) -> User:
    user = repository.get_by_id(db, user_id)
    if user is None:
        raise NotFound(f"User {user_id} was not found.")
    return user


def _set_password(user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    # Every session created with the old password stops working.
    user.session_version += 1


def create_account(db: Session, actor: User, data: UserCreate) -> UserListOut:
    """An Admin adds a Sales User or another Admin."""
    try:
        user = create_user(db, data)
    except IntegrityError as exc:  # same email created at the same moment
        db.rollback()
        message = f"The email '{data.email}' is already used by another account."
        raise Conflict(
            message, code="email_taken", details=[{"field": "email", "message": message}]
        ) from exc
    db.refresh(user)
    return _to_list_item(actor, user)


def update_profile(db: Session, actor: User, user_id: int, data: UserProfileUpdate) -> UserListOut:
    target = _get_or_404(db, user_id)
    if not can_edit_profile(actor, target):
        raise Forbidden("Admins can edit Sales Users and their own account, not other Admins.")
    taken = repository.get_by_email(db, data.email)
    if taken and taken.id != target.id:
        message = f"The email '{data.email}' is already used by another account."
        raise Conflict(
            message, code="email_taken", details=[{"field": "email", "message": message}]
        )
    target.name = data.name
    target.email = data.email
    try:
        db.commit()
    except IntegrityError as exc:  # another request took the email at the same moment
        db.rollback()
        message = f"The email '{data.email}' is already used by another account."
        raise Conflict(message, code="email_taken") from exc
    db.refresh(target)
    return _to_list_item(actor, target)


def reset_password(db: Session, actor: User, user_id: int, data: PasswordReset) -> None:
    target = _get_or_404(db, user_id)
    if target.id == actor.id:
        raise Forbidden(
            "Change your own password from your Account page; it asks for your current password.",
            code="use_account_page",
        )
    if not can_reset_password(actor, target):
        raise Forbidden("Admins can set passwords for Sales Users only.")
    _set_password(target, data.new_password)
    db.commit()


def change_own_password(db: Session, user: User, data: PasswordChange) -> User:
    if not user.is_admin:
        raise Forbidden(
            "Sales Users cannot change their own password. Please ask an Admin to set a new one.",
            code="ask_an_admin",
        )
    if not verify_password(data.current_password, user.password_hash):
        message = "Current password is incorrect."
        raise ValidationFailed(message, details=[{"field": "current_password", "message": message}])
    if data.new_password == data.current_password:
        message = "The new password must be different from the current one."
        raise ValidationFailed(message, details=[{"field": "new_password", "message": message}])
    _set_password(user, data.new_password)
    db.commit()
    db.refresh(user)
    return user
