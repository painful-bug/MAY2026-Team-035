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
#
# The first three spell an HTTP status because that was the whole of what they
# had to say. `HBUSE` is the first that names a *reason* instead: a resident
# cancelling a pass whose guest already walked through the gate is not the same
# answer as one cancelling from a state that was never cancellable, and 8 Q2 asks
# for a client to be able to tell them apart. The prefix is what marks a signal
# as ours; the remaining three characters are free to mean whatever the signal
# needs.
_CUSTOM = {
    "HB403": (AuthorizationError, "forbidden"),
    "HB404": (NotFoundError, "not_found"),
    "HB409": (ConflictError, "conflict"),
    "HBLOC": (ValidationError, "provider_location_required"),
    "HBUSE": (ConflictError, "pass_already_used"),
    # The separate-account rule, refused from the membership side
    # (`20260812113000_professional_membership_symmetry.sql`). A 409 like
    # `HB409`, because it is the same answer as the registration-time refusal it
    # mirrors -- but its own code, because "this account is the wrong kind of
    # account" and "you already belong here" are two different things to tell a
    # user, and an HTTP status cannot tell them apart.
    "HBSEP": (ConflictError, "professional_account_separate"),
}

# Postgres classes worth distinguishing from a generic failure.
#
# `P0002`, `22P02` and `22004` were added when the resident complaint RPCs
# (`0031`) started raising them. They were already reachable before that --
# `0020`'s `update_complaint` has raised `P0002` for a missing complaint since it
# was written -- and every one of them surfaced as a 500, which is the API
# reporting its own failure for what is squarely the caller's mistake.
_STANDARD = {
    "23505": (ConflictError, "unique_violation"),       # duplicate key
    # `23P01` is the GiST exclusion constraints: an amenity booked twice for one
    # slot (`0001`), a worker sent to two places at once (`0036`). It belongs
    # beside `23505` because it is the same answer -- somebody else has that
    # already -- and without it a double-booking surfaced as a bare 400 whose
    # message could not say which of the caller's fields was the problem.
    "23P01": (ConflictError, "exclusion_violation"),
    "23503": (ValidationError, "foreign_key_violation"),  # references a missing row
    "23514": (ValidationError, "check_violation"),        # failed a CHECK
    "23502": (ValidationError, "not_null_violation"),
    "42501": (AuthorizationError, "insufficient_privilege"),
    "P0002": (NotFoundError, "not_found"),                # `select into` found nothing
    "22P02": (ValidationError, "invalid_value"),          # unparseable enum or number
    "22004": (ValidationError, "missing_value"),          # a required argument was null
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


def custom_error(exc: Exception) -> AppError | None:
    """The caller-facing error *our own* functions raised, or ``None``.

    For call sites that already have a good generic answer for "the database
    refused this" and only need our own refusals -- the ones whose message was
    written for the caller -- to pass through it rather than be flattened into
    it. ``access_request_service.approve`` is the case: every failure there was
    reported as "this access request cannot be approved", which is true of a
    request somebody else already decided and misleading about an applicant the
    separate-account rule refuses.

    Returns ``None`` for a standard SQLSTATE, for an unknown code, and for one
    of ours that arrived without a message, so a caller can always fall back.
    """
    code = _extract_code(exc)
    mapping = _CUSTOM.get(code or "")
    if mapping is None:
        return None
    message = getattr(exc, "message", None)
    if not isinstance(message, str) or not message.strip():
        return None
    error_class, error_code = mapping
    return error_class(message, code=error_code)


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
