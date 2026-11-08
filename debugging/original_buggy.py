"""The function exactly as given in the assignment, kept unchanged as evidence.

The tests import it to demonstrate the bug: it returns 150 instead of 350.
Do not use it anywhere else.
"""


def calculate_total(items):
    total = 0
    for item in items:
        amount = item["qty"] * item["rate"]
        total = amount  # BUG: overwrites the running total instead of adding to it
    return total
