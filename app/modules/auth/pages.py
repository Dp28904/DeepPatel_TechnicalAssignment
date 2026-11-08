"""HTML pages: login and the dashboard (home page)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import current_user_or_none, get_page_user
from app.core.templating import templates
from app.modules.users.models import User

router = APIRouter(include_in_schema=False)


def safe_next_path(next_path: str | None) -> str:
    """Only allow redirects to paths on this site (prevents open redirects)."""
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


@router.get("/login")
def login_page(request: Request, next: str | None = None, db: Session = Depends(get_db)):
    if current_user_or_none(request, db):
        return RedirectResponse(safe_next_path(next), status_code=303)
    return templates.TemplateResponse(
        request, "auth/login.html", {"next_path": safe_next_path(next), "user": None}
    )


@router.get("/")
def dashboard(request: Request, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})
