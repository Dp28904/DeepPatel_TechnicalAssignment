"""App skeleton: health check, JSON error shape, request IDs."""


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_response_carries_request_id(client):
    response = client.get("/api/health")
    assert response.headers.get("X-Request-ID")


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
