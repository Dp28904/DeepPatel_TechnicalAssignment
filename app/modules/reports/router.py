"""Reports API (Admin only). Sales figures include Confirmed orders only.

GET /api/reports/customer-sales?from=&to=
GET /api/reports/product-sales?from=&to=
GET /api/reports/low-stock?threshold=10&include_inactive=false
GET /api/reports/stock-movements?product_id=&movement_type=&from=&to=&page=&page_size=
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.constants import MAX_STOCK_QUANTITY
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.enums import MovementType
from app.core.pagination import Page, PageParams, page_params
from app.modules.inventory.schemas import StockMovementOut
from app.modules.reports import service
from app.modules.reports.schemas import CustomerSalesReport, LowStockReport, ProductSalesReport

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(require_admin)])

DateFrom = Query(None, alias="from", description="Order date from (inclusive), YYYY-MM-DD")
DateTo = Query(None, alias="to", description="Order date to (inclusive), YYYY-MM-DD")


@router.get("/customer-sales", response_model=CustomerSalesReport)
def customer_sales(
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
    db: Session = Depends(get_db),
):
    return service.customer_sales(db, date_from, date_to)


@router.get("/product-sales", response_model=ProductSalesReport)
def product_sales(
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
    db: Session = Depends(get_db),
):
    return service.product_sales(db, date_from, date_to)


@router.get("/low-stock", response_model=LowStockReport)
def low_stock(
    threshold: int = Query(..., ge=0, le=MAX_STOCK_QUANTITY, description="Show stock below this"),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    return service.low_stock(db, threshold, include_inactive)


@router.get("/stock-movements", response_model=Page[StockMovementOut])
def stock_movements(
    product_id: int | None = Query(None, ge=1),
    movement_type: MovementType | None = Query(None),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return service.stock_movements(
        db,
        params,
        product_id=product_id,
        movement_type=movement_type,
        date_from=date_from,
        date_to=date_to,
    )
