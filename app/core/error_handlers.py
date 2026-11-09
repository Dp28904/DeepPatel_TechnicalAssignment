"""Convert every error into a consistent response, without leaking tracebacks.

- ``/api/...`` requests get JSON: ``{"error": {"code", "message", "details"}}``.
- Page requests get a redirect to /login (when not logged in) or an HTML error page.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.database import is_lock_conflict
from app.core.dependencies import LoginRequired
from app.core.exceptions import AppError
from app.core.logging import request_id_var
from app.core.templating import templates
from app.core.validation_messages import friendly_errors, summary

logger = logging.getLogger("app.errors")

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
}


def error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def _respond(request: Request, status: int, code: str, message: str, details=None, headers=None):
    if _is_api(request):
        return JSONResponse(
            status_code=status, content=error_body(code, message, details), headers=headers
        )
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status": status, "message": message, "user": None},
        status_code=status,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(LoginRequired)
    async def handle_login_required(request: Request, exc: LoginRequired):
        return RedirectResponse(exc.redirect_url, status_code=303)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return _respond(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # Plain-language messages for every field (see app/core/validation_messages.py).
        details = friendly_errors(exc.errors())
        return _respond(request, 422, "validation_error", summary(details), details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        if exc.status_code == 404 and message == "Not Found":
            message = "This page or record does not exist. Check the address and try again."
        elif exc.status_code == 405:
            message = "This action is not available here."
        return _respond(
            request, exc.status_code, code, message, headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(OperationalError)
    async def handle_operational_error(request: Request, exc: OperationalError):
        # Two requests competing for the same rows (deadlock / lock wait timeout):
        # the transaction was rolled back, so it is safe for the client to retry.
        if is_lock_conflict(exc):
            logger.warning("Lock conflict on %s %s", request.method, request.url.path)
            return _respond(
                request,
                409,
                "lock_conflict",
                "This record is being updated by another request. Please try again.",
            )
        # Any other database error (e.g. connection lost): log it here, because this
        # handler runs inside the middleware, which therefore never sees the exception.
        logger.exception("Database error on %s %s", request.method, request.url.path)
        return await handle_unexpected_error(request, exc)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # The traceback was already logged (with the request id) by RequestIdMiddleware.
        # The client only gets a generic message plus the id to quote to support.
        request_id = getattr(request.state, "request_id", None) or request_id_var.get()
        return _respond(
            request,
            500,
            "internal_error",
            "An unexpected error occurred. Please try again later.",
            {"request_id": request_id},
            headers={"X-Request-ID": request_id},
        )
