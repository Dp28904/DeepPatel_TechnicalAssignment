# Debugging Exercise (Part 11)

| File | What it is |
|---|---|
| [debugging/original_buggy.py](../debugging/original_buggy.py) | The function exactly as given, kept unchanged as evidence |
| [debugging/calculate_total.py](../debugging/calculate_total.py) | The corrected function |
| [debugging/test_calculate_total.py](../debugging/test_calculate_total.py) | 36 tests demonstrating the bug and the fix |

Run them with:

```bash
pytest debugging -v
```

These tests need no database.

## 1. Reproducing the problem

Before changing anything I ran the original with the given input, and with a few edge cases:

```text
original returns: 150 (expected 350)
empty list:       0
missing rate:     KeyError 'rate'
negative qty:     -200
string qty "2":   '222'
float rate 0.1:   0.30000000000000004
```

## 2. Cause of the incorrect result

```python
for item in items:
    amount = item["qty"] * item["rate"]
    total = amount  # <- bug
```

`total = amount` **replaces** the running total on every pass of the loop instead of adding to it. When the loop ends, `total` holds only the **last** item's amount: 3 × 50 = **150**. The first item (2 × 100 = 200) was overwritten. The correct result is 200 + 150 = **350**.

The fix is one character, an accumulating assignment:

```python
total += qty * rate
```

The test `test_original_function_returns_only_the_last_item` proves the bug exists (150). The test `test_fixed_function_returns_350_for_the_assignment_example` proves the fix (350).

## 3. Behaviour for an empty list

The function returns `Decimal("0.00")`. The sum of no items is zero, and it is not an error. An order that must have at least one item is a business rule. The application enforces that rule separately in the order service, not in a generic summing function.

## 4. Behaviour when quantity or rate is missing

The original raised a bare `KeyError: 'rate'`, which does not say which item was wrong. The corrected function checks for both keys first. It raises a `ValueError` that names the item (1-based, as a person would count) and every missing key:

```text
Item 2 is missing 'rate'.
Item 2 is missing 'qty' and 'rate'.
```

## 5. Validation of invalid quantities and rates

| Input | Original behaviour | Corrected behaviour |
|---|---|---|
| `qty = 0` or negative | Silently counted, could make the total negative | `ValueError: qty must be at least 1` |
| `qty = 2.5`, `2.0` | Accepted | `ValueError: qty must be a whole number` |
| `qty = "2"` | `"2" * 3` returned the **string** `'222'` | `ValueError: qty must be a whole number` |
| `qty = True` | Counted as 1, because `bool` is a subclass of `int` | `ValueError: qty must be a whole number` |
| `rate < 0` | Accepted | `ValueError: rate cannot be negative` |
| `rate = "100"`, `None` | Crashed or produced garbage | `ValueError: rate must be a number` |
| `rate = NaN` / `inf` | Total became NaN or inf | `ValueError: rate must be a finite number` |
| `items` not a list, item not a dict | Obscure `TypeError` | Clear `TypeError` naming the problem |

**Money precision.** The original used floats, so `3 × 0.1` gave `0.30000000000000004`. The corrected function uses `Decimal`, converts floats via `str()` (so `0.1` becomes exactly `0.1`), and rounds the result to 2 decimals with `ROUND_HALF_UP`. This is the same rounding rule the application uses in `app/core/money.py`.

## 6. Tests demonstrating the correction

[debugging/test_calculate_total.py](../debugging/test_calculate_total.py) covers:

- the bug reproduced on the original (150) and fixed (350)
- order independence, a single item, tuple input, and extra keys ignored
- the empty list returning 0.00
- missing `qty`, missing `rate`, and both missing, each with its exact message
- zero, negative and non-integer quantities, including `"2"` and `True`
- negative, non-numeric and non-finite rates; a zero rate is allowed
- wrong container types
- float noise removed, and half-up rounding

## Relation to the application

The application does not call this function. Order totals are computed in [app/modules/orders/calculations.py](../app/modules/orders/calculations.py), which follows the same principles: `Decimal` throughout, whole-number quantities of at least 1, non-negative rates, and one rounding rule. It is unit-tested in [tests/unit/test_calculations.py](../tests/unit/test_calculations.py).
