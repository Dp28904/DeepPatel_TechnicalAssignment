"""Product pages. These only render HTML shells; data and permissions come from the API."""

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import get_page_user, require_page_admin
from app.core.templating import templates
from app.modules.users.models import User

router = APIRouter(prefix="/products", include_in_schema=False)


@router.get("")
def product_list(request: Request, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(request, "products/list.html", {"user": user})


@router.get("/new")
def product_new(request: Request, user: User = Depends(require_page_admin)):
    return templates.TemplateResponse(
        request, "products/form.html", {"user": user, "product_id": None}
    )


@router.get("/{product_id}")
def product_detail(request: Request, product_id: int, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(
        request, "products/form.html", {"user": user, "product_id": product_id}
    )
