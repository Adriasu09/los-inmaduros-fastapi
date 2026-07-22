from fastapi import Request
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _real_client_ip(request: Request) -> str:
    """The user's real IP, used to bucket rate-limit counters."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# The shared limiter. No default_limits: limits are applied per-route via the
# @limiter.limit(...) decorator, so there is no global bucket.
limiter = Limiter(key_func=_real_client_ip)

# Named limits (mirror Express). slowapi/limits string format: "<count>/<period>".
AUTH_LIMIT = "5/15minutes"
CREATION_LIMIT = "20/15minutes"

# Messages mirror Express so the frontend surfaces the same text (D13: the error
# envelope reads `message`).
AUTH_LIMIT_MESSAGE = "Too many authentication attempts, please try again later"
CREATION_LIMIT_MESSAGE = "Too many creation requests, please slow down"


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    """Translate slowapi's RateLimitExceeded into the 429 error envelope (D13)."""
    assert isinstance(exc, RateLimitExceeded)  # registered only for this type
    response = JSONResponse(
        status_code=429,
        content={"success": False, "message": exc.detail},
    )
    return request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
