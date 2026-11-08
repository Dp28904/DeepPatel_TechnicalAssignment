"""Sales orders through the API: create, edit, confirm, cancel, ownership.

Tests named ``test_required_*`` map one-to-one to the scenarios listed in Part 12 of
the assignment (see docs/TESTING.md).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.enums import MovementType
from app.models import Product, SalesOrder, StockMovement
from tests.factories import make_customer, make_product, see_latest

URL = "/api/orders"


# --- Fixtures -----------------------------------------------------------------
@pytest.fixture
def catalog(db_session):
    """An active customer plus Keyboard (1500, stock 10) and Mouse (500, stock 10)."""
    data = {
        "customer": make_customer(db_session, name="Acme Traders"),
        "inactive_customer": make_customer(db_session, name="Gone Ltd", is_active=False),
        "keyboard": make_product(
            db_session, code="KB", name="Keyboard", price=Decimal("1500.00"), stock_quantity=10
        ),
        "mouse": make_product(
            db_session, code="MS", name="Mouse", price=Decimal("500.00"), stock_quantity=10
        ),
        "old": make_product(db_session, code="OLD", name="Old", is_active=False),
    }
    db_session.commit()
    return data


def order_body(catalog, items=None, discount="10", **extra):
    if items is None:
        items = [(catalog["keyboard"], 2), (catalog["mouse"], 3)]
    return {
        "customer_id": catalog["customer"].id,
        "discount_percent": discount,
        "items": [{"product_id": p.id, "quantity": q} for p, q in items],
        **extra,
    }


def create(client, catalog, **kwargs):
    response = client.post(URL, json=order_body(catalog, **kwargs))
    assert response.status_code == 201, response.text
    return response.json()


def stock(db, product) -> int:
    see_latest(db)
    return db.get(Product, product.id).stock_quantity


def movement_count(db, order_id=None) -> int:
    see_latest(db)
    query = select(func.count()).select_from(StockMovement)
    if order_id is not None:
        query = query.where(StockMovement.order_id == order_id)
    return db.scalar(query)


# --- Required scenario 1: multi-item order with discount ----------------------
def test_required_1_multi_item_order_with_discount_has_correct_totals(sales_client, catalog):
    order = create(sales_client, catalog)
    assert [(i["product_code"], i["quantity"], i["rate"], i["amount"]) for i in order["items"]] == [
        ("KB", 2, "1500.00", "3000.00"),
        ("MS", 3, "500.00", "1500.00"),
    ]
    assert order["subtotal"] == "4500.00"
    assert order["discount_percent"] == "10.00"
    assert order["discount_amount"] == "450.00"
    assert order["grand_total"] == "4050.00"
    assert order["status"] == "DRAFT"


def test_draft_order_does_not_touch_stock(sales_client, catalog, db_session):
    create(sales_client, catalog)
    assert stock(db_session, catalog["keyboard"]) == 10
    assert movement_count(db_session) == 0


def test_order_number_is_generated_and_unique(sales_client, catalog):
    first, second = create(sales_client, catalog), create(sales_client, catalog)
    today = date.today().strftime("%Y%m%d")
    assert first["order_number"] == f"SO-{today}-{first['id']:06d}"
    assert first["order_number"] != second["order_number"]


def test_owner_comes_from_session(sales_client, catalog, sales_user):
    assert create(sales_client, catalog)["created_by"]["id"] == sales_user.id


# --- Required scenarios 2 and 3: invalid quantity and discount ----------------
@pytest.mark.parametrize("quantity", [0, -1])
def test_required_2_zero_or_negative_quantity_is_rejected(sales_client, catalog, quantity):
    response = sales_client.post(
        URL, json=order_body(catalog, items=[(catalog["mouse"], quantity)])
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "items.0.quantity"


@pytest.mark.parametrize("discount", ["-1", "-0.01", "20.01", "21", "50"])
def test_required_3_discount_outside_0_to_20_is_rejected(sales_client, catalog, discount):
    response = sales_client.post(URL, json=order_body(catalog, discount=discount))
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "discount_percent"


@pytest.mark.parametrize("discount", ["0", "20", "12.5"])
def test_discount_boundaries_are_accepted(sales_client, catalog, discount):
    assert sales_client.post(URL, json=order_body(catalog, discount=discount)).status_code == 201


# --- Other validation ------------------------------------------------------
@pytest.mark.parametrize(
    "field", ["rate", "grand_total", "subtotal", "status", "created_by", "order_number"]
)
def test_server_controlled_fields_cannot_be_sent(sales_client, catalog, field):
    response = sales_client.post(URL, json=order_body(catalog, **{field: "1"}))
    assert response.status_code == 422


def test_item_rate_cannot_be_sent(sales_client, catalog):
    body = order_body(catalog)
    body["items"][0]["rate"] = "1.00"
    assert sales_client.post(URL, json=body).status_code == 422


def test_order_needs_at_least_one_item(sales_client, catalog):
    response = sales_client.post(URL, json=order_body(catalog, items=[]))
    assert response.status_code == 422
    assert "at least one item" in response.json()["error"]["details"][0]["message"]


def test_duplicate_product_in_one_order_is_rejected(sales_client, catalog):
    items = [(catalog["mouse"], 1), (catalog["mouse"], 2)]
    response = sales_client.post(URL, json=order_body(catalog, items=items))
    assert response.status_code == 422
    assert "more than once" in response.json()["error"]["details"][0]["message"]


@pytest.mark.parametrize("quantity", [1.5, "2", True])
def test_non_whole_quantity_is_rejected(sales_client, catalog, quantity):
    body = order_body(catalog)
    body["items"][0]["quantity"] = quantity
    assert sales_client.post(URL, json=body).status_code == 422


def test_inactive_customer_is_rejected(sales_client, catalog):
    body = order_body(catalog, customer_id=None)
    body["customer_id"] = catalog["inactive_customer"].id
    response = sales_client.post(URL, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "customer_id"


def test_inactive_or_missing_product_is_rejected(sales_client, catalog):
    body = order_body(catalog, items=[(catalog["mouse"], 1), (catalog["old"], 1)])
    body["items"].append({"product_id": 999999, "quantity": 1})
    response = sales_client.post(URL, json=body)
    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert fields == ["items.1.product_id", "items.2.product_id"]


def test_future_order_date_is_rejected(sales_client, catalog):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = sales_client.post(URL, json=order_body(catalog, order_date=tomorrow))
    assert response.status_code == 422


def test_past_order_date_is_kept(sales_client, catalog):
    order = create(sales_client, catalog, order_date="2026-01-15")
    assert order["order_date"] == "2026-01-15"


# --- Rate snapshot and Draft editing --------------------------------------------
def test_rate_is_snapshotted_and_survives_price_change(admin_client, sales_client, catalog):
    order = create(sales_client, catalog)
    keyboard = catalog["keyboard"]
    admin_client.put(
        f"/api/products/{keyboard.id}",
        json={"code": "KB", "name": "Keyboard", "category": "Accessories", "price": "9999.00"},
    )
    again = sales_client.get(f"{URL}/{order['id']}").json()
    assert again["items"][0]["rate"] == "1500.00"
    assert again["grand_total"] == "4050.00"


def test_edit_draft_changes_quantity_removes_and_adds_rows(admin_client, sales_client, catalog):
    order = create(sales_client, catalog)  # KB x2, MS x3
    # The keyboard price changes after the order was created.
    admin_client.put(
        f"/api/products/{catalog['keyboard'].id}",
        json={"code": "KB", "name": "Keyboard", "category": "Accessories", "price": "2000.00"},
    )
    extra = make_product_via_api(admin_client, "HUB", "250.00")

    body = order_body(catalog, items=[(catalog["keyboard"], 1)], discount="0")
    body["items"].append({"product_id": extra["id"], "quantity": 4})
    response = sales_client.put(f"{URL}/{order['id']}", json=body)
    assert response.status_code == 200
    updated = response.json()
    rows = [(i["product_code"], i["quantity"], i["rate"]) for i in updated["items"]]
    # Keyboard keeps its original rate; the mouse row is gone; the new hub uses today's price.
    assert rows == [("KB", 1, "1500.00"), ("HUB", 4, "250.00")]
    assert updated["subtotal"] == "2500.00"
    assert updated["grand_total"] == "2500.00"


def make_product_via_api(admin_client, code, price):
    response = admin_client.post(
        "/api/products",
        json={"code": code, "name": code, "category": "Misc", "price": price, "stock_quantity": 0},
    )
    assert response.status_code == 201
    return response.json()


# --- Required scenario 4: confirmation with sufficient stock ------------------
def test_required_4_confirm_with_sufficient_stock_deducts_stock(
    sales_client, catalog, db_session, sales_user
):
    order = create(sales_client, catalog)
    response = sales_client.post(f"{URL}/{order['id']}/confirm")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CONFIRMED"
    assert body["confirmed_at"] is not None
    assert body["can_edit"] is False

    assert stock(db_session, catalog["keyboard"]) == 8
    assert stock(db_session, catalog["mouse"]) == 7
    movements = db_session.scalars(
        select(StockMovement).where(StockMovement.order_id == order["id"])
    ).all()
    assert sorted((m.movement_type, m.quantity_change) for m in movements) == [
        (MovementType.ORDER_CONFIRM, -3),
        (MovementType.ORDER_CONFIRM, -2),
    ]
    assert {m.created_by for m in movements} == {sales_user.id}


def test_confirm_uses_exactly_all_available_stock(sales_client, catalog, db_session):
    order = create(sales_client, catalog, items=[(catalog["mouse"], 10)])
    assert sales_client.post(f"{URL}/{order['id']}/confirm").status_code == 200
    assert stock(db_session, catalog["mouse"]) == 0


# --- Required scenario 5: one item short -> nothing changes -------------------
def test_required_5_confirm_with_one_insufficient_item_changes_nothing(
    sales_client, catalog, db_session
):
    # Keyboard is fine (2 of 10) but Mouse is short (11 of 10).
    order = create(sales_client, catalog, items=[(catalog["keyboard"], 2), (catalog["mouse"], 11)])
    response = sales_client.post(f"{URL}/{order['id']}/confirm")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "insufficient_stock"
    assert error["details"] == [
        {
            "product_id": catalog["mouse"].id,
            "product_code": "MS",
            "product_name": "Mouse",
            "requested": 11,
            "available": 10,
        }
    ]
    # No stock change for ANY product (not even the keyboard), no movements, still Draft.
    assert stock(db_session, catalog["keyboard"]) == 10
    assert stock(db_session, catalog["mouse"]) == 10
    assert movement_count(db_session) == 0
    assert sales_client.get(f"{URL}/{order['id']}").json()["status"] == "DRAFT"


# --- Required scenario 6: repeated confirmation -------------------------------
def test_required_6_repeated_confirmation_does_not_deduct_again(sales_client, catalog, db_session):
    order = create(sales_client, catalog)
    assert sales_client.post(f"{URL}/{order['id']}/confirm").status_code == 200
    second = sales_client.post(f"{URL}/{order['id']}/confirm")

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "invalid_order_status"
    assert stock(db_session, catalog["keyboard"]) == 8  # deducted once only
    assert stock(db_session, catalog["mouse"]) == 7
    assert movement_count(db_session, order["id"]) == 2


# --- Required scenario 7: cancel a confirmed order ------------------------------
def test_required_7_cancelling_confirmed_order_restores_stock_once(
    sales_client, catalog, db_session
):
    order = create(sales_client, catalog)
    sales_client.post(f"{URL}/{order['id']}/confirm")
    assert stock(db_session, catalog["keyboard"]) == 8

    response = sales_client.post(f"{URL}/{order['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert stock(db_session, catalog["keyboard"]) == 10
    assert stock(db_session, catalog["mouse"]) == 10

    again = sales_client.post(f"{URL}/{order['id']}/cancel")
    assert again.status_code == 409
    assert stock(db_session, catalog["keyboard"]) == 10  # not restored twice
    movement_types = db_session.scalars(
        select(StockMovement.movement_type).where(StockMovement.order_id == order["id"])
    ).all()
    assert sorted(movement_types) == sorted(
        [MovementType.ORDER_CONFIRM] * 2 + [MovementType.ORDER_CANCEL] * 2
    )


def test_cancelling_draft_does_not_touch_stock(sales_client, catalog, db_session):
    order = create(sales_client, catalog)
    assert sales_client.post(f"{URL}/{order['id']}/cancel").json()["status"] == "CANCELLED"
    assert stock(db_session, catalog["keyboard"]) == 10
    assert movement_count(db_session) == 0


def test_cancelled_order_cannot_be_confirmed(sales_client, catalog, db_session):
    order = create(sales_client, catalog)
    sales_client.post(f"{URL}/{order['id']}/cancel")
    assert sales_client.post(f"{URL}/{order['id']}/confirm").status_code == 409
    assert stock(db_session, catalog["keyboard"]) == 10


@pytest.mark.parametrize("action", ["confirm", "cancel"])
def test_confirmed_and_cancelled_orders_are_read_only(sales_client, catalog, action):
    order = create(sales_client, catalog)
    sales_client.post(f"{URL}/{order['id']}/{action}")
    response = sales_client.put(f"{URL}/{order['id']}", json=order_body(catalog, discount="5"))
    assert response.status_code == 409
    assert "only draft orders can be edited" in response.json()["error"]["message"]


def test_confirm_rejects_product_deactivated_after_drafting(
    admin_client, sales_client, catalog, db_session
):
    order = create(sales_client, catalog)
    admin_client.put(
        f"/api/products/{catalog['mouse'].id}",
        json={
            "code": "MS",
            "name": "Mouse",
            "category": "Accessories",
            "price": "500",
            "is_active": False,
        },
    )
    response = sales_client.post(f"{URL}/{order['id']}/confirm")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inactive_products"
    assert stock(db_session, catalog["keyboard"]) == 10


# --- Required scenario 8: ownership --------------------------------------------
def test_required_8_sales_user_cannot_access_another_users_order(
    sales_client, other_sales_client, catalog, db_session
):
    order = create(sales_client, catalog)
    order_url = f"{URL}/{order['id']}"

    # Every way of reaching the order by changing the id in the URL is denied.
    assert other_sales_client.get(order_url).status_code == 404
    assert other_sales_client.put(order_url, json=order_body(catalog)).status_code == 404
    assert other_sales_client.post(f"{order_url}/confirm").status_code == 404
    assert other_sales_client.post(f"{order_url}/cancel").status_code == 404
    assert other_sales_client.get(order_url).json()["error"]["message"] == (
        f"Order {order['id']} was not found."  # same message as a truly missing order
    )
    # Nothing happened to the order or the stock.
    assert sales_client.get(order_url).json()["status"] == "DRAFT"
    assert stock(db_session, catalog["keyboard"]) == 10


def test_order_list_shows_sales_users_only_their_own(
    sales_client, other_sales_client, admin_client, catalog
):
    mine = create(sales_client, catalog)
    theirs = create(other_sales_client, catalog)
    assert [o["id"] for o in sales_client.get(URL).json()["items"]] == [mine["id"]]
    assert [o["id"] for o in other_sales_client.get(URL).json()["items"]] == [theirs["id"]]
    assert {o["id"] for o in admin_client.get(URL).json()["items"]} == {mine["id"], theirs["id"]}


def test_admin_can_manage_any_users_order(sales_client, admin_client, catalog, db_session):
    order = create(sales_client, catalog)
    assert admin_client.get(f"{URL}/{order['id']}").status_code == 200
    assert admin_client.post(f"{URL}/{order['id']}/confirm").status_code == 200
    assert stock(db_session, catalog["keyboard"]) == 8


def test_missing_order_returns_404(admin_client, migrated_database):
    assert admin_client.get(f"{URL}/999999").status_code == 404
    assert admin_client.post(f"{URL}/999999/confirm").status_code == 404


def test_orders_require_login(client, migrated_database):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401


# --- List filters -------------------------------------------------------------
def test_list_filters_by_status_search_and_date(admin_client, catalog):
    a = create(admin_client, catalog, order_date="2026-03-10")
    b = create(admin_client, catalog, order_date="2026-04-20")
    admin_client.post(f"{URL}/{b['id']}/confirm")

    def ids(**params):
        return [o["id"] for o in admin_client.get(URL, params=params).json()["items"]]

    assert ids(status="CONFIRMED") == [b["id"]]
    assert ids(status="DRAFT") == [a["id"]]
    assert ids(**{"from": "2026-04-01", "to": "2026-04-30"}) == [b["id"]]
    assert ids(search=a["order_number"]) == [a["id"]]
    assert ids(search="acme") == [b["id"], a["id"]]  # newest order date first
    bad_range = admin_client.get(URL, params={"from": "2026-05-01", "to": "2026-04-01"})
    assert bad_range.status_code == 422


def test_list_summary_shape(sales_client, catalog):
    create(sales_client, catalog)
    [summary] = sales_client.get(URL).json()["items"]
    assert summary["customer_name"] == "Acme Traders"
    assert summary["item_count"] == 2
    assert summary["grand_total"] == "4050.00"
    assert summary["created_by_name"] == "Test Sales"


def test_stored_order_matches_response(sales_client, catalog, db_session):
    order = create(sales_client, catalog)
    see_latest(db_session)
    stored = db_session.get(SalesOrder, order["id"])
    assert stored.grand_total == Decimal("4050.00")
    assert stored.discount_amount == Decimal("450.00")
