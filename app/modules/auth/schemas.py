from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Plain str (not EmailStr): a malformed email simply fails to log in with the
    # same generic message as a wrong password.
    email: str = Field(min_length=1, max_length=255)
    # Never trimmed: spaces are part of a password.
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def trim_email(cls, value: str) -> str:
        return value.strip()
