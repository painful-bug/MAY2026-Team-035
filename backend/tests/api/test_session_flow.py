"""The browser session end to end: the redirect out, the redirect back, the
authenticated call, and logout.

**Why this file exists separately from the rest of `tests/api`.** Every other
file here uses `resident_api_client`, which overrides `get_current_user` and
`get_active_membership` with fixtures. That is the right seam for testing a
handler — it isolates the thing under test — but it means no test in this suite
has ever asked the question the resident portal actually depends on: *can
somebody who is not signed in reach one of these endpoints?* An override answers
"yes, because we told it to". Nothing overrides anything below: the token is a
real HS256 JWT, `decode_token` really verifies it, `get_active_membership` really
resolves tenancy, and `require_csrf` really compares the cookie against the
header. The only patched boundaries are the two the suite has always patched —
the Supabase network calls and the identity provider.

**The probe endpoint is `GET /resident/snapshot`**, chosen because it is the one
screen a resident lands on after signing in and because it depends on the whole
chain: `get_active_membership` for tenancy and `get_request_client` for a
token-scoped Supabase client. If the chain is wrong anywhere, this endpoint is
where a resident finds out.

Three properties are worth naming, because they are the ones that would be
invisible in a handler test and expensive in production:

* **A signed-out browser gets `401`, not an empty page.** The distinction that
  matters to the frontend is between *no session* (`401` — send them to sign in)
  and *a session with no community* (`403 active_membership_required` — send them
  to the Join/Create chooser). Collapsing the two is how a newly-registered user
  ends up in a redirect loop.
* **`?next=` cannot leave this origin.** An OAuth start that echoes an arbitrary
  `next` into the post-callback redirect is an open redirect wearing a login
  page, and it is the classic way a phishing link borrows a real domain.
* **Logout works when the access token has already expired.** Anything that
  verifies the token before clearing the cookies leaves the one user who most
  needs to sign out unable to.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.web_session import (
    OAUTH_COOKIE,
    PREAUTH_CSRF_COOKIE,
    cookie_name,
    csrf_token,
    sign_payload,
)
from app.domain.resident_snapshot_schemas import ResidentSnapshot
from app.main import create_app

FRONTEND_ORIGIN = "http://localhost:5173"
JWT_SECRET = "placeholder-jwt-secret"
COOKIE_SECRET = "placeholder-cookie-signing-secret-0123456789"

SNAPSHOT = "/api/v1/resident/snapshot"
OAUTH_START = "/api/v1/auth/oauth/google/start"
OAUTH_CALLBACK = "/api/v1/auth/oauth/google/callback"
LOGOUT = "/api/v1/auth/logout"

PROFILE_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def session_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A client with the same settings as `api_client`, but a real provider timeout.

    `api_client` pins `AUTH_PROVIDER_TIMEOUT_SECONDS` to a millisecond so it can
    prove the timeout path fires. Every provider call below is patched to return
    instantly and would race that budget on a loaded machine, so this fixture
    gives them a real one. Nothing else differs.
    """
    for key, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "placeholder-anon-key",
        "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
        "SUPABASE_JWT_SECRET": JWT_SECRET,
        "COOKIE_SIGNING_SECRET": COOKIE_SECRET,
        "AUTH_PRIMARY_METHOD": "google",
        "AUTH_ENABLED_METHODS": "google,email_password",
        "AUTH_PROVIDER_TIMEOUT_SECONDS": "10",
        "FRONTEND_BASE_URL": FRONTEND_ORIGIN,
        "BACKEND_BASE_URL": "http://testserver",
        "CORS_ORIGINS": FRONTEND_ORIGIN,
        "ENV": "testing",
    }.items():
        monkeypatch.setenv(key, value)

    get_settings.cache_clear()
    with TestClient(create_app(), follow_redirects=False) as client:
        yield client
    get_settings.cache_clear()


def access_token(*, subject: str = PROFILE_ID, expires_in: int = 3600) -> str:
    """A JWT of the shape Supabase issues, signed with the configured HS256 secret.

    Minted rather than stubbed so `decode_token` does the verifying: audience,
    signature and expiry are all really checked, which is the point of the file.
    """
    now = int(time.time())
    return jwt.encode(
        {
            "sub": subject,
            "aud": "authenticated",
            "role": "authenticated",
            "email": "resident@example.com",
            "email_confirmed_at": "2026-08-01T00:00:00+00:00",
            "iat": now,
            "exp": now + expires_in,
        },
        JWT_SECRET,
        algorithm="HS256",
    )


