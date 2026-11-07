"""Enumerations shared by models, schemas and services.

Member names equal their values, so the database stores readable text such as
``CONFIRMED`` in a MySQL ENUM column.
"""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    SALES = "SALES"


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class StatusFilter(StrEnum):
    """List filter for active/inactive master data (query parameter values are lowercase)."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ALL = "all"


class MovementType(StrEnum):
    OPENING = "OPENING"  # opening stock when a product is created or imported
    ADJUSTMENT_IN = "ADJUSTMENT_IN"  # manual increase by an admin
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"  # manual decrease by an admin
    ORDER_CONFIRM = "ORDER_CONFIRM"  # deduction when an order is confirmed
    ORDER_CANCEL = "ORDER_CANCEL"  # restoration when a confirmed order is cancelled
