"""Customers API. Everyone logged in can read (Sales Users: active only); only Admins write."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.enums import StatusFilter
from app.core.pagination import Page, PageParams, page_params
from app.modules.customers import service
from app.modules.customers.schemas import CustomerIn, CustomerOut
from app.modules.users.models import User

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=Page[CustomerOut])
def list_customers(
    search: str | None = Query(None, max_length=100, description="Name, email or mobile"),
    status: StatusFilter = Query(StatusFilter.ACTIVE),
    params: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_customers(db, user, search, status, params)


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    payload: CustomerIn, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    return service.create_customer(db, payload)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return service.get_customer(db, user, customer_id)


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    payload: CustomerIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.update_customer(db, user, customer_id, payload)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)
) -> None:
    service.delete_customer(db, user, customer_id)
