from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import (
    CITY_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    MOBILE_MAX_LENGTH,
    NAME_MAX_LENGTH,
)
from app.core.database import Base, utc_now


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Indexed because the customer list is searched by name, email and mobile.
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), index=True)
    email: Mapped[str | None] = mapped_column(String(EMAIL_MAX_LENGTH), index=True)
    mobile: Mapped[str | None] = mapped_column(String(MOBILE_MAX_LENGTH), index=True)
    city: Mapped[str | None] = mapped_column(String(CITY_MAX_LENGTH))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<Customer {self.id} {self.name}>"
