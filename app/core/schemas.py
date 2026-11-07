"""Reusable validated field types, so every module applies the same rules."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import MAX_PRICE, MONEY_PRECISION, MONEY_SCALE

# Money: exact decimal, never negative, at most 2 decimal places.
Money = Annotated[
    Decimal,
    Field(ge=0, le=MAX_PRICE, max_digits=MONEY_PRECISION, decimal_places=MONEY_SCALE),
]

# Whole numbers only. strict=True rejects 2.5, 2.0, true and "2", so a quantity is
# always a real integer.
WholeNumber = Annotated[int, Field(strict=True)]
NonNegativeWholeNumber = Annotated[int, Field(strict=True, ge=0)]
PositiveWholeNumber = Annotated[int, Field(strict=True, ge=1)]


class InputModel(BaseModel):
    """Base for request bodies: unknown fields are rejected, strings are trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def blank_to_none(value):
    """Treat '' (an empty form field) as 'not provided'."""
    if isinstance(value, str) and not value.strip():
        return None
    return value