class _Result:
    def __init__(self, data: Any, count: int | None = None) -> None:
        self.data = data
        self.count = count


class _MembershipQuery:
    """The narrow slice of the PostgREST builder `get_active_membership` uses."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def select(self, *_: Any, **__: Any) -> _MembershipQuery:
        return self

    def eq(self, *_: Any) -> _MembershipQuery:
        return self

    def is_(self, *_: Any) -> _MembershipQuery:
        return self

    def order(self, *_: Any, **__: Any) -> _MembershipQuery:
        return self

    def limit(self, *_: Any) -> _MembershipQuery:
        return self

    def execute(self) -> _Result:
        return _Result(self._rows)


class _ServiceClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def table(self, _name: str) -> _MembershipQuery:
        return _MembershipQuery(self._rows)


def stub_membership(
    monkeypatch: pytest.MonkeyPatch, *, rows: list[dict[str, Any]] | None = None
) -> None:
    """Replace only the membership lookup's database call, not the dependency."""
    from app.api import deps

    default = [
        {
            "id": "membership-id",
            "community_id": "community-id",
            "role": "resident",
            "department_id": None,
        }
    ]
    resolved = default if rows is None else rows
    monkeypatch.setattr(deps, "get_service_client", lambda: _ServiceClient(resolved))


def stub_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer the probe endpoint's one service call with an empty aggregate."""
    from app.api.v1.routers import resident_snapshot as router

    monkeypatch.setattr(
        router.service,
        "snapshot",
        lambda *_, **__: ResidentSnapshot(generated_at=datetime.now(timezone.utc)),
    )


#: `TestClient` resolves `http://testserver` to this domain in its cookie jar.
#: Cookies planted without it sit in a different scope from the ones the app
#: sets, so `clear_session`'s deletions would appear not to work and the test
#: would be measuring the jar rather than the endpoint.
TEST_COOKIE_DOMAIN = "testserver.local"


def put_cookie(client: TestClient, name: str, value: str) -> None:
    client.cookies.set(name, value, domain=TEST_COOKIE_DOMAIN, path="/")


def sign_in(client: TestClient, *, token: str | None = None) -> str:
    """Put a session on the client the way `establish_session` would, and return
    the CSRF header value that session requires."""
    token = token or access_token()
    put_cookie(client, cookie_name("access"), token)
    put_cookie(client, cookie_name("refresh"), "refresh-token")
    put_cookie(client, cookie_name("csrf"), csrf_token(token))
    return csrf_token(token)


# ---------------------------------------------------------------------------
# The redirect out
# ---------------------------------------------------------------------------


def test_api_100_oauth_start_redirects_to_the_provider_with_a_bound_transaction(
    session_client: TestClient,
) -> None:
    endpoint = "GET /api/v1/auth/oauth/{provider}/start"
    expected_output = {"status_code": 307, "provider_host": "example.supabase.co"}

    response = session_client.get(OAUTH_START)
    location = urlparse(response.headers["location"])
    actual_output = {
        "status_code": response.status_code,
        "provider_host": location.netloc,
    }

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/start"
    assert actual_output == expected_output
    # The PKCE challenge travels to the provider; the verifier stays in a signed,
    # HTTP-only cookie, which is what binds the callback to this browser.
    query = parse_qs(location.query)
    assert query["code_challenge_method"] == ["s256"]
    assert query["code_challenge"]
    assert session_client.cookies.get(OAUTH_COOKIE)


def test_api_101_oauth_start_carries_the_requested_return_path(
    session_client: TestClient,
) -> None:
    from app.core.web_session import verify_payload

    endpoint = "GET /api/v1/auth/oauth/{provider}/start"
    input_data = {"next": "/resident/dashboard"}
    expected_output = {"status_code": 307, "next": "/resident/dashboard"}

    response = session_client.get(OAUTH_START, params=input_data)
    transaction = verify_payload(session_client.cookies.get(OAUTH_COOKIE))
    actual_output = {"status_code": response.status_code, "next": transaction["next"]}

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/start"
    assert actual_output == expected_output


