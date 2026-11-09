"""Stock movement ledger.

Every change to a product's stock writes exactly one movement row in the same
transaction as the change. These functions never commit: the caller (product
creation, stock adjustment, order confirm/cancel) owns the transaction, so the
stock change and its movement are saved or rolled back together.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import MovementType
from app.modules.inventory.models import StockMovement


def record_movement(
    db: Session,
    *,
    product_id: int,
    movement_type: MovementType,
    quantity_change: int,
    user_id: int,
    order_id: int | None = None,
    reason: str | None = None,
) -> StockMovement:
    movement = StockMovement(
        product_id=product_id,
        movement_type=movement_type,
        quantity_change=quantity_change,
        order_id=order_id,
        reason=reason,
        created_by=user_id,
    )
    db.add(movement)
    db.flush()
    return movement


def count_movements_for_product(db: Session, product_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(StockMovement)
        .where(StockMovement.product_id == product_id)
    )
