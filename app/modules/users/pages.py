"""Account pages: the user list and edit page (Admin), and "My account" (everyone)."""

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import get_page_user, require_page_admin
from app.core.templating import templates
from app.modules.users.models import User

router = APIRouter(include_in_schema=False)


@router.get("/users")
def user_list(request: Request, user: User = Depends(require_page_admin)):
    return templates.TemplateResponse(request, "users/list.html", {"user": user})


@router.get("/users/new")
def user_new(request: Request, user: User = Depends(require_page_admin)):
    return templates.TemplateResponse(request, "users/new.html", {"user": user})


@router.get("/users/{user_id}")
def user_edit(request: Request, user_id: int, user: User = Depends(require_page_admin)):
    return templates.TemplateResponse(
        request, "users/edit.html", {"user": user, "target_id": user_id}
    )


@router.get("/account")
def my_account(request: Request, user: User = Depends(get_page_user)):
    return templates.TemplateResponse(request, "users/account.html", {"user": user})
