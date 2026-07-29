from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.domain.schemas import CommunityOnboardingRequest, CreateAccessRequest
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


def test_google_is_the_only_supported_configured_method() -> None:
    settings = _settings()
    settings.validate_auth_configuration()
    assert settings.enabled_auth_methods == ["google"]


def test_unsupported_auth_method_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported authentication methods"):
        _settings(AUTH_ENABLED_METHODS="google,password").validate_auth_configuration()


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
    response = client.get("/api/v1/auth/methods")
    assert response.status_code == 200
    assert response.json()["primary"] == "google"
    assert client.get("/api/v1/communities/search?q=pa").status_code == 401
    assert client.get("/api/v1/access-requests/mine").status_code == 401
    assert client.get("/api/v1/admin/access-requests").status_code == 401
    assert client.get("/api/v1/dashboard/snapshot").status_code == 401
    assert client.get("/api/v1/dashboard/events").status_code == 401
    get_settings.cache_clear()
