"""Application error hierarchy and FastAPI exception handlers.

Services raise these framework-agnostic errors; the handlers registered in
:func:`register_exception_handlers` translate them into JSON HTTP responses so
business logic never has to import FastAPI's ``HTTPException``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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
    """Register JSON handlers for :class:`AppError` and uncaught exceptions."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
