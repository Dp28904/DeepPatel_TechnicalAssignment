"""Sales orders API.

GET  /api/orders                 list (Sales Users: own orders only)
POST /api/orders                 create a Draft order
GET  /api/orders/{id}            one accessible order with its items
PUT  /api/orders/{id}            replace a Draft order's customer/discount/items
POST /api/orders/{id}/confirm    confirm and deduct stock
POST /api/orders/{id}/cancel     cancel; restore stock if it was Confirmed
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.enums import OrderStatus
from app.core.pagination import Page, PageParams, page_params
from app.modules.orders import service
from app.modules.orders.schemas import OrderIn, OrderOut, OrderSummaryOut
from app.modules.users.models import User

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=Page[OrderSummaryOut])
def list_orders(
    status: OrderStatus | None = Query(None),
    customer_id: int | None = Query(None, ge=1),
    search: str | None = Query(None, max_length=100, description="Order number or customer"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    params: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_orders(
        db,
        user,
        params,
        status=status,
        customer_id=customer_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return OrderOut.from_model(service.create_order(db, user, payload))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return OrderOut.from_model(service.get_order(db, user, order_id))


@router.put("/{order_id}", response_model=OrderOut)
def update_order(
    order_id: int,
    payload: OrderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return OrderOut.from_model(service.update_order(db, user, order_id, payload))


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_order(
    order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return OrderOut.from_model(service.confirm_order(db, user, order_id))


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return OrderOut.from_model(service.cancel_order(db, user, order_id))
