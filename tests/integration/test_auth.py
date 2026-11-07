"""Login, logout, sessions, role checks, CSRF guard and protected pages."""

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.core.dependencies import get_current_user, require_admin
from app.core.error_handlers import register_error_handlers
from app.core.security import CsrfHeaderMiddleware
from app.modules.auth import router as auth_api
from tests.conftest import TEST_PASSWORD, login_client

LOGIN = "/api/auth/login"
ME = "/api/auth/me"


# --- Login ----------------------------------------------------------------
def test_login_succeeds_and_returns_user_without_password_hash(client, admin_user):
    response = client.post(LOGIN, json={"email": admin_user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": admin_user.id,
        "name": "Test Admin",
        "email": "admin@example.com",
        "role": "ADMIN",
        "is_active": True,
    }
    assert "password" not in response.text


def test_session_cookie_is_httponly_and_samesite_lax(client, admin_user):
    response = client.post(LOGIN, json={"email": admin_user.email, "password": TEST_PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "sales_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_login_email_is_case_insensitive(client, sales_user):
    response = client.post(LOGIN, json={"email": "  SALES@Example.com ", "password": TEST_PASSWORD})
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("admin@example.com", "wrong-password"),  # wrong password
        ("nobody@example.com", TEST_PASSWORD),  # unknown email
        ("not-an-email", TEST_PASSWORD),  # malformed email
    ],
)
def test_bad_credentials_get_one_generic_message(client, admin_user, email, password):
    response = client.post(LOGIN, json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "invalid_credentials",
        "message": "Invalid email or password.",
        "details": None,
    }


def test_inactive_user_cannot_log_in(client, db_session, sales_user):
    sales_user.is_active = False
    db_session.commit()
    response = client.post(LOGIN, json={"email": sales_user.email, "password": TEST_PASSWORD})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_login_with_missing_fields_returns_422_with_field_details(client):
    response = client.post(LOGIN, json={"email": ""})
    assert response.status_code == 422
    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert fields == {"email", "password"}


def test_login_rejects_unexpected_fields(client, admin_user):
    response = client.post(
        LOGIN, json={"email": admin_user.email, "password": TEST_PASSWORD, "role": "ADMIN"}
    )
    assert response.status_code == 422


def test_password_is_stored_as_argon2_hash(admin_user):
    assert admin_user.password_hash.startswith("$argon2id$")
    assert TEST_PASSWORD not in admin_user.password_hash


# --- Session --------------------------------------------------------------
def test_me_requires_login(client, migrated_database):
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_me_returns_logged_in_user(sales_client, sales_user):
    response = sales_client.get(ME)
    assert response.status_code == 200
    assert response.json()["id"] == sales_user.id
    assert response.json()["role"] == "SALES"


def test_logout_ends_the_session(sales_client):
    assert sales_client.post("/api/auth/logout").status_code == 204
    assert sales_client.get(ME).status_code == 401


def test_deactivated_user_is_logged_out_on_next_request(sales_client, db_session, sales_user):
    sales_user.is_active = False
    db_session.commit()
    assert sales_client.get(ME).status_code == 401


def test_tampered_session_cookie_is_rejected(app, sales_user):
    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.cookies.set("sales_session", "forged-value")
    assert test_client.get(ME).status_code == 401


# --- CSRF -----------------------------------------------------------------
def test_write_request_without_csrf_header_is_rejected(app, admin_user):
    raw_client = TestClient(app, raise_server_exceptions=False)  # no X-Requested-With
    response = raw_client.post(LOGIN, json={"email": admin_user.email, "password": TEST_PASSWORD})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_check_failed"


def test_read_request_does_not_need_csrf_header(app, migrated_database):
    raw_client = TestClient(app, raise_server_exceptions=False)
    assert raw_client.get("/api/health").status_code == 200


# --- Role checks (backend enforcement) ------------------------------------
@pytest.fixture
def role_test_client_factory(app):
    """A tiny app with one admin-only and one login-only route, using the real dependencies."""
    probe = APIRouter(prefix="/api/probe")

    @probe.get("/admin")
    def admin_only(user=Depends(require_admin)):
        return {"ok": True}

    @probe.get("/any")
    def any_user(user=Depends(get_current_user)):
        return {"role": user.role}

    test_app = FastAPI()
    test_app.add_middleware(CsrfHeaderMiddleware)
    test_app.add_middleware(SessionMiddleware, secret_key="x" * 32, session_cookie="sales_session")
    register_error_handlers(test_app)
    test_app.include_router(auth_api.router)
    test_app.include_router(probe)

    def make(email=None):
        if email is None:
            return TestClient(test_app, raise_server_exceptions=False)
        return login_client(test_app, email)

    return make


def test_admin_only_route_allows_admin(role_test_client_factory, admin_user):
    assert role_test_client_factory(admin_user.email).get("/api/probe/admin").status_code == 200


def test_admin_only_route_forbids_sales_user(role_test_client_factory, sales_user):
    response = role_test_client_factory(sales_user.email).get("/api/probe/admin")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_admin_only_route_requires_login(role_test_client_factory, migrated_database):
    assert role_test_client_factory().get("/api/probe/admin").status_code == 401


def test_login_only_route_allows_sales_user(role_test_client_factory, sales_user):
    response = role_test_client_factory(sales_user.email).get("/api/probe/any")
    assert response.json() == {"role": "SALES"}


# --- Pages ----------------------------------------------------------------
def test_dashboard_redirects_anonymous_visitor_to_login(client, migrated_database):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/"


def test_login_page_renders(client, migrated_database):
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="login-form"' in response.text


def test_dashboard_shows_logged_in_user(sales_client):
    response = sales_client.get("/")
    assert response.status_code == 200
    assert "Test Sales" in response.text
    assert 'data-user-role="SALES"' in response.text


def test_dashboard_exposes_business_limits_to_javascript(admin_client):
    assert 'data-max-discount="20"' in admin_client.get("/").text


def test_login_page_redirects_when_already_logged_in(sales_client):
    response = sales_client.get("/login?next=/orders", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/orders"


def test_login_page_never_redirects_off_site(sales_client):
    response = sales_client.get("/login?next=//evil.example.com", follow_redirects=False)
    assert response.headers["location"] == "/"


def test_unknown_page_returns_html_404(sales_client):
    response = sales_client.get("/no-such-page")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
