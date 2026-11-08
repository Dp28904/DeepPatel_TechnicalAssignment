"""Database queries for sales orders. No business rules here.

Locking reads use ``FOR UPDATE OF <table>`` so only the named table's rows are
locked, even though the query also joins customers or products for display.
"""

from datetime import date

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import OrderStatus
from app.modules.customers.models import Customer
from app.modules.orders.models import SalesOrder


def get(db: Session, order_id: int) -> SalesOrder | None:
    return db.scalar(
        select(SalesOrder)
        .where(SalesOrder.id == order_id)
        .options(selectinload(SalesOrder.items), selectinload(SalesOrder.creator))
        .execution_options(populate_existing=True)
    )


def get_for_update(db: Session, order_id: int) -> SalesOrder | None:
    """Lock the order row until the transaction ends. Other edits, confirmations and
    cancellations of this order wait here, so they run one at a time."""
    return db.scalar(
        select(SalesOrder)
        .where(SalesOrder.id == order_id)
        .with_for_update(of=SalesOrder)
        .execution_options(populate_existing=True)
    )


def search_statement(
    *,
    created_by: int | None,
    status: OrderStatus | None,
    customer_id: int | None,
    search: str | None,
    date_from: date | None,
    date_to: date | None,
) -> Select:
    statement = (
        select(SalesOrder)
        .join(SalesOrder.customer)
        .options(selectinload(SalesOrder.items), selectinload(SalesOrder.creator))
    )
    if created_by is not None:
        statement = statement.where(SalesOrder.created_by == created_by)
    if status is not None:
        statement = statement.where(SalesOrder.status == status)
    if customer_id is not None:
        statement = statement.where(SalesOrder.customer_id == customer_id)
    if search:
        term = search.strip()
        statement = statement.where(
            or_(
                SalesOrder.order_number.contains(term, autoescape=True),
                Customer.name.contains(term, autoescape=True),
            )
        )
    if date_from is not None:
        statement = statement.where(SalesOrder.order_date >= date_from)
    if date_to is not None:
        statement = statement.where(SalesOrder.order_date <= date_to)
    return statement.order_by(SalesOrder.order_date.desc(), SalesOrder.id.desc())


def add(db: Session, order: SalesOrder) -> SalesOrder:
    db.add(order)
    db.flush()
    return order
