"""Reports API and the standalone SQL queries, against a small known dataset.

Dataset (built through the real order service, so totals and stock are realistic):

    Alpha  : 2026-09-10 CONFIRMED  KB x2 @1000 + MS x3 @100 = 2300, 10% -> 2070.00
             2026-10-05 CONFIRMED  MS x5 @100               =  500,  0% ->  500.00
    Beta   : 2026-10-20 CONFIRMED  KB x1 @1000              = 1000,  5% ->  950.00
             2026-10-21 DRAFT      KB x9                      (not a sale)
             2026-10-22 CANCELLED  MS x4 (confirmed, then cancelled: not a sale)
    Gamma  : no orders at all
    Delta  : 2026-10-01 DRAFT only (has "placed" an order, but no sales)
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.database import engine
from app.modules.orders import service as order_service
from app.modules.orders.schemas import OrderIn
from tests.factories import make_customer, make_product

URL = "/api/reports"
SQL_FILE = Path(__file__).resolve().parents[2] / "sql" / "queries.sql"


@pytest.fixture
def sales_data(db_session, admin_user):
    alpha = make_customer(db_session, name="Alpha")
    beta = make_customer(db_session, name="Beta")
    gamma = make_customer(db_session, name="Gamma")
    delta = make_customer(db_session, name="Delta")
    kb = make_product(
        db_session, code="KB", name="Keyboard", price=Decimal("1000"), stock_quantity=50
    )
    ms = make_product(db_session, code="MS", name="Mouse", price=Decimal("100"), stock_quantity=50)
    cable = make_product(db_session, code="CB", name="Cable", price=Decimal("10"), stock_quantity=3)
    old = make_product(
        db_session, code="OLD", name="Old", price=Decimal("5"), stock_quantity=1, is_active=False
    )
    db_session.commit()

    def order(customer, day, items, discount="0", action="confirm"):
        data = OrderIn(
            customer_id=customer.id,
            order_date=date.fromisoformat(day),
            discount_percent=discount,
            items=[{"product_id": p.id, "quantity": q} for p, q in items],
        )
        created = order_service.create_order(db_session, admin_user, data)
        if action in ("confirm", "confirm+cancel"):
            order_service.confirm_order(db_session, admin_user, created.id)
        if action in ("cancel", "confirm+cancel"):
            order_service.cancel_order(db_session, admin_user, created.id)
        return created

    order(alpha, "2026-09-10", [(kb, 2), (ms, 3)], discount="10")
    order(alpha, "2026-10-05", [(ms, 5)])
    order(beta, "2026-10-20", [(kb, 1)], discount="5")
    order(beta, "2026-10-21", [(kb, 9)], action="draft")
    order(beta, "2026-10-22", [(ms, 4)], action="confirm+cancel")
    order(delta, "2026-10-01", [(ms, 1)], action="draft")
    return {"customers": (alpha, beta, gamma, delta), "products": (kb, ms, cable, old)}


def by_name(rows, key="customer_name"):
    return {row[key]: row for row in rows}


# --- Customer Sales Summary -------------------------------------------------------
def test_customer_sales_all_time(admin_client, sales_data):
    body = admin_client.get(f"{URL}/customer-sales").json()
    rows = by_name(body["rows"])
    assert (rows["Alpha"]["confirmed_orders"], rows["Alpha"]["total_sales"]) == (2, "2570.00")
    assert (rows["Beta"]["confirmed_orders"], rows["Beta"]["total_sales"]) == (1, "950.00")
    # Customers without confirmed orders are listed with zero totals.
    assert (rows["Gamma"]["confirmed_orders"], rows["Gamma"]["total_sales"]) == (0, "0.00")
    assert (rows["Delta"]["confirmed_orders"], rows["Delta"]["total_sales"]) == (0, "0.00")
    assert [r["customer_name"] for r in body["rows"]] == ["Alpha", "Beta", "Delta", "Gamma"]
    assert body["totals"] == {
        "customers": 4,
        "customers_with_sales": 2,
        "confirmed_orders": 3,
        "total_sales": "3520.00",
    }


def test_customer_sales_does_not_double_count_multi_item_orders(admin_client, sales_data):
    # Alpha's September order has two item rows; it must count as ONE order.
    body = admin_client.get(
        f"{URL}/customer-sales", params={"from": "2026-09-01", "to": "2026-09-30"}
    )
    alpha = by_name(body.json()["rows"])["Alpha"]
    assert alpha["confirmed_orders"] == 1
    assert alpha["total_sales"] == "2070.00"  # not 2 x 2070


def test_customer_sales_date_range_keeps_customers_with_no_sales_in_range(admin_client, sales_data):
    body = admin_client.get(
        f"{URL}/customer-sales", params={"from": "2026-10-01", "to": "2026-10-31"}
    )
    rows = by_name(body.json()["rows"])
    assert len(rows) == 4
    assert (rows["Alpha"]["confirmed_orders"], rows["Alpha"]["total_sales"]) == (1, "500.00")
    assert rows["Beta"]["total_sales"] == "950.00"
    assert rows["Gamma"]["total_sales"] == "0.00"


def test_customer_sales_range_bounds_are_inclusive(admin_client, sales_data):
    body = admin_client.get(
        f"{URL}/customer-sales", params={"from": "2026-10-20", "to": "2026-10-20"}
    )
    assert by_name(body.json()["rows"])["Beta"]["confirmed_orders"] == 1


def test_customer_sales_rejects_reversed_range(admin_client, migrated_database):
    response = admin_client.get(
        f"{URL}/customer-sales", params={"from": "2026-10-31", "to": "2026-10-01"}
    )
    assert response.status_code == 422


# --- Product Sales Summary ----------------------------------------------------------
def test_product_sales_counts_confirmed_orders_only_before_discount(admin_client, sales_data):
    body = admin_client.get(f"{URL}/product-sales").json()
    rows = by_name(body["rows"], key="code")
    # KB: 2 + 1 confirmed (the draft for 9 is excluded); gross before discount.
    assert (rows["KB"]["quantity_sold"], rows["KB"]["order_count"], rows["KB"]["gross_value"]) == (
        3,
        2,
        "3000.00",
    )
    # MS: 3 + 5 confirmed (the cancelled 4 and the draft 1 are excluded).
    assert (rows["MS"]["quantity_sold"], rows["MS"]["gross_value"]) == (8, "800.00")
    # Products that never sold are listed with zeros.
    assert (rows["CB"]["quantity_sold"], rows["CB"]["gross_value"]) == (0, "0.00")
    assert body["totals"] == {"quantity_sold": 11, "gross_value": "3800.00"}


def test_product_sales_date_range(admin_client, sales_data):
    body = admin_client.get(
        f"{URL}/product-sales", params={"from": "2026-10-01", "to": "2026-10-31"}
    )
    rows = by_name(body.json()["rows"], key="code")
    assert rows["KB"]["quantity_sold"] == 1
    assert rows["MS"]["quantity_sold"] == 5


# --- Low stock --------------------------------------------------------------------------
def test_low_stock_uses_strictly_below_threshold(admin_client, sales_data):
    # After the confirmed orders: KB 50-3=47, MS 50-8=42, CB 3, OLD 1 (inactive).
    rows = admin_client.get(f"{URL}/low-stock", params={"threshold": 3}).json()["rows"]
    assert rows == []  # CB has exactly 3, which is not below 3
    rows = admin_client.get(f"{URL}/low-stock", params={"threshold": 4}).json()["rows"]
    assert [(r["code"], r["stock_quantity"], r["below_threshold_by"]) for r in rows] == [
        ("CB", 3, 1)
    ]


def test_low_stock_can_include_inactive_products(admin_client, sales_data):
    params = {"threshold": 10, "include_inactive": "true"}
    rows = admin_client.get(f"{URL}/low-stock", params=params).json()["rows"]
    assert [r["code"] for r in rows] == ["OLD", "CB"]


@pytest.mark.parametrize("params", [{}, {"threshold": -1}, {"threshold": "abc"}])
def test_low_stock_requires_a_valid_threshold(admin_client, migrated_database, params):
    assert admin_client.get(f"{URL}/low-stock", params=params).status_code == 422


# --- Stock movement history -----------------------------------------------------------
def test_stock_movement_history_lists_every_change_newest_first(admin_client, sales_data):
    body = admin_client.get(f"{URL}/stock-movements", params={"page_size": 100}).json()
    # Confirms: Alpha#1 (2 items) + Alpha#2 + Beta#1 + Beta#3 = 5; Beta#3 cancel = 1.
    assert body["total"] == 6
    newest = body["items"][0]
    assert newest["movement_type"] == "ORDER_CANCEL"
    assert newest["quantity_change"] == 4
    assert newest["order_number"].startswith("SO-")
    assert newest["reason"].endswith("cancelled")
    assert newest["created_by_name"] == "Test Admin"


def test_stock_movement_history_filters(admin_client, sales_data):
    kb = sales_data["products"][0]
    by_product = admin_client.get(f"{URL}/stock-movements", params={"product_id": kb.id}).json()
    assert {m["product_code"] for m in by_product["items"]} == {"KB"}
    assert sum(m["quantity_change"] for m in by_product["items"]) == -3

    cancels = admin_client.get(f"{URL}/stock-movements", params={"movement_type": "ORDER_CANCEL"})
    assert cancels.json()["total"] == 1

    today = date.today().isoformat()
    in_range = admin_client.get(f"{URL}/stock-movements", params={"from": today, "to": today})
    assert in_range.json()["total"] == 6
    long_ago = admin_client.get(
        f"{URL}/stock-movements", params={"from": "2000-01-01", "to": "2000-01-31"}
    )
    assert long_ago.json()["total"] == 0


def test_stock_movement_history_paginates(admin_client, sales_data):
    body = admin_client.get(f"{URL}/stock-movements", params={"page": 2, "page_size": 4}).json()
    assert (body["total"], body["pages"], len(body["items"])) == (6, 2, 2)


# --- Access -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path",
    ["/customer-sales", "/product-sales", "/low-stock?threshold=5", "/stock-movements"],
)
def test_reports_are_admin_only(sales_client, client, path):
    assert sales_client.get(f"{URL}{path}").status_code == 403
    assert client.get(f"{URL}{path}").status_code == 401


def test_reports_page_is_admin_only(admin_client, sales_client):
    assert admin_client.get("/reports").status_code == 200
    assert sales_client.get("/reports").status_code == 403
    assert 'href="/reports"' in admin_client.get("/").text
    assert 'href="/reports"' not in sales_client.get("/").text


# --- sql/queries.sql ----------------------------------------------------------------------
def run_sql_file() -> dict[str, list[tuple]]:
    """Run each '-- name:' block of sql/queries.sql on ONE connection (the @threshold
    user variable only exists within the connection that set it)."""
    blocks = SQL_FILE.read_text().split("-- name: ")[1:]
    results = {}
    with engine.connect() as connection:
        for block in blocks:
            name, sql = block.split("\n", 1)
            statement = sql.strip().rstrip(";")
            result = connection.execute(text(statement))
            results[name.strip()] = [tuple(row) for row in result] if result.returns_rows else []
    return results


def test_sql_top_three_customers(sales_data):
    rows = run_sql_file()["top_customers"]
    assert [(name, orders, total) for _, name, orders, total in rows] == [
        ("Alpha", 2, Decimal("2570.00")),
        ("Beta", 1, Decimal("950.00")),
    ]


def test_sql_top_three_products_by_quantity(sales_data):
    rows = run_sql_file()["top_products"]
    assert [(code, qty) for _, code, _, qty, _ in rows] == [("MS", 8), ("KB", 3)]


def test_sql_customers_who_never_ordered(sales_data):
    rows = run_sql_file()["customers_without_orders"]
    # Delta has a draft order, so it HAS placed an order; only Gamma never did.
    assert [row[1] for row in rows] == ["Gamma"]


def test_sql_month_wise_confirmed_sales(sales_data):
    rows = run_sql_file()["monthly_sales"]
    assert rows == [
        (2026, 9, 1, Decimal("2300.00"), Decimal("230.00"), Decimal("2070.00")),
        (2026, 10, 2, Decimal("1500.00"), Decimal("50.00"), Decimal("1450.00")),
    ]


def test_sql_products_below_threshold(sales_data):
    rows = run_sql_file()["low_stock"]  # @threshold = 10 in the file
    assert [(row[1], row[4]) for row in rows] == [("OLD", 1), ("CB", 3)]
