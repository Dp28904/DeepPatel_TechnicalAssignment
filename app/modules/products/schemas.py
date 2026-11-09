import re
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import (
    CATEGORY_MAX_LENGTH,
    MAX_STOCK_QUANTITY,
    MIN_ADJUSTMENT_REASON_LENGTH,
    NAME_MAX_LENGTH,
    PRODUCT_CODE_PATTERN,
    REASON_MAX_LENGTH,
)
from app.core.schemas import InputModel, Money, NonNegativeWholeNumber, PositiveWholeNumber
from app.modules.inventory.schemas import StockMovementOut

_CODE_RE = re.compile(PRODUCT_CODE_PATTERN)


def normalise_product_code(value: str) -> str:
    """Product codes are stored upper-case, so 'prd-001' and 'PRD-001' are the same code."""
    code = value.strip().upper()
    if not _CODE_RE.match(code):
        raise ValueError("Code must be 1-30 characters: letters, digits and dashes only.")
    return code


class _ProductFields(InputModel):
    code: str
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    category: str = Field(min_length=1, max_length=CATEGORY_MAX_LENGTH)
    price: Money
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return normalise_product_code(value)


class ProductCreate(_ProductFields):
    # Opening stock. Recorded as an OPENING stock movement when greater than zero.
    stock_quantity: Annotated[NonNegativeWholeNumber, Field(le=MAX_STOCK_QUANTITY)] = 0


class ProductUpdate(_ProductFields):
    """Stock is deliberately not editable here: it changes only through stock
    adjustments and orders, so every change is recorded in the movement ledger."""

    @model_validator(mode="before")
    @classmethod
    def reject_stock_edits(cls, data):
        if isinstance(data, dict) and "stock_quantity" in data:
            raise ValueError("Stock cannot be edited directly. Use 'Adjust stock' instead.")
        return data


class AdjustmentType(StrEnum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"


class StockAdjustmentIn(InputModel):
    adjustment_type: AdjustmentType
    quantity: Annotated[PositiveWholeNumber, Field(le=MAX_STOCK_QUANTITY)]
    reason: str = Field(min_length=MIN_ADJUSTMENT_REASON_LENGTH, max_length=REASON_MAX_LENGTH)

    @property
    def signed_change(self) -> int:
        return self.quantity if self.adjustment_type == AdjustmentType.INCREASE else -self.quantity


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    category: str
    price: Decimal
    stock_quantity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StockAdjustmentOut(BaseModel):
    product: ProductOut
    movement: StockMovementOut
