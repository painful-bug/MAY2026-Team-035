"""FastAPI application factory.

Assembles the app: logging, CORS for the React SPA, exception handlers, and the
versioned API router. Run locally with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings
from app.core.dispatcher import dispatcher
from app.core.exceptions import ErrorResponse, register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.push import sender
from app.core.realtime import hub


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run the three background workers for the life of the process.

    They start differently, and the differences are the point. The SSE hub is
    started lazily by its first subscriber, so a process that never serves a
    stream never polls at all. The push sender is started here, because it
    exists precisely to reach a resident who has *nothing* open -- a sender that
    waited for a connection would only ever run when it was not needed.

    ``sender.start()`` is a no-op without a VAPID keypair, logging one line and
    returning. An environment with no push configured is an environment where
    push is off, not one that is broken (design §10.5).

    ``dispatcher.start()`` has no such escape hatch, and deliberately: there is
    no configuration for it to be missing, and a deployment that quietly did not
    dispatch would look exactly like one where nobody happened to be free.

    Stopped in reverse. The dispatcher goes first because it is the only one of
    the three that *writes* -- letting it finish its current task before the
    sender that delivers the resulting notification shuts down is the ordering
    that loses the least.
    """
    await sender.start()
    await dispatcher.start()
    yield
    await dispatcher.stop()
    await sender.stop()
    await hub.stop()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    settings = get_settings()
    settings.validate_auth_configuration()

    app = FastAPI(
        title="HomeBandhu API",
        version="0.1.0",
        summary="Backend for the HomeBandhu residential community platform.",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    request_logger = get_logger("homebandhu.requests")

    @app.middleware("http")
    async def prevent_sensitive_response_caching(request: Request, call_next):
        started = perf_counter()
        response: Response = await call_next(request)
        duration_ms = (perf_counter() - started) * 1000
        route = getattr(request.scope.get("route"), "path", "unmatched")
        request_logger.info(
            "http_request method=%s route=%s status=%d duration_ms=%.2f",
            request.method,
            route,
            response.status_code,
            duration_ms,
        )
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.2f}"
        path = request.url.path
        if path.startswith("/api/v1/auth/") and not path.endswith("/methods"):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Vary"] = "Cookie, Origin"
        elif request.cookies.get("__Host-hb_access") or request.cookies.get(
            "hb_access"
        ):
            response.headers.setdefault("Cache-Control", "no-store, private")
            response.headers.setdefault("Vary", "Cookie, Origin")
        return response

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "env": settings.env}

    app.include_router(
        api_router,
        prefix="/api/v1",
        responses={
            422: {
                "model": ErrorResponse,
                "description": "Request validation or business-rule validation error.",
            }
        },
    )
    return app


app = create_app()
