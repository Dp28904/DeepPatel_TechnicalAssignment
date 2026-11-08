"""FastAPI dependencies for authentication and role checks.

Two flavours:
- API routes use ``get_current_user`` / ``require_admin``: they raise 401/403 JSON errors.
- Page routes use ``get_page_user`` / ``require_page_admin``: an anonymous visitor is
  redirected to the login page instead.

Permissions are always enforced here, on the server. Hiding a link in the UI is
only a convenience.
"""

from urllib.parse import quote

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import Forbidden, Unauthenticated
from app.modules.users import service as user_service
from app.modules.users.models import User

SESSION_USER_KEY = "user_id"
SESSION_VERSION_KEY = "session_version"


class LoginRequired(Exception):
    """Raised by page dependencies; handled by redirecting to /login."""

    def __init__(self, next_path: str):
        self.next_path = next_path

    @property
    def redirect_url(self) -> str:
        return f"/login?next={quote(self.next_path)}"


def _load_session_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get(SESSION_USER_KEY)
    if not isinstance(user_id, int):
        return None
    user = user_service.get_active_user(db, user_id)
    if user is None or request.session.get(SESSION_VERSION_KEY) != user.session_version:
        # The account was deactivated, or its password changed after this session
        # was created: end the session.
        request.session.clear()
        return None
    return user


def start_session(request: Request, user: User) -> None:
    """Store who is logged in, and the password 'version' this session belongs to."""
    request.session.clear()  # drop anything from a previous session
    request.session[SESSION_USER_KEY] = user.id
    request.session[SESSION_VERSION_KEY] = user.session_version


def current_user_or_none(request: Request, db: Session) -> User | None:
    """The logged-in user, or None (used where being logged out is not an error)."""
    return _load_session_user(request, db)


# --- API ------------------------------------------------------------------
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = _load_session_user(request, db)
    if user is None:
        raise Unauthenticated("Please log in to continue.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise Forbidden("Only Admin users can perform this action.")
    return user


# --- Pages ----------------------------------------------------------------
def get_page_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = _load_session_user(request, db)
    if user is None:
        raise LoginRequired(request.url.path)
    return user


def require_page_admin(user: User = Depends(get_page_user)) -> User:
    if not user.is_admin:
        raise Forbidden("Only Admin users can open this page.")
    return user
