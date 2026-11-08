"""CSV import API (Admin only): POST /api/imports/products with a multipart ``file``."""

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.constants import CSV_MAX_BYTES
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.exceptions import ValidationFailed
from app.modules.imports import service
from app.modules.products.schemas import ProductOut
from app.modules.users.models import User

router = APIRouter(prefix="/api/imports", tags=["imports"])


class ImportResponse(BaseModel):
    imported_count: int
    opening_stock_movements: int
    products: list[ProductOut]


@router.post("/products", response_model=ImportResponse, status_code=201)
def import_products(
    file: UploadFile = File(..., description="CSV file"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise ValidationFailed(
            "Please upload a .csv file.",
            details=[
                {
                    "field": "file",
                    "message": "This is not a CSV file. Save it as CSV and upload it again.",
                }
            ],
        )
    # Read one byte more than the limit, so an oversized file is detected without
    # loading all of it into memory.
    content = file.file.read(CSV_MAX_BYTES + 1)
    result = service.import_products(db, user, content)
    return ImportResponse(
        imported_count=len(result.products),
        opening_stock_movements=result.opening_movements,
        products=[ProductOut.model_validate(p) for p in result.products],
    )
