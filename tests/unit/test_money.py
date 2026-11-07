"""The single money rounding rule: two decimals, ROUND_HALF_UP."""

from decimal import Decimal

import pytest

from app.core.money import has_at_most_two_decimals, round_money, to_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.005", "0.01"),  # half rounds up
        ("0.004", "0.00"),
        ("2.675", "2.68"),  # a float would give 2.67 here
        ("4050", "4050.00"),
        ("1234.5650", "1234.57"),
        (2.675, "2.68"),  # floats are converted through str(), not binary
        (10, "10.00"),
    ],
)
def test_round_money_half_up(value, expected):
    assert round_money(value) == Decimal(expected)
    assert str(round_money(value)) == expected


@pytest.mark.parametrize("bad", ["abc", "", None, True, "NaN", "Infinity", [1]])
def test_to_decimal_rejects_non_numbers(bad):
    with pytest.raises(ValueError):
        to_decimal(bad)


def test_has_at_most_two_decimals():
    assert has_at_most_two_decimals(Decimal("10"))
    assert has_at_most_two_decimals(Decimal("10.25"))
    assert not has_at_most_two_decimals(Decimal("10.255"))
