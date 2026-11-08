"""API contract: rules that must hold for EVERY endpoint.

- Unauthenticated -> 401, wrong role -> 403, missing CSRF header -> 403.
- Malformed input never causes a 500; it gets 422 with the standard error body.
- Error bodies always look like {"error": {"code", "message", "details"}} and never
  leak tracebacks, SQL or password hashes.
- Success bodies have exactly the documented fields.
- Regression tests for bugs found by exploratory testing (see docs/TESTING.md).
"""

from decimal import Decimal

import pytest
from sqlalchemy.exc import OperationalError

from tests.factories import make_customer, make_product

HUGE = 10**20


# --- Fixture data ---------------------------------------------------------------
@pytest.fixture
def ids(db_session, sales_client, sales_user):
    customer = make_customer(db_session)
    product = make_product(db_session, price=Decimal("100.00"), stock_quantity=10)
    db_session.commit()
    order = sales_client.post(
        "/api/orders",
        json={"customer_id": customer.id, "items": [{"product_id": product.id, "quantity": 1}]},
    ).json()
    return {
        "customer": customer.id,
        "product": product.id,
        "order": order["id"],
        "sales_user": sales_user.id,
    }


def endpoints(ids):
    """Every API operation: (method, path, body, admin_only)."""
    c, p, o = ids["customer"], ids["product"], ids["order"]
    customer = {"name": "X"}
    product = {"code": "C-1", "name": "X", "category": "Y", "price": "1"}
    order = {"customer_id": c, "items": [{"product_id": p, "quantity": 1}]}
    adjust = {"adjustment_type": "INCREASE", "quantity": 1, "reason": "test"}
    return [
        ("GET", "/api/auth/me", None, False),
        ("GET", "/api/dashboard", None, False),
        ("POST", "/api/auth/password", {"current_password": "x", "new_password": "y" * 8}, False),
        ("GET", "/api/users", None, True),
        (
            "POST",
            "/api/users",
            {"name": "X", "email": "n@example.com", "role": "SALES", "password": "y" * 8},
            True,
        ),
        ("GET", f"/api/users/{ids['sales_user']}", None, True),
        ("PUT", f"/api/users/{ids['sales_user']}", {"name": "X", "email": "x@example.com"}, True),
        ("POST", f"/api/users/{ids['sales_user']}/password", {"new_password": "y" * 8}, True),
        ("GET", "/api/customers", None, False),
        ("POST", "/api/customers", customer, True),
        ("GET", f"/api/customers/{c}", None, False),
        ("PUT", f"/api/customers/{c}", customer, True),
        ("DELETE", f"/api/customers/{c}", None, True),
        ("GET", "/api/products", None, False),
        ("POST", "/api/products", product, True),
        ("GET", "/api/products/categories", None, False),
        ("GET", f"/api/products/{p}", None, False),
        ("PUT", f"/api/products/{p}", product, True),
        ("DELETE", f"/api/products/{p}", None, True),
        ("POST", f"/api/products/{p}/adjust-stock", adjust, True),
        ("GET", "/api/orders", None, False),
        ("POST", "/api/orders", order, False),
        ("GET", f"/api/orders/{o}", None, False),
        ("PUT", f"/api/orders/{o}", order, False),
        ("POST", f"/api/orders/{o}/confirm", None, False),
        ("POST", f"/api/orders/{o}/cancel", None, False),
        ("POST", "/api/imports/products", None, True),
        ("GET", "/api/reports/customer-sales", None, True),
        ("GET", "/api/reports/product-sales", None, True),
        ("GET", "/api/reports/low-stock?threshold=5", None, True),
        ("GET", "/api/reports/stock-movements", None, True),
    ]


def assert_error(response, status, code=None):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    if code:
        assert body["error"]["code"] == code
    for leak in ("Traceback", "sqlalchemy", "pymysql", "password_hash", "SELECT "):
        assert leak not in response.text
    return body["error"]


# --- Authentication, roles, CSRF on every endpoint ----------------------------------
def test_every_endpoint_requires_login(client, ids):
    for method, path, body, _ in endpoints(ids):
        response = client.request(method, path, json=body)
        assert_error(response, 401, "unauthenticated")


