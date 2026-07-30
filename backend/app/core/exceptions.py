"""Application error hierarchy and FastAPI exception handlers.

Services raise these framework-agnostic errors; the handlers registered in
:func:`register_exception_handlers` translate them into JSON HTTP responses so
business logic never has to import FastAPI's ``HTTPException``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base class for expected, client-reportable errors.

    Attributes:
        message: Human-readable description safe to return to the caller.
        status_code: HTTP status the API should respond with.
        code: Stable machine-readable error identifier.
    """

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class AuthenticationError(AppError):
    """The caller could not be authenticated (missing/invalid token)."""

    status_code = 401
    code = "authentication_error"


class AuthorizationError(AppError):
    """The caller is authenticated but lacks the required role."""

    status_code = 403
    code = "authorization_error"


class NotFoundError(AppError):
    """A requested resource does not exist."""

    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    """Input failed a business-rule validation check."""

    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    """The request conflicts with current state (e.g. invite already used)."""

    status_code = 409
    code = "conflict"


class ServiceUnavailableError(AppError):
    """A required external dependency has not been provisioned correctly."""

    status_code = 503
    code = "service_unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    """Register JSON handlers so every error response shares one envelope.

    Previously only :class:`AppError` was handled, despite the docstring claiming
    otherwise. That left **three** wire shapes in production: our
    ``{"error": {...}}``, FastAPI's ``{"detail": [...]}`` for request-validation
    failures, and ``{"detail": "Internal Server Error"}`` for uncaught exceptions.
    A client cannot parse errors generically against three shapes, so all four
    handlers below emit the same envelope::

        {"error": {"code": "not_found", "message": "..."}}

    with an optional ``details`` array for field-level validation errors.
    """

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Malformed request body/query -> 422 in the standard envelope."""
        details = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": error.get("msg", ""),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "The request could not be validated.",
                    "details": details,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Framework-raised HTTP errors (404 on an unknown path, 405, ...)."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"http_{exc.status_code}",
                    "message": str(exc.detail),
                }
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        """Anything unanticipated -> 500, logged in full, opaque to the caller.

        The message is deliberately fixed: an exception string can carry a table
        name, a row value or a connection string, and this is the one handler
        that sees errors nobody designed.
        """
        from app.core.logging import get_logger

        get_logger(__name__).exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong. Please try again.",
                }
            },
        )
