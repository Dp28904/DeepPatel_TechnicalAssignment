"""Products API: CRUD, unique codes, validation, visibility, safe delete, stock adjustment."""

import threading
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.enums import MovementType
from app.models import Product, StockMovement
from tests.conftest import login_client
from tests.factories import make_customer, make_movement, make_order, make_product, see_latest

URL = "/api/products"

VALID = {
    "code": "prd-001",
    "name": "Keyboard",
    "category": "Accessories",
    "price": "1500.00",
    "stock_quantity": 20,
}


def movements_for(db, product_id: int) -> list[StockMovement]:
    see_latest(db)
    return list(
        db.scalars(
            select(StockMovement)
            .where(StockMovement.product_id == product_id)
            .order_by(StockMovement.id)
        )
    )


def assert_ledger_matches_stock(db, product_id: int) -> None:
    """Invariant: the sum of all movements equals the product's stock."""
    see_latest(db)
    total = db.scalar(
        select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(
            StockMovement.product_id == product_id
        )
    )
    assert total == db.get(Product, product_id).stock_quantity


@pytest.fixture
def products(db_session):
    rows = [
        make_product(db_session, code="KB-1", name="Keyboard", category="Accessories"),
        make_product(db_session, code="MS-1", name="Mouse", category="Accessories"),
        make_product(db_session, code="MN-1", name="Monitor", category="Displays"),
        make_product(
            db_session, code="OLD-1", name="Old Cable", category="Cables", is_active=False
        ),
    ]
    db_session.commit()
    return rows


# --- Create ---------------------------------------------------------------
def test_create_product_uppercases_code_and_records_opening_stock(
    admin_client, db_session, admin_user
):
    response = admin_client.post(URL, json=VALID)
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "PRD-001"
    assert body["price"] == "1500.00"  # money is serialised as an exact string
    assert body["stock_quantity"] == 20

    [movement] = movements_for(db_session, body["id"])
    assert movement.movement_type is MovementType.OPENING
    assert movement.quantity_change == 20
    assert movement.created_by == admin_user.id
    assert movement.reason == "Opening stock"


def test_create_product_with_zero_stock_records_no_movement(admin_client, db_session):
    response = admin_client.post(URL, json={**VALID, "stock_quantity": 0})
    assert response.status_code == 201
    assert movements_for(db_session, response.json()["id"]) == []


def test_duplicate_code_is_rejected_case_insensitively(admin_client, products):
    response = admin_client.post(URL, json={**VALID, "code": "kb-1"})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "duplicate_product_code"
    assert error["details"][0]["field"] == "code"


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"price": "-1"}, "price"),
        ({"price": "10.555"}, "price"),
        ({"price": "abc"}, "price"),
        ({"stock_quantity": -5}, "stock_quantity"),
        ({"stock_quantity": 2.5}, "stock_quantity"),
        ({"stock_quantity": "5"}, "stock_quantity"),
        ({"code": "BAD CODE!"}, "code"),
        ({"name": ""}, "name"),
        ({"category": ""}, "category"),
    ],
)
def test_invalid_product_is_rejected(admin_client, migrated_database, changes, field):
    response = admin_client.post(URL, json={**VALID, **changes})
    assert response.status_code == 422
    assert field in {d["field"] for d in response.json()["error"]["details"]}


# --- Update -----------------------------------------------------------------
def test_update_product_details(admin_client, products):
    keyboard = products[0]
    payload = {"code": "KB-1", "name": "Mech Keyboard", "category": "Accessories", "price": "2500"}
    response = admin_client.put(f"{URL}/{keyboard.id}", json=payload)
    assert response.status_code == 200
    assert response.json()["name"] == "Mech Keyboard"
    assert response.json()["price"] == "2500.00"


def test_update_cannot_change_stock_directly(admin_client, products, db_session):
    keyboard = products[0]
    payload = {
        "code": "KB-1",
        "name": "Keyboard",
        "category": "Accessories",
        "price": "100",
        "stock_quantity": 999,
    }
    response = admin_client.put(f"{URL}/{keyboard.id}", json=payload)
    assert response.status_code == 422
    assert "Adjust stock" in str(response.json()["error"]["details"])
    see_latest(db_session)
    assert db_session.get(Product, keyboard.id).stock_quantity == 10


