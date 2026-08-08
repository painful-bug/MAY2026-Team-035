from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from postgrest.exceptions import APIError

from app.config import Settings
from app.core.exceptions import ServiceUnavailableError
from app.domain.schemas import (
    CommunityOnboardingRequest,
    CreateAccessRequest,
    DashboardSnapshot,
    MembershipContext,
    PasswordSignUpRequest,
)
from app.services.auth_service import start_google_oauth


def _settings(**overrides: str) -> Settings:
    values = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "anon",
        "SUPABASE_SERVICE_ROLE_KEY": "service",
        "COOKIE_SIGNING_SECRET": "test-secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_google_and_email_password_are_supported_configured_methods() -> None:
    settings = _settings()
    settings.validate_auth_configuration()
    assert settings.enabled_auth_methods == ["google", "email_password"]


def test_unsupported_auth_method_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported authentication methods"):
        _settings(AUTH_ENABLED_METHODS="google,password").validate_auth_configuration()


def test_auth_methods_can_swap_primary_without_changing_enabled_order() -> None:
    settings = _settings(
        AUTH_PRIMARY_METHOD="email_password",
        AUTH_ENABLED_METHODS="email_password,google",
    )
    settings.validate_auth_configuration()
    assert settings.auth_primary_method == "email_password"
    assert settings.enabled_auth_methods == ["email_password", "google"]


def test_password_signup_requires_a_long_password() -> None:
    with pytest.raises(ValidationError):
        PasswordSignUpRequest(full_name="Test User", email="test@example.com", password="short")


