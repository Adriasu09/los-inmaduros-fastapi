def test_health_returns_success_envelope(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "OK"
    assert body["data"]["database"] == "connected"
    # optional empty fields must NOT travel in the JSON (exclude_none)
    assert "message" not in body


def test_unknown_route_returns_error_envelope(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert "message" in body