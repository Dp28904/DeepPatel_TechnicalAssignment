from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.constants import NAME_MAX_LENGTH
from app.core.enums import Role

PASSWORD_MIN_LENGTH = 8


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)  # never trimmed
    role: Role

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.lower()


class UserOut(BaseModel):
    """Public view of a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: Role
    is_active: bool


class UserProfileUpdate(BaseModel):
    """Name and login email. Used by an Admin for a Sales User or for themselves."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.lower()


# Passwords are NOT trimmed: leading or trailing spaces are part of the password.
class PasswordReset(BaseModel):
    """An Admin setting a new password for a Sales User (no old password needed)."""

    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)


class PasswordChange(BaseModel):
    """An Admin changing their own password: the current one must be given."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)


class UserListOut(UserOut):
    created_at: datetime
    can_edit_profile: bool  # what the UI may offer; the server checks again
    can_reset_password: bool
