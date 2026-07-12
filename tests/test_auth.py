from types import SimpleNamespace
from uuid import uuid4

from clerk_backend_api.security import AuthStatus, RequestState
from sqlalchemy import select

from src.auth import service as auth_service
from src.auth.models import User, UserRole

import base64
import json
from datetime import datetime, timezone

from svix.webhooks import Webhook


# --- Scenario: Access a protected endpoint with a valid token ---
def test_valid_token_identifies_user(client, as_user):
    response = client.get("/_test/protected")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == as_user.id
    assert body["role"] == "USER"


# --- Scenario: Reject a protected endpoint without a token ---
def test_missing_token_returns_401_envelope(client):
    response = client.get("/_test/protected")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "No authentication token provided"


# --- Scenario: The dependency rejects an invalid token ---
def test_invalid_token_returns_401(client, monkeypatch):
    # The SDK, rigged: whatever the token says, Clerk answers "not signed in"
    monkeypatch.setattr(
        auth_service.clerk,
        "authenticate_request",
        lambda request, options: RequestState(status=AuthStatus.SIGNED_OUT),
    )

    response = client.get(
        "/_test/protected", headers={"Authorization": "Bearer forged-token"}
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid authentication token"


# --- Scenario: Reject an admin-only action for a normal user ---
def test_user_gets_403_on_admin_endpoint(client, as_user):
    response = client.get("/_test/admin-only")

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Admin access required"


# Bonus (not in the gherkin, nearly free): the happy path of require_admin
def test_admin_passes_admin_endpoint(client, as_admin):
    response = client.get("/_test/admin-only")

    assert response.status_code == 200
    assert response.json()["id"] == as_admin.id


# --- Scenario: A first-time authenticated user is created in the database ---
def test_first_login_creates_user_with_role_user(db_session, monkeypatch):
    clerk_id = f"user_{uuid4().hex[:12]}"
    fake_clerk_user = SimpleNamespace(
        email_addresses=[SimpleNamespace(email_address="newcomer@example.com")],
        first_name="New",
        last_name="Comer",
        image_url="https://img.example.com/x.png",
    )
    monkeypatch.setattr(
        auth_service.clerk.users, "get", lambda user_id: fake_clerk_user
    )

    user = auth_service.get_or_create_user(db_session, clerk_id)

    assert user.role == UserRole.USER
    assert user.email == "newcomer@example.com"
    # The INSERT really happened (inside the bubble; the fixture will undo it):
    found = db_session.scalar(select(User).where(User.clerk_id == clerk_id))
    assert found is not None
    assert found.id == user.id


# Bonus: the second call must NOT touch Clerk (the SELECT path)
def test_existing_user_skips_clerk(db_session, monkeypatch):
    clerk_id = f"user_{uuid4().hex[:12]}"
    fake_clerk_user = SimpleNamespace(
        email_addresses=[], first_name=None, last_name=None, image_url=None
    )
    monkeypatch.setattr(
        auth_service.clerk.users, "get", lambda user_id: fake_clerk_user
    )
    first = auth_service.get_or_create_user(db_session, clerk_id)

    def explode(user_id):
        raise AssertionError("Clerk should NOT be called for an existing user")

    monkeypatch.setattr(auth_service.clerk.users, "get", explode)
    second = auth_service.get_or_create_user(db_session, clerk_id)

    assert second.id == first.id


# --- Scenario: Generate a test token in development ---
def test_test_token_returns_token(client, monkeypatch):
    monkeypatch.setattr(
        auth_service.clerk.users,
        "list",
        lambda request: [
            SimpleNamespace(
                id="user_abc123",
                email_addresses=[SimpleNamespace(email_address="real@example.com")],
            )
        ],
    )
    monkeypatch.setattr(
        auth_service.clerk.sessions,
        "create",
        lambda request: SimpleNamespace(id="sess_xyz789"),
    )
    monkeypatch.setattr(
        auth_service.clerk.sessions,
        "create_token_from_template",
        lambda session_id, template_name: SimpleNamespace(jwt="fake.jwt.token"),
    )

    response = client.post("/api/auth/test-token", json={"email": "real@example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Test token generated successfully"
    assert body["data"]["token"] == "fake.jwt.token"
    assert body["data"]["sessionId"] == "sess_xyz789"


def test_test_token_without_email_returns_400(client):
    response = client.post("/api/auth/test-token", json={})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert "email" in body["errors"]


def test_test_token_unknown_email_returns_404(client, monkeypatch):
    monkeypatch.setattr(auth_service.clerk.users, "list", lambda request: [])

    response = client.post("/api/auth/test-token", json={"email": "ghost@example.com"})

    assert response.status_code == 404
    assert response.json()["message"] == "User not found. Create user in Clerk dashboard first."


# --- Scenario: The test-token endpoint is disabled in production ---
def test_test_token_disabled_in_production(client, monkeypatch):
    monkeypatch.setattr(auth_service.settings, "ENVIRONMENT", "production")

    response = client.post("/api/auth/test-token", json={"email": "real@example.com"})

    assert response.status_code == 404
    assert response.json()["message"] == "Endpoint not available in production"


# Race condition (deterministic): the rival wins between our SELECT and our INSERT
def test_user_sync_race_returns_rival_user(db_session, monkeypatch):
    clerk_id = f"user_{uuid4().hex[:12]}"

    def rival_wins_meanwhile(user_id):
        # Simulate the parallel request committing FIRST, right in the race window:
        # get_or_create_user already SELECTed (nothing), and is about to INSERT.
        db_session.add(User(clerk_id=clerk_id, email="rival@example.com"))
        db_session.commit()
        return SimpleNamespace(
            email_addresses=[SimpleNamespace(email_address="loser@example.com")],
            first_name=None, last_name=None, image_url=None,
        )

    monkeypatch.setattr(auth_service.clerk.users, "get", rival_wins_meanwhile)

    user = auth_service.get_or_create_user(db_session, clerk_id)

    # We lost the race but recovered: we got the RIVAL's row, no 500, no duplicate
    assert user.email == "rival@example.com"


TEST_WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"test-secret-for-auth-suite-32b!!").decode()


def signed_webhook_headers(payload: str, secret: str = TEST_WEBHOOK_SECRET) -> dict:
    """Sign a payload exactly like Clerk (svix) does."""
    msg_id = "msg_test_001"
    timestamp = datetime.now(timezone.utc)
    signature = Webhook(secret).sign(msg_id, timestamp, payload)
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(int(timestamp.timestamp())),
        "svix-signature": signature,
    }


# --- D14: Clerk webhook keeps the users mirror fresh ---
def test_webhook_user_updated_refreshes_user(client_db, db_session, monkeypatch):
    monkeypatch.setattr(auth_service.settings, "CLERK_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    clerk_id = f"user_{uuid4().hex[:12]}"
    db_session.add(User(clerk_id=clerk_id, email="old@example.com", name="Old"))
    db_session.commit()

    payload = json.dumps({
        "type": "user.updated",
        "data": {
            "id": clerk_id,
            "first_name": "Fresh",
            "last_name": "Name",
            "image_url": "https://img.example.com/new.png",
            "email_addresses": [
                {"id": "em_1", "email_address": "fresh@example.com"},
            ],
            "primary_email_address_id": "em_1",
        },
    })
    response = client_db.post(
        "/api/webhooks/clerk", content=payload, headers=signed_webhook_headers(payload)
    )

    assert response.status_code == 200
    user = db_session.scalar(select(User).where(User.clerk_id == clerk_id))
    assert user is not None
    assert user.name == "Fresh"
    assert user.email == "fresh@example.com"
    assert user.image_url == "https://img.example.com/new.png"


def test_webhook_invalid_signature_returns_401(client, monkeypatch):
    monkeypatch.setattr(auth_service.settings, "CLERK_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    payload = json.dumps({"type": "user.updated", "data": {}})
    forged = "whsec_" + base64.b64encode(b"attacker-guessed-secret-wrong!!!").decode()

    response = client.post(
        "/api/webhooks/clerk",
        content=payload,
        headers=signed_webhook_headers(payload, secret=forged),
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid webhook signature"


def test_webhook_unconfigured_returns_404(client, monkeypatch):
    monkeypatch.setattr(auth_service.settings, "CLERK_WEBHOOK_SECRET", None)

    response = client.post("/api/webhooks/clerk", content="{}")

    assert response.status_code == 404


def test_webhook_unknown_user_is_ignored(client_db, db_session, monkeypatch):
    monkeypatch.setattr(auth_service.settings, "CLERK_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    clerk_id = f"user_{uuid4().hex[:12]}"
    payload = json.dumps({"type": "user.updated", "data": {"id": clerk_id, "email_addresses": []}})

    response = client_db.post(
        "/api/webhooks/clerk", content=payload, headers=signed_webhook_headers(payload)
    )

    assert response.status_code == 200  # acknowledged...
    user = db_session.scalar(select(User).where(User.clerk_id == clerk_id))
    assert user is None  # ...but NOT created: first login owns creation