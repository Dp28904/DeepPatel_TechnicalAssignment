"""Customers API: CRUD, search, status filter, role visibility, safe delete."""

import pytest

from app.models import Customer
from tests.factories import make_customer, make_order, see_latest

URL = "/api/customers"

VALID = {"name": "Acme Traders", "email": "Buyer@Acme.com", "mobile": "98765 43210", "city": "Pune"}


@pytest.fixture
def customers(db_session):
    """Three customers: two active, one inactive."""
    rows = [
        make_customer(db_session, name="Alpha Stores", email="alpha@shop.com", mobile="9000000001"),
        make_customer(db_session, name="Beta Mart", email="beta@mart.com", mobile="9000000002"),
        make_customer(db_session, name="Gamma Retail", email="gamma@x.com", is_active=False),
    ]
    db_session.commit()
    return rows


# --- Create / read / update -----------------------------------------------
def test_admin_creates_customer_with_normalised_fields(admin_client):
    response = admin_client.post(URL, json=VALID)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "buyer@acme.com"  # lower-cased
    assert body["mobile"] == "9876543210"  # spaces removed
    assert body["is_active"] is True

    fetched = admin_client.get(f"{URL}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Acme Traders"


def test_optional_fields_can_be_blank(admin_client):
    response = admin_client.post(
        URL, json={"name": "Walk-in", "email": "", "mobile": "", "city": ""}
    )
    assert response.status_code == 201
    assert response.json()["email"] is None


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({**VALID, "name": "   "}, "name"),
        ({**VALID, "email": "not-an-email"}, "email"),
        ({**VALID, "mobile": "12345"}, "mobile"),
        ({**VALID, "mobile": "98765abcde"}, "mobile"),
        ({**VALID, "name": "x" * 151}, "name"),
    ],
)
def test_invalid_customer_is_rejected_with_field_error(admin_client, payload, field):
    response = admin_client.post(URL, json=payload)
    assert response.status_code == 422
    assert field in {d["field"] for d in response.json()["error"]["details"]}


def test_unknown_fields_are_rejected(admin_client):
    response = admin_client.post(URL, json={**VALID, "id": 99})
    assert response.status_code == 422


def test_admin_updates_and_deactivates_customer(admin_client, customers):
    alpha = customers[0]
    response = admin_client.put(
        f"{URL}/{alpha.id}", json={**VALID, "name": "Alpha Stores Ltd", "is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Alpha Stores Ltd"
    assert response.json()["is_active"] is False


def test_missing_customer_returns_404(admin_client, migrated_database):
    assert admin_client.get(f"{URL}/999999").status_code == 404
    assert admin_client.put(f"{URL}/999999", json=VALID).status_code == 404
    assert admin_client.delete(f"{URL}/999999").status_code == 404


# --- Search, filter, pagination --------------------------------------------
@pytest.mark.parametrize(
    ("search", "expected"),
    [("beta", ["Beta Mart"]), ("alpha@shop", ["Alpha Stores"]), ("9000000002", ["Beta Mart"])],
)
def test_search_by_name_email_or_mobile(admin_client, customers, search, expected):
    response = admin_client.get(URL, params={"search": search, "status": "all"})
    assert [c["name"] for c in response.json()["items"]] == expected


def test_search_treats_wildcards_literally(admin_client, customers):
    response = admin_client.get(URL, params={"search": "%", "status": "all"})
    assert response.json()["total"] == 0


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("active", ["Alpha Stores", "Beta Mart"]),
        ("inactive", ["Gamma Retail"]),
        ("all", ["Alpha Stores", "Beta Mart", "Gamma Retail"]),
    ],
)
def test_admin_status_filter(admin_client, customers, status, expected):
    response = admin_client.get(URL, params={"status": status})
    assert [c["name"] for c in response.json()["items"]] == expected


def test_list_defaults_to_active(admin_client, customers):
    assert admin_client.get(URL).json()["total"] == 2


def test_pagination_metadata(admin_client, customers):
    body = admin_client.get(URL, params={"status": "all", "page": 2, "page_size": 2}).json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert body["page"] == 2
    assert [c["name"] for c in body["items"]] == ["Gamma Retail"]


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 101}, {"status": "deleted"}])
def test_invalid_list_parameters_return_422(admin_client, migrated_database, params):
    assert admin_client.get(URL, params=params).status_code == 422


# --- Role rules -------------------------------------------------------------
def test_sales_user_only_sees_active_customers_even_when_asking_for_all(sales_client, customers):
    for status in ("all", "inactive"):
        names = [
            c["name"] for c in sales_client.get(URL, params={"status": status}).json()["items"]
        ]
        assert names == ["Alpha Stores", "Beta Mart"]


def test_sales_user_gets_404_for_inactive_customer(sales_client, customers):
    inactive = customers[2]
    assert sales_client.get(f"{URL}/{inactive.id}").status_code == 404
    assert sales_client.get(f"{URL}/{customers[0].id}").status_code == 200


def test_sales_user_cannot_modify_customers(sales_client, customers):
    alpha = customers[0]
    assert sales_client.post(URL, json=VALID).status_code == 403
    assert sales_client.put(f"{URL}/{alpha.id}", json=VALID).status_code == 403
    assert sales_client.delete(f"{URL}/{alpha.id}").status_code == 403


def test_anonymous_requests_are_rejected(client, migrated_database):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=VALID).status_code == 401


# --- Safe delete --------------------------------------------------------------
def test_unreferenced_customer_can_be_deleted(admin_client, customers, db_session):
    alpha_id = customers[0].id
    assert admin_client.delete(f"{URL}/{alpha_id}").status_code == 204
    see_latest(db_session)
    assert db_session.get(Customer, alpha_id) is None


def test_customer_with_orders_cannot_be_deleted(admin_client, db_session, admin_user, customers):
    alpha = customers[0]
    make_order(db_session, customer=alpha, created_by=admin_user)
    db_session.commit()

    response = admin_client.delete(f"{URL}/{alpha.id}")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "customer_in_use"
    assert "Deactivate" in error["message"]
    see_latest(db_session)
    assert db_session.get(Customer, alpha.id) is not None
