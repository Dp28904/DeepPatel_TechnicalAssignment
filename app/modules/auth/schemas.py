from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Plain str (not EmailStr): a malformed email simply fails to log in with the
    # same generic message as a wrong password.
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)
