"""Corrected calculate_total() for the Part 11 debugging exercise.

The bug
    ``total = amount`` replaced the running total on every loop, so only the LAST
    item was returned: 3 x 50 = 150 instead of 2 x 100 + 3 x 50 = 350.
    The fix is to accumulate: ``total += amount``.

Behaviour of the corrected version
    - Empty list        -> Decimal("0.00"); a sum of nothing is zero, not an error.
    - Missing qty/rate  -> ValueError naming the item and the missing key(s),
                           instead of a bare KeyError.
    - Invalid qty       -> ValueError unless it is a whole number >= 1
                           (rejects 0, negatives, 2.5, "2" and True).
    - Invalid rate      -> ValueError unless it is a finite number >= 0
                           (rejects negatives, "100", None, NaN and True).
    - Wrong shapes      -> TypeError if ``items`` is not a list/tuple or an item is
                           not a dict.
    - Money is Decimal, rounded to 2 places with ROUND_HALF_UP, so 3 x 0.1 gives
      0.30 and not 0.30000000000000004.
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
REQUIRED_KEYS = ("qty", "rate")


def _validate_qty(qty, position: int) -> int:
    # bool is a subclass of int in Python, so True would otherwise count as 1.
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise ValueError(f"Item {position}: qty must be a whole number, got {qty!r}.")
    if qty < 1:
        raise ValueError(f"Item {position}: qty must be at least 1, got {qty}.")
    return qty


def _validate_rate(rate, position: int) -> Decimal:
    if isinstance(rate, bool) or not isinstance(rate, int | float | Decimal):
        raise ValueError(f"Item {position}: rate must be a number, got {rate!r}.")
    # Floats go through str() so 0.1 becomes exactly Decimal("0.1").
    value = Decimal(str(rate)) if isinstance(rate, float) else Decimal(rate)
    if not value.is_finite():
        raise ValueError(f"Item {position}: rate must be a finite number, got {rate!r}.")
    if value < 0:
        raise ValueError(f"Item {position}: rate cannot be negative, got {rate}.")
    return value


def calculate_total(items) -> Decimal:
    """Return the sum of qty x rate over all items, rounded to 2 decimal places."""
    if not isinstance(items, list | tuple):
        raise TypeError(f"items must be a list of dicts, got {type(items).__name__}.")

    total = Decimal("0")
    for position, item in enumerate(items, start=1):  # 1-based, as a person would count
        if not isinstance(item, Mapping):
            raise TypeError(f"Item {position} must be a dict, got {type(item).__name__}.")
        missing = [key for key in REQUIRED_KEYS if key not in item]
        if missing:
            raise ValueError(f"Item {position} is missing {' and '.join(map(repr, missing))}.")

        qty = _validate_qty(item["qty"], position)
        rate = _validate_rate(item["rate"], position)
        total += qty * rate  # THE FIX: add to the running total (was: total = amount)

    return total.quantize(CENT, rounding=ROUND_HALF_UP)
