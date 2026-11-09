"""Parse and validate a product CSV file. Pure Python: no database access.

Expected format (column order does not matter; header names are case-insensitive):

    product_code,product_name,category,price,stock_quantity,status
    PRD-001,Keyboard,Accessories,1500,20,Active

Rules:
- The header must contain exactly the six columns above.
- Row numbers are file line numbers: the header is row 1, the first product row 2.
- Blank lines are skipped. A UTF-8 byte-order mark (added by Excel) is accepted.
- Each row is checked with the same ``ProductCreate`` schema the API uses, so the
  rules (code format, name length, price >= 0 with 2 decimals, ...) live in one place.
- stock_quantity must be a whole number >= 0; status must be Active or Inactive
  (any letter case).
- A product code may appear only once in the file (codes compare upper-cased).

Checking codes against the database happens in the import service.
"""

import csv
import io
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.core.constants import CSV_MAX_ROWS
from app.core.validation_messages import format_number
from app.modules.products.schemas import ProductCreate

REQUIRED_COLUMNS = (
    "product_code",
    "product_name",
    "category",
    "price",
    "stock_quantity",
    "status",
)
STATUS_VALUES = {"active": True, "inactive": False}

# ProductCreate field name -> CSV column name, for error messages.
FIELD_TO_COLUMN = {
    "code": "product_code",
    "name": "product_name",
    "category": "category",
    "price": "price",
    "stock_quantity": "stock_quantity",
    "is_active": "status",
}
COLUMN_LABELS = {
    "product_code": "Product code",
    "product_name": "Product name",
    "category": "Category",
    "price": "Price",
    "stock_quantity": "Stock quantity",
    "status": "Status",
}

_WHOLE_NUMBER = re.compile(r"^\d+$")
_NEGATIVE_NUMBER = re.compile(r"^-\d+(\.\d+)?$")


@dataclass(frozen=True)
class CsvError:
    row: int | None  # None = problem with the whole file
    field: str | None
    message: str

    def as_dict(self) -> dict:
        return {"row": self.row, "field": self.field, "message": self.message}


@dataclass(frozen=True)
class CsvProductRow:
    row: int
    product: ProductCreate


@dataclass
class CsvParseResult:
    rows: list[CsvProductRow] = field(default_factory=list)
    errors: list[CsvError] = field(default_factory=list)


def _friendly_message(column: str, error: dict) -> str:
    """Turn a Pydantic error into a sentence a shop admin understands."""
    label = COLUMN_LABELS[column]
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    if kind == "string_too_short":
        return f"{label} is required."
    if kind == "string_too_long":
        return f"{label} is too long (maximum {ctx.get('max_length')} characters)."
    if kind == "greater_than_equal" and str(ctx.get("ge")) == "0":
        return f"{label} cannot be negative."
    if kind == "less_than_equal":
        return f"{label} is too large (maximum {format_number(ctx.get('le'))})."
    if kind == "decimal_max_places":
        return f"{label} can have at most 2 decimal places."
    if kind in ("decimal_parsing", "decimal_type") or (kind == "value_error" and column == "price"):
        return f"{label} must be a number, such as 1500 or 1500.50."
    if kind == "decimal_max_digits":
        return f"{label} is too large."
    return error.get("msg", "Invalid value").removeprefix("Value error, ")


def _check_header(header: list[str], line: int) -> list[CsvError]:
    names = [name.strip().lower() for name in header]
    errors = []
    duplicates = sorted({name for name in names if names.count(name) > 1})
    missing = [name for name in REQUIRED_COLUMNS if name not in names]
    unknown = [name for name in names if name not in REQUIRED_COLUMNS]
    if duplicates:
        errors.append(
            CsvError(line, None, f"Column(s) repeated in header: {', '.join(duplicates)}.")
        )
    if missing:
        errors.append(CsvError(line, None, f"Missing required column(s): {', '.join(missing)}."))
    if unknown:
        shown = ", ".join(name or "(blank)" for name in unknown)
        errors.append(CsvError(line, None, f"Unknown column(s): {shown}."))
    return errors


