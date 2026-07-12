from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.exceptions import register_exception_handlers


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

def test_unhandled_exception_returns_500_envelope():
    # Isolated mini-app with the SAME handlers as the real one,
    # plus a route that blows up (we never mount this on the real app).
    bomb_app = FastAPI()
    register_exception_handlers(bomb_app)

    @bomb_app.get("/boom")
    def boom():
        raise RuntimeError("secret internal details")

    # raise_server_exceptions=False: give me the 500 response
    # instead of re-raising the exception into the test
    client = TestClient(bomb_app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Internal server error"
    # the real exception text must NEVER leak to the client
    assert "secret internal details" not in response.text