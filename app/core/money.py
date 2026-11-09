"""Money helpers. All monetary values are ``Decimal`` and are rounded with one rule.

Rounding rule: two decimal places, ROUND_HALF_UP (0.005 -> 0.01), the rule people
expect on invoices. Floats are never used for money, because 0.1 + 0.2 != 0.3 in
binary floating point.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(value) -> Decimal:
    """Convert an int, str or Decimal to Decimal. Floats go through str() to avoid binary noise.

    Raises ValueError for anything that is not a finite number.
    """
    if isinstance(value, bool):
        raise ValueError("Boolean is not a valid number.")
    try:
        result = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"'{value}' is not a valid number.") from exc
    if not result.is_finite():
        raise ValueError(f"'{value}' is not a valid number.")
    return result


def round_money(value) -> Decimal:
    """Round to two decimal places using ROUND_HALF_UP."""
    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def has_at_most_two_decimals(value: Decimal) -> bool:
    return value == value.quantize(CENT)