def test_community_search_reports_an_unapplied_blacklist_schema_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rollout mismatch must be a safe 503, never a blacklist-bypassing fallback."""
    from app.services import community_directory_service

    monkeypatch.setattr(community_directory_service, "get_service_client", lambda: object())

    def missing_rpc(*_: object, **__: object) -> list[dict]:
        raise APIError(
            {
                "message": "Could not find the function public.search_joinable_communities(p_limit, p_profile_id, p_query) in the schema cache",
                "code": "PGRST202",
                "hint": None,
                "details": None,
            }
        )

    monkeypatch.setattr(
        community_directory_service.communities_repository,
        "search_joinable_communities",
        missing_rpc,
    )

    with pytest.raises(ServiceUnavailableError) as raised:
        community_directory_service.search("Palm", 10, "profile-id")

    assert raised.value.code == "community_search_schema_unavailable"
    assert raised.value.status_code == 503


def test_google_authorize_url_leaves_provider_state_to_supabase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("BACKEND_BASE_URL", "http://localhost:8000")
    from app.config import get_settings

    get_settings.cache_clear()
    url, transaction = start_google_oauth()
    params = parse_qs(urlparse(url).query)

    assert params["provider"] == ["google"]
    assert params["redirect_to"] == [
        "http://localhost:8000/api/v1/auth/google/callback"
    ]
    assert params["code_challenge_method"] == ["s256"]
    assert "state" not in params
    assert set(transaction) == {"verifier"}
    get_settings.cache_clear()


def test_access_request_rejects_client_owned_identity_fields() -> None:
    with pytest.raises(ValidationError):
        CreateAccessRequest(
            community_id="community-id",
            requested_relationship="tenant",
            applicant_email="forged@example.com",
        )


def test_founder_contract_rejects_inline_profile_image() -> None:
    with pytest.raises(ValidationError):
        CommunityOnboardingRequest(
            name="Palm Grove Residency",
            community_type="apartment",
            address_line1="12 Palm Grove Road",
            city="Kolkata",
            state="West Bengal",
            postal_code="700001",
            blocks=[{"id": "block-1", "name": "Block A"}],
            block_locations={"block-1": {"x": 50, "y": 50}},
            admin_profile={
                "fullName": "Founder Admin",
                "unitNumber": "A-101",
                "founderStructureId": "block-1",
                "profileImage": "data:image/png;base64,not-allowed",
            },
        )


def test_legacy_bridge_installs_founder_rpc_only_when_missing() -> None:
    bridge = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "0006_legacy_founder_onboarding_bridge.sql"
    ).read_text()
    assert "to_regprocedure('public.create_founder_community(jsonb)') is null" in bridge
    assert (
        "grant execute on function public.create_founder_community(jsonb) "
        "to service_role"
    ) in bridge


def test_founder_rpc_compatibility_migration_replaces_stale_legacy_functions() -> None:
    bridge = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "20260805144502_replace_legacy_founder_rpc.sql"
    ).read_text()
    assert "create or replace function public.create_founder_community" in bridge
    assert "column_name='address_line2'" in bridge
    assert "column_name='payload'" in bridge
    assert (
        "grant execute on function public.create_founder_community(jsonb) "
        "to service_role"
    ) in bridge


def test_community_status_compatibility_migration_normalizes_legacy_values() -> None:
    migration = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "20260730163759_normalize_community_statuses.sql"
    ).read_text()
    assert "set status = lower(btrim(status))" in migration
    assert "communities_status_canonical" in migration


def test_join_and_invitation_flows_do_not_require_an_email_confirmation_claim() -> None:
    access_service = (
        Path(__file__).parents[1] / "app" / "services" / "access_request_service.py"
    ).read_text()
    invitation_service = (
        Path(__file__).parents[1] / "app" / "services" / "invitation_service.py"
    ).read_text()
    assert "not principal.email_verified" not in access_service
    assert "not identity.email_verified" not in invitation_service


def test_access_request_identity_compatibility_migration_preserves_legacy_rows() -> None:
    migration = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "20260730164555_add_access_request_applicant_profile.sql"
    ).read_text()
    assert "add column if not exists applicant_profile_id uuid" in migration
    assert "check (applicant_profile_id is not null) not valid" in migration
    assert "access_requests_one_pending_per_profile_community" in migration


def test_resident_access_request_decision_rpcs_are_available_for_legacy_projects() -> None:
    migration = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "20260730165410_add_resident_access_request_decision_rpcs.sql"
    ).read_text()
    assert "create or replace function public.approve_access_request(" in migration
    assert "create or replace function public.reject_access_request(" in migration
    assert "p_reviewer_profile_id uuid" in migration


def test_resident_approval_handles_both_legacy_and_baseline_unique_indexes() -> None:
    migration = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "20260730170036_make_resident_approval_legacy_index_compatible.sql"
    ).read_text()
    assert "when unique_violation then" in migration
    assert "on conflict (community_id, profile_id)" not in migration


def test_dashboard_realtime_bridge_is_tenant_scoped() -> None:
    bridge = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "0007_dashboard_realtime_outbox.sql"
    ).read_text()
    assert "create table if not exists public.sse_events" in bridge
    assert "sse_events (community_id, id)" in bridge
    assert "dashboard.refresh" in bridge
    assert "community_memberships" in bridge
    assert "notices" in bridge


def test_auth_method_and_registration_routes_are_mounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "anon",
        "SUPABASE_SERVICE_ROLE_KEY": "service",
        "COOKIE_SIGNING_SECRET": "test-secret",
        "AUTH_PRIMARY_METHOD": "google",
        "AUTH_ENABLED_METHODS": "google",
    }.items():
        monkeypatch.setenv(key, value)

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    client.get("/api/v1/auth/csrf")
    response = client.get("/api/v1/auth/methods")
    assert response.status_code == 200
    assert response.json()["primary"] == "google"
    assert response.headers["cache-control"] == "public, max-age=300"
    assert client.get("/api/v1/communities/search?q=pa").status_code == 401
    assert client.get("/api/v1/access-requests/mine").status_code == 401
    assert client.get("/api/v1/admin/access-requests").status_code == 401
    assert client.get("/api/v1/dashboard/snapshot").status_code == 401
    assert client.get("/api/v1/dashboard/events").status_code == 401
    get_settings.cache_clear()


def test_stalled_refresh_does_not_block_public_auth_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider I/O must not freeze the login screen's public configuration."""
    for key, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "anon",
        "SUPABASE_SERVICE_ROLE_KEY": "service",
        "COOKIE_SIGNING_SECRET": "test-secret",
    }.items():
        monkeypatch.setenv(key, value)

    from app.api.v1.routers import auth as auth_router
    from app.config import get_settings
    from app.core.web_session import cookie_name
    from app.main import create_app

    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200

    def stalled_refresh(_: str) -> None:
        time.sleep(0.05)

    monkeypatch.setattr(auth_router.auth_service, "refresh_session", stalled_refresh)
    original_get_settings = auth_router.get_settings
    monkeypatch.setattr(
        auth_router,
        "get_settings",
        lambda: SimpleNamespace(auth_provider_timeout_seconds=0.001),
    )
    client.cookies.set(cookie_name("refresh"), "refresh-token")
    response = client.post(
        "/api/v1/auth/refresh",
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": client.cookies.get("hb_preauth_csrf", domain="testserver") or client.cookies.get("hb_preauth_csrf") or "",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_provider_timeout"
    monkeypatch.setattr(auth_router, "get_settings", original_get_settings)
    assert client.get("/api/v1/auth/methods").status_code == 200
    get_settings.cache_clear()


def test_dashboard_snapshot_does_not_block_the_api_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow tenant projection must leave public auth routes schedulable."""
    from app.api.v1.routers import dashboard as dashboard_router

    def slow_snapshot(_: MembershipContext) -> DashboardSnapshot:
        time.sleep(0.05)
        return DashboardSnapshot()

    monkeypatch.setattr(dashboard_router.dashboard_service, "snapshot", slow_snapshot)
    membership = MembershipContext(
        id="membership-id", community_id="community-id", role="admin"
    )

    async def verify() -> None:
        task = asyncio.create_task(
            dashboard_router.get_dashboard_snapshot(membership)
        )
        await asyncio.sleep(0.002)
        assert not task.done()
        assert await task == DashboardSnapshot()

    asyncio.run(verify())
