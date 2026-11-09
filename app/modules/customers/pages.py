"""Customer pages. These only render HTML shells; data and permissions come from the API."""

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import get_page_user, require_page_admin
from app.core.templating import templates
from app.modules.users.models import User

router = APIRouter(prefix="/customers", include_in_schema=False)


@router.get("")
def customer_list(request: Request, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(request, "customers/list.html", {"user": user})


@router.get("/new")
def customer_new(request: Request, user: User = Depends(require_page_admin)):
    return templates.TemplateResponse(
        request, "customers/form.html", {"user": user, "customer_id": None}
    )


@router.get("/{customer_id}")
def customer_detail(request: Request, customer_id: int, user: User = Depends(get_page_user)):
    # Admins get an editable form; Sales Users get the same page read-only.
    return templates.TemplateResponse(
        request, "customers/form.html", {"user": user, "customer_id": customer_id}
    )
