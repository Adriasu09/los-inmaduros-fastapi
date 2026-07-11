from typing import Annotated

from clerk_backend_api.security import AuthenticateRequestOptions
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.auth.models import User, UserRole
from src.auth.service import clerk, get_or_create_user
from src.core.database import get_db
from src.core.exceptions import UnauthorizedError, ForbiddenError

# auto_error=False: if the header is missing we decide the error (401 + envelope),
# instead of FastAPI's default 403 with {"detail": ...}
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Validate the Clerk JWT and return the local user (creating it on first login)."""
    if credentials is None:
        raise UnauthorizedError("No authentication token provided")

    state = clerk.authenticate_request(request, AuthenticateRequestOptions())
    if not state.is_signed_in or state.payload is None:
        raise UnauthorizedError("Invalid authentication token")

    return get_or_create_user(db, state.payload["sub"])

def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require an authenticated user with the ADMIN role."""
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    return user

def optional_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Return the user if a valid token is present, None otherwise. Never raises."""
    if credentials is None:
        return None

    state = clerk.authenticate_request(request, AuthenticateRequestOptions())
    if not state.is_signed_in or state.payload is None:
        return None

    return get_or_create_user(db, state.payload["sub"])