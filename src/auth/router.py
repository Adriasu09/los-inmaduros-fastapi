from fastapi import APIRouter

from src.auth import service
from src.auth.schemas import TestTokenData, TestTokenRequest
from src.core.schemas import ApiResponse

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post(
    "/test-token",
    response_model=ApiResponse[TestTokenData],
    response_model_exclude_none=True,
)
def generate_test_token(body: TestTokenRequest):
    """DEV ONLY (D1): generate a Clerk JWT for Postman/tests. 404 in production."""
    data = service.generate_test_token(body.email)
    return ApiResponse[TestTokenData](
        success=True,
        data=data,
        message="Test token generated successfully",
    )