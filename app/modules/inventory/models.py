from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import REASON_MAX_LENGTH
from app.core.database import Base, utc_now
from app.core.enums import MovementType
from app.modules.orders.models import SalesOrder
from app.modules.products.models import Product
from app.modules.users.models import User


class StockMovement(Base):
    """Append-only ledger: every change to ``products.stock_quantity`` writes one row.

    ``quantity_change`` is signed: positive adds stock, negative removes it, so
    SUM(quantity_change) per product always equals the product's current stock.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity_change <> 0", name="quantity_change_non_zero"),
        Index("ix_stock_movements_product_id_created_at", "product_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type"), index=True
    )
    quantity_change: Mapped[int] = mapped_column(Integer)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="RESTRICT"), index=True
    )
    reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    product: Mapped[Product] = relationship(lazy="joined")
    order: Mapped[SalesOrder | None] = relationship()
    creator: Mapped[User] = relationship()

    def __repr__(self) -> str:
        change = f"{self.quantity_change:+d}"
        return f"<StockMovement {self.movement_type} {change} product={self.product_id}>"
