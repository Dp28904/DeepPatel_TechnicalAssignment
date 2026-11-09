"""CSV import page and sample file downloads (Admin only)."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from app.core.dependencies import require_page_admin
from app.core.exceptions import NotFound
from app.core.templating import templates
from app.modules.users.models import User

router = APIRouter(prefix="/imports", include_in_schema=False)

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"
SAMPLE_FILES = {"valid": "products_valid.csv", "invalid": "products_invalid.csv"}


@router.get("/products")
def import_page(request: Request, user: User = Depends(require_page_admin)):
    return templates.TemplateResponse(request, "imports/products.html", {"user": user})


@router.get("/products/samples/{name}")
def download_sample(name: str, _: User = Depends(require_page_admin)):
    filename = SAMPLE_FILES.get(name)  # fixed whitelist: no user-controlled paths
    if filename is None or not (SAMPLES_DIR / filename).is_file():
        raise NotFound("Sample file not found.")
    return FileResponse(SAMPLES_DIR / filename, media_type="text/csv", filename=filename)
