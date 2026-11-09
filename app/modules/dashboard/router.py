"""Dashboard API: GET /api/dashboard?from=&to= (any logged-in user, scoped by role)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.dashboard import service
from app.modules.dashboard.schemas import Dashboard
from app.modules.users.models import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=Dashboard)
def get_dashboard(
    date_from: date | None = Query(None, alias="from", description="Order date from (inclusive)"),
    date_to: date | None = Query(None, alias="to", description="Order date to (inclusive)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_dashboard(db, user, date_from, date_to)
