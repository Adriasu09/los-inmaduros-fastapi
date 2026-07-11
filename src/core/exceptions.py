from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

class AppError(Exception):
    """Base class for all domain errors. Subclasses set their status code."""

    status_code = 500

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class BadRequestError(AppError):
    """Invalid input or invalid state transition."""
    status_code = 400


class UnauthorizedError(AppError):
    """No identity: missing or invalid credentials."""
    status_code = 401


class ForbiddenError(AppError):
    """Identity is known but lacks permission."""
    status_code = 403


class NotFoundError(AppError):
    """The requested resource does not exist."""
    status_code = 404


class ConflictError(AppError):
    """Duplicate or conflicting resource."""
    status_code = 409


# --- Global handlers: translate exceptions into the envelope (D11) ---

def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Any domain error -> its status code + error envelope."""
    assert isinstance(exc, AppError)  # registered only for AppError
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message},
    )


def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI/Pydantic request validation -> 400 + per-field errors (D11)."""
    assert isinstance(exc, RequestValidationError)  # registered only for it
    errors: dict[str, list[str]] = {}
    for err in exc.errors():
        # loc is a tuple like ("body", "rating"): drop the source, keep the field path
        field = ".".join(str(part) for part in err["loc"] if part not in ("body", "query", "path"))
        errors.setdefault(field or "request", []).append(err["msg"])
    return JSONResponse(
        status_code=400,
        content={"success": False, "message": "Validation error", "errors": errors},
    )


def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Framework-raised HTTP errors (e.g. 404 on unknown routes) -> envelope too."""
    assert isinstance(exc, StarletteHTTPException)  # registered only for it
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": str(exc.detail)},
    )

def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort net: any uncontrolled exception -> generic 500 with envelope.

    The client never sees internal details; the full traceback goes to the log.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error"},
    )

def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global handlers to the app (called from main.py)."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)