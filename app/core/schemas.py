"""Reusable validated field types, so every module applies the same rules."""

import re
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.core.constants import MAX_PRICE, MONEY_PRECISION, MONEY_SCALE

_PLAIN_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
# Control characters (NUL, tab, newline, escape, DEL, ...) have no place in names or codes.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def plain_number(value):
    """Accept numbers, or strings written plainly like "1500" or "1500.50".

    Python's Decimal would also accept "1e2", "1_000", "Infinity" and " 100 ", which
    are surprising for money typed by a person, so text input must be plain digits.
    """
    if isinstance(value, str):
        text = value.strip()
        if not _PLAIN_NUMBER.match(text):
            raise ValueError("Enter a plain number such as 1500 or 1500.50.")
        return text
    return value


# Money: exact decimal, never negative, at most 2 decimal places.
Money = Annotated[
    Decimal,
    BeforeValidator(plain_number),
    Field(ge=0, le=MAX_PRICE, max_digits=MONEY_PRECISION, decimal_places=MONEY_SCALE),
]

# Whole numbers only. strict=True rejects 2.5, 2.0, true and "2", so a quantity is
# always a real integer.
WholeNumber = Annotated[int, Field(strict=True)]
NonNegativeWholeNumber = Annotated[int, Field(strict=True, ge=0)]
PositiveWholeNumber = Annotated[int, Field(strict=True, ge=1)]


class InputModel(BaseModel):
    """Base for request bodies: unknown fields are rejected, strings are trimmed, and
    no text field may contain control characters."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def reject_control_characters(cls, value):
        if isinstance(value, str) and _CONTROL_CHARACTERS.search(value):
            raise ValueError("Must not contain control characters (such as tabs or line breaks).")
        return value


def blank_to_none(value):
    """Treat '' (an empty form field) as 'not provided'."""
    if isinstance(value, str) and not value.strip():
        return None
    return value
