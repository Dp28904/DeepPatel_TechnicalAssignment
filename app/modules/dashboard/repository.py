"""Dashboard queries. Every query takes ``:owner``:

- NULL for an Admin, so it covers every user's orders;
- the user's id for a Sales User, so it covers only the orders they created.

Sales figures count CONFIRMED orders only, like the reports.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

_ORDER_SCOPE = """
      AND (:owner IS NULL OR o.created_by = :owner)
      AND (:date_from IS NULL OR o.order_date >= :date_from)
      AND (:date_to   IS NULL OR o.order_date <= :date_to)
"""

# One pass over the orders gives every headline number and the status split.
TOTALS_SQL = text(
    f"""
    SELECT
        COUNT(CASE WHEN o.status = 'CONFIRMED' THEN 1 END)                  AS confirmed_orders,
        COALESCE(SUM(CASE WHEN o.status = 'CONFIRMED' THEN o.grand_total END), 0)
                                                                            AS net_sales,
        COALESCE(SUM(CASE WHEN o.status = 'CONFIRMED' THEN o.subtotal END), 0)
                                                                            AS gross_sales,
        COALESCE(SUM(CASE WHEN o.status = 'CONFIRMED' THEN o.discount_amount END), 0)
                                                                            AS discounts,
        COUNT(CASE WHEN o.status = 'DRAFT' THEN 1 END)                      AS draft_orders,
        COALESCE(SUM(CASE WHEN o.status = 'DRAFT' THEN o.grand_total END), 0)
                                                                            AS draft_value,
        COUNT(CASE WHEN o.status = 'CANCELLED' THEN 1 END)                  AS cancelled_orders,
        COALESCE(SUM(CASE WHEN o.status = 'CANCELLED' THEN o.grand_total END), 0)
                                                                            AS cancelled_value,
        MIN(CASE WHEN o.status = 'CONFIRMED' THEN o.order_date END)         AS first_sale_date
    FROM sales_orders o
    WHERE 1 = 1 {_ORDER_SCOPE}
    """
)

MONTHLY_SQL = text(
    f"""
    SELECT YEAR(o.order_date)   AS sales_year,
           MONTH(o.order_date)  AS sales_month,
           COUNT(*)             AS orders,
           SUM(o.grand_total)   AS net_sales
    FROM sales_orders o
    WHERE o.status = 'CONFIRMED' {_ORDER_SCOPE}
    GROUP BY YEAR(o.order_date), MONTH(o.order_date)
    ORDER BY sales_year, sales_month
    """
)

TOP_CUSTOMERS_SQL = text(
    f"""
    SELECT c.id AS customer_id, c.name AS customer_name,
           COUNT(o.id) AS orders, SUM(o.grand_total) AS net_sales
    FROM sales_orders o
    JOIN customers c ON c.id = o.customer_id
    WHERE o.status = 'CONFIRMED' {_ORDER_SCOPE}
    GROUP BY c.id, c.name
    ORDER BY net_sales DESC, c.name
    LIMIT :limit
    """
)

TOP_PRODUCTS_SQL = text(
    f"""
    SELECT p.id AS product_id, p.code, p.name,
           SUM(i.quantity) AS quantity_sold, SUM(i.amount) AS gross_value
    FROM sales_order_items i
    JOIN sales_orders o ON o.id = i.order_id
    JOIN products p ON p.id = i.product_id
    WHERE o.status = 'CONFIRMED' {_ORDER_SCOPE}
    GROUP BY p.id, p.code, p.name
    ORDER BY quantity_sold DESC, p.code
    LIMIT :limit
    """
)

CATEGORY_SQL = text(
    f"""
    SELECT p.category, SUM(i.quantity) AS quantity_sold, SUM(i.amount) AS gross_value
    FROM sales_order_items i
    JOIN sales_orders o ON o.id = i.order_id
    JOIN products p ON p.id = i.product_id
    WHERE o.status = 'CONFIRMED' {_ORDER_SCOPE}
    GROUP BY p.category
    ORDER BY gross_value DESC, p.category
    """
)

SALES_BY_USER_SQL = text(
    f"""
    SELECT u.id AS user_id, u.name AS user_name,
           COUNT(o.id) AS orders, SUM(o.grand_total) AS net_sales
    FROM sales_orders o
    JOIN users u ON u.id = o.created_by
    WHERE o.status = 'CONFIRMED' {_ORDER_SCOPE}
    GROUP BY u.id, u.name
    ORDER BY net_sales DESC, u.name
    """
)

# Stock is current (not date-scoped). Only active products: both roles can see them.
LOW_STOCK_SQL = text(
    """
    SELECT p.id AS product_id, p.code, p.name, p.stock_quantity,
           COUNT(*) OVER () AS total_low
    FROM products p
    WHERE p.is_active = TRUE AND p.stock_quantity < :threshold
    ORDER BY p.stock_quantity, p.code
    LIMIT :limit
    """
)


def _params(owner: int | None, date_from: date | None, date_to: date | None, **extra) -> dict:
    return {"owner": owner, "date_from": date_from, "date_to": date_to, **extra}


def _rows(db: Session, sql, params: dict) -> list[dict]:
    return [dict(row._mapping) for row in db.execute(sql, params)]


def totals(db, owner, date_from, date_to) -> dict:
    return _rows(db, TOTALS_SQL, _params(owner, date_from, date_to))[0]


def monthly_sales(db, owner, date_from, date_to) -> list[dict]:
    return _rows(db, MONTHLY_SQL, _params(owner, date_from, date_to))


def top_customers(db, owner, date_from, date_to, limit: int) -> list[dict]:
    return _rows(db, TOP_CUSTOMERS_SQL, _params(owner, date_from, date_to, limit=limit))


def top_products(db, owner, date_from, date_to, limit: int) -> list[dict]:
    return _rows(db, TOP_PRODUCTS_SQL, _params(owner, date_from, date_to, limit=limit))


def sales_by_category(db, owner, date_from, date_to) -> list[dict]:
    return _rows(db, CATEGORY_SQL, _params(owner, date_from, date_to))


def sales_by_user(db, owner, date_from, date_to) -> list[dict]:
    return _rows(db, SALES_BY_USER_SQL, _params(owner, date_from, date_to))


def low_stock(db, threshold: int, limit: int) -> list[dict]:
    return _rows(db, LOW_STOCK_SQL, {"threshold": threshold, "limit": limit})
