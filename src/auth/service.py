from clerk_backend_api import Clerk, CreateSessionRequestBody, GetUserListRequest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from svix.webhooks import Webhook, WebhookVerificationError

from src.auth.models import User
from src.auth.schemas import TestTokenData
from src.core.config import settings
from src.core.exceptions import NotFoundError, UnauthorizedError


TESTING_TEMPLATE = "testing-template"

# Single SDK instance for the whole app (same pattern as the engine in core/database.py):
# module-level code runs once, on first import.
clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)


def get_or_create_user(db: Session, clerk_id: str) -> User:
    """User-sync: return the local user for a Clerk ID, creating it on first login."""
    user = db.scalar(select(User).where(User.clerk_id == clerk_id))
    if user is not None:
        return user

    # First login: snapshot the profile from Clerk into our users table
    clerk_user = clerk.users.get(user_id=clerk_id)
    email = (
        clerk_user.email_addresses[0].email_address
        if clerk_user.email_addresses
        else ""  # Express fallback: email column is NOT NULL
    )
    user = User(
        clerk_id=clerk_id,
        email=email,
        name=clerk_user.first_name,
        last_name=clerk_user.last_name,
        image_url=clerk_user.image_url,
    )
    try:
        db.add(user)
        db.commit()
    except IntegrityError:
        # Lost the race: a parallel request created this user first. Use theirs.
        db.rollback()
        user = db.scalar(select(User).where(User.clerk_id == clerk_id))
        assert user is not None
    else:
        db.refresh(user)
    return user


def generate_test_token(email: str) -> TestTokenData:
    """DEV ONLY (D1): mint a Clerk session token for a user, for Postman/tests."""
    if settings.ENVIRONMENT == "production":
        # 404, not 403: don't reveal that the endpoint exists at all
        raise NotFoundError("Endpoint not available in production")

    users = clerk.users.list(request=GetUserListRequest(email_address=[email]))
    if not users:
        raise NotFoundError("User not found. Create user in Clerk dashboard first.")
    clerk_user = users[0]

    session = clerk.sessions.create(
        request=CreateSessionRequestBody(user_id=clerk_user.id)
    )
    token_response = clerk.sessions.create_token_from_template(
        session_id=session.id, template_name=TESTING_TEMPLATE
    )
    if token_response.jwt is None:
        raise RuntimeError("Clerk did not return a token")  # bug/outage -> catch-all 500

    return TestTokenData(
        userId=clerk_user.id,
        email=clerk_user.email_addresses[0].email_address if clerk_user.email_addresses else email,
        sessionId=session.id,
        token=token_response.jwt,
        warning="This endpoint should be removed in production",
        instructions="Copy this token and use it in Postman: Authorization: Bearer <token>",
    )


def verify_clerk_webhook(payload: bytes, headers: dict) -> dict:
    """D14: verify the svix signature and return the parsed Clerk event."""
    if settings.CLERK_WEBHOOK_SECRET is None:
        # Feature disabled: indistinguishable from a route that does not exist
        raise NotFoundError("Not found")
    webhook = Webhook(settings.CLERK_WEBHOOK_SECRET)
    try:
        return webhook.verify(payload, headers)
    except WebhookVerificationError:
        raise UnauthorizedError("Invalid webhook signature")


def update_user_from_clerk_event(db: Session, data: dict) -> None:
    """D14: refresh our mirror of a user after a Clerk `user.updated` event."""
    user = db.scalar(select(User).where(User.clerk_id == data["id"]))
    if user is None:
        return  # never logged in here: their first login will snapshot the fresh profile

    emails = data.get("email_addresses") or []
    primary_id = data.get("primary_email_address_id")
    primary = next((e["email_address"] for e in emails if e["id"] == primary_id), None)
    if primary is not None:
        user.email = primary
    user.name = data.get("first_name")
    user.last_name = data.get("last_name")
    user.image_url = data.get("image_url")
    db.commit()