"""CSV import page (Admin only)."""

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import require_page_admin
from app.core.templating import templates
from app.modules.users.models import User

router = APIRouter(prefix="/imports", include_in_schema=False)


@router.get("/products")
def import_page(request: Request, user: User = Depends(require_page_admin)):
    return templates.TemplateResponse(request, "imports/products.html", {"user": user})
