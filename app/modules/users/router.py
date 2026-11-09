"""User management API (Admin only).

    GET  /api/users                  every account, with what the caller may change
    POST /api/users                  add a Sales User or an Admin
    GET  /api/users/{id}             one account
    PUT  /api/users/{id}             change name and login email (Sales Users, or yourself)
    POST /api/users/{id}/password    set a new password for a Sales User

An Admin's own password is changed through POST /api/auth/password, which requires
the current password.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import PasswordReset, UserCreate, UserListOut, UserProfileUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserListOut])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.list_users(db, admin)


@router.post("", response_model=UserListOut, status_code=201)
def create_user(
    payload: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """Add a Sales User or an Admin. The password is hashed; it is never returned."""
    return service.create_account(db, admin, payload)


@router.get("/{user_id}", response_model=UserListOut)
def get_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.get_user(db, admin, user_id)


@router.put("/{user_id}", response_model=UserListOut)
def update_user(
    user_id: int,
    payload: UserProfileUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.update_profile(db, admin, user_id, payload)


@router.post("/{user_id}/password", status_code=204)
def reset_password(
    user_id: int,
    payload: PasswordReset,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    service.reset_password(db, admin, user_id, payload)
