"""Rate limiting: the 429 response carries the error envelope (D13).

The suite disables the limiter globally (see conftest), so here we spin up a
throwaway app wired exactly like the real one — shared `limiter` + real handler —
enable it locally with a low limit, and assert the 429 envelope. `reset()` clears
the shared counters before and after so the test is self-contained.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
import pytest

from src.common.rate_limit import limiter, rate_limit_exceeded_handler


@pytest.fixture()
def limited_client():
    """A minimal app with one route capped at 2 requests, limiter enabled."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.get("/probe")
    @limiter.limit("2/minute", error_message="Too many requests, please slow down")
    def probe(request: Request):
        return {"ok": True}

    limiter.reset()
    limiter.enabled = True
    try:
        yield TestClient(app)
    finally:
        limiter.enabled = False
        limiter.reset()


def test_rate_limit_returns_429_envelope(limited_client):
    # The first two requests are within the 2/minute budget.
    assert limited_client.get("/probe").status_code == 200
    assert limited_client.get("/probe").status_code == 200

    # The third trips the limit: 429 with our error envelope and Express' message.
    response = limited_client.get("/probe")
    assert response.status_code == 429
    assert response.json() == {
        "success": False,
        "message": "Too many requests, please slow down",
    }
