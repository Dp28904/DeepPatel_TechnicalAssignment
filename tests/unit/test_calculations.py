"""Order calculations (pure functions, no database).

Covers required scenario 1 (multi-item order with discount) and the calculation
side of scenarios 2 and 3 (bad quantity, discount outside 0-20%).
"""

from decimal import Decimal

import pytest

from app.core.exceptions import ValidationFailed
from app.modules.orders.calculations import calculate_order_totals, line_amount

D = Decimal


def test_assignment_example_multi_item_order_with_discount():
    """Keyboard 2 x 1500 + Mouse 3 x 500, 10% discount -> 4500 / 450 / 4050."""
    totals = calculate_order_totals([(2, D("1500.00")), (3, D("500.00"))], D("10"))
    assert totals.line_amounts == [D("3000.00"), D("1500.00")]
    assert totals.subtotal == D("4500.00")
    assert totals.discount_amount == D("450.00")
    assert totals.grand_total == D("4050.00")
    assert str(totals.grand_total) == "4050.00"  # always 2 decimal places


def test_no_discount():
    totals = calculate_order_totals([(1, D("99.99"))], D("0"))
    assert (totals.subtotal, totals.discount_amount, totals.grand_total) == (
        D("99.99"),
        D("0.00"),
        D("99.99"),
    )


def test_discount_rounds_half_up():
    # 10% of 0.05 is 0.005, which rounds UP to 0.01 (banker's rounding would give 0.00).
    totals = calculate_order_totals([(1, D("0.05"))], D("10"))
    assert totals.discount_amount == D("0.01")
    assert totals.grand_total == D("0.04")


def test_fractional_discount_percent():
    # 12.5% of 333.33 = 41.66625 -> 41.67
    totals = calculate_order_totals([(1, D("333.33"))], D("12.5"))
    assert totals.discount_amount == D("41.67")
    assert totals.grand_total == D("291.66")


def test_lines_always_add_up_to_subtotal():
    totals = calculate_order_totals([(3, D("0.10")), (7, D("19.99")), (1, D("1000"))], D("0"))
    assert sum(totals.line_amounts) == totals.subtotal


def test_maximum_discount_is_allowed():
    assert calculate_order_totals([(1, D("100"))], D("20")).grand_total == D("80.00")


@pytest.mark.parametrize("quantity", [0, -1, -100])
def test_zero_or_negative_quantity_is_rejected(quantity):
    with pytest.raises(ValidationFailed, match="Quantity"):
        line_amount(quantity, D("10"))


@pytest.mark.parametrize("quantity", [1.5, "2", None, True])
def test_non_whole_quantity_is_rejected(quantity):
    with pytest.raises(ValidationFailed, match="whole number"):
        line_amount(quantity, D("10"))


@pytest.mark.parametrize("discount", ["-1", "-0.01", "20.01", "21", "100"])
def test_discount_outside_0_to_20_is_rejected(discount):
    with pytest.raises(ValidationFailed, match="Discount"):
        calculate_order_totals([(1, D("100"))], D(discount))


def test_negative_rate_is_rejected():
    with pytest.raises(ValidationFailed, match="Rate"):
        line_amount(1, D("-0.01"))


def test_order_without_items_is_rejected():
    with pytest.raises(ValidationFailed, match="at least one item"):
        calculate_order_totals([], D("0"))
