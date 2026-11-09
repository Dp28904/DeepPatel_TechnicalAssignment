"""Reports page (Admin only): one page with four tabs; data comes from /api/reports."""

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import require_page_admin
from app.core.templating import templates
from app.modules.users.models import User

router = APIRouter(prefix="/reports", include_in_schema=False)


@router.get("")
def reports_page(request: Request, user: User = Depends(require_page_admin)):
    return templates.TemplateResponse(request, "reports/index.html", {"user": user})
