"""Application factory: wires middleware, error handlers, routers and static files."""

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.core.database import ping_database
from app.core.error_handlers import error_body, register_error_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.core.security import CsrfHeaderMiddleware
from app.modules.auth import pages as auth_pages
from app.modules.auth import router as auth_api

BASE_DIR = Path(__file__).resolve().parent

health_router = APIRouter(prefix="/api", tags=["health"])


@health_router.get("/health")
def health():
    """Liveness + database connectivity check."""
    if not ping_database():
        return JSONResponse(
            status_code=503,
            content=error_body("database_unavailable", "The database is not reachable."),
        )
    return {"status": "ok", "database": "ok"}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Sales Order & Inventory Management",
        version="0.1.0",
        debug=False,
    )

    # Middleware runs outermost-last-added: RequestId -> Session -> CSRF -> routes.
    app.add_middleware(CsrfHeaderMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="sales_session",
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.is_production,
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    app.include_router(health_router)
    app.include_router(auth_api.router)
    app.include_router(auth_pages.router)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    return app


app = create_app()
