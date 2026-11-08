"""Product business rules: visibility by role, unique codes, safe delete, stock adjustment.

``stock_quantity`` only changes in two places in this module, and each one writes a
stock movement in the same transaction:
- opening stock when a product is created
- an Admin stock adjustment
(Phase 4 adds order confirmation and cancellation.)
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access import can_see, visible_status
from app.core.enums import MovementType, StatusFilter
from app.core.exceptions import Conflict, NotFound
from app.core.pagination import PageParams, paginate
from app.modules.inventory import service as inventory_service
from app.modules.inventory.schemas import StockMovementOut
from app.modules.orders import usage as order_usage
from app.modules.products import repository
from app.modules.products.models import Product
from app.modules.products.schemas import (
    AdjustmentType,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    StockAdjustmentIn,
    StockAdjustmentOut,
)
from app.modules.users.models import User

OPENING_STOCK_REASON = "Opening stock"


def _duplicate_code_error(code: str) -> Conflict:
    return Conflict(
        f"Product code '{code}' already exists.",
        code="duplicate_product_code",
        details=[{"field": "code", "message": f"Product code '{code}' already exists."}],
    )


# --- Reading --------------------------------------------------------------
def list_products(
    db: Session,
    user: User,
    search: str | None,
    category: str | None,
    status: StatusFilter,
    params: PageParams,
) -> dict:
    statement = repository.search_statement(search, category, visible_status(user, status))
    return paginate(db, statement, params, ProductOut.model_validate)


def list_categories(db: Session, user: User) -> list[str]:
    return repository.list_categories(db, visible_status(user, StatusFilter.ALL))


def get_product(db: Session, user: User, product_id: int) -> Product:
    """Return a product the user may see. Inactive products are hidden from Sales Users."""
    product = repository.get(db, product_id)
    if product is None or not can_see(user, product.is_active):
        raise NotFound(f"Product {product_id} was not found.")
    return product


# --- Writing --------------------------------------------------------------
def add_product(
    db: Session, user: User, data: ProductCreate, reason: str = OPENING_STOCK_REASON
) -> Product:
    """Insert a product and record its opening stock as a stock movement. Does NOT commit:
    used by create_product (one product) and the CSV import (many, in one transaction)."""
    product = repository.add(db, Product(**data.model_dump()))
    if product.stock_quantity > 0:
        inventory_service.record_movement(
            db,
            product_id=product.id,
            movement_type=MovementType.OPENING,
            quantity_change=product.stock_quantity,
            user_id=user.id,
            reason=reason,
        )
    return product


def existing_codes(db: Session, codes: list[str]) -> set[str]:
    """Which of these product codes already exist (any status)."""
    return repository.existing_codes(db, codes)


def create_product(db: Session, user: User, data: ProductCreate) -> Product:
    if repository.get_by_code(db, data.code):
        raise _duplicate_code_error(data.code)
    try:
        product = add_product(db, user, data)
        db.commit()
    except IntegrityError as exc:
        # Another request inserted the same code after our check: the UNIQUE key caught it.
        db.rollback()
        raise _duplicate_code_error(data.code) from exc
    db.refresh(product)  # return exactly what was stored (e.g. price 2500 -> "2500.00")
    return product


def update_product(db: Session, user: User, product_id: int, data: ProductUpdate) -> Product:
    product = get_product(db, user, product_id)
    existing = repository.get_by_code(db, data.code)
    if existing and existing.id != product.id:
        raise _duplicate_code_error(data.code)
    for field, value in data.model_dump().items():
        setattr(product, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code_error(data.code) from exc
    db.refresh(product)
    return product


def delete_product(db: Session, user: User, product_id: int) -> None:
    product = get_product(db, user, product_id)
    item_count = order_usage.count_items_for_product(db, product.id)
    movement_count = inventory_service.count_movements_for_product(db, product.id)
    if item_count or movement_count:
        reasons = []
        if item_count:
            reasons.append(f"{item_count} order item(s)")
        if movement_count:
            reasons.append(f"{movement_count} stock movement(s)")
        raise Conflict(
            f"'{product.code}' is referenced by {' and '.join(reasons)} and cannot be deleted. "
            "Deactivate the product instead.",
            code="product_in_use",
        )
    try:
        repository.delete(db, product)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(
            f"'{product.code}' is in use and cannot be deleted. Deactivate it instead.",
            code="product_in_use",
        ) from exc


def adjust_stock(
    db: Session, user: User, product_id: int, data: StockAdjustmentIn
) -> StockAdjustmentOut:
    """Increase or decrease stock with a mandatory reason, in one transaction.

    The product row is locked first (SELECT ... FOR UPDATE), so a concurrent order
    confirmation or adjustment waits for us instead of working with a stale quantity.
    """
    product = repository.get_for_update(db, product_id)
    if product is None:
        db.rollback()
        raise NotFound(f"Product {product_id} was not found.")

    new_quantity = product.stock_quantity + data.signed_change
    if new_quantity < 0:
        db.rollback()  # release the lock
        raise Conflict(
            f"Cannot remove {data.quantity} unit(s) of '{product.code}': only "
            f"{product.stock_quantity} in stock. Stock cannot go below zero.",
            code="insufficient_stock",
            details=[{"field": "quantity", "message": f"At most {product.stock_quantity}."}],
        )

    product.stock_quantity = new_quantity
    movement = inventory_service.record_movement(
        db,
        product_id=product.id,
        movement_type=(
            MovementType.ADJUSTMENT_IN
            if data.adjustment_type == AdjustmentType.INCREASE
            else MovementType.ADJUSTMENT_OUT
        ),
        quantity_change=data.signed_change,
        user_id=user.id,
        reason=data.reason,
    )
    db.commit()
    db.refresh(product)
    db.refresh(movement)
    return StockAdjustmentOut(
        product=ProductOut.model_validate(product),
        movement=StockMovementOut.from_model(movement),
    )


# --- Used by the orders module ----------------------------------------------
def get_products_by_ids(db: Session, product_ids: list[int]) -> dict[int, Product]:
    """Plain read (no lock) of several products, keyed by id. Missing ids are absent."""
    return repository.get_many(db, product_ids)


def lock_products(db: Session, product_ids: list[int]) -> dict[int, Product]:
    """Lock product rows (ascending id order) for a stock-changing transaction."""
    return repository.lock_many(db, sorted(set(product_ids)))
