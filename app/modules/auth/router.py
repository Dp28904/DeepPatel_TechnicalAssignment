"""Auth API: POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest
from app.modules.users.models import User
from app.modules.users.schemas import UserOut

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
