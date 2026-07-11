from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.core.exceptions import register_exception_handlers
from src.core.schemas import ApiResponse
from src.auth.router import router as auth_router


def create_app() -> FastAPI:
    """App factory: build and configure the FastAPI application."""
    app = FastAPI(
        title="Los Inmaduros Rollers Madrid API",
        docs_url="/api-docs",     
        openapi_url="/api-docs.json", 
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

    # Module routers will be registered here, one per session:
    app.include_router(auth_router)

    @app.get(
        "/health",
        response_model=ApiResponse[dict],
        response_model_exclude_none=True,
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