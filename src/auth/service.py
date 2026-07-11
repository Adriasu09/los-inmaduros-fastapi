from clerk_backend_api import Clerk
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.models import User
from src.core.config import settings

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