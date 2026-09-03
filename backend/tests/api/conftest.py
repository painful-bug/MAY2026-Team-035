"""Shared fixtures for in-process HTTP API tests.

The suite exercises FastAPI routing, request validation, dependencies, response
serialization and exception handling. Supabase and provider calls are replaced at
the service boundary, so these tests need no network or staging database.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.deps import (
    get_active_membership,
    get_current_user,
    get_request_client,
)
from app.config import get_settings
from app.domain.schemas import MembershipContext, Principal
from app.main import create_app

FRONTEND_ORIGIN = "http://localhost:5173"


@pytest.fixture(autouse=True)
def no_unit_residency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nobody in this suite holds a flat unless their test says so.

    ``require_resident_capability`` asks ``unit_residencies`` whether a
    non-``resident`` caller lives here. That is a service-role read, and the
    fixtures below authenticate by overriding dependencies rather than by
    standing up a database -- so without this the first admin to touch a
    resident route would open a real connection to the placeholder Supabase URL
    and turn a 403 assertion into a timeout.

    Default **False**, which is what the fixture memberships describe: only
    ``resident_api_client`` carries a ``unit_id``. A test about the admin who
    does own a flat re-patches this to ``True``; because that happens after this
    autouse fixture has run, the later ``setattr`` is the one that stands.
    """
    monkeypatch.setattr(deps, "_has_active_residency", lambda membership_id: False)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Create an isolated client with deterministic, non-secret settings."""
    for key, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "placeholder-anon-key",
        "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
        "SUPABASE_JWT_SECRET": "placeholder-jwt-secret",
        "COOKIE_SIGNING_SECRET": "placeholder-cookie-signing-secret-0123456789",
        "AUTH_PRIMARY_METHOD": "google",
        "AUTH_ENABLED_METHODS": "google,email_password",
        # A real budget. This used to be "0.001" so the timeout test could
        # prove the 503 path, but that put every provider call in the suite
        # inside a one-millisecond `asyncio.wait_for` -- and the threadpool
        # handoff alone can take ~5ms under a Windows scheduler quantum, so
        # any auth test could sporadically 503 in a full-suite run
        # (test_api_006 was the one observed). The timeout test now pins the
        # millisecond budget on the cached settings object itself.
        "AUTH_PROVIDER_TIMEOUT_SECONDS": "10",
        "FRONTEND_BASE_URL": FRONTEND_ORIGIN,
        "CORS_ORIGINS": FRONTEND_ORIGIN,
        "ENV": "testing",
    }.items():
        monkeypatch.setenv(key, value)

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def _authenticated_client(client: TestClient, *, role: str) -> TestClient:
    principal = Principal(
        user_id=f"{role}-profile-id",
        email=f"{role}@example.com",
        email_verified=True,
        full_name=f"Test {role.title()}",
    )
    membership = MembershipContext(
        id=f"{role}-membership-id",
        community_id="community-id",
        role=role,
        unit_id="unit-id" if role == "resident" else None,
    )
    client.app.dependency_overrides[get_current_user] = lambda: principal
    client.app.dependency_overrides[get_active_membership] = lambda: membership
    client.app.dependency_overrides[get_request_client] = lambda: object()
    return client


@pytest.fixture
def resident_api_client(api_client: TestClient) -> TestClient:
    return _authenticated_client(api_client, role="resident")


@pytest.fixture
def admin_api_client(api_client: TestClient) -> TestClient:
    return _authenticated_client(api_client, role="admin")


@pytest.fixture
def manager_api_client(api_client: TestClient) -> TestClient:
    """A department manager.

    Added when the `/manager` portal was built. Until staff provisioning nothing
    minted a `manager` membership, so this role had never been exercised by a
    test -- which is exactly why the departments router's guards needed one.
    """
    return _authenticated_client(api_client, role="manager")


@pytest.fixture
def worker_api_client(api_client: TestClient) -> TestClient:
    return _authenticated_client(api_client, role="worker")


@pytest.fixture
def csrf_headers(api_client: TestClient) -> dict[str, str]:
    """Start the pre-auth CSRF flow and return unsafe-request headers."""
    response = api_client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    token = api_client.cookies.get("hb_preauth_csrf")
    assert token
    return {"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": token}
