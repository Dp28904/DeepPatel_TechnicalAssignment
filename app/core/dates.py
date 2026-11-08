"""Shared date-range rule used by order lists, reports and the dashboard."""

from datetime import date

from app.core.exceptions import ValidationFailed

RANGE_ERROR = "'From' date must be on or before 'To' date."


def validate_date_range(date_from: date | None, date_to: date | None) -> None:
    """Both ends are optional and inclusive; when both are given, from <= to."""
    if date_from and date_to and date_from > date_to:
        raise ValidationFailed(RANGE_ERROR, details=[{"field": "from", "message": RANGE_ERROR}])