def test_api_102_oauth_start_defaults_the_return_path_when_none_is_given(
    session_client: TestClient,
) -> None:
    from app.core.web_session import verify_payload

    endpoint = "GET /api/v1/auth/oauth/{provider}/start"
    expected_output = {"status_code": 307, "next": "/auth/callback"}

    response = session_client.get(OAUTH_START)
    transaction = verify_payload(session_client.cookies.get(OAUTH_COOKIE))
    actual_output = {"status_code": response.status_code, "next": transaction["next"]}

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/start"
    assert actual_output == expected_output


@pytest.mark.parametrize(
    "hostile_next",
    [
        "https://evil.example/harvest",
        "//evil.example/harvest",
        "/\\evil.example",
        "http://localhost:5173.evil.example/",
    ],
)
def test_api_103_oauth_start_refuses_a_return_path_that_leaves_this_origin(
    session_client: TestClient, hostile_next: str
) -> None:
    """An open redirect behind a sign-in page is a phishing link with our domain
    on it. `safe_return_path` refuses rather than silently substituting a default,
    so a caller sending a hostile value learns it was rejected instead of being
    quietly signed in somewhere else."""
    endpoint = "GET /api/v1/auth/oauth/{provider}/start"
    expected_output = {"status_code": 422, "code": "invalid_return_path"}

    response = session_client.get(OAUTH_START, params={"next": hostile_next})
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/start"
    assert actual_output == expected_output
    # Nothing was started, so no transaction cookie was minted to be replayed.
    assert session_client.cookies.get(OAUTH_COOKIE) is None


def test_api_104_oauth_start_refuses_a_provider_that_is_not_enabled(
    session_client: TestClient,
) -> None:
    endpoint = "GET /api/v1/auth/oauth/{provider}/start"
    expected_output = {"status_code": 422, "code": "provider_disabled"}

    response = session_client.get("/api/v1/auth/oauth/github/start")
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/start"
    assert actual_output == expected_output


# ---------------------------------------------------------------------------
# The redirect back
# ---------------------------------------------------------------------------


def _stub_exchange(monkeypatch: pytest.MonkeyPatch, token: str | None = None) -> None:
    from app.api.v1.routers import auth as auth_router
    from app.services.auth_service import SupabaseSession

    monkeypatch.setattr(
        auth_router.auth_service,
        "exchange_google_code",
        lambda *_, **__: SupabaseSession(
            access_token=token or access_token(),
            refresh_token="refresh-token",
            expires_in=3600,
        ),
    )


