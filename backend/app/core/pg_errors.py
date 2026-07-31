"""Translate PostgREST/Postgres errors into our :class:`AppError` hierarchy.

The RPCs in migration 0012 signal failure with custom SQLSTATEs rather than with
message text, so the API can map them to HTTP codes without string matching --
which would break the first time someone rewords a message.

    HB403 -> 403 Forbidden
    HB404 -> 404 Not Found
    HB409 -> 409 Conflict

Standard SQLSTATEs raised by constraints are mapped too, so a unique-violation
surfaces as a 409 rather than an opaque 500.
"""

from __future__ import annotations

from app.core.exceptions import (
    AppError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

# Custom codes raised by our SECURITY DEFINER functions.
_CUSTOM = {
    "HB403": (AuthorizationError, "forbidden"),
    "HB404": (NotFoundError, "not_found"),
    "HB409": (ConflictError, "conflict"),
}

# Postgres classes worth distinguishing from a generic failure.
_STANDARD = {
    "23505": (ConflictError, "unique_violation"),       # duplicate key
    "23503": (ValidationError, "foreign_key_violation"),  # references a missing row
    "23514": (ValidationError, "check_violation"),        # failed a CHECK
    "23502": (ValidationError, "not_null_violation"),
    "42501": (AuthorizationError, "insufficient_privilege"),
}


def _extract_code(exc: Exception) -> str | None:
    """Pull the SQLSTATE out of a postgrest-py error.

    The SDK surfaces it as ``.code`` on APIError, but has moved that attribute
    between versions and sometimes carries a dict instead, so this reads
    defensively rather than assuming one shape.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code

    for attr in ("details", "args"):
        value = getattr(exc, attr, None)
        if isinstance(value, dict) and isinstance(value.get("code"), str):
            return value["code"]
    return None


def translate(exc: Exception, *, default_message: str) -> AppError:
    """Return the :class:`AppError` corresponding to ``exc``.

    Falls back to a generic :class:`AppError` carrying ``default_message`` -- the
    original exception text is deliberately not forwarded, since a Postgres error
    can quote a row value or a constraint definition.
    """
    code = _extract_code(exc)
    mapping = _CUSTOM.get(code or "") or _STANDARD.get(code or "")
    if mapping is None:
        return AppError(default_message)

    error_class, error_code = mapping
    # Our own RPCs write messages meant for the caller; Postgres' built-in
    # messages are not, so only the custom ones are passed through. `.message`
    # rather than str(exc), which on an APIError renders the whole JSON payload.
    if code in _CUSTOM:
        message = getattr(exc, "message", None) or default_message
    else:
        message = default_message
    return error_class(str(message), code=error_code)
