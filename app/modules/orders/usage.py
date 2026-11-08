"""Read-only queries telling other modules whether master data is used by orders.

Kept separate from ``orders.service`` so the customers and products modules can
check references without importing the order service, which itself depends on
the products service. That avoids a circular import.
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