def test_admin_only_endpoints_reject_sales_users(sales_client, ids):
    for method, path, body, admin_only in endpoints(ids):
        if admin_only:
            assert_error(sales_client.request(method, path, json=body), 403, "forbidden")


def test_every_write_endpoint_requires_the_csrf_header(app, admin_user, ids):
    from tests.conftest import login_client

    logged_in = login_client(app, admin_user.email)
    del logged_in.headers["X-Requested-With"]
    for method, path, body, _ in endpoints(ids):
        if method != "GET":
            assert_error(logged_in.request(method, path, json=body), 403, "csrf_check_failed")


def test_wrong_csrf_header_value_is_rejected(app, admin_user):
    from tests.conftest import login_client

    logged_in = login_client(app, admin_user.email)
    response = logged_in.post(
        "/api/customers", json={"name": "X"}, headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert_error(response, 403, "csrf_check_failed")


# --- Malformed bodies never crash -----------------------------------------------------
MALFORMED = [
    ("invalid JSON", {"content": b"{bad", "headers": {"Content-Type": "application/json"}}),
    ("JSON array", {"json": [1, 2]}),
    ("JSON string", {"json": "hello"}),
    ("empty body", {"content": b""}),
    ("text/plain", {"content": b"x", "headers": {"Content-Type": "text/plain"}}),
    ("form encoded", {"data": {"name": "x"}}),
    ("empty object", {"json": {}}),
]


@pytest.mark.parametrize(("label", "kwargs"), MALFORMED, ids=[m[0] for m in MALFORMED])
def test_malformed_bodies_get_422_on_every_json_endpoint(admin_client, ids, label, kwargs):
    for method, path, body, _ in endpoints(ids):
        if body is not None:
            assert_error(admin_client.request(method, path, **kwargs), 422, "validation_error")


def test_validation_errors_name_the_field(admin_client):
    error = assert_error(admin_client.post("/api/customers", json={"name": ""}), 422)
    assert error["details"] == [{"field": "name", "message": "Name is required."}]


# --- Ids, paging and dates ------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/api/customers/{}", "/api/products/{}", "/api/orders/{}"])
@pytest.mark.parametrize(
    ("bad_id", "status"), [("0", 404), ("-1", 404), (str(HUGE), 404), ("abc", 422), ("1.5", 422)]
)
def test_bad_ids_get_404_or_422(admin_client, migrated_database, path, bad_id, status):
    assert_error(admin_client.get(path.format(bad_id)), status)


LIST_PATHS = ["/api/customers", "/api/products", "/api/orders", "/api/reports/stock-movements"]
BAD_PAGING = ["page=0", "page=abc", f"page={HUGE}", "page=100001", "page_size=0", "page_size=101"]
TOO_LONG_SEARCH = "search=" + "a" * 101


@pytest.mark.parametrize(
    ("path", "query"),
    [(path, query) for path in LIST_PATHS for query in BAD_PAGING]
    # Free-text search exists on the three master-data/order lists.
    + [(path, TOO_LONG_SEARCH) for path in LIST_PATHS[:3]],
)
def test_bad_paging_and_search_get_422(admin_client, migrated_database, path, query):
    assert_error(admin_client.get(f"{path}?{query}"), 422)


def test_page_beyond_the_end_is_empty_not_an_error(admin_client, migrated_database):
    body = admin_client.get("/api/products?page=100000").json()
    assert body["items"] == [] and body["page"] == 100000


@pytest.mark.parametrize(
    "path",
    [
        "/api/orders",
        "/api/reports/customer-sales",
        "/api/reports/product-sales",
        "/api/reports/stock-movements",
    ],
)
@pytest.mark.parametrize(
    "query", ["from=2026-13-01", "from=abc", "to=2026-02-30", "from=2026-12-01&to=2026-01-01"]
)
def test_bad_dates_get_422(admin_client, migrated_database, path, query):
    assert_error(admin_client.get(f"{path}?{query}"), 422)


# --- Success body shapes -------------------------------------------------------------------
PAGE_KEYS = {"items", "total", "page", "page_size", "pages"}
CUSTOMER_KEYS = {"id", "name", "email", "mobile", "city", "is_active", "created_at", "updated_at"}
PRODUCT_KEYS = {
    "id",
    "code",
    "name",
    "category",
    "price",
    "stock_quantity",
    "is_active",
    "created_at",
    "updated_at",
}
ORDER_KEYS = {
    "id",
    "order_number",
    "customer",
    "order_date",
    "status",
    "discount_percent",
    "subtotal",
    "discount_amount",
    "grand_total",
    "items",
    "created_by",
    "created_at",
    "updated_at",
    "confirmed_at",
    "cancelled_at",
    "can_edit",
    "can_confirm",
    "can_cancel",
}
ORDER_ITEM_KEYS = {
    "id",
    "product_id",
    "product_code",
    "product_name",
    "quantity",
    "rate",
    "amount",
    "available_stock",
}
ORDER_SUMMARY_KEYS = {
    "id",
    "order_number",
    "customer_name",
    "order_date",
    "status",
    "item_count",
    "grand_total",
    "created_by_name",
}
MOVEMENT_KEYS = {
    "id",
    "product_id",
    "product_code",
    "product_name",
    "movement_type",
    "quantity_change",
    "order_id",
    "order_number",
    "reason",
    "created_by",
    "created_by_name",
    "created_at",
}


def test_success_bodies_have_exactly_the_documented_fields(admin_client, ids):
    customers = admin_client.get("/api/customers").json()
    assert set(customers) == PAGE_KEYS and set(customers["items"][0]) == CUSTOMER_KEYS
    assert set(admin_client.get(f"/api/customers/{ids['customer']}").json()) == CUSTOMER_KEYS

    products = admin_client.get("/api/products").json()
    assert set(products) == PAGE_KEYS and set(products["items"][0]) == PRODUCT_KEYS

    order = admin_client.get(f"/api/orders/{ids['order']}").json()
    assert set(order) == ORDER_KEYS
    assert set(order["items"][0]) == ORDER_ITEM_KEYS
    assert set(order["customer"]) == {"id", "name"} and set(order["created_by"]) == {"id", "name"}
    assert set(admin_client.get("/api/orders").json()["items"][0]) == ORDER_SUMMARY_KEYS

    adjusted = admin_client.post(
        f"/api/products/{ids['product']}/adjust-stock",
        json={"adjustment_type": "INCREASE", "quantity": 1, "reason": "shape test"},
    ).json()
    assert set(adjusted) == {"product", "movement"} and set(adjusted["movement"]) == MOVEMENT_KEYS
    movements = admin_client.get("/api/reports/stock-movements").json()
    assert set(movements) == PAGE_KEYS and set(movements["items"][0]) == MOVEMENT_KEYS


def test_money_is_always_a_two_decimal_string(admin_client, ids):
    order = admin_client.get(f"/api/orders/{ids['order']}").json()
    for value in [
        order["subtotal"],
        order["discount_amount"],
        order["grand_total"],
        order["items"][0]["rate"],
    ]:
        assert isinstance(value, str)
        assert value.count(".") == 1 and len(value.split(".")[1]) == 2


def test_user_payloads_never_include_the_password_hash(admin_client, ids):
    for path in ["/api/auth/me", f"/api/orders/{ids['order']}", "/api/reports/stock-movements"]:
        assert "password" not in admin_client.get(path).text


# --- Server errors and lock conflicts ----------------------------------------------------
def test_unexpected_error_returns_generic_500_with_request_id(
    admin_client, monkeypatch, migrated_database
):
    from app.modules.customers import service

    def explode(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(service, "list_customers", explode)
    response = admin_client.get("/api/customers", headers={"X-Request-ID": "req-123"})
    error = assert_error(response, 500, "internal_error")
    assert "secret internal detail" not in response.text
    assert error["details"] == {"request_id": "req-123"}
    assert response.headers["X-Request-ID"] == "req-123"


def test_non_lock_database_error_returns_generic_500(admin_client, monkeypatch, ids):
    from app.modules.orders import service

    class ConnectionLost(Exception):
        args = (2013, "Lost connection to MySQL server")

    def lost(*args, **kwargs):
        raise OperationalError("SELECT ...", {}, ConnectionLost())

    monkeypatch.setattr(service, "get_order", lost)
    response = admin_client.get(f"/api/orders/{ids['order']}")
    assert_error(response, 500, "internal_error")
    assert "Lost connection" not in response.text


def test_database_lock_conflict_returns_409_retry(admin_client, monkeypatch, ids):
    from app.modules.orders import service

    class LockError(Exception):
        args = (1213, "Deadlock found")

    def deadlock(*args, **kwargs):
        raise OperationalError("UPDATE ...", {}, LockError())

    monkeypatch.setattr(service, "confirm_order", deadlock)
    error = assert_error(
        admin_client.post(f"/api/orders/{ids['order']}/confirm"), 409, "lock_conflict"
    )
    assert "try again" in error["message"]


# --- Regression tests: bugs found by exploratory testing ----------------------------------
def test_regression_huge_page_number_is_rejected_not_500(admin_client, migrated_database):
    assert_error(admin_client.get(f"/api/products?page={HUGE}"), 422)


def test_regression_latest_possible_date_does_not_overflow(admin_client, migrated_database):
    response = admin_client.get("/api/reports/stock-movements?to=9999-12-31")
    assert response.status_code == 200


def test_regression_stock_cannot_exceed_the_maximum(admin_client, ids):
    path = f"/api/products/{ids['product']}/adjust-stock"
    body = {"adjustment_type": "INCREASE", "quantity": 1_000_000_000, "reason": "too much"}
    error = assert_error(admin_client.post(path, json=body), 409, "stock_limit_exceeded")
    assert "maximum of 1,000,000,000" in error["message"]
    body["quantity"] = 999_999_990  # stock 10 + this = exactly the maximum
    assert admin_client.post(path, json=body).json()["product"]["stock_quantity"] == 1_000_000_000


def test_regression_order_total_too_large_is_rejected_not_500(admin_client, db_session, ids):
    expensive = make_product(db_session, code="LUXE", price=Decimal("9999999.99"))
    db_session.commit()
    body = {
        "customer_id": ids["customer"],
        "items": [{"product_id": expensive.id, "quantity": 1_000_000}],
    }
    error = assert_error(admin_client.post("/api/orders", json=body), 422, "validation_error")
    assert "too large" in error["message"]


@pytest.mark.parametrize("value", ["Bad\x00Name", "Tab\there", "New\nline", "Esc\x1b"])
def test_regression_control_characters_are_rejected(admin_client, migrated_database, value):
    error = assert_error(admin_client.post("/api/customers", json={"name": value}), 422)
    assert "control characters" in error["details"][0]["message"]


@pytest.mark.parametrize("price", ["1e2", "1_000", "0x10", "Infinity", "NaN", "1,000"])
def test_regression_money_must_be_a_plain_number(admin_client, migrated_database, price):
    body = {"code": "P-1", "name": "X", "category": "Y", "price": price}
    assert_error(admin_client.post("/api/products", json=body), 422)


@pytest.mark.parametrize(
    ("price", "stored"),
    [("1500", "1500.00"), (" 99.5 ", "99.50"), (12.25, "12.25"), ("-0", "0.00")],
)
def test_plain_numbers_and_json_numbers_are_accepted(
    admin_client, migrated_database, price, stored
):
    body = {"code": "P-1", "name": "X", "category": "Y", "price": price}
    assert admin_client.post("/api/products", json=body).json()["price"] == stored


def test_regression_ancient_order_date_is_rejected(sales_client, ids):
    body = {
        "customer_id": ids["customer"],
        "order_date": "0001-01-01",
        "items": [{"product_id": ids["product"], "quantity": 1}],
    }
    error = assert_error(sales_client.post("/api/orders", json=body), 422)
    assert "2000-01-01" in error["details"][0]["message"]


def test_regression_health_answers_head_requests(client, migrated_database):
    assert client.head("/api/health").status_code == 200


def test_injection_strings_are_stored_as_plain_text(admin_client, migrated_database):
    for name in ["' OR 1=1 --", "<script>alert(1)</script>", "Robert'); DROP TABLE customers;--"]:
        created = admin_client.post("/api/customers", json={"name": name}).json()
        assert admin_client.get(f"/api/customers/{created['id']}").json()["name"] == name
    assert admin_client.get("/api/customers?search=%27%20OR%201%3D1").json()["total"] == 1
