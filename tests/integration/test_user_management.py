"""Account management rules.

- Admin edits a Sales User's name/login email and sets their password.
- Admin changes their own name/email, and their own password with the current one.
- Admins cannot edit another Admin; Sales Users cannot change any account,
  including their own password.
- A password change signs out every other session of that user.
"""

import pytest

from app.core.enums import Role
from app.modules.users import service as user_service
from app.modules.users.schemas import UserCreate
from tests.conftest import TEST_PASSWORD, login_client

NEW_PASSWORD = "Brand-New-Pass-42"


@pytest.fixture
def second_admin(db_session):
    return user_service.create_user(
        db_session,
        UserCreate(
            name="Second Admin", email="admin2@example.com", password=TEST_PASSWORD, role=Role.ADMIN
        ),
    )


def login(app, email, password):
    from fastapi.testclient import TestClient

    test_client = TestClient(
        app, raise_server_exceptions=False, headers={"X-Requested-With": "fetch"}
    )
    response = test_client.post("/api/auth/login", json={"email": email, "password": password})
    return test_client, response.status_code


# --- Listing ---------------------------------------------------------------------------
def test_admin_lists_users_with_what_they_may_change(
    admin_client, admin_user, sales_user, second_admin
):
    users = {u["email"]: u for u in admin_client.get("/api/users").json()}
    assert (
        users["sales@example.com"]["can_edit_profile"],
        users["sales@example.com"]["can_reset_password"],
    ) == (True, True)
    assert (
        users["admin@example.com"]["can_edit_profile"],
        users["admin@example.com"]["can_reset_password"],
    ) == (True, False)
    assert (
        users["admin2@example.com"]["can_edit_profile"],
        users["admin2@example.com"]["can_reset_password"],
    ) == (False, False)
    assert "password_hash" not in str(users)


def test_sales_user_cannot_use_user_management(sales_client, sales_user, other_sales_user):
    assert sales_client.get("/api/users").status_code == 403
    assert sales_client.get(f"/api/users/{sales_user.id}").status_code == 403
    assert (
        sales_client.put(
            f"/api/users/{sales_user.id}", json={"name": "X", "email": "x@example.com"}
        ).status_code
        == 403
    )
    assert (
        sales_client.post(
            f"/api/users/{other_sales_user.id}/password", json={"new_password": NEW_PASSWORD}
        ).status_code
        == 403
    )


# --- Admin manages a Sales User --------------------------------------------------------
def test_admin_changes_sales_user_name_and_login_email(app, admin_client, sales_user):
    response = admin_client.put(
        f"/api/users/{sales_user.id}", json={"name": "Ravi Kumar", "email": " Ravi.K@Example.com "}
    )
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["email"]) == (
        "Ravi Kumar",
        "ravi.k@example.com",
    )
    assert login(app, "ravi.k@example.com", TEST_PASSWORD)[1] == 200  # new username works
    assert login(app, "sales@example.com", TEST_PASSWORD)[1] == 401  # old one does not


def test_email_must_be_unique_and_valid(admin_client, sales_user, other_sales_user):
    taken = admin_client.put(
        f"/api/users/{sales_user.id}", json={"name": "X", "email": other_sales_user.email}
    )
    assert taken.status_code == 409
    assert taken.json()["error"]["details"][0]["field"] == "email"
    assert (
        admin_client.put(
            f"/api/users/{sales_user.id}", json={"name": "X", "email": "not-an-email"}
        ).status_code
        == 422
    )
    assert (
        admin_client.put(
            f"/api/users/{sales_user.id}", json={"name": "", "email": "a@example.com"}
        ).status_code
        == 422
    )


def test_admin_sets_sales_user_password_and_signs_them_out(app, admin_client, sales_user):
    sales_session = login_client(app, sales_user.email)
    assert sales_session.get("/api/auth/me").status_code == 200

    response = admin_client.post(
        f"/api/users/{sales_user.id}/password", json={"new_password": NEW_PASSWORD}
    )
    assert response.status_code == 204

    assert sales_session.get("/api/auth/me").status_code == 401  # signed out everywhere
    assert login(app, sales_user.email, TEST_PASSWORD)[1] == 401  # old password rejected
    assert login(app, sales_user.email, NEW_PASSWORD)[1] == 200


@pytest.mark.parametrize("password", ["short", "", "x" * 129])
def test_new_password_must_be_8_to_128_characters(admin_client, sales_user, password):
    response = admin_client.post(
        f"/api/users/{sales_user.id}/password", json={"new_password": password}
    )
    assert response.status_code == 422


def test_password_spaces_are_kept_not_trimmed(app, admin_client, sales_user):
    admin_client.post(
        f"/api/users/{sales_user.id}/password", json={"new_password": "  spaced pass  "}
    )
    assert login(app, sales_user.email, "  spaced pass  ")[1] == 200
    assert login(app, sales_user.email, "spaced pass")[1] == 401


# --- Admins and other Admins ------------------------------------------------------------
def test_admin_cannot_edit_another_admin(admin_client, second_admin):
    assert (
        admin_client.put(
            f"/api/users/{second_admin.id}", json={"name": "Hacked", "email": "hacked@example.com"}
        ).status_code
        == 403
    )
    assert (
        admin_client.post(
            f"/api/users/{second_admin.id}/password", json={"new_password": NEW_PASSWORD}
        ).status_code
        == 403
    )


