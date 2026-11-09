"""Tests proving the calculate_total() fix (run: pytest debugging)."""

from decimal import Decimal

import pytest

from debugging import original_buggy
from debugging.calculate_total import calculate_total

ASSIGNMENT_ITEMS = [{"qty": 2, "rate": 100}, {"qty": 3, "rate": 50}]


# --- The bug and the fix ------------------------------------------------------
def test_original_function_returns_only_the_last_item():
    """Reproduces the reported bug: 150 (3 x 50) instead of 350."""
    assert original_buggy.calculate_total(ASSIGNMENT_ITEMS) == 150


def test_fixed_function_returns_350_for_the_assignment_example():
    result = calculate_total(ASSIGNMENT_ITEMS)
    assert result == 350
    assert result == Decimal("350.00")


def test_every_item_contributes_regardless_of_order():
    items = [{"qty": 1, "rate": 10}, {"qty": 1, "rate": 20}, {"qty": 1, "rate": 30}]
    assert calculate_total(items) == 60
    assert calculate_total(list(reversed(items))) == 60


def test_single_item():
    assert calculate_total([{"qty": 4, "rate": 25}]) == 100


def test_tuple_input_and_extra_keys_are_accepted():
    items = ({"qty": 2, "rate": 5, "name": "Pen"},)
    assert calculate_total(items) == 10


# --- Empty list ---------------------------------------------------------------
def test_empty_list_returns_zero():
    result = calculate_total([])
    assert result == 0
    assert str(result) == "0.00"


# --- Missing quantity or rate ---------------------------------------------------
@pytest.mark.parametrize(
    ("item", "message"),
    [
        ({"rate": 100}, "Item 2 is missing 'qty'."),
        ({"qty": 2}, "Item 2 is missing 'rate'."),
        ({}, "Item 2 is missing 'qty' and 'rate'."),
    ],
)
def test_missing_qty_or_rate_raises_clear_error(item, message):
    with pytest.raises(ValueError) as error:
        calculate_total([{"qty": 1, "rate": 1}, item])
    assert str(error.value) == message


# --- Invalid quantities -----------------------------------------------------------
@pytest.mark.parametrize("qty", [0, -1, -100])
def test_zero_or_negative_qty_is_rejected(qty):
    with pytest.raises(ValueError, match="qty must be at least 1"):
        calculate_total([{"qty": qty, "rate": 10}])


@pytest.mark.parametrize("qty", [2.5, 2.0, "2", None, True, [2]])
def test_non_whole_number_qty_is_rejected(qty):
    # Without this check "2" * 3 would silently give the string "222".
    with pytest.raises(ValueError, match="qty must be a whole number"):
        calculate_total([{"qty": qty, "rate": 3}])


# --- Invalid rates -------------------------------------------------------------
@pytest.mark.parametrize("rate", [-1, -0.01, Decimal("-5")])
def test_negative_rate_is_rejected(rate):
    with pytest.raises(ValueError, match="rate cannot be negative"):
        calculate_total([{"qty": 1, "rate": rate}])


@pytest.mark.parametrize("rate", ["100", None, True, [1]])
def test_non_numeric_rate_is_rejected(rate):
    with pytest.raises(ValueError, match="rate must be a number"):
        calculate_total([{"qty": 1, "rate": rate}])


@pytest.mark.parametrize("rate", [float("nan"), float("inf"), Decimal("NaN")])
def test_non_finite_rate_is_rejected(rate):
    with pytest.raises(ValueError, match="rate must be a finite number"):
        calculate_total([{"qty": 1, "rate": rate}])


def test_zero_rate_is_allowed():
    assert calculate_total([{"qty": 5, "rate": 0}]) == 0


# --- Wrong shapes ----------------------------------------------------------------
@pytest.mark.parametrize("items", [None, "abc", {"qty": 1, "rate": 1}, 5])
def test_items_must_be_a_list(items):
    with pytest.raises(TypeError, match="items must be a list"):
        calculate_total(items)


def test_each_item_must_be_a_dict():
    with pytest.raises(TypeError, match="Item 1 must be a dict"):
        calculate_total([(2, 100)])


# --- Money precision -----------------------------------------------------------
def test_float_rates_do_not_produce_binary_noise():
    # The original would return 0.30000000000000004 here.
    assert str(calculate_total([{"qty": 3, "rate": 0.1}])) == "0.30"


def test_decimal_rates_and_half_up_rounding():
    assert calculate_total([{"qty": 1, "rate": Decimal("1499.99")}]) == Decimal("1499.99")
    assert str(calculate_total([{"qty": 1, "rate": Decimal("0.005")}])) == "0.01"