def _validate_row(values: dict[str, str], line: int) -> tuple[ProductCreate | None, list[CsvError]]:
    errors: list[CsvError] = []

    stock_text = values["stock_quantity"]
    stock: int | None = None
    if _WHOLE_NUMBER.match(stock_text):
        stock = int(stock_text)
    elif not stock_text:
        errors.append(CsvError(line, "stock_quantity", "Stock quantity is required."))
    elif _NEGATIVE_NUMBER.match(stock_text):
        errors.append(CsvError(line, "stock_quantity", "Stock quantity cannot be negative."))
    else:
        errors.append(
            CsvError(
                line,
                "stock_quantity",
                f"Stock quantity must be a whole number, got '{stock_text}'.",
            )
        )

    status_text = values["status"]
    is_active = STATUS_VALUES.get(status_text.lower())
    if is_active is None:
        errors.append(
            CsvError(line, "status", f"Status must be 'Active' or 'Inactive', got '{status_text}'.")
        )

    try:
        product = ProductCreate(
            code=values["product_code"],
            name=values["product_name"],
            category=values["category"],
            price=values["price"],
            stock_quantity=stock if stock is not None else 0,  # placeholder when invalid
            is_active=is_active if is_active is not None else True,
        )
    except ValidationError as exc:
        product = None
        flagged = {error.field for error in errors}
        for err in exc.errors():
            column = FIELD_TO_COLUMN.get(str(err["loc"][0]) if err["loc"] else "")
            if column and column not in flagged:
                message = (
                    f"{COLUMN_LABELS[column]} is required."
                    if not values[column]
                    else _friendly_message(column, err)
                )
                errors.append(CsvError(line, column, message))
                flagged.add(column)

    return (None if errors else product), errors


def parse_products_csv(content: bytes) -> CsvParseResult:
    result = CsvParseResult()

    if not content.strip():
        result.errors.append(CsvError(None, None, "The file is empty."))
        return result
    try:
        text = content.decode("utf-8-sig")  # utf-8-sig strips an Excel byte-order mark
    except UnicodeDecodeError:
        result.errors.append(CsvError(None, None, "The file must be a UTF-8 encoded CSV file."))
        return result

    reader = csv.reader(io.StringIO(text, newline=""))
    header: list[str] | None = None
    first_row_for_code: dict[str, int] = {}
    data_rows = 0

    try:
        for record in reader:
            line = reader.line_num
            if not any(cell.strip() for cell in record):
                continue  # blank line

            if header is None:
                header = [name.strip().lower() for name in record]
                header_errors = _check_header(record, line)
                if header_errors:
                    result.errors.extend(header_errors)
                    return result
                continue

            data_rows += 1
            if data_rows > CSV_MAX_ROWS:
                result.errors.append(
                    CsvError(
                        line, None, f"Too many rows: the limit is {CSV_MAX_ROWS} products per file."
                    )
                )
                return result

            if len(record) != len(header):
                result.errors.append(
                    CsvError(line, None, f"Expected {len(header)} values but found {len(record)}.")
                )
                continue

            values = {name: cell.strip() for name, cell in zip(header, record, strict=True)}
            product, row_errors = _validate_row(values, line)

            code = (product.code if product else values["product_code"].upper()) or None
            if code and code in first_row_for_code:
                row_errors = [e for e in row_errors if e.field != "product_code"]
                row_errors.append(
                    CsvError(
                        line,
                        "product_code",
                        f"Duplicate product code '{code}' "
                        f"(first used on row {first_row_for_code[code]}).",
                    )
                )
                product = None
            elif code:
                first_row_for_code[code] = line

            result.errors.extend(row_errors)
            if product is not None and not row_errors:
                result.rows.append(CsvProductRow(row=line, product=product))
    except csv.Error as exc:
        result.errors.append(CsvError(reader.line_num, None, f"The file is not valid CSV: {exc}."))
        return result

    if header is None:
        result.errors.append(CsvError(None, None, "The file is empty."))
    elif data_rows == 0:
        result.errors.append(CsvError(None, None, "The file has a header but no product rows."))
    return result
