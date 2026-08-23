"""The sign-in card's "Remember me" answer, end to end through the cookies.

The feature is entirely a question about *one header*: does the refresh cookie
carry a ``Max-Age``? Without one the browser drops it when the window closes and
the login page is there again, which is what someone on a shared machine expects.
With one, the returning visitor is silently signed back in.

Nothing else in the suite could catch a regression here, because every other auth
test asserts on the cookie *jar* -- and a jar shows the value, never the lifetime.
So these tests read ``Set-Cookie`` directly.

The companion ``hb_remember`` cookie is why ``/auth/refresh`` can keep the answer:
rotation re-issues the session cookies and has no other memory of what the user
chose. Logout has to clear it, or the next sign-in would inherit a decision made
by whoever used the browser last.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

FRONTEND_ORIGIN = "http://localhost:5173"


@pytest.fixture
def remember_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """`api_client` with a realistic provider timeout.

    The shared fixture pins the budget to a millisecond so it can prove the
    timeout path fires. Every provider call below is patched to return instantly
    and would race that budget on a loaded machine.
    """
    for key, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "placeholder-anon-key",
        "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
        "SUPABASE_JWT_SECRET": "placeholder-jwt-secret",
        "COOKIE_SIGNING_SECRET": "placeholder-cookie-signing-secret-0123456789",
        "AUTH_PRIMARY_METHOD": "google",
        "AUTH_ENABLED_METHODS": "google,email_password",
        "FRONTEND_BASE_URL": FRONTEND_ORIGIN,
        "CORS_ORIGINS": FRONTEND_ORIGIN,
        "ENV": "testing",
    }.items():
        monkeypatch.setenv(key, value)

    get_settings.cache_clear()
    # `follow_redirects=False`: the OAuth routes answer 307 towards the provider,
    # and following that would leave the test client on the open internet.
    with TestClient(create_app(), follow_redirects=False) as client:
        yield client
    get_settings.cache_clear()


@pytest.fixture
def headers(remember_client: TestClient) -> dict[str, str]:
    response = remember_client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    token = remember_client.cookies.get("hb_preauth_csrf")
    assert token
    return {"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": token}


def set_cookie_for(response: object, name: str) -> str:
    """The raw ``Set-Cookie`` line for `name`, which is where the lifetime lives."""
    for line in response.headers.get_list("set-cookie"):  # type: ignore[attr-defined]
        if line.startswith(f"{name}="):
            return line
    raise AssertionError(f"{name} was never set on this response")


def patch_sign_in(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1.routers import auth as auth_router
    from app.services.auth_service import SupabaseSession

    monkeypatch.setattr(
        auth_router.auth_service,
        "sign_in_with_password",
        lambda **_: SupabaseSession("access-token", "refresh-token", 3600),
    )


def test_remembered_sign_in_persists_the_refresh_cookie(
    remember_client: TestClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_sign_in(monkeypatch)

    response = remember_client.post(
        "/api/v1/auth/password/sign-in",
        json={
            "email": "resident@example.com",
            "password": "a-long-enough-password",
            "remember_me": True,
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert "Max-Age=2592000" in set_cookie_for(response, "hb_refresh")
    remember = set_cookie_for(response, "hb_remember")
    assert remember.startswith("hb_remember=1;")
    assert "Max-Age=2592000" in remember


def test_sign_in_defaults_to_a_browser_session(
    remember_client: TestClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No `remember_me` in the body means the safe answer, not the sticky one."""
    patch_sign_in(monkeypatch)

    response = remember_client.post(
        "/api/v1/auth/password/sign-in",
        json={"email": "resident@example.com", "password": "a-long-enough-password"},
        headers=headers,
    )

    assert response.status_code == 200
    refresh = set_cookie_for(response, "hb_refresh")
    assert refresh.startswith("hb_refresh=refresh-token;")
    assert "Max-Age" not in refresh
    assert "Expires" not in refresh
    # The stale answer from a previous, remembered sign-in must not survive.
    assert "Max-Age=0" in set_cookie_for(response, "hb_remember")


def test_email_confirmation_never_persists(
    remember_client: TestClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The confirmation link never asked the question, so it cannot assume yes."""
    from app.api.v1.routers import auth as auth_router
    from app.services.auth_service import SupabaseSession

    monkeypatch.setattr(
        auth_router.auth_service,
        "verify_email_token",
        lambda *_: SupabaseSession("confirmed-access", "confirmed-refresh", 3600),
    )

    response = remember_client.post(
        "/api/v1/auth/email/verify",
        json={"token_hash": "confirmation-token", "verification_type": "signup"},
        headers=headers,
    )

    assert response.status_code == 200
    assert "Max-Age" not in set_cookie_for(response, "hb_refresh")


@pytest.mark.parametrize(
    ("remember_cookie", "expect_persistent"), [("1", True), (None, False)]
)
def test_refresh_preserves_the_original_answer(
    remember_client: TestClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    remember_cookie: str | None,
    expect_persistent: bool,
) -> None:
    """Rotation must not promote a browser session into a remembered one."""
    from app.api.v1.routers import auth as auth_router
    from app.services.auth_service import SupabaseSession

    monkeypatch.setattr(
        auth_router.auth_service,
        "refresh_session",
        lambda _: SupabaseSession("rotated-access", "rotated-refresh", 3600),
    )
    remember_client.cookies.set("hb_refresh", "refresh-token")
    if remember_cookie is not None:
        remember_client.cookies.set("hb_remember", remember_cookie)

    response = remember_client.post("/api/v1/auth/refresh", headers=headers)

    assert response.status_code == 200
    persisted = "Max-Age=2592000" in set_cookie_for(response, "hb_refresh")
    assert persisted is expect_persistent


def test_logout_clears_the_remember_cookie(
    remember_client: TestClient,
    headers: dict[str, str],
) -> None:
    """Otherwise signing out would leave autologin armed for the next person."""
    remember_client.cookies.set("hb_remember", "1")

    response = remember_client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 200
    assert "Max-Age=0" in set_cookie_for(response, "hb_remember")


def test_oauth_start_carries_remember_into_the_signed_transaction(
    remember_client: TestClient,
) -> None:
    from app.core.web_session import OAUTH_COOKIE, verify_payload

    remembered = remember_client.get(
        "/api/v1/auth/oauth/google/start", params={"remember": "true"}
    )
    assert remembered.status_code == 307
    assert verify_payload(remember_client.cookies.get(OAUTH_COOKIE))["remember"] is True

    plain = remember_client.get("/api/v1/auth/oauth/google/start")
    assert plain.status_code == 307
    transaction = verify_payload(remember_client.cookies.get(OAUTH_COOKIE))
    assert transaction["remember"] is False


def test_oauth_callback_honours_the_remembered_transaction(
    remember_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import auth as auth_router
    from app.core.web_session import OAUTH_COOKIE, sign_payload
    from app.services.auth_service import SupabaseSession

    monkeypatch.setattr(
        auth_router.auth_service,
        "exchange_google_code",
        lambda *_: SupabaseSession("oauth-access", "oauth-refresh", 3600),
    )
    remember_client.cookies.set(
        OAUTH_COOKIE,
        sign_payload(
            {"verifier": "pkce-verifier", "next": "/auth/callback", "remember": True},
            ttl_seconds=300,
        ),
    )

    response = remember_client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "provider-code"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert "Max-Age=2592000" in set_cookie_for(response, "hb_refresh")
