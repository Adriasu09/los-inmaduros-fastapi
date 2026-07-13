from pydantic import BaseModel, EmailStr

from src.core.schemas import CamelModel


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