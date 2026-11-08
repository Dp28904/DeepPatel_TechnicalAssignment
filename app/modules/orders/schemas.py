"""Order request and response shapes.

Requests carry only what the user chooses: customer, order date, discount %, and
(product, quantity) pairs. Rates, amounts, totals, status and owner are always
set by the server; sending them is rejected (``extra="forbid"``).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from app.core.constants import (
    MAX_DISCOUNT_PERCENT,
    MAX_ITEM_QUANTITY,
    MIN_DISCOUNT_PERCENT,
    MIN_ORDER_DATE,
)
from app.core.enums import OrderStatus
from app.core.schemas import InputModel, PositiveWholeNumber, plain_number
from app.modules.orders.models import SalesOrder


class OrderItemIn(InputModel):
    product_id: PositiveWholeNumber
    quantity: Annotated[PositiveWholeNumber, Field(le=MAX_ITEM_QUANTITY)]


class OrderIn(InputModel):
    """Body for creating (POST) and replacing (PUT) a Draft order."""

    customer_id: PositiveWholeNumber
    order_date: date | None = None  # defaults to today
    discount_percent: Annotated[
        Decimal,
        BeforeValidator(plain_number),
        Field(ge=MIN_DISCOUNT_PERCENT, le=MAX_DISCOUNT_PERCENT, max_digits=5, decimal_places=2),
    ] = Decimal("0")
    items: list[OrderItemIn]

    @field_validator("order_date")
    @classmethod
    def within_sensible_range(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Order date cannot be in the future.")
        if value is not None and value < MIN_ORDER_DATE:
            raise ValueError(f"Order date cannot be before {MIN_ORDER_DATE.isoformat()}.")
        return value

    @field_validator("items")
    @classmethod
    def at_least_one_item_and_no_duplicates(cls, items: list[OrderItemIn]) -> list[OrderItemIn]:
        if not items:
            raise ValueError("Add at least one item to the order.")
        seen: set[int] = set()
        for item in items:
            if item.product_id in seen:
                raise ValueError(
                    f"Product {item.product_id} appears more than once. "
                    "Change the quantity on one row instead."
                )
            seen.add(item.product_id)
        return items


class PersonRef(BaseModel):
    id: int
    name: str


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    product_code: str
    product_name: str
    quantity: int
    rate: Decimal
    amount: Decimal
    available_stock: int  # current stock, so the UI can warn before confirming


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer: PersonRef
    order_date: date
    status: OrderStatus
    discount_percent: Decimal
    subtotal: Decimal
    discount_amount: Decimal
    grand_total: Decimal
    items: list[OrderItemOut]
    created_by: PersonRef
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    # What the UI may offer. The server checks again on every request.
    can_edit: bool
    can_confirm: bool
    can_cancel: bool

    @classmethod
    def from_model(cls, order: SalesOrder) -> "OrderOut":
        is_draft = order.status == OrderStatus.DRAFT
        return cls(
            id=order.id,
            order_number=order.order_number,
            customer=PersonRef(id=order.customer.id, name=order.customer.name),
            order_date=order.order_date,
            status=order.status,
            discount_percent=order.discount_percent,
            subtotal=order.subtotal,
            discount_amount=order.discount_amount,
            grand_total=order.grand_total,
            items=[
                OrderItemOut(
                    id=item.id,
                    product_id=item.product_id,
                    product_code=item.product.code,
                    product_name=item.product.name,
                    quantity=item.quantity,
                    rate=item.rate,
                    amount=item.amount,
                    available_stock=item.product.stock_quantity,
                )
                for item in order.items
            ],
            created_by=PersonRef(id=order.creator.id, name=order.creator.name),
            created_at=order.created_at,
            updated_at=order.updated_at,
            confirmed_at=order.confirmed_at,
            cancelled_at=order.cancelled_at,
            can_edit=is_draft,
            can_confirm=is_draft,
            can_cancel=order.status != OrderStatus.CANCELLED,
        )


class OrderSummaryOut(BaseModel):
    id: int
    order_number: str
    customer_name: str
    order_date: date
    status: OrderStatus
    item_count: int
    grand_total: Decimal
    created_by_name: str

    @classmethod
    def from_model(cls, order: SalesOrder) -> "OrderSummaryOut":
        return cls(
            id=order.id,
            order_number=order.order_number,
            customer_name=order.customer.name,
            order_date=order.order_date,
            status=order.status,
            item_count=len(order.items),
            grand_total=order.grand_total,
            created_by_name=order.creator.name,
        )
