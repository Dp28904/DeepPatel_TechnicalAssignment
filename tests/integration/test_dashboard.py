"""Dashboard API: role scoping, headline numbers, chart series, date range.

Dataset (through the real order service):
    sales_user        2026-08-10 CONFIRMED  KB x2 @1000            = 2000, 10% -> 1800.00
                      2026-10-15 CONFIRMED  MS x5 @100             =  500        ->  500.00
                      2026-10-20 DRAFT      KB x1                                 (1000.00)
    other_sales_user  2026-09-05 CONFIRMED  KB x1 + MS x3          = 1300        -> 1300.00
                      2026-09-06 CANCELLED  MS x2 (confirmed, then cancelled)
"""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.orders import service as order_service
from app.modules.orders.schemas import OrderIn
from tests.factories import make_customer, make_product

URL = "/api/dashboard"


@pytest.fixture
def data(db_session, sales_user, other_sales_user):
    alpha = make_customer(db_session, name="Alpha")
    beta = make_customer(db_session, name="Beta")
    kb = make_product(
        db_session,
        code="KB",
        name="Keyboard",
        category="Accessories",
        price=Decimal("1000"),
        stock_quantity=50,
    )
    ms = make_product(
        db_session,
        code="MS",
        name="Mouse",
        category="Peripherals",
        price=Decimal("100"),
        stock_quantity=50,
    )
    make_product(db_session, code="LOW", name="Nearly gone", stock_quantity=2)
    make_product(db_session, code="ZERO", name="Sold out", stock_quantity=0)
    make_product(db_session, code="OFF", name="Inactive low", stock_quantity=1, is_active=False)
    db_session.commit()

    def order(user, customer, day, items, discount="0", action="confirm"):
        created = order_service.create_order(
            db_session,
            user,
            OrderIn(
                customer_id=customer.id,
                order_date=date.fromisoformat(day),
                discount_percent=discount,
                items=[{"product_id": p.id, "quantity": q} for p, q in items],
            ),
        )
        if "confirm" in action:
            order_service.confirm_order(db_session, user, created.id)
        if "cancel" in action:
            order_service.cancel_order(db_session, user, created.id)

    order(sales_user, alpha, "2026-08-10", [(kb, 2)], discount="10")
    order(sales_user, beta, "2026-10-15", [(ms, 5)])
    order(sales_user, alpha, "2026-10-20", [(kb, 1)], action="draft")
    order(other_sales_user, beta, "2026-09-05", [(kb, 1), (ms, 3)])
    order(other_sales_user, beta, "2026-09-06", [(ms, 2)], action="confirm+cancel")


ALL_TIME = {"from": "2026-01-01", "to": "2026-10-31"}


def test_admin_sees_the_whole_business(admin_client, data):
    body = admin_client.get(URL, params=ALL_TIME).json()
    assert body["scope"] == "all"
    k = body["kpis"]
    assert (k["net_sales"], k["gross_sales"], k["discounts"]) == ("3600.00", "3800.00", "200.00")
    assert (k["confirmed_orders"], k["average_order_value"]) == (3, "1200.00")
    assert (k["draft_orders"], k["draft_value"], k["cancelled_orders"]) == (1, "1000.00", 1)
    assert {s["status"]: s["orders"] for s in body["orders_by_status"]} == {
        "CONFIRMED": 3,
        "DRAFT": 1,
        "CANCELLED": 1,
    }
    assert [c["customer_name"] for c in body["top_customers"]] == ["Alpha", "Beta"]
    assert len(body["recent_orders"]) == 5
    assert [(u["user_name"], u["orders"], u["net_sales"]) for u in body["sales_by_user"]] == [
        ("Test Sales", 2, "2300.00"),
        ("Other Sales", 1, "1300.00"),
    ]


