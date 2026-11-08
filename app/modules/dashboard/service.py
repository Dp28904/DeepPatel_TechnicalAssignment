"""Dashboard: headline numbers and chart data, scoped by role.

An Admin sees the whole business. A Sales User sees only the orders they created,
which is the same ownership rule the orders API applies.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.core.dates import validate_date_range
from app.core.enums import OrderStatus
from app.core.money import ZERO, round_money
from app.core.pagination import PageParams
from app.modules.dashboard import repository
from app.modules.dashboard.schemas import (
    CategoryBar,
    CustomerBar,
    Dashboard,
    Kpis,
    LowStockItem,
    MonthPoint,
    ProductBar,
    StatusSlice,
    UserBar,
)
from app.modules.orders import service as order_service
from app.modules.users.models import User

LOW_STOCK_THRESHOLD = 10
TOP_N = 5
MAX_MONTHS = 24
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _fill_months(rows: list[dict], first: date | None, last: date) -> list[MonthPoint]:
    """One point per calendar month from ``first`` to ``last``, with zero for months that
    had no confirmed sales, so the trend line does not skip gaps. Capped at 24 months."""
    by_month = {_month_index(r["sales_year"], r["sales_month"]): r for r in rows}
    if first is None:
        return []
    start = _month_index(first.year, first.month)
    end = _month_index(last.year, last.month)
    start = max(start, end - MAX_MONTHS + 1)
    points = []
    for index in range(start, end + 1):
        year, month = divmod(index, 12)
        row = by_month.get(index)
        points.append(
            MonthPoint(
                year=year,
                month=month + 1,
                label=f"{MONTH_NAMES[month]} {year}",
                orders=row["orders"] if row else 0,
                net_sales=round_money(row["net_sales"]) if row else ZERO,
            )
        )
    return points


def get_dashboard(
    db: Session, user: User, date_from: date | None, date_to: date | None
) -> Dashboard:
    validate_date_range(date_from, date_to)
    owner = None if user.is_admin else user.id

    totals = repository.totals(db, owner, date_from, date_to)
    confirmed = totals["confirmed_orders"]
    net_sales = round_money(totals["net_sales"])
    low_stock = repository.low_stock(db, LOW_STOCK_THRESHOLD, limit=8)

    kpis = Kpis(
        net_sales=net_sales,
        gross_sales=round_money(totals["gross_sales"]),
        discounts=round_money(totals["discounts"]),
        confirmed_orders=confirmed,
        average_order_value=round_money(net_sales / confirmed) if confirmed else ZERO,
        draft_orders=totals["draft_orders"],
        draft_value=round_money(totals["draft_value"]),
        cancelled_orders=totals["cancelled_orders"],
        low_stock_products=low_stock[0]["total_low"] if low_stock else 0,
    )

    # The trend runs from the range start (or the first sale) to the range end (or today).
    monthly = _fill_months(
        repository.monthly_sales(db, owner, date_from, date_to),
        first=date_from or totals["first_sale_date"],
        last=min(date_to or date.today(), date.today()),
    )

    recent = order_service.list_orders(
        db, user, PageParams(page=1, page_size=5), date_from=date_from, date_to=date_to
    )

    return Dashboard(
        scope="all" if owner is None else "own",
        date_from=date_from,
        date_to=date_to,
        low_stock_threshold=LOW_STOCK_THRESHOLD,
        kpis=kpis,
        monthly_sales=monthly,
        orders_by_status=[
            StatusSlice(status=OrderStatus.CONFIRMED, orders=confirmed, value=net_sales),
            StatusSlice(
                status=OrderStatus.DRAFT,
                orders=totals["draft_orders"],
                value=round_money(totals["draft_value"]),
            ),
            StatusSlice(
                status=OrderStatus.CANCELLED,
                orders=totals["cancelled_orders"],
                value=round_money(totals["cancelled_value"]),
            ),
        ],
        top_customers=[
            CustomerBar(**{**r, "net_sales": round_money(r["net_sales"])})
            for r in repository.top_customers(db, owner, date_from, date_to, TOP_N)
        ],
        top_products=[
            ProductBar(
                **{
                    **r,
                    "quantity_sold": int(r["quantity_sold"]),
                    "gross_value": round_money(r["gross_value"]),
                }
            )
            for r in repository.top_products(db, owner, date_from, date_to, TOP_N)
        ],
        sales_by_category=[
            CategoryBar(
                category=r["category"],
                quantity_sold=int(r["quantity_sold"]),
                gross_value=round_money(r["gross_value"]),
            )
            for r in repository.sales_by_category(db, owner, date_from, date_to)
        ],
        sales_by_user=[
            UserBar(**{**r, "net_sales": round_money(r["net_sales"])})
            for r in repository.sales_by_user(db, owner, date_from, date_to)
        ]
        if owner is None
        else [],
        low_stock=[
            LowStockItem(**{k: r[k] for k in ("product_id", "code", "name", "stock_quantity")})
            for r in low_stock
        ],
        recent_orders=recent["items"],
    )