def test_update_to_another_products_code_is_rejected(admin_client, products):
    keyboard = products[0]
    payload = {"code": "ms-1", "name": "Keyboard", "category": "Accessories", "price": "100"}
    assert admin_client.put(f"{URL}/{keyboard.id}", json=payload).status_code == 409


# --- List, search, filters, visibility -------------------------------------
def test_list_defaults_to_active_products(sales_client, products):
    codes = [p["code"] for p in sales_client.get(URL).json()["items"]]
    assert codes == ["KB-1", "MN-1", "MS-1"]


def test_search_by_code_or_name(admin_client, products):
    assert [p["code"] for p in admin_client.get(URL, params={"search": "mn-"}).json()["items"]] == [
        "MN-1"
    ]
    assert [
        p["code"] for p in admin_client.get(URL, params={"search": "mouse"}).json()["items"]
    ] == ["MS-1"]


def test_filter_by_category_and_status(admin_client, products):
    accessories = admin_client.get(URL, params={"category": "Accessories"}).json()["items"]
    assert {p["code"] for p in accessories} == {"KB-1", "MS-1"}
    inactive = admin_client.get(URL, params={"status": "inactive"}).json()["items"]
    assert [p["code"] for p in inactive] == ["OLD-1"]


def test_categories_respect_visibility(admin_client, sales_client, products):
    assert admin_client.get(f"{URL}/categories").json() == ["Accessories", "Cables", "Displays"]
    assert sales_client.get(f"{URL}/categories").json() == ["Accessories", "Displays"]


def test_sales_user_cannot_see_inactive_products(sales_client, products):
    old_cable = products[3]
    assert sales_client.get(f"{URL}/{old_cable.id}").status_code == 404
    items = sales_client.get(URL, params={"status": "all"}).json()["items"]
    assert "OLD-1" not in [p["code"] for p in items]


def test_sales_user_cannot_modify_products(sales_client, products):
    keyboard = products[0]
    assert sales_client.post(URL, json=VALID).status_code == 403
    assert sales_client.put(f"{URL}/{keyboard.id}", json=VALID).status_code == 403
    assert sales_client.delete(f"{URL}/{keyboard.id}").status_code == 403
    adjust = {"adjustment_type": "INCREASE", "quantity": 1, "reason": "test"}
    assert sales_client.post(f"{URL}/{keyboard.id}/adjust-stock", json=adjust).status_code == 403


# --- Safe delete -------------------------------------------------------------
def test_unreferenced_product_can_be_deleted(admin_client, products, db_session):
    keyboard_id = products[0].id
    assert admin_client.delete(f"{URL}/{keyboard_id}").status_code == 204
    see_latest(db_session)
    assert db_session.get(Product, keyboard_id) is None


