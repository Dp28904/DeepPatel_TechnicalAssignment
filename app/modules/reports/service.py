"""Report business rules: input checks, totals and consistent money formatting."""

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.enums import MovementType
from app.core.exceptions import ValidationFailed
from app.core.money import ZERO, round_money
from app.core.pagination import PageParams, paginate
from app.modules.inventory.schemas import StockMovementOut
from app.modules.reports import repository
from app.modules.reports.schemas import (
    CustomerSalesReport,
    CustomerSalesRow,
    CustomerSalesTotals,
    DateRange,
    LowStockReport,
    LowStockRow,
    ProductSalesReport,
    ProductSalesRow,
    ProductSalesTotals,
)


def _check_range(date_from: date | None, date_to: date | None) -> DateRange:
    if date_from and date_to and date_from > date_to:
        message = "'From' date must be on or before 'To' date."
        raise ValidationFailed(message, details=[{"field": "from", "message": message}])
    return DateRange(date_from=date_from, date_to=date_to)


def customer_sales(
    db: Session, date_from: date | None, date_to: date | None
) -> CustomerSalesReport:
    filters = _check_range(date_from, date_to)
    rows = [
        CustomerSalesRow(
            **{
                **row,
                "is_active": bool(row["is_active"]),
                "total_sales": round_money(row["total_sales"]),
            }
        )
        for row in repository.customer_sales(db, date_from, date_to)
    ]
    totals = CustomerSalesTotals(
        customers=len(rows),
        customers_with_sales=sum(1 for row in rows if row.confirmed_orders),
        confirmed_orders=sum(row.confirmed_orders for row in rows),
        total_sales=round_money(sum((row.total_sales for row in rows), ZERO)),
    )
    return CustomerSalesReport(filters=filters, rows=rows, totals=totals)


def product_sales(db: Session, date_from: date | None, date_to: date | None) -> ProductSalesReport:
    filters = _check_range(date_from, date_to)
    rows = [
        ProductSalesRow(
            **{
                **row,
                "is_active": bool(row["is_active"]),
                "quantity_sold": int(row["quantity_sold"]),
                "gross_value": round_money(row["gross_value"]),
            }
        )
        for row in repository.product_sales(db, date_from, date_to)
    ]
    totals = ProductSalesTotals(
        quantity_sold=sum(row.quantity_sold for row in rows),
        gross_value=round_money(sum((row.gross_value for row in rows), ZERO)),
    )
    return ProductSalesReport(filters=filters, rows=rows, totals=totals)


def low_stock(db: Session, threshold: int, include_inactive: bool) -> LowStockReport:
    rows = [
        LowStockRow(
            **{
                **row,
                "is_active": bool(row["is_active"]),
                "price": round_money(row["price"]),
                "below_threshold_by": threshold - row["stock_quantity"],
            }
        )
        for row in repository.low_stock(db, threshold, include_inactive)
    ]
    return LowStockReport(threshold=threshold, include_inactive=include_inactive, rows=rows)


def stock_movements(
    db: Session,
    params: PageParams,
    *,
    product_id: int | None,
    movement_type: MovementType | None,
    date_from: date | None,
    date_to: date | None,
) -> dict:
    _check_range(date_from, date_to)
    # Movement timestamps are stored in UTC; the range covers whole days, so the
    # end bound is "before the start of the day after date_to".
    statement = repository.stock_movements_statement(
        product_id=product_id,
        movement_type=movement_type,
        created_from=datetime.combine(date_from, time.min) if date_from else None,
        created_before=datetime.combine(date_to + timedelta(days=1), time.min) if date_to else None,
    )
    return paginate(db, statement, params, StockMovementOut.from_model)
