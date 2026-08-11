"""Email-confirmation behavior at the password-session boundary.

Production defaults to confirmation-required. Local/test bypass is explicit and
the backend still enforces the setting when GoTrue returns a session.

Google identities are deliberately untouched here -- the provider has already
verified the address, and an OAuth JWT is not required to carry the claim at all
(``docs/BACKEND_CHANGES.md``).
"""

from __future__ import annotations

from typing import Any

import jwt
import pytest

from app.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.services import auth_service

CONFIRMED = "2026-08-01T00:00:00+00:00"


class _User:
    def __init__(self, email_confirmed_at: str | None) -> None:
        self.email_confirmed_at = email_confirmed_at


class _Session:
    access_token = "access-token"
    refresh_token = "refresh-token"
    expires_in = 3600


class _ProviderError(Exception):
    """Shaped like ``supabase_auth.errors.AuthApiError``: it carries a ``code``."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _Auth:
    def __init__(
        self,
        *,
        user: _User | None = None,
        session: _Session | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._user = user
        self._session = session
        self._raises = raises
        self.signed_out: list[dict[str, Any]] = []
        self.resent: list[dict[str, Any]] = []

    def sign_in_with_password(self, _credentials: dict[str, Any]) -> _Auth:
        if self._raises is not None:
            raise self._raises
        return self

    def sign_out(self, options: dict[str, Any]) -> None:
        self.signed_out.append(options)

    def resend(self, credentials: dict[str, Any]) -> None:
        if self._raises is not None:
            raise self._raises
        self.resent.append(credentials)

    @property
    def user(self) -> _User | None:
        return self._user

    @property
    def session(self) -> _Session | None:
        return self._session


class _Client:
    def __init__(self, auth: _Auth) -> None:
        self.auth = auth


def install(monkeypatch: pytest.MonkeyPatch, auth: _Auth) -> _Auth:
    """Answer every ``get_auth_client()`` in the service with one fake."""
    monkeypatch.setattr(auth_service, "get_auth_client", lambda: _Client(auth))
    return auth


def sign_in() -> auth_service.SupabaseSession:
    return auth_service.sign_in_with_password(
        email="resident@example.com",
        password="a-long-enough-password",
        captcha_token=None,
    )


def test_an_unconfirmed_address_cannot_sign_in_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, _Auth(user=_User(None), session=_Session()))

    with pytest.raises(AuthenticationError) as raised:
        sign_in()

    assert raised.value.code == "email_not_confirmed"


def test_refusing_an_unconfirmed_address_revokes_the_minted_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = install(monkeypatch, _Auth(user=_User(None), session=_Session()))

    with pytest.raises(AuthenticationError):
        sign_in()

    assert auth.signed_out == [{"scope": "local"}]


def test_explicit_local_override_allows_an_unconfirmed_test_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(), "auth_email_confirmation_required", False
    )
    install(monkeypatch, _Auth(user=_User(None), session=_Session()))

    assert sign_in().access_token == "access-token"


def test_a_provider_that_refuses_the_grant_reports_the_same_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With **Confirm email** on, GoTrue refuses first -- one code either way, so
    the caller's experience does not depend on a dashboard toggle."""
    install(monkeypatch, _Auth(raises=_ProviderError("email_not_confirmed")))

    with pytest.raises(AuthenticationError) as raised:
        sign_in()

    assert raised.value.code == "email_not_confirmed"


def test_a_confirmed_address_still_signs_in(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, _Auth(user=_User(CONFIRMED), session=_Session()))

    session = sign_in()

    assert session.access_token == "access-token"
    assert session.refresh_token == "refresh-token"


def test_a_wrong_password_is_not_reported_as_an_unconfirmed_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only GoTrue's own ``email_not_confirmed`` earns the specific message;
    everything else stays the generic answer that reveals nothing."""
    install(monkeypatch, _Auth(raises=_ProviderError("invalid_credentials")))

    with pytest.raises(AuthenticationError) as raised:
        sign_in()

    assert raised.value.code == "invalid_credentials"


def test_a_session_without_a_user_record_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, _Auth(user=None, session=_Session()))

    with pytest.raises(AuthenticationError) as raised:
        sign_in()

    assert raised.value.code == "email_not_confirmed"


def test_resending_asks_for_a_signup_link_pointing_at_the_confirmation_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The link has to land on the page that spends the token hash; anywhere else
    and the user meets a confirm button with nothing to confirm."""
    auth = install(monkeypatch, _Auth())

    auth_service.resend_confirmation_email(
        email="resident@example.com", captcha_token="turnstile"
    )

    frontend = get_settings().frontend_base_url.rstrip("/")
    assert auth.resent == [
        {
            "type": "signup",
            "email": "resident@example.com",
            "options": {
                "email_redirect_to": f"{frontend}/auth/confirm-email",
                "captcha_token": "turnstile",
            },
        }
    ]


def test_resending_stays_silent_when_the_provider_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resend that raised on unknown addresses would enumerate accounts."""
    install(monkeypatch, _Auth(raises=_ProviderError("over_email_send_rate_limit")))

    auth_service.resend_confirmation_email(
        email="stranger@example.com", captcha_token=None
    )


def _token(claims: dict[str, Any]) -> str:
    return jwt.encode(
        {
            "sub": "profile-id",
            "aud": "authenticated",
            "email": "resident@example.com",
            **claims,
        },
        get_settings().supabase_jwt_secret,
        algorithm="HS256",
    )


def _verified(claims: dict[str, Any]) -> bool:
    return decode_token(_token(claims)).email_verified


def test_email_confirmation_is_read_from_where_supabase_actually_puts_it() -> None:
    """Supabase nests the flag in ``user_metadata``. Reading only the top level
    left the field false for every real caller -- inert while nothing consults
    it, and a total lockout for whoever first writes ``if not email_verified``."""
    assert _verified({"user_metadata": {"email_verified": True}}) is True
    assert _verified({"email_confirmed_at": CONFIRMED}) is True
    assert _verified({"user_metadata": {"email_verified": False}}) is False
    assert _verified({}) is False
