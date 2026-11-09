"""Products API.

GET /api/products lists **active** products by default (as the assignment specifies),
with search and pagination. Admins may pass status=inactive|all; Sales Users always
get active products only.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.enums import StatusFilter
from app.core.pagination import Page, PageParams, page_params
from app.modules.products import service
from app.modules.products.schemas import (
    ProductCreate,
    ProductOut,
    ProductUpdate,
    StockAdjustmentIn,
    StockAdjustmentOut,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=Page[ProductOut])
def list_products(
    search: str | None = Query(None, max_length=100, description="Product code or name"),
    category: str | None = Query(None, max_length=80),
    status: StatusFilter = Query(StatusFilter.ACTIVE),
    params: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_products(db, user, search, category, status, params)


@router.get("/categories", response_model=list[str])
def list_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_categories(db, user)


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)
):
    return service.create_product(db, user, payload)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return service.get_product(db, user, product_id)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.update_product(db, user, product_id, payload)


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)
) -> None:
    service.delete_product(db, user, product_id)


@router.post("/{product_id}/adjust-stock", response_model=StockAdjustmentOut)
def adjust_stock(
    product_id: int,
    payload: StockAdjustmentIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.adjust_stock(db, user, product_id, payload)
