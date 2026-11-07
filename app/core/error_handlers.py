"""Convert every error into the same JSON shape, without leaking tracebacks."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.logging import request_id_var

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


def _format_validation_errors(exc: RequestValidationError) -> list[dict]:
    """Turn Pydantic's error list into ``[{field, message}]`` that the UI can show."""
    details = []
    for err in exc.errors():
        # loc looks like ("body", "items", 0, "quantity"); drop the "body"/"query" prefix.
        loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")]
        message = err.get("msg", "Invalid value")
        message = message.removeprefix("Value error, ")
        details.append({"field": ".".join(loc) or None, "message": message})
    return details


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error", "Some fields are invalid.", _format_validation_errors(exc)
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        if exc.status_code == 404 and message == "Not Found":
            message = "The requested resource was not found."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # Full traceback goes to the server log only; the client gets a generic message.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body(
                "internal_error",
                "An unexpected error occurred. Please try again later.",
                {"request_id": request_id_var.get()},
            ),
        )
