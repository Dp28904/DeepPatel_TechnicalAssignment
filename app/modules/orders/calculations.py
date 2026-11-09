"""Order money calculations. This is the only place order totals are computed.

    Item Amount     = Quantity x Rate
    Subtotal        = Sum of Item Amounts
    Discount Amount = Subtotal x Discount Percentage / 100
    Grand Total     = Subtotal - Discount Amount

All values are Decimal. Rounding uses one rule everywhere: 2 decimal places,
ROUND_HALF_UP (see app/core/money.py). The functions are pure (no database), so
they are easy to unit-test.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from app.core.constants import (
    MAX_DISCOUNT_PERCENT,
    MAX_ITEM_QUANTITY,
    MIN_DISCOUNT_PERCENT,
    MIN_ITEM_QUANTITY,
)
from app.core.exceptions import ValidationFailed
from app.core.money import round_money, to_decimal


@dataclass(frozen=True)
class OrderTotals:
    line_amounts: list[Decimal]
    subtotal: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    grand_total: Decimal


def validate_quantity(quantity) -> int:
    # bool is a subclass of int in Python, so True would otherwise count as 1.
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValidationFailed(f"Quantity must be a whole number, got {quantity!r}.")
    if not MIN_ITEM_QUANTITY <= quantity <= MAX_ITEM_QUANTITY:
        raise ValidationFailed(
            f"Quantity must be between {MIN_ITEM_QUANTITY} and {MAX_ITEM_QUANTITY}, got {quantity}."
        )
    return quantity


def validate_rate(rate) -> Decimal:
    try:
        value = to_decimal(rate)
    except ValueError as exc:
        raise ValidationFailed(f"Rate must be a number, got {rate!r}.") from exc
    if value < 0:
        raise ValidationFailed(f"Rate cannot be negative, got {value}.")
    return value


def validate_discount_percent(discount_percent) -> Decimal:
    try:
        value = to_decimal(discount_percent)
    except ValueError as exc:
        raise ValidationFailed(f"Discount must be a number, got {discount_percent!r}.") from exc
    if not MIN_DISCOUNT_PERCENT <= value <= MAX_DISCOUNT_PERCENT:
        raise ValidationFailed(
            f"Discount must be between {MIN_DISCOUNT_PERCENT}% and {MAX_DISCOUNT_PERCENT}%."
        )
    return value


def line_amount(quantity, rate) -> Decimal:
    """Item Amount = Quantity x Rate, rounded to 2 decimals."""
    return round_money(validate_quantity(quantity) * validate_rate(rate))


def calculate_order_totals(lines: Iterable[tuple[int, Decimal]], discount_percent) -> OrderTotals:
    """Compute every money value for an order from (quantity, rate) pairs.

    Item amounts are rounded first and the subtotal is their sum, so the printed
    lines always add up to the printed subtotal.
    """
    amounts = [line_amount(quantity, rate) for quantity, rate in lines]
    if not amounts:
        raise ValidationFailed("An order needs at least one item.")

    percent = validate_discount_percent(discount_percent)
    subtotal = round_money(sum(amounts, Decimal("0")))
    discount_amount = round_money(subtotal * percent / Decimal("100"))
    grand_total = round_money(subtotal - discount_amount)

    return OrderTotals(
        line_amounts=amounts,
        subtotal=subtotal,
        discount_percent=percent,
        discount_amount=discount_amount,
        grand_total=grand_total,
    )