def test_sales_user_sees_only_their_own_orders(sales_client, other_sales_client, data):
    mine = sales_client.get(URL, params=ALL_TIME).json()
    assert mine["scope"] == "own"
    assert (mine["kpis"]["net_sales"], mine["kpis"]["confirmed_orders"]) == ("2300.00", 2)
    assert mine["kpis"]["cancelled_orders"] == 0
    assert {o["created_by_name"] for o in mine["recent_orders"]} == {"Test Sales"}
    assert mine["sales_by_user"] == []  # team comparison is for Admins only

    theirs = other_sales_client.get(URL, params=ALL_TIME).json()
    assert (theirs["kpis"]["net_sales"], theirs["kpis"]["confirmed_orders"]) == ("1300.00", 1)
    assert theirs["kpis"]["cancelled_orders"] == 1
    assert [c["customer_name"] for c in theirs["top_customers"]] == ["Beta"]


def test_monthly_series_fills_months_without_sales(sales_client, data):
    months = sales_client.get(URL, params={"from": "2026-08-01", "to": "2026-10-31"}).json()[
        "monthly_sales"
    ]
    assert [(m["label"], m["orders"], m["net_sales"]) for m in months] == [
        ("Aug 2026", 1, "1800.00"),
        ("Sep 2026", 0, "0.00"),  # no confirmed sale for this user in September
        ("Oct 2026", 1, "500.00"),
    ]


def test_products_categories_and_low_stock(admin_client, data):
    body = admin_client.get(URL, params=ALL_TIME).json()
    assert [(p["code"], p["quantity_sold"]) for p in body["top_products"]] == [("MS", 8), ("KB", 3)]
    assert [(c["category"], c["gross_value"]) for c in body["sales_by_category"]] == [
        ("Accessories", "3000.00"),
        ("Peripherals", "800.00"),
    ]
    # Active products under the threshold of 10, lowest first; inactive ones are excluded.
    assert [(p["code"], p["stock_quantity"]) for p in body["low_stock"]] == [
        ("ZERO", 0),
        ("LOW", 2),
    ]
    assert body["kpis"]["low_stock_products"] == 2


def test_date_range_scopes_every_figure(admin_client, data):
    body = admin_client.get(URL, params={"from": "2026-09-01", "to": "2026-09-30"}).json()
    assert (body["kpis"]["net_sales"], body["kpis"]["confirmed_orders"]) == ("1300.00", 1)
    assert body["kpis"]["draft_orders"] == 0
    assert [m["label"] for m in body["monthly_sales"]] == ["Sep 2026"]
    assert [c["customer_name"] for c in body["top_customers"]] == ["Beta"]


def test_empty_period_returns_zeros_not_errors(sales_client, data):
    body = sales_client.get(URL, params={"from": "2025-01-01", "to": "2025-01-31"}).json()
    assert body["kpis"]["net_sales"] == "0.00"
    assert body["kpis"]["average_order_value"] == "0.00"
    assert body["top_customers"] == [] and body["top_products"] == []
    assert [m["net_sales"] for m in body["monthly_sales"]] == ["0.00"]


def test_all_time_trend_starts_at_first_sale(admin_client, data):
    months = admin_client.get(URL).json()["monthly_sales"]
    assert months[0]["label"] == "Aug 2026"


def test_dashboard_requires_login_and_valid_range(client, admin_client, migrated_database):
    assert client.get(URL).status_code == 401
    assert (
        admin_client.get(URL, params={"from": "2026-10-01", "to": "2026-09-01"}).status_code == 422
    )
    assert admin_client.get(URL, params={"from": "not-a-date"}).status_code == 422


def test_dashboard_page_renders_role_specific_heading(admin_client, sales_client):
    assert "Business overview" in admin_client.get("/").text
    page = sales_client.get("/").text
    assert "My sales" in page and "Only the orders you created" in page
    assert 'src="/static/js/dashboard.js"' in page
    assert 'data-chart="users"' in admin_client.get("/").text
    assert 'data-chart="users"' not in page
