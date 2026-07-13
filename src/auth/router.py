from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.auth import service
from src.auth.schemas import TestTokenData, TestTokenRequest
from src.core.database import get_db
from src.core.schemas import ApiResponse

router = APIRouter(prefix="/api/auth", tags=["Auth"])
webhook_router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post(
    "/test-token",
    response_model=ApiResponse[TestTokenData],
    response_model_exclude_unset=True,
)
def generate_test_token(body: TestTokenRequest):
    """DEV ONLY (D1): generate a Clerk JWT for Postman/tests. 404 in production."""
    data = service.generate_test_token(body.email)
    return ApiResponse[TestTokenData](
        success=True,
        data=data,
        message="Test token generated successfully",
    )


async def get_raw_body(request: Request) -> bytes:
    """Async dependency: the svix signature covers the EXACT raw bytes of the body."""
    return await request.body()


@webhook_router.post(
    "/clerk",
    response_model=ApiResponse[dict],
    response_model_exclude_unset=True,
)
def clerk_webhook(
    request: Request,
    payload: Annotated[bytes, Depends(get_raw_body)],
    db: Annotated[Session, Depends(get_db)],
):
    """D14: Clerk notifies profile changes; we refresh our users mirror."""
    event = service.verify_clerk_webhook(payload, dict(request.headers))
    if event.get("type") == "user.updated":
        service.update_user_from_clerk_event(db, event["data"])
    return ApiResponse[dict](success=True, message="Webhook processed")