def test_product_with_stock_movements_cannot_be_deleted(
    admin_client, products, db_session, admin_user
):
    keyboard = products[0]
    make_movement(db_session, product=keyboard, user=admin_user, change=10)
    db_session.commit()
    response = admin_client.delete(f"{URL}/{keyboard.id}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "product_in_use"
    assert "stock movement" in response.json()["error"]["message"]


def test_product_on_an_order_cannot_be_deleted(admin_client, products, db_session, admin_user):
    keyboard = products[0]
    make_order(
        db_session,
        customer=make_customer(db_session),
        created_by=admin_user,
        items=[(keyboard, 1)],
    )
    db_session.commit()
    response = admin_client.delete(f"{URL}/{keyboard.id}")
    assert response.status_code == 409
    assert "order item" in response.json()["error"]["message"]


# --- Stock adjustment --------------------------------------------------------
@pytest.fixture
def stocked_product(admin_client, db_session):
    """A product created through the API, so its opening stock is in the ledger."""
    response = admin_client.post(URL, json={**VALID, "stock_quantity": 10})
    return db_session.get(Product, response.json()["id"])


def adjust(test_client, product_id, kind, quantity, reason="Stock count correction"):
    return test_client.post(
        f"{URL}/{product_id}/adjust-stock",
        json={"adjustment_type": kind, "quantity": quantity, "reason": reason},
    )


def test_increase_stock_records_adjustment_in(admin_client, stocked_product, db_session):
    response = adjust(admin_client, stocked_product.id, "INCREASE", 5, "Supplier delivery")
    assert response.status_code == 200
    body = response.json()
    assert body["product"]["stock_quantity"] == 15
    assert body["movement"]["movement_type"] == "ADJUSTMENT_IN"
    assert body["movement"]["quantity_change"] == 5
    assert body["movement"]["reason"] == "Supplier delivery"
    assert_ledger_matches_stock(db_session, stocked_product.id)


def test_decrease_stock_records_negative_adjustment_out(admin_client, stocked_product, db_session):
    response = adjust(admin_client, stocked_product.id, "DECREASE", 4, "Damaged")
    assert response.status_code == 200
    assert response.json()["product"]["stock_quantity"] == 6
    assert response.json()["movement"]["quantity_change"] == -4
    assert_ledger_matches_stock(db_session, stocked_product.id)


def test_decrease_to_exactly_zero_is_allowed(admin_client, stocked_product):
    response = adjust(admin_client, stocked_product.id, "DECREASE", 10)
    assert response.status_code == 200
    assert response.json()["product"]["stock_quantity"] == 0


def test_decrease_below_zero_is_rejected_without_changes(admin_client, stocked_product, db_session):
    response = adjust(admin_client, stocked_product.id, "DECREASE", 11)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"
    see_latest(db_session)
    assert db_session.get(Product, stocked_product.id).stock_quantity == 10
    assert len(movements_for(db_session, stocked_product.id)) == 1  # only the opening stock


@pytest.mark.parametrize(
    "payload",
    [
        {"adjustment_type": "INCREASE", "quantity": 5},  # reason missing
        {"adjustment_type": "INCREASE", "quantity": 5, "reason": "   "},  # blank reason
        {"adjustment_type": "INCREASE", "quantity": 0, "reason": "valid reason"},
        {"adjustment_type": "INCREASE", "quantity": -3, "reason": "valid reason"},
        {"adjustment_type": "INCREASE", "quantity": 1.5, "reason": "valid reason"},
        {"adjustment_type": "SET", "quantity": 1, "reason": "valid reason"},
    ],
)
def test_invalid_adjustment_is_rejected(admin_client, stocked_product, db_session, payload):
    response = admin_client.post(f"{URL}/{stocked_product.id}/adjust-stock", json=payload)
    assert response.status_code == 422
    assert len(movements_for(db_session, stocked_product.id)) == 1


def test_adjusting_missing_product_returns_404(admin_client, migrated_database):
    assert adjust(admin_client, 999999, "INCREASE", 1).status_code == 404


def test_ledger_stays_consistent_over_many_adjustments(admin_client, stocked_product, db_session):
    for kind, quantity in [("INCREASE", 7), ("DECREASE", 3), ("DECREASE", 14), ("INCREASE", 1)]:
        assert adjust(admin_client, stocked_product.id, kind, quantity).status_code == 200
    see_latest(db_session)
    assert db_session.get(Product, stocked_product.id).stock_quantity == 1
    assert_ledger_matches_stock(db_session, stocked_product.id)


def test_price_is_exact_decimal_end_to_end(admin_client, db_session):
    response = admin_client.post(URL, json={**VALID, "price": "0.10", "stock_quantity": 0})
    product = db_session.get(Product, response.json()["id"])
    assert product.price == Decimal("0.10")


def test_concurrent_decreases_cannot_drive_stock_negative(
    app, admin_user, stocked_product, db_session
):
    """Two admins remove 6 units each from a stock of 10 at the same moment.

    The product row lock (SELECT ... FOR UPDATE) makes the second request wait and
    then see the updated stock, so exactly one succeeds and stock never goes below 0.
    """
    clients = [login_client(app, admin_user.email) for _ in range(2)]
    barrier = threading.Barrier(2)
    statuses = []

    def worker(test_client):
        barrier.wait()  # release both requests together
        statuses.append(adjust(test_client, stocked_product.id, "DECREASE", 6).status_code)

    threads = [threading.Thread(target=worker, args=(c,)) for c in clients]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(statuses) == [200, 409]
    see_latest(db_session)
    assert db_session.get(Product, stocked_product.id).stock_quantity == 4
    assert_ledger_matches_stock(db_session, stocked_product.id)
