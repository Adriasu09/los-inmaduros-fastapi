from pydantic import BaseModel, EmailStr


class TestTokenRequest(BaseModel):
    """Body of POST /api/auth/test-token."""

    email: EmailStr


class TestTokenData(BaseModel):
    """Data block of the test-token response, exactly as Express returns it (camelCase)."""

    userId: str
    email: str
    sessionId: str
    token: str
    warning: str
    instructions: str