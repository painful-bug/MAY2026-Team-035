"""FastAPI application factory.

Assembles the app: logging, CORS for the React SPA, exception handlers, and the
versioned API router. Run locally with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="HomeBandhu API",
        version="0.1.0",
        summary="Backend for the HomeBandhu residential community platform.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "env": settings.env}

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
