"""CSV parsing and row validation (no database)."""

import pytest

from app.modules.imports.csv_validator import parse_products_csv

HEADER = "product_code,product_name,category,price,stock_quantity,status"


def parse(*lines: str, prefix: bytes = b""):
    return parse_products_csv(prefix + "\n".join(lines).encode("utf-8"))


def errors_of(result):
    return [(e.row, e.field, e.message) for e in result.errors]


def test_assignment_example_parses():
    result = parse(
        HEADER,
        "PRD-001,Keyboard,Accessories,1500,20,Active",
        "PRD-002,Mouse,Accessories,500,50,Active",
    )
    assert result.errors == []
    assert [
        (r.row, r.product.code, str(r.product.price), r.product.stock_quantity) for r in result.rows
    ] == [
        (2, "PRD-001", "1500", 20),
        (3, "PRD-002", "500", 50),
    ]


def test_columns_may_be_in_any_order_and_any_case():
    result = parse(
        "STATUS,Price,product_name,product_code,stock_quantity,category",
        "Inactive,10.50,Cable,cab-1,0,Cables",
    )
    assert result.errors == []
    product = result.rows[0].product
    assert (product.code, product.is_active, str(product.price)) == ("CAB-1", False, "10.50")


def test_excel_byte_order_mark_is_accepted():
    result = parse(HEADER, "A-1,Item,Cat,1,1,Active", prefix=b"\xef\xbb\xbf")
    assert result.errors == [] and len(result.rows) == 1


def test_status_is_case_insensitive():
    result = parse(HEADER, "A-1,Item,Cat,1,1,active", "A-2,Item,Cat,1,1,INACTIVE")
    assert [r.product.is_active for r in result.rows] == [True, False]


def test_blank_lines_are_skipped_and_row_numbers_stay_file_lines():
    result = parse(HEADER, "", "A-1,Item,Cat,1,1,Active", "  ,  , ", "A-2,Item,Cat,-1,1,Active")
    assert [r.row for r in result.rows] == [3]
    assert errors_of(result) == [(5, "price", "Price cannot be negative.")]


def test_quoted_values_with_commas():
    result = parse(HEADER, 'A-1,"Lamp, LED",Furniture,1299.99,2,Active')
    assert result.rows[0].product.name == "Lamp, LED"


@pytest.mark.parametrize(
    ("row", "field", "message"),
    [
        (",Item,Cat,1,1,Active", "product_code", "Product code is required."),
        ("A B!,Item,Cat,1,1,Active", "product_code", "letters, digits and dashes"),
        ("A-1,,Cat,1,1,Active", "product_name", "Product name is required."),
        ("A-1,Item,,1,1,Active", "category", "Category is required."),
        ("A-1,Item,Cat,,1,Active", "price", "Price is required."),
        ("A-1,Item,Cat,abc,1,Active", "price", "Price must be a number."),
        ("A-1,Item,Cat,-0.01,1,Active", "price", "Price cannot be negative."),
        ("A-1,Item,Cat,1.005,1,Active", "price", "at most 2 decimal places"),
        ("A-1,Item,Cat,1,,Active", "stock_quantity", "Stock quantity is required."),
        ("A-1,Item,Cat,1,2.5,Active", "stock_quantity", "whole number"),
        ("A-1,Item,Cat,1,abc,Active", "stock_quantity", "whole number"),
        ("A-1,Item,Cat,1,-3,Active", "stock_quantity", "Stock quantity cannot be negative."),
        ("A-1,Item,Cat,1,1,Pending", "status", "Status must be 'Active' or 'Inactive'"),
        ("A-1,Item,Cat,1,1,", "status", "Status must be 'Active' or 'Inactive'"),
    ],
)
def test_invalid_values_are_reported_with_row_and_column(row, field, message):
    result = parse(HEADER, row)
    assert result.rows == []
    [(error_row, error_field, error_message)] = errors_of(result)
    assert (error_row, error_field) == (2, field)
    assert message in error_message


def test_one_row_can_report_several_problems():
    result = parse(HEADER, "A-1,,Cat,-5,x,Maybe")
    assert sorted(field for _, field, _ in errors_of(result)) == [
        "price",
        "product_name",
        "status",
        "stock_quantity",
    ]


def test_duplicate_code_within_file_is_rejected_case_insensitively():
    result = parse(HEADER, "A-1,Item,Cat,1,1,Active", "a-1,Again,Cat,1,1,Active")
    assert [r.row for r in result.rows] == [2]
    assert errors_of(result) == [
        (3, "product_code", "Duplicate product code 'A-1' (first used on row 2).")
    ]


def test_wrong_number_of_values_is_reported():
    result = parse(HEADER, "A-1,Item,Cat,1")
    assert errors_of(result) == [(2, None, "Expected 6 values but found 4.")]


@pytest.mark.parametrize(
    ("header", "message"),
    [
        (
            "product_code,product_name,category,price,stock_quantity",
            "Missing required column(s): status.",
        ),
        (HEADER + ",colour", "Unknown column(s): colour."),
        (HEADER.replace("category", "price"), "Column(s) repeated in header: price."),
    ],
)
def test_bad_header_is_rejected(header, message):
    result = parse(header, "A-1,Item,Cat,1,1,Active")
    assert message in [m for _, _, m in errors_of(result)]
    assert result.rows == []


@pytest.mark.parametrize("content", [b"", b"   \n\n"])
def test_empty_file_is_rejected(content):
    assert errors_of(parse_products_csv(content)) == [(None, None, "The file is empty.")]


def test_header_without_rows_is_rejected():
    assert errors_of(parse(HEADER)) == [(None, None, "The file has a header but no product rows.")]


def test_non_utf8_file_is_rejected():
    result = parse_products_csv(HEADER.encode() + b"\nA-1,Caf\xe9,Cat,1,1,Active")
    assert errors_of(result) == [(None, None, "The file must be a UTF-8 encoded CSV file.")]


def test_too_many_rows_is_rejected(monkeypatch):
    monkeypatch.setattr("app.modules.imports.csv_validator.CSV_MAX_ROWS", 2)
    result = parse(HEADER, *[f"A-{i},Item,Cat,1,1,Active" for i in range(3)])
    assert "Too many rows" in result.errors[-1].message
