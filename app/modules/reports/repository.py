"""Report queries, written as plain SQL with named parameters (never string formatting).

Sales figures only count CONFIRMED orders. Draft and Cancelled orders are ignored.
"""

from datetime import date, datetime

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.enums import MovementType
from app.modules.inventory.models import StockMovement

# Customer Sales Summary
# - LEFT JOIN keeps customers with no confirmed orders in the range (they show 0).
# - The status and date conditions sit in the ON clause, not in WHERE. In WHERE they
#   would remove those customers again, turning the LEFT JOIN into an INNER JOIN.
# - Totals come from sales_orders.grand_total. Order items are NOT joined, so an
#   order with several items is still counted once.
CUSTOMER_SALES_SQL = text(
    """
    SELECT c.id                                 AS customer_id,
           c.name                               AS customer_name,
           c.city                               AS city,
           c.is_active                          AS is_active,
           COUNT(o.id)                          AS confirmed_orders,
           COALESCE(SUM(o.grand_total), 0)      AS total_sales
    FROM customers c
    LEFT JOIN sales_orders o
           ON o.customer_id = c.id
          AND o.status = 'CONFIRMED'
          AND (:date_from IS NULL OR o.order_date >= :date_from)
          AND (:date_to   IS NULL OR o.order_date <= :date_to)
    GROUP BY c.id, c.name, c.city, c.is_active
    ORDER BY total_sales DESC, c.name
    """
)

# Product Sales Summary
# Gross item value = SUM(item amount), i.e. before the order-level discount.
# The bracketed join only lets in items that belong to confirmed orders in the range,
# while the outer LEFT JOIN still lists products that sold nothing.
PRODUCT_SALES_SQL = text(
    """
    SELECT p.id                                 AS product_id,
           p.code                               AS code,
           p.name                               AS name,
           p.category                           AS category,
           p.is_active                          AS is_active,
           COALESCE(SUM(i.quantity), 0)         AS quantity_sold,
           COUNT(DISTINCT o.id)                 AS order_count,
           COALESCE(SUM(i.amount), 0)           AS gross_value
    FROM products p
    LEFT JOIN (sales_order_items i
               JOIN sales_orders o
                 ON o.id = i.order_id
                AND o.status = 'CONFIRMED'
                AND (:date_from IS NULL OR o.order_date >= :date_from)
                AND (:date_to   IS NULL OR o.order_date <= :date_to))
           ON i.product_id = p.id
    GROUP BY p.id, p.code, p.name, p.category, p.is_active
    ORDER BY quantity_sold DESC, p.code
    """
)

LOW_STOCK_SQL = text(
    """
    SELECT p.id             AS product_id,
           p.code           AS code,
           p.name           AS name,
           p.category       AS category,
           p.price          AS price,
           p.stock_quantity AS stock_quantity,
           p.is_active      AS is_active
    FROM products p
    WHERE p.stock_quantity < :threshold
      AND (:include_inactive OR p.is_active = TRUE)
    ORDER BY p.stock_quantity, p.code
    """
)


def customer_sales(db: Session, date_from: date | None, date_to: date | None) -> list[dict]:
    rows = db.execute(CUSTOMER_SALES_SQL, {"date_from": date_from, "date_to": date_to})
    return [dict(row._mapping) for row in rows]


def product_sales(db: Session, date_from: date | None, date_to: date | None) -> list[dict]:
    rows = db.execute(PRODUCT_SALES_SQL, {"date_from": date_from, "date_to": date_to})
    return [dict(row._mapping) for row in rows]


def low_stock(db: Session, threshold: int, include_inactive: bool) -> list[dict]:
    rows = db.execute(LOW_STOCK_SQL, {"threshold": threshold, "include_inactive": include_inactive})
    return [dict(row._mapping) for row in rows]


def stock_movements_statement(
    *,
    product_id: int | None,
    movement_type: MovementType | None,
    created_from: datetime | None,
    created_to: datetime | None,
) -> Select:
    statement = select(StockMovement).options(
        selectinload(StockMovement.order), selectinload(StockMovement.creator)
    )
    if product_id is not None:
        statement = statement.where(StockMovement.product_id == product_id)
    if movement_type is not None:
        statement = statement.where(StockMovement.movement_type == movement_type)
    if created_from is not None:
        statement = statement.where(StockMovement.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(StockMovement.created_at <= created_to)
    return statement.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
