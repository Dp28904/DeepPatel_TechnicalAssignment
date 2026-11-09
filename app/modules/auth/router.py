"""Auth API: login, logout, current user, and an Admin changing their own password."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, start_session
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest
from app.modules.users import service as user_service
from app.modules.users.models import User
from app.modules.users.schemas import PasswordChange, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return service.login(request, db, payload.email, payload.password)


@router.post("/logout", status_code=204)
def logout(request: Request) -> None:
    service.logout(request)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/password", status_code=204)
def change_my_password(
    payload: PasswordChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Admins only: Sales Users get 403 and must ask an Admin."""
    updated = user_service.change_own_password(db, user, payload)
    # Other sessions are now logged out; renew this one so the Admin stays signed in.
    start_session(request, updated)
