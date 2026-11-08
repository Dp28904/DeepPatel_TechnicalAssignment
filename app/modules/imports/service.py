"""All-or-nothing product import from CSV.

1. Parse and validate every row (csv_validator), collecting ALL problems.
2. Check the file's product codes against the database.
3. If there is any problem at all, reject the file: 422 with every row number and
   reason, and nothing is written.
4. Otherwise insert every product and its OPENING stock movement in ONE
   transaction, so a failure part-way through also leaves the database unchanged.
"""

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import CSV_MAX_BYTES
from app.core.database import transaction
from app.core.exceptions import Conflict, PayloadTooLarge, ValidationFailed
from app.modules.imports.csv_validator import (
    REQUIRED_COLUMNS,
    CsvError,
    parse_products_csv,
)
from app.modules.products import service as product_service
from app.modules.products.models import Product
from app.modules.users.models import User

IMPORT_STOCK_REASON = "Opening stock (CSV import)"
MAX_ERRORS_REPORTED = 500


@dataclass
class ImportResult:
    products: list[Product]
    opening_movements: int


def _sort_key(error: CsvError) -> tuple:
    column_order = REQUIRED_COLUMNS.index(error.field) if error.field in REQUIRED_COLUMNS else -1
    return (error.row or 0, column_order)


def import_products(db: Session, user: User, content: bytes) -> ImportResult:
    if len(content) > CSV_MAX_BYTES:
        raise PayloadTooLarge(f"The file is too large. The limit is {CSV_MAX_BYTES // 1024} KB.")

    parsed = parse_products_csv(content)
    errors = list(parsed.errors)

    taken = product_service.existing_codes(db, [row.product.code for row in parsed.rows])
    for row in parsed.rows:
        if row.product.code in taken:
            errors.append(
                CsvError(
                    row.row, "product_code", f"Product code '{row.product.code}' already exists."
                )
            )

    if errors:
        errors.sort(key=_sort_key)
        shown = errors[:MAX_ERRORS_REPORTED]
        more = f" Showing the first {len(shown)}." if len(errors) > len(shown) else ""
        raise ValidationFailed(
            f"Nothing was imported: we found {len(errors)} problem(s) in the file. "
            f"Fix the rows listed below and upload the file again.{more}",
            code="csv_invalid",
            details=[error.as_dict() for error in shown],
        )

    try:
        with transaction(db):
            products = [
                product_service.add_product(db, user, row.product, reason=IMPORT_STOCK_REASON)
                for row in parsed.rows
            ]
    except IntegrityError as exc:
        # Someone created one of these codes between our check and the insert.
        raise Conflict(
            "Another user added one of these product codes while the file was being imported. "
            "No products were imported; please upload the file again.",
            code="duplicate_product_code",
        ) from exc

    # Re-read in one query so the response shows exactly what was stored (e.g. "1500.00").
    stored = product_service.get_products_by_ids(db, [product.id for product in products])
    products = [stored[product.id] for product in products]
    return ImportResult(
        products=products,
        opening_movements=sum(1 for product in products if product.stock_quantity > 0),
    )