def test_api_105_oauth_callback_lands_on_the_frontend_and_establishes_the_session(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = "GET /api/v1/auth/oauth/{provider}/callback"
    expected_output = {
        "status_code": 307,
        "location": f"{FRONTEND_ORIGIN}/resident/dashboard",
    }

    _stub_exchange(monkeypatch)
    session_client.get(OAUTH_START, params={"next": "/resident/dashboard"})
    response = session_client.get(OAUTH_CALLBACK, params={"code": "provider-code"})
    actual_output = {
        "status_code": response.status_code,
        "location": response.headers["location"],
    }

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/callback"
    assert actual_output == expected_output
    # The session the browser leaves with, and the transaction it no longer needs.
    assert session_client.cookies.get(cookie_name("access"))
    assert session_client.cookies.get(cookie_name("refresh"))
    assert session_client.cookies.get(cookie_name("csrf"))
    assert session_client.cookies.get(OAUTH_COOKIE) is None


def test_api_106_oauth_callback_without_a_transaction_cookie_is_unauthenticated(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cookie is the only thing binding a provider code to the browser that
    asked for it. Without it there is nothing to verify against, so a code
    replayed from elsewhere buys nothing."""
    endpoint = "GET /api/v1/auth/oauth/{provider}/callback"
    expected_output = {"status_code": 401, "code": "authentication_error"}

    _stub_exchange(monkeypatch)
    response = session_client.get(OAUTH_CALLBACK, params={"code": "provider-code"})
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/callback"
    assert actual_output == expected_output


def test_api_107_oauth_callback_refuses_a_transaction_signed_with_another_secret(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The destination is read out of the transaction cookie rather than the query
    string, so the signature is what stands between a forged cookie and a redirect
    to anywhere. Forging one with the wrong key must fail closed."""
    endpoint = "GET /api/v1/auth/oauth/{provider}/callback"
    expected_output = {"status_code": 401, "code": "authentication_error"}

    _stub_exchange(monkeypatch)
    monkeypatch.setenv("COOKIE_SIGNING_SECRET", "an-attackers-secret-0123456789abcdef")
    get_settings.cache_clear()
    forged = sign_payload(
        {"verifier": "attacker-verifier", "next": "/anything"}, ttl_seconds=300
    )
    monkeypatch.setenv("COOKIE_SIGNING_SECRET", COOKIE_SECRET)
    get_settings.cache_clear()

    put_cookie(session_client, OAUTH_COOKIE, forged)
    response = session_client.get(OAUTH_CALLBACK, params={"code": "provider-code"})
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/callback"
    assert actual_output == expected_output


def test_api_108_oauth_callback_refuses_an_expired_transaction(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = "GET /api/v1/auth/oauth/{provider}/callback"
    expected_output = {"status_code": 401, "code": "authentication_error"}

    _stub_exchange(monkeypatch)
    put_cookie(
        session_client,
        OAUTH_COOKIE,
        sign_payload({"verifier": "verifier", "next": "/"}, ttl_seconds=-1),
    )
    response = session_client.get(OAUTH_CALLBACK, params={"code": "provider-code"})
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/callback"
    assert actual_output == expected_output


def test_api_109_oauth_callback_without_a_code_is_unauthenticated(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The provider sends the browser back with no code when the user cancels at
    the consent screen. It is a refusal, not a malformed request."""
    endpoint = "GET /api/v1/auth/oauth/{provider}/callback"
    expected_output = {"status_code": 401, "code": "oauth_code_missing"}

    _stub_exchange(monkeypatch)
    session_client.get(OAUTH_START)
    response = session_client.get(OAUTH_CALLBACK)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/auth/oauth/{provider}/callback"
    assert actual_output == expected_output


# ---------------------------------------------------------------------------
# The authenticated call
# ---------------------------------------------------------------------------


def test_api_110_a_resident_endpoint_refuses_a_browser_with_no_session(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = "GET /api/v1/resident/snapshot"
    expected_output = {"status_code": 401, "code": "authentication_error"}

    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    response = session_client.get(SNAPSHOT)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/resident/snapshot"
    assert actual_output == expected_output


def test_api_111_a_resident_endpoint_refuses_a_forged_access_cookie(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Signed with the right algorithm and the wrong key. `decode_token` verifies
    the signature rather than reading the claims, so this is a `401` and not a
    session belonging to whoever the `sub` claim names."""
    endpoint = "GET /api/v1/resident/snapshot"
    expected_output = {"status_code": 401, "code": "authentication_error"}

    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    forged = jwt.encode(
        {"sub": PROFILE_ID, "aud": "authenticated", "exp": int(time.time()) + 3600},
        "not-the-projects-jwt-secret",
        algorithm="HS256",
    )
    put_cookie(session_client, cookie_name("access"), forged)
    response = session_client.get(SNAPSHOT)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/resident/snapshot"
    assert actual_output == expected_output


def test_api_112_a_resident_endpoint_reports_an_expired_session_distinguishably(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`token_expired` is the signal the client refreshes on. If it arrived as a
    generic `authentication_error` the browser would sign the user out on every
    hourly expiry instead of quietly renewing."""
    endpoint = "GET /api/v1/resident/snapshot"
    expected_output = {"status_code": 401, "code": "token_expired"}

    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    put_cookie(session_client, cookie_name("access"), access_token(expires_in=-3600))
    response = session_client.get(SNAPSHOT)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/resident/snapshot"
    assert actual_output == expected_output


def test_api_113_a_signed_in_user_with_no_community_is_told_so_not_refused(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case a newly-registered user is in for exactly as long as it takes them
    to join or create a community. It has to be distinguishable from *not signed
    in*, or the frontend sends them back to a sign-in page they have already
    completed and the loop never ends. `403` with `active_membership_required` is
    the frontend's cue to show the Join/Create chooser."""
    endpoint = "GET /api/v1/resident/snapshot"
    expected_output = {"status_code": 403, "code": "active_membership_required"}

    stub_membership(monkeypatch, rows=[])
    stub_snapshot(monkeypatch)
    sign_in(session_client)
    response = session_client.get(SNAPSHOT)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "GET /api/v1/resident/snapshot"
    assert actual_output == expected_output


def test_api_114_a_signed_in_resident_reaches_the_handler_through_the_real_chain(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing here is overridden: the cookie is verified, the membership is
    resolved from a row, and a token-scoped Supabase client is built. This is the
    test that fails if any link in the chain is rewired."""
    endpoint = "GET /api/v1/resident/snapshot"
    expected_output = {"status_code": 200, "unread": 0}

    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    sign_in(session_client)
    response = session_client.get(SNAPSHOT)
    actual_output = {
        "status_code": response.status_code,
        "unread": response.json()["unreadNotifications"],
    }

    assert endpoint == "GET /api/v1/resident/snapshot"
    assert actual_output == expected_output


def test_api_115_the_membership_is_resolved_from_the_database_not_the_token(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A token claiming to be an admin changes nothing: the role comes from
    `community_memberships`. The claim below is ignored, and the resolved role is
    whatever the row says."""
    from app.api import deps

    endpoint = "GET /api/v1/resident/snapshot"
    expected_output = {"status_code": 200, "resolved_role": "resident"}

    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    boastful = jwt.encode(
        {
            "sub": PROFILE_ID,
            "aud": "authenticated",
            "user_role": "ADMIN",
            "role": "service_role",
            "exp": int(time.time()) + 3600,
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    sign_in(session_client, token=boastful)
    response = session_client.get(SNAPSHOT)
    resolved = deps.get_active_membership(deps.decode_token(boastful))
    actual_output = {
        "status_code": response.status_code,
        "resolved_role": resolved.role,
    }

    assert endpoint == "GET /api/v1/resident/snapshot"
    assert actual_output == expected_output


def test_api_116_a_bearer_header_authenticates_the_same_call(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cookie is for browsers; the header is what the contract has always
    documented and what a non-browser caller uses. Both must reach the same place,
    or the OpenAPI security scheme is describing something that does not work."""
    endpoint = "GET /api/v1/resident/snapshot"
    expected_output = {"status_code": 200}

    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    response = session_client.get(
        SNAPSHOT, headers={"Authorization": f"Bearer {access_token()}"}
    )
    actual_output = {"status_code": response.status_code}

    assert endpoint == "GET /api/v1/resident/snapshot"
    assert actual_output == expected_output


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


def _stub_revoke(monkeypatch: pytest.MonkeyPatch, *, failing: bool = False) -> None:
    from app.api.v1.routers import auth as auth_router
    from app.core.exceptions import AuthenticationError

    def revoke(**_: Any) -> None:
        if failing:
            raise AuthenticationError("Provider rejected the revocation.")

    monkeypatch.setattr(auth_router.auth_service, "revoke_session", revoke)


def test_api_117_logout_clears_the_session_and_the_next_call_is_refused(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The property that matters is the second half. A logout that returns `200`
    and leaves a usable cookie behind is worse than no logout at all, because the
    user has been told they are signed out."""
    endpoint = "POST /api/v1/auth/logout"
    expected_output = {"status_code": 200, "after_logout": 401}

    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    _stub_revoke(monkeypatch)
    token = sign_in(session_client)
    assert session_client.get(SNAPSHOT).status_code == 200

    response = session_client.post(
        LOGOUT, headers={"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": token}
    )
    after = session_client.get(SNAPSHOT)
    actual_output = {
        "status_code": response.status_code,
        "after_logout": after.status_code,
    }

    assert endpoint == "POST /api/v1/auth/logout"
    assert actual_output == expected_output
    for name in (cookie_name("access"), cookie_name("refresh"), cookie_name("csrf")):
        assert session_client.cookies.get(name) is None


def test_api_118_logout_clears_the_session_even_when_the_provider_refuses(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revocation is best-effort by design. If Supabase is unreachable, the local
    session must still end — otherwise a provider outage is also a security
    incident, because nobody in the building can sign out."""
    endpoint = "POST /api/v1/auth/logout"
    expected_output = {"status_code": 200, "after_logout": 401}

    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    _stub_revoke(monkeypatch, failing=True)
    token = sign_in(session_client)

    response = session_client.post(
        LOGOUT, headers={"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": token}
    )
    after = session_client.get(SNAPSHOT)
    actual_output = {
        "status_code": response.status_code,
        "after_logout": after.status_code,
    }

    assert endpoint == "POST /api/v1/auth/logout"
    assert actual_output == expected_output


def test_api_119_logout_works_when_the_access_token_has_already_expired(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Logout deliberately does not depend on `get_current_user`. The user whose
    token expired while the tab was open is precisely the one who presses Sign
    out, and a logout that first verifies the token would refuse them."""
    endpoint = "POST /api/v1/auth/logout"
    expected_output = {"status_code": 200}

    _stub_revoke(monkeypatch)
    expired = access_token(expires_in=-3600)
    token = sign_in(session_client, token=expired)

    response = session_client.post(
        LOGOUT, headers={"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": token}
    )
    actual_output = {"status_code": response.status_code}

    assert endpoint == "POST /api/v1/auth/logout"
    assert actual_output == expected_output
    assert session_client.cookies.get(cookie_name("access")) is None


def test_api_120_logout_refuses_a_cross_origin_caller(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forced logout is a real nuisance attack, and `POST` with no body is the
    easiest thing in the world for another origin to submit."""
    endpoint = "POST /api/v1/auth/logout"
    expected_output = {"status_code": 403, "code": "csrf_origin_invalid"}

    _stub_revoke(monkeypatch)
    token = sign_in(session_client)
    response = session_client.post(
        LOGOUT,
        headers={"Origin": "https://evil.example", "X-CSRF-Token": token},
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "POST /api/v1/auth/logout"
    assert actual_output == expected_output
    # The session survives a refused logout, which is the point of refusing it.
    assert session_client.cookies.get(cookie_name("access"))


def test_api_121_logout_refuses_a_csrf_token_that_is_not_bound_to_the_session(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cookie and the header matching is not enough on its own — an attacker
    who can set a cookie can set both. The token is an HMAC of the access token,
    so one lifted from a different session does not verify against this one."""
    endpoint = "POST /api/v1/auth/logout"
    expected_output = {"status_code": 403, "code": "csrf_invalid"}

    _stub_revoke(monkeypatch)
    sign_in(session_client)
    someone_elses = csrf_token(access_token(subject="a-different-user"))
    put_cookie(session_client, cookie_name("csrf"), someone_elses)

    response = session_client.post(
        LOGOUT,
        headers={"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": someone_elses},
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint == "POST /api/v1/auth/logout"
    assert actual_output == expected_output


def test_api_122_logout_is_idempotent_for_a_browser_that_has_no_session(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pressing Sign out twice, or landing on a stale tab, must not produce an
    error page. With no access cookie the pre-auth CSRF token is what authorizes
    the call, and the answer is the same `200`."""
    endpoint = "POST /api/v1/auth/logout"
    expected_output = {"status_code": 200}

    _stub_revoke(monkeypatch)
    session_client.get("/api/v1/auth/csrf")
    preauth = session_client.cookies.get(PREAUTH_CSRF_COOKIE)
    response = session_client.post(
        LOGOUT, headers={"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": preauth}
    )
    actual_output = {"status_code": response.status_code}

    assert endpoint == "POST /api/v1/auth/logout"
    assert actual_output == expected_output


def test_api_123_the_whole_round_trip_signs_in_reads_and_signs_out(
    session_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Start, callback, an authenticated read, logout, and a refused read — in one
    client, with one cookie jar, in the order a browser does them. The individual
    steps are tested above; what this adds is that the cookies one step sets are
    the cookies the next step accepts."""
    endpoint = "GET /api/v1/resident/snapshot"
    expected_output = {
        "start": 307,
        "callback": 307,
        "read": 200,
        "logout": 200,
        "read_after_logout": 401,
    }

    token = access_token()
    stub_membership(monkeypatch)
    stub_snapshot(monkeypatch)
    _stub_exchange(monkeypatch, token=token)
    _stub_revoke(monkeypatch)

    start = session_client.get(OAUTH_START, params={"next": "/resident/dashboard"})
    callback = session_client.get(OAUTH_CALLBACK, params={"code": "provider-code"})
    read = session_client.get(SNAPSHOT)
    logout = session_client.post(
        LOGOUT,
        headers={
            "Origin": FRONTEND_ORIGIN,
            "X-CSRF-Token": session_client.cookies.get(cookie_name("csrf")),
        },
    )
    read_after_logout = session_client.get(SNAPSHOT)
    actual_output = {
        "start": start.status_code,
        "callback": callback.status_code,
        "read": read.status_code,
        "logout": logout.status_code,
        "read_after_logout": read_after_logout.status_code,
    }

    assert endpoint == "GET /api/v1/resident/snapshot"
    assert actual_output == expected_output
