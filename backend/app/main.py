"""FastAPI application factory.

Assembles the app: logging, CORS for the React SPA, exception handlers, and the
versioned API router. Run locally with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    settings = get_settings()
    settings.validate_auth_configuration()

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

    @app.middleware("http")
    async def prevent_sensitive_response_caching(request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/v1/auth/") and not path.endswith("/methods"):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Vary"] = "Cookie, Origin"
        elif request.cookies.get("__Host-hb_access") or request.cookies.get("hb_access"):
            response.headers.setdefault("Cache-Control", "no-store, private")
            response.headers.setdefault("Vary", "Cookie, Origin")
        return response

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "env": settings.env}

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
