"""CSV product import through the API: all-or-nothing, row errors, opening stock."""

from pathlib import Path

from sqlalchemy import func, select

from app.core.enums import MovementType
from app.models import Product, StockMovement
from tests.factories import make_product, see_latest

URL = "/api/imports/products"
SAMPLES = Path(__file__).resolve().parents[2] / "samples"
HEADER = "product_code,product_name,category,price,stock_quantity,status"


def upload(test_client, content: str | bytes, filename: str = "products.csv"):
    data = content.encode() if isinstance(content, str) else content
    return test_client.post(URL, files={"file": (filename, data, "text/csv")})


def counts(db) -> tuple[int, int]:
    see_latest(db)
    products = db.scalar(select(func.count()).select_from(Product))
    movements = db.scalar(select(func.count()).select_from(StockMovement))
    return products, movements


# --- Required scenario 9 ----------------------------------------------------
def test_required_9_csv_with_an_invalid_row_imports_nothing(admin_client, db_session):
    csv_text = "\n".join(
        [
            HEADER,
            "PRD-001,Keyboard,Accessories,1500,20,Active",  # valid
            "PRD-002,Mouse,Accessories,-500,50,Active",  # invalid: negative price
            "PRD-003,Monitor,Displays,9000,5,Active",  # valid
        ]
    )
    response = upload(admin_client, csv_text)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "csv_invalid"
    assert error["message"].startswith("Nothing was imported: we found 1 problem(s)")
    assert error["details"] == [
        {"row": 3, "field": "price", "message": "Price cannot be negative."}
    ]
    assert counts(db_session) == (0, 0)  # not even the two valid rows


# --- Successful import ---------------------------------------------------------
def test_valid_file_imports_products_and_records_opening_stock(
    admin_client, db_session, admin_user
):
    csv_text = "\n".join(
        [
            HEADER,
            "PRD-001,Keyboard,Accessories,1500,20,Active",
            "PRD-002,Mouse,Accessories,500,0,Inactive",
        ]
    )
    response = upload(admin_client, csv_text)
    assert response.status_code == 201
    body = response.json()
    assert body["imported_count"] == 2
    assert body["opening_stock_movements"] == 1  # zero stock needs no movement
    assert [
        (p["code"], p["price"], p["stock_quantity"], p["is_active"]) for p in body["products"]
    ] == [
        ("PRD-001", "1500.00", 20, True),
        ("PRD-002", "500.00", 0, False),
    ]

    see_latest(db_session)
    [movement] = db_session.scalars(select(StockMovement)).all()
    assert movement.movement_type is MovementType.OPENING
    assert movement.quantity_change == 20
    assert movement.reason == "Opening stock (CSV import)"
    assert movement.created_by == admin_user.id


def test_code_already_in_database_is_rejected(admin_client, db_session):
    make_product(db_session, code="PRD-001")
    db_session.commit()
    csv_text = "\n".join([HEADER, "prd-001,Keyboard,Accessories,1500,20,Active"])
    response = upload(admin_client, csv_text)
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"row": 2, "field": "product_code", "message": "Product code 'PRD-001' already exists."}
    ]
    assert counts(db_session) == (1, 0)


def test_errors_are_listed_in_row_order(admin_client, db_session):
    csv_text = "\n".join([HEADER, "A-1,X,C,abc,1,Active", "A-2,X,C,1,1,Nope", "A-1,X,C,1,1,Active"])
    details = upload(admin_client, csv_text).json()["error"]["details"]
    assert [(d["row"], d["field"]) for d in details] == [
        (2, "price"),
        (3, "status"),
        (4, "product_code"),
    ]


# --- Sample files shipped with the project ------------------------------------
def test_sample_valid_file_imports(admin_client, db_session):
    response = upload(admin_client, (SAMPLES / "products_valid.csv").read_bytes())
    assert response.status_code == 201
    assert response.json()["imported_count"] == 6
    products, movements = counts(db_session)
    assert products == 6
    assert movements == 5  # IMP-003 has zero opening stock


def test_sample_invalid_file_reports_every_problem_and_imports_nothing(admin_client, db_session):
    make_product(db_session, code="PRD-001")  # so the "already in database" row is caught
    db_session.commit()
    response = upload(admin_client, (SAMPLES / "products_invalid.csv").read_bytes())
    assert response.status_code == 422
    rows = [d["row"] for d in response.json()["error"]["details"]]
    assert rows == [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]  # every row except the valid row 2
    assert counts(db_session) == (1, 0)


# --- Limits and permissions ------------------------------------------------------
def test_file_over_size_limit_is_rejected(admin_client, db_session, monkeypatch):
    monkeypatch.setattr("app.modules.imports.service.CSV_MAX_BYTES", 50)
    monkeypatch.setattr("app.modules.imports.router.CSV_MAX_BYTES", 50)
    response = upload(admin_client, HEADER + "\n" + "A-1,Item,Cat,1,1,Active\n" * 5)
    assert response.status_code == 413
    assert counts(db_session) == (0, 0)


def test_non_csv_filename_is_rejected(admin_client, migrated_database):
    response = upload(admin_client, HEADER, filename="products.xlsx")
    assert response.status_code == 422


def test_missing_file_field_is_rejected(admin_client, migrated_database):
    assert admin_client.post(URL, files={}).status_code == 422


def test_sales_user_cannot_import(sales_client, db_session):
    response = upload(sales_client, (SAMPLES / "products_valid.csv").read_bytes())
    assert response.status_code == 403
    assert counts(db_session) == (0, 0)


def test_import_requires_login(client, migrated_database):
    assert upload(client, HEADER).status_code == 401


# --- Page and sample downloads ------------------------------------------------------
def test_import_page_is_admin_only(admin_client, sales_client):
    assert admin_client.get("/imports/products").status_code == 200
    assert sales_client.get("/imports/products").status_code == 403


def test_import_page_no_longer_offers_sample_downloads(admin_client):
    page = admin_client.get("/imports/products").text
    assert "samples/valid" not in page and "code-block" not in page
    assert admin_client.get("/imports/products/samples/valid").status_code == 404
