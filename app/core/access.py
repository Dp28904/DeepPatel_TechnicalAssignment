"""Shared visibility rule for master data (customers and products).

Admins can list active, inactive or all records. Sales Users only ever see active
records, whatever filter they send.
"""

from app.core.enums import StatusFilter
from app.modules.users.models import User


def visible_status(user: User, requested: StatusFilter) -> StatusFilter:
    return requested if user.is_admin else StatusFilter.ACTIVE


def can_see(user: User, is_active: bool) -> bool:
    return user.is_admin or is_active
