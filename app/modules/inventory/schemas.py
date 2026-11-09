from datetime import datetime

from pydantic import BaseModel

from app.core.enums import MovementType
from app.modules.inventory.models import StockMovement


class StockMovementOut(BaseModel):
    id: int
    product_id: int
    product_code: str
    product_name: str
    movement_type: MovementType
    quantity_change: int
    order_id: int | None
    order_number: str | None
    reason: str | None
    created_by: int
    created_by_name: str
    created_at: datetime

    @classmethod
    def from_model(cls, movement: StockMovement) -> "StockMovementOut":
        return cls(
            id=movement.id,
            product_id=movement.product_id,
            product_code=movement.product.code,
            product_name=movement.product.name,
            movement_type=movement.movement_type,
            quantity_change=movement.quantity_change,
            order_id=movement.order_id,
            order_number=movement.order.order_number if movement.order else None,
            reason=movement.reason,
            created_by=movement.created_by,
            created_by_name=movement.creator.name,
            created_at=movement.created_at,
        )
