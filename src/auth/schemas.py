from pydantic import BaseModel, EmailStr

from src.auth.models import UserRole
from src.core.schemas import CamelModel, UTCDateTime


class UserOut(CamelModel):
    """PRIVATE shape of a user: only ever returned to that same user (GET /api/auth/me).

    It carries `email`, `role` and `clerkId`, so it must NEVER be used for a user
    embedded in a public response (attendees, organizer, review author): that slice
    is `UserPublicOut` below.
    """

    id: str
    clerk_id: str
    email: str
    name: str | None
    last_name: str | None
    image_url: str | None
    role: UserRole
    created_at: UTCDateTime
    updated_at: UTCDateTime


class UserPublicOut(CamelModel):
    """Public slice of a user, as embedded in reviews, route-calls and attendances."""

    id: str
    name: str | None
    image_url: str | None


class TestTokenRequest(BaseModel):
    """Body of POST /api/auth/test-token."""

    email: EmailStr


class TestTokenData(CamelModel):
    """Data block of the test-token response, exactly as Express returns it."""

    user_id: str
    email: str
    session_id: str
    token: str
    warning: str
    instructions: str