from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.attendances.router import flat_router as attendances_flat_router
from src.attendances.router import nested_router as attendances_nested_router
from slowapi.errors import RateLimitExceeded

from src.auth.router import router as auth_router, webhook_router
from src.common.rate_limit import limiter, rate_limit_exceeded_handler
from src.common.scheduler import start_scheduler
from src.core.config import settings
from src.core.database import get_db
from src.core.exceptions import register_exception_handlers
import src.core.models_registry  # noqa: F401  (register all models before any is used)
from src.core.schemas import ApiResponse
from src.photos.router import router as photos_router
from src.route_calls.router import router as route_calls_router
from src.routes.router import router as routes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: kick off the route-call status scheduler (unless disabled, e.g.
    in tests). On shutdown: stop it cleanly."""
    scheduler = start_scheduler() if settings.SCHEDULER_ENABLED else None
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    """App factory: build and configure the FastAPI application."""
    app = FastAPI(
        title="Los Inmaduros Rollers Madrid API",
        docs_url="/api-docs",
        openapi_url="/api-docs.json",
        lifespan=lifespan,
    )

    # CORS: only these origins may call the API from a browser
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Rate limiting (slowapi): the decorators on the routes need the limiter on
    # app.state, and RateLimitExceeded is translated to the 429 error envelope.
    # RateLimitExceeded subclasses StarletteHTTPException, so this more specific
    # handler wins over the generic one registered above.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Module routers will be registered here, one per session:
    app.include_router(auth_router)
    app.include_router(webhook_router)
    app.include_router(routes_router)
    app.include_router(route_calls_router)
    app.include_router(attendances_nested_router)
    app.include_router(attendances_flat_router)
    app.include_router(photos_router)

    # GET + HEAD: FastAPI's @app.get answers GET only (unlike raw Starlette), so a
    # HEAD probe 405s. UptimeRobot's free tier can ONLY send HEAD, so /health must
    # accept it to keep the service awake (D21). HEAD runs the handler and drops the
    # body — the SELECT 1 still verifies the DB.
    @app.api_route(
        "/health",
        methods=["GET", "HEAD"],
        response_model=ApiResponse[dict],
        response_model_exclude_unset=True,
    )
    def health(db: Annotated[Session, Depends(get_db)]):
        """Healthcheck: real DB ping (SELECT 1), wrapped in the envelope."""
        db.execute(text("SELECT 1"))
        return ApiResponse[dict](
            success=True,
            data={"status": "OK", "database": "connected"},
        )

    return app


app = create_app()