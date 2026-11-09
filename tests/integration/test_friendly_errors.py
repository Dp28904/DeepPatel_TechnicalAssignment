"""Every validation error reads as a plain sentence naming the field.

These are the exact messages a user sees under a form field (or in the banner),
so they are pinned here.
"""

from decimal import Decimal

import pytest

from tests.factories import make_customer, make_product


def details(response):
    assert response.status_code == 422, response.text
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    return {d["field"]: d["message"] for d in body["details"]}, body["message"]


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({}, "name", "Name is required."),
        ({"name": ""}, "name", "Name is required."),
        ({"name": "x" * 151}, "name", "Name must be at most 150 characters."),
        (
            {"name": "X", "email": "no-at-sign"},
            "email",
            "Email: enter a valid email address, for example name@company.com.",
        ),
        ({"name": "X", "is_active": "maybe"}, "is_active", "Active must be true or false."),
        (
            {"name": "X", "id": 5},
            "id",
            "Id cannot be sent here; it is not an accepted field (the system sets it itself).",
        ),
    ],
)
def test_customer_messages(admin_client, migrated_database, payload, field, message):
    fields, _ = details(admin_client.post("/api/customers", json=payload))
    assert fields[field] == message


@pytest.mark.parametrize(
    ("changes", "field", "message"),
    [
        ({"price": "abc"}, "price", "Enter a plain number such as 1500 or 1500.50."),
        ({"price": "-5"}, "price", "Price must be 0 or more."),
        ({"price": "10.999"}, "price", "Price can have at most 2 decimal places."),
        (
            {"stock_quantity": 2.5},
            "stock_quantity",
            "Stock quantity must be a whole number (for example 5).",
        ),
        ({"stock_quantity": -1}, "stock_quantity", "Stock quantity must be 0 or more."),
        (
            {"code": "BAD CODE"},
            "code",
            "Code must be 1-30 characters: letters, digits and dashes only.",
        ),
    ],
)
def test_product_messages(admin_client, migrated_database, changes, field, message):
    body = {"code": "P-1", "name": "X", "category": "Y", "price": "1", **changes}
    fields, _ = details(admin_client.post("/api/products", json=body))
    assert fields[field] == message


@pytest.fixture
def ids(db_session):
    customer = make_customer(db_session)
    product = make_product(db_session, price=Decimal("10"))
    db_session.commit()
    return customer.id, product.id


def test_order_item_messages_name_the_row(sales_client, ids):
    customer_id, product_id = ids
    body = {
        "customer_id": customer_id,
        "discount_percent": "25",
        "items": [
            {"product_id": product_id, "quantity": 1},
            {"product_id": product_id + 1, "quantity": 0},
        ],
    }
    fields, summary = details(sales_client.post("/api/orders", json=body))
    assert fields["items.1.quantity"] == "Item 2 quantity must be 1 or more."
    assert fields["discount_percent"] == "Discount % must be 20 or less."
    assert summary.startswith("2 things need fixing:")


def test_bad_date_message(sales_client, ids):
    customer_id, product_id = ids
    body = {
        "customer_id": customer_id,
        "order_date": "2026-13-01",
        "items": [{"product_id": product_id, "quantity": 1}],
    }
    fields, _ = details(sales_client.post("/api/orders", json=body))
    assert (
        fields["order_date"]
        == "Order date must be a valid date in the format YYYY-MM-DD (for example 2026-11-08)."
    )


def test_query_parameter_messages(admin_client, migrated_database):
    fields, _ = details(admin_client.get("/api/products?page=0&page_size=500"))
    assert fields["page"] == "Page must be 1 or more."
    assert fields["page_size"] == "Page size must be 100 or less."
    fields, _ = details(admin_client.get("/api/reports/low-stock"))
    assert fields["threshold"] == "Threshold is required."


def test_invalid_json_message(admin_client, migrated_database):
    response = admin_client.post(
        "/api/customers", content=b"{oops", headers={"Content-Type": "application/json"}
    )
    _, summary = details(response)
    assert summary == "The request could not be read: it is not valid JSON."


def test_single_problem_summary_is_the_message_itself(admin_client, migrated_database):
    _, summary = details(admin_client.post("/api/customers", json={"name": ""}))
    assert summary == "Name is required."


def test_unknown_page_message_is_plain(admin_client, migrated_database):
    response = admin_client.get("/api/nothing-here")
    assert (
        response.json()["error"]["message"]
        == "This page or record does not exist. Check the address and try again."
    )
