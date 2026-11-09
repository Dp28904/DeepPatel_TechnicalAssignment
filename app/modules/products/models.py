from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import (
    CATEGORY_MAX_LENGTH,
    MONEY_PRECISION,
    MONEY_SCALE,
    NAME_MAX_LENGTH,
    PRODUCT_CODE_MAX_LENGTH,
)
from app.core.database import Base, utc_now


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        # Database-level backstops: even a buggy code path cannot store these.
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="stock_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(PRODUCT_CODE_MAX_LENGTH), unique=True)
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), index=True)
    category: Mapped[str] = mapped_column(String(CATEGORY_MAX_LENGTH), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE))
    # Changed only through stock movements (opening, adjustment, confirm, cancel).
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<Product {self.id} {self.code} stock={self.stock_quantity}>"
