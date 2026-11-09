"""Session login/logout. The session is a signed, httpOnly cookie holding only the user id."""

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.dependencies import SESSION_USER_KEY
from app.core.exceptions import Unauthenticated
from app.modules.users import service as user_service
from app.modules.users.models import User

INVALID_CREDENTIALS = "Invalid email or password."


def login(request: Request, db: Session, email: str, password: str) -> User:
    user = user_service.authenticate(db, email, password)
    if user is None:
        # Same message for unknown email, wrong password and inactive account.
        raise Unauthenticated(INVALID_CREDENTIALS, code="invalid_credentials")
    request.session.clear()  # drop anything from a previous session
    request.session[SESSION_USER_KEY] = user.id
    return user


def logout(request: Request) -> None:
    request.session.clear()
