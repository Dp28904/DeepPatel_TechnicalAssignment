"""Turn Pydantic validation errors into plain sentences anyone can act on.

Pydantic's own wording ("String should have at least 1 character", "Input should
be a valid integer") is written for developers. Every request-validation error goes
through ``friendly_errors`` instead, which names the field the way a person would
("Item 2 quantity") and says what to do ("must be a whole number, for example 5").
"""

import re
from decimal import Decimal, InvalidOperation

# Field names whose plain label is not just "replace _ with a space".
FIELD_LABELS = {
    "customer_id": "Customer",
    "product_id": "Product",
    "discount_percent": "Discount %",
    "stock_quantity": "Stock quantity",
    "order_date": "Order date",
    "email": "Email",
    "new_password": "New password",
    "current_password": "Current password",
    "adjustment_type": "Adjustment type",
    "is_active": "Active",
    "page_size": "Page size",
    "from": "From date",
    "to": "To date",
    "file": "File",
    "code": "Product code",
}

_LOCATION_PREFIXES = ("body", "query", "path", "header", "cookie")


def field_path(loc: tuple) -> str | None:
    """("body", "items", 0, "quantity") -> "items.0.quantity" (used by the UI to find the input)."""
    parts = [str(part) for part in loc if part not in _LOCATION_PREFIXES]
    return ".".join(parts) or None


def field_label(loc: tuple) -> str:
    """("body", "items", 1, "quantity") -> "Item 2 quantity"; ("body", "name") -> "Name"."""
    parts = [part for part in loc if part not in _LOCATION_PREFIXES]
    if not parts:
        return "The request"
    words = []
    for index, part in enumerate(parts):
        if isinstance(part, int):
            # A list position: show it 1-based, attached to the singular of the list name.
            if words and words[-1].endswith("s"):
                words[-1] = words[-1][:-1]
            words.append(str(part + 1))
        else:
            label = FIELD_LABELS.get(part, part.replace("_", " "))
            words.append(label if index == 0 else label.lower())
    text = " ".join(words)
    return text[0].upper() + text[1:]


def format_number(value) -> str:
    """Format a limit for people: 1000000 -> "1,000,000", Decimal("20") -> "20".

    FastAPI may pass Decimal limits through as the text "Decimal('20')", so that
    form is unwrapped too. Shared with the CSV import's error messages.
    """
    if isinstance(value, str):
        match = re.fullmatch(r"Decimal\('([^']*)'\)", value)
        value = match.group(1) if match else value
        try:
            value = Decimal(value)
        except InvalidOperation:
            return value
    if isinstance(value, Decimal | float):
        value = int(value) if value == int(value) else value
    return f"{value:,}" if isinstance(value, int | Decimal) else str(value)


def friendly_message(error: dict) -> str:
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    loc = tuple(error.get("loc", ()))
    label = field_label(loc)
    message = error.get("msg", "")

    if kind == "missing":
        return f"{label} is required."
    if kind == "string_too_short":
        minimum = ctx.get("min_length", 1)
        return (
            f"{label} is required."
            if minimum <= 1
            else f"{label} must be at least {minimum} characters."
        )
    if kind == "string_too_long":
        return f"{label} must be at most {ctx.get('max_length')} characters."
    if kind in ("string_type",):
        return f"{label} must be text."
    if kind in ("int_type", "int_parsing", "int_from_float"):
        return f"{label} must be a whole number (for example 5)."
    if kind in ("decimal_parsing", "decimal_type", "float_parsing", "float_type", "finite_number"):
        return f"{label} must be a number (for example 1500 or 1500.50)."
    if kind == "decimal_max_places":
        return f"{label} can have at most {ctx.get('decimal_places')} decimal places."
    if kind in ("decimal_max_digits", "decimal_whole_digits"):
        return f"{label} is too large."
    if kind == "greater_than_equal":
        return f"{label} must be {format_number(ctx.get('ge'))} or more."
    if kind == "greater_than":
        return f"{label} must be more than {format_number(ctx.get('gt'))}."
    if kind == "less_than_equal":
        return f"{label} must be {format_number(ctx.get('le'))} or less."
    if kind == "less_than":
        return f"{label} must be less than {format_number(ctx.get('lt'))}."
    if kind in ("bool_type", "bool_parsing"):
        return f"{label} must be true or false."
    if kind == "enum":
        return f"{label} must be one of: {ctx.get('expected', '').replace(chr(39), '')}."
    if kind.startswith("date") or kind.startswith("datetime"):
        return f"{label} must be a valid date in the format YYYY-MM-DD (for example 2026-11-08)."
    if kind == "extra_forbidden":
        return (
            f"{label} cannot be sent here; it is not an accepted field (the system sets it itself)."
        )
    if kind == "json_invalid":
        return "The request could not be read: it is not valid JSON."
    if kind in ("model_type", "model_attributes_type", "dict_type"):
        return "The request must be a JSON object with the expected fields."
    if kind == "list_type":
        return f"{label} must be a list."
    if kind == "value_error":
        text = message.removeprefix("Value error, ")
        if "email address" in text:
            return f"{label}: enter a valid email address, for example name@company.com."
        return text  # our own validators already write plain sentences
    return re.sub(r"^Input should be", f"{label} should be", message) or "This value is not valid."


def friendly_errors(errors: list[dict]) -> list[dict]:
    """[{field, message}] for the UI: field locates the input, message is shown to the user."""
    return [
        {"field": field_path(tuple(e.get("loc", ()))), "message": friendly_message(e)}
        for e in errors
    ]


def summary(details: list[dict]) -> str:
    """One sentence for the whole response, readable on its own (e.g. in an API client)."""
    if len(details) == 1:
        return details[0]["message"]
    return (
        f"{len(details)} things need fixing: "
        + " ".join(d["message"] for d in details[:5])
        + (" …" if len(details) > 5 else "")
    )