def test_admin_cannot_reset_own_password_without_current_one(admin_client, admin_user):
    response = admin_client.post(
        f"/api/users/{admin_user.id}/password", json={"new_password": NEW_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "use_account_page"


def test_admin_edits_own_name_and_email(admin_client, admin_user):
    response = admin_client.put(
        f"/api/users/{admin_user.id}", json={"name": "Asha Patel", "email": "asha@example.com"}
    )
    assert response.status_code == 200
    assert (
        admin_client.get("/api/auth/me").json()["email"] == "asha@example.com"
    )  # session continues


# --- Own password -------------------------------------------------------------------------
def test_admin_changes_own_password_and_stays_signed_in(app, admin_client, admin_user):
    other_device = login_client(app, admin_user.email)
    response = admin_client.post(
        "/api/auth/password", json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 204
    assert admin_client.get("/api/auth/me").status_code == 200  # this session renewed
    assert other_device.get("/api/auth/me").status_code == 401  # other sessions signed out
    assert login(app, admin_user.email, NEW_PASSWORD)[1] == 200
    assert login(app, admin_user.email, TEST_PASSWORD)[1] == 401


def test_own_password_change_needs_the_correct_current_password(admin_client):
    response = admin_client.post(
        "/api/auth/password", json={"current_password": "wrong-one", "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "current_password", "message": "Current password is incorrect."}
    ]


def test_new_password_must_differ_from_current(admin_client):
    response = admin_client.post(
        "/api/auth/password",
        json={"current_password": TEST_PASSWORD, "new_password": TEST_PASSWORD},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "new_password"


def test_sales_user_cannot_change_own_password(app, sales_client, sales_user):
    response = sales_client.post(
        "/api/auth/password", json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ask_an_admin"
    assert login(app, sales_user.email, TEST_PASSWORD)[1] == 200  # unchanged


# --- Pages -----------------------------------------------------------------------------------
def test_user_pages_are_admin_only(admin_client, sales_client, sales_user):
    assert admin_client.get("/users").status_code == 200
    assert admin_client.get(f"/users/{sales_user.id}").status_code == 200
    assert sales_client.get("/users").status_code == 403
    assert 'href="/users"' in admin_client.get("/").text
    assert 'href="/users"' not in sales_client.get("/").text


def test_account_page_offers_password_change_to_admins_only(admin_client, sales_client):
    admin_page = admin_client.get("/account").text
    assert 'id="password-form"' in admin_page and 'id="current_password"' in admin_page
    sales_page = sales_client.get("/account").text
    assert 'id="password-form"' not in sales_page
    assert "only an Admin can change these" in sales_page


def test_header_links_to_my_account(sales_client):
    assert 'href="/account"' in sales_client.get("/").text


# --- Adding users --------------------------------------------------------------------------
def new_user(**overrides):
    return {
        "name": "Neha Shah",
        "email": "neha@example.com",
        "role": "SALES",
        "password": NEW_PASSWORD,
        **overrides,
    }


def test_admin_adds_a_sales_user_who_can_log_in(app, admin_client):
    response = admin_client.post("/api/users", json=new_user(email=" Neha@Example.com "))
    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["email"], body["role"], body["is_active"]) == (
        "Neha Shah",
        "neha@example.com",
        "SALES",
        True,
    )
    assert "password_hash" not in response.text and NEW_PASSWORD not in response.text
    client_, status = login(app, "neha@example.com", NEW_PASSWORD)
    assert status == 200
    assert client_.get("/api/auth/me").json()["role"] == "SALES"


def test_admin_adds_another_admin(app, admin_client):
    response = admin_client.post("/api/users", json=new_user(email="ops@example.com", role="ADMIN"))
    assert response.status_code == 201
    assert response.json()["role"] == "ADMIN"
    assert login(app, "ops@example.com", NEW_PASSWORD)[1] == 200


def test_new_user_email_must_be_unique(admin_client, sales_user):
    response = admin_client.post("/api/users", json=new_user(email="SALES@example.com"))
    assert response.status_code == 409
    assert response.json()["error"]["details"] == [
        {
            "field": "email",
            "message": "The email 'sales@example.com' is already used by another account.",
        }
    ]


@pytest.mark.parametrize(
    ("overrides", "field", "message"),
    [
        ({"name": ""}, "name", "Name is required."),
        (
            {"email": "nope"},
            "email",
            "Email: enter a valid email address, for example name@company.com.",
        ),
        ({"role": "BOSS"}, "role", "Role must be one of: ADMIN or SALES."),
        ({"password": "short"}, "password", "Password must be at least 8 characters."),
    ],
)
def test_new_user_validation_messages(admin_client, migrated_database, overrides, field, message):
    response = admin_client.post("/api/users", json=new_user(**overrides))
    assert response.status_code == 422
    assert {d["field"]: d["message"] for d in response.json()["error"]["details"]}[field] == message


def test_sales_user_cannot_add_users(sales_client):
    assert sales_client.post("/api/users", json=new_user()).status_code == 403


def test_new_user_page_is_admin_only(admin_client, sales_client):
    page = admin_client.get("/users/new")
    assert page.status_code == 200 and 'id="new-user-form"' in page.text
    assert sales_client.get("/users/new").status_code == 403
    assert 'href="/users/new"' in admin_client.get("/users").text
