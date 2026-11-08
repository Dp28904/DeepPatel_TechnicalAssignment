"""Order pages. HTML shells only; the API enforces ownership and status rules."""

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import get_page_user
from app.core.templating import templates
from app.modules.users.models import User

router = APIRouter(prefix="/orders", include_in_schema=False)


@router.get("")
def order_list(request: Request, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(request, "orders/list.html", {"user": user})


@router.get("/new")
def order_new(request: Request, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(request, "orders/form.html", {"user": user, "order_id": None})


@router.get("/{order_id}")
def order_detail(request: Request, order_id: int, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(
        request, "orders/detail.html", {"user": user, "order_id": order_id}
    )


@router.get("/{order_id}/edit")
def order_edit(request: Request, order_id: int, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(
        request, "orders/form.html", {"user": user, "order_id": order_id}
    )
