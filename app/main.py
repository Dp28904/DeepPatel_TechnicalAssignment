"""Application factory: wires middleware, error handlers, routers and static files."""

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import RequestIdMiddleware, configure_logging

BASE_DIR = Path(__file__).resolve().parent

health_router = APIRouter(prefix="/api", tags=["health"])


@health_router.get("/health")
def health() -> dict:
    return {"status": "ok"}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Sales Order & Inventory Management",
        version="0.1.0",
        debug=False,
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    app.include_router(health_router)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    return app


app = create_app()
