"""Mapping of Postgres/PostgREST SQLSTATEs to our error hierarchy.

These matter because the RPCs in migration 0012 signal authorization and state
failures through SQLSTATEs rather than message text -- if this mapping is wrong,
a 403 silently becomes a 500.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import (
    AppError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.pg_errors import custom_error, translate


class FakeAPIError(Exception):
    """Stands in for postgrest's APIError, which carries .code and .message."""

    def __init__(self, code: str, message: str = "boom") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@pytest.mark.parametrize(
    ("code", "expected_class", "expected_code"),
    [
        ("HB403", AuthorizationError, "forbidden"),
        ("HB404", NotFoundError, "not_found"),
        ("HB409", ConflictError, "conflict"),
        # The membership half of the separate-account rule
        # (`20260812113000_professional_membership_symmetry.sql`). A 409, like
        # the registration-time refusal it mirrors, but its own code: "you
        # already belong here" and "this account is the wrong kind of account"
        # are different things to tell a user and cannot be told apart from a
        # status alone.
        ("HBSEP", ConflictError, "professional_account_separate"),
        ("23505", ConflictError, "unique_violation"),
        ("23503", ValidationError, "foreign_key_violation"),
        ("23514", ValidationError, "check_violation"),
        ("42501", AuthorizationError, "insufficient_privilege"),
    ],
)
def test_known_sqlstates_map_to_typed_errors(code, expected_class, expected_code):
    error = translate(FakeAPIError(code), default_message="fallback")
    assert isinstance(error, expected_class)
    assert error.code == expected_code


def test_custom_codes_forward_their_message():
    """Our own RPCs write messages meant for the caller."""
    error = translate(
        FakeAPIError("HB409", "This request has already been reviewed."),
        default_message="fallback",
    )
    assert error.message == "This request has already been reviewed."


def test_builtin_codes_do_not_leak_postgres_text():
    """A constraint message can quote a row value, so it must not be forwarded."""
    error = translate(
        FakeAPIError("23505", 'duplicate key value violates "secret_idx"'),
        default_message="Could not save.",
    )
    assert error.message == "Could not save."
    assert "secret_idx" not in error.message


def test_unknown_code_falls_back_without_leaking():
    error = translate(FakeAPIError("XX000", "internal detail"), default_message="Nope.")
    assert type(error) is AppError
    assert error.message == "Nope."


def test_error_without_a_code_is_handled():
    """Not every exception from the SDK is an APIError."""
    error = translate(RuntimeError("connection reset"), default_message="Nope.")
    assert type(error) is AppError
    assert error.message == "Nope."


# ---------------------------------------------------------------------------
# `custom_error` -- for call sites that keep their own fallback
# ---------------------------------------------------------------------------


def test_custom_error_returns_our_own_refusals():
    error = custom_error(FakeAPIError("HBSEP", "Use a separate account."))
    assert isinstance(error, ConflictError)
    assert error.code == "professional_account_separate"
    assert error.message == "Use a separate account."


@pytest.mark.parametrize(
    "exc",
    [
        FakeAPIError("23505", 'duplicate key value violates "secret_idx"'),
        FakeAPIError("XX000", "internal detail"),
        RuntimeError("connection reset"),
    ],
)
def test_custom_error_declines_everything_that_is_not_ours(exc):
    """A standard SQLSTATE's message is Postgres' words, not ours to forward."""
    assert custom_error(exc) is None


def test_custom_error_declines_one_of_ours_that_arrived_empty():
    """The caller must always be able to fall back to its own wording."""
    assert custom_error(FakeAPIError("HB409", "   ")) is None
