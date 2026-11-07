"""Application error types.

Services raise these; ``error_handlers`` turns them into JSON responses of the form
``{"error": {"code": ..., "message": ..., "details": ...}}``.
"""

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details


class ValidationFailed(AppError):
    """Input is well-formed but breaks a business rule (HTTP 422)."""

    status_code = 422
    code = "validation_error"


class Unauthenticated(AppError):
    status_code = 401
    code = "unauthenticated"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    """The request conflicts with the current state, e.g. stock or order status (HTTP 409)."""

    status_code = 409
    code = "conflict"
