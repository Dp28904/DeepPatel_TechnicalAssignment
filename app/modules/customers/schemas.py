import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.constants import CITY_MAX_LENGTH, MOBILE_MAX_LENGTH, NAME_MAX_LENGTH
from app.core.schemas import InputModel, blank_to_none

# 10-15 digits, optional leading +. Spaces, dashes and brackets are stripped first.
MOBILE_PATTERN = re.compile(r"^\+?\d{10,15}$")


class CustomerIn(InputModel):
    """Body for creating (POST) and replacing (PUT) a customer."""

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=MOBILE_MAX_LENGTH)
    city: str | None = Field(default=None, max_length=CITY_MAX_LENGTH)
    is_active: bool = True

    @field_validator("email", "mobile", "city", mode="before")
    @classmethod
    def empty_string_means_not_provided(cls, value):
        return blank_to_none(value)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str | None) -> str | None:
        return value.lower() if value else value

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"[\s\-()]", "", value)
        if not MOBILE_PATTERN.match(cleaned):
            raise ValueError("Mobile must be 10-15 digits, optionally starting with +.")
        return cleaned


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None
    mobile: str | None
    city: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
