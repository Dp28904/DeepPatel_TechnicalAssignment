"""Customer and product pages render for the right roles."""

import pytest


@pytest.mark.parametrize("path", ["/customers", "/products", "/customers/1", "/products/1"])
def test_pages_render_for_sales_user(sales_client, path):
    response = sales_client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/customers/new", "/products/new"])
def test_create_pages_are_admin_only(sales_client, admin_client, path):
    assert sales_client.get(path).status_code == 403
    assert admin_client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/customers", "/products/new"])
def test_pages_require_login(client, migrated_database, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")


def test_admin_sees_new_buttons_and_sales_user_does_not(admin_client, sales_client):
    assert 'href="/products/new"' in admin_client.get("/products").text
    assert 'href="/products/new"' not in sales_client.get("/products").text


def test_product_page_shows_adjust_stock_panel_to_admin_only(admin_client, sales_client):
    assert 'id="adjust-form"' in admin_client.get("/products/1").text
    assert 'id="adjust-form"' not in sales_client.get("/products/1").text


def test_nav_links_to_master_data(sales_client):
    html = sales_client.get("/").text
    assert 'href="/customers"' in html
    assert 'href="/products"' in html
