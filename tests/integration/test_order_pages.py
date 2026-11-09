"""Order pages render for logged-in users; data access is enforced by the API."""

import pytest


@pytest.mark.parametrize("path", ["/orders", "/orders/new", "/orders/1", "/orders/1/edit"])
def test_order_pages_render_for_sales_user(sales_client, path):
    response = sales_client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/orders", "/orders/new", "/orders/1"])
def test_order_pages_require_login(client, migrated_database, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303


def test_order_form_has_dynamic_row_template_and_live_totals(sales_client):
    html = sales_client.get("/orders/new").text
    assert 'id="item-row-template"' in html
    assert 'id="grand-total"' in html
    assert 'id="add-row"' in html
    assert "Discount % (0–20)" in html  # limit rendered from app/core/constants.py


def test_nav_label_depends_on_role(sales_client, admin_client):
    assert ">My orders</a>" in sales_client.get("/orders").text
    assert ">Orders</a>" in admin_client.get("/orders").text
