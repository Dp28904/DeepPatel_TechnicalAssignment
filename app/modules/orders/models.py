from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MAX_DISCOUNT_PERCENT, MONEY_PRECISION, MONEY_SCALE
from app.core.database import Base, utc_now
from app.core.enums import OrderStatus
from app.modules.customers.models import Customer
from app.modules.products.models import Product
from app.modules.users.models import User

Money = Numeric(MONEY_PRECISION, MONEY_SCALE)


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        CheckConstraint(
            f"discount_percent >= 0 AND discount_percent <= {MAX_DISCOUNT_PERCENT}",
            name="discount_percent_range",
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount_amount >= 0 AND grand_total >= 0",
            name="amounts_non_negative",
        ),
        # Reports filter confirmed orders by date range.
        Index("ix_sales_orders_status_order_date", "status", "order_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(40), unique=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    order_date: Mapped[date] = mapped_column(Date)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.DRAFT
    )
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    subtotal: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    customer: Mapped[Customer] = relationship(lazy="joined")
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    items: Mapped[list["SalesOrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="SalesOrderItem.id",
    )

    @property
    def is_draft(self) -> bool:
        return self.status == OrderStatus.DRAFT

    def __repr__(self) -> str:
        return f"<SalesOrder {self.id} {self.order_number} {self.status}>"


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"
    __table_args__ = (
        # The same product may appear only once per order.
        UniqueConstraint("order_id", "product_id", name="uq_sales_order_items_order_product"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("rate >= 0 AND amount >= 0", name="amounts_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    # Price copied from the product when the line was added, so later price changes
    # never alter an existing order.
    rate: Mapped[Decimal] = mapped_column(Money)
    amount: Mapped[Decimal] = mapped_column(Money)

    order: Mapped[SalesOrder] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<SalesOrderItem order={self.order_id} product={self.product_id} qty={self.quantity}>"
        )
