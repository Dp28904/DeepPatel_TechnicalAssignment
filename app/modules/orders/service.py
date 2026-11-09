"""Sales order business rules.

Phase 3 only needs the reference counts used by safe-delete checks in the customers
and products modules; order creation, confirmation and cancellation come next.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.orders.models import SalesOrder, SalesOrderItem


def count_orders_for_customer(db: Session, customer_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(SalesOrder).where(SalesOrder.customer_id == customer_id)
    )


def count_items_for_product(db: Session, product_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(SalesOrderItem)
        .where(SalesOrderItem.product_id == product_id)
    )
