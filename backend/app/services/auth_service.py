"""Authentication service: phone SMS OTP login, refresh, and profile lookup.

Wraps Supabase GoTrue so routers stay thin. Supabase remains the identity
authority — this layer only translates SDK calls and errors into our domain
types and :class:`AppError` responses.

Login is intentionally restricted to already-provisioned numbers
(``should_create_user=False``); new members join only through the admin invite
flow (see :mod:`app.services.invitation_service`).
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import AppError, AuthenticationError
from app.core.logging import get_logger
from app.core.supabase_client import get_anon_client
from app.domain.roles import parse_role
from app.domain.schemas import Principal, Profile, Session
from app.repositories import profiles_repository
from supabase import Client

_logger = get_logger(__name__)


def request_login_otp(phone: str) -> None:
    """Send a login OTP over SMS to an existing member's ``phone``.

    Does not reveal whether the number is registered (to avoid user
    enumeration); unknown numbers simply never receive a code because
    ``should_create_user`` is False.
    """
    try:
        get_anon_client().auth.sign_in_with_otp(
            {
                "phone": phone,
                "options": {"channel": "sms", "should_create_user": False},
            }
        )
    except Exception as exc:  # noqa: BLE001 - normalize SDK errors to AppError
        _logger.warning("OTP request failed for phone ending %s", phone[-4:])
        raise AppError("Could not send the login code. Try again.") from exc


def verify_login_otp(phone: str, token: str) -> Session:
    """Verify an SMS OTP and return the resulting Supabase session."""
    try:
        result = get_anon_client().auth.verify_otp(
            {"phone": phone, "token": token, "type": "sms"}
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Invalid or expired code.") from exc

    if result.session is None or result.user is None:
        raise AuthenticationError("Invalid or expired code.")
    return _to_session(result.session, result.user)


def refresh_session(refresh_token: str) -> Session:
    """Exchange a refresh token for a fresh session ('remember me')."""
    try:
        result = get_anon_client().auth.refresh_session(refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Could not refresh the session.") from exc

    if result.session is None or result.user is None:
        raise AuthenticationError("Could not refresh the session.")
    return _to_session(result.session, result.user)


def get_me(client: Client, principal: Principal) -> Profile:
    """Return the caller's profile, read under their own RLS scope.

    Args:
        client: A caller-scoped Supabase client (from ``get_request_client``).
        principal: The verified caller.
    """
    return profiles_repository.get_profile(client, principal.user_id)


def _to_session(session: Any, user: Any) -> Session:
    """Map a GoTrue session/user pair to our :class:`Session` DTO."""
    role = parse_role(
        (getattr(user, "user_metadata", None) or {}).get("role")
    )
    return Session(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_at=getattr(session, "expires_at", None),
        user_id=user.id,
        role=role,
    )
