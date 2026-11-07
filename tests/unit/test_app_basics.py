"""App skeleton: JSON error shape, request IDs, health check when the DB is down.

These tests do not need a database.
"""

import app.main as main_module


def test_response_carries_request_id(client):
    response = client.get("/api/does-not-exist")
    assert response.headers.get("X-Request-ID")


def test_incoming_request_id_is_echoed(client):
    response = client.get("/api/does-not-exist", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"]


def test_wrong_method_returns_json_405(client):
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_health_reports_503_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(main_module, "ping_database", lambda: False)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
