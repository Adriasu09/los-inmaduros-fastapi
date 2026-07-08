import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture()
def client():
    """HTTP client against the real app, running in memory."""
    with TestClient(app) as c:
        yield c