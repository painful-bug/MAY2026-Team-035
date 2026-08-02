"""Endpoint-level API cases prepared for the Milestone 3 submission.

Each test keeps the course-required evidence visible in the function body:
endpoint, input, expected output, actual output, and the assertion that determines
the result.  The tests use FastAPI's in-process ``TestClient`` and replace only
external Supabase/provider calls, so no network or staging database is required.

The final test reproduces a real contract mismatch between the generated OpenAPI
422 schema and the runtime error envelope.  It is skipped in the normal suite so
the project stays green.  Run it explicitly when capturing the required failing
test evidence::

    HOMEBANDHU_MILESTONE3_FAILURE_DEMO=1 \
      uv run --extra dev pytest \
      tests/test_milestone3_api_cases.py -k failure_demo -vv
"""

from __future__ import annotations

import os
import time
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_request_client
from app.config import get_settings
from app.domain.amenity_schemas import CancelBookingRequest
from app.main import create_app

_FRONTEND_ORIGIN = "http://localhost:5173"
_RUN_FAILURE_DEMO = (
    os.getenv("HOMEBANDHU_MILESTONE3_FAILURE_DEMO", "").strip() == "1"
)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Create an isolated API client with deterministic, non-secret settings."""
    for key, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "placeholder-anon-key",
        "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
        "SUPABASE_JWT_SECRET": "placeholder-jwt-secret",
        "COOKIE_SIGNING_SECRET": "placeholder-cookie-signing-secret-0123456789",
        "AUTH_PRIMARY_METHOD": "google",
        "AUTH_ENABLED_METHODS": "google,email_password",
        "AUTH_PROVIDER_TIMEOUT_SECONDS": "0.001",
        "FRONTEND_BASE_URL": _FRONTEND_ORIGIN,
        "CORS_ORIGINS": _FRONTEND_ORIGIN,
        "ENV": "testing",
    }.items():
        monkeypatch.setenv(key, value)

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def _csrf_headers(client: TestClient) -> dict[str, str]:
    """Start the pre-auth CSRF flow and return the unsafe-request headers."""
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    token = client.cookies.get("hb_preauth_csrf")
    assert token
    return {"Origin": _FRONTEND_ORIGIN, "X-CSRF-Token": token}


def test_m3_api_001_health_check_returns_environment(api_client: TestClient) -> None:
    endpoint = "GET /health"
    input_data = {"method": "GET", "path": "/health"}
    expected_output = {
        "status_code": 200,
        "body": {"status": "ok", "env": "testing"},
    }

    response = api_client.get(input_data["path"])
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "GET /health"
    assert actual_output == expected_output


def test_m3_api_002_auth_methods_returns_configured_methods(
    api_client: TestClient,
) -> None:
    endpoint = "GET /api/v1/auth/methods"
    input_data = {"method": "GET", "path": "/api/v1/auth/methods"}
    expected_output = {
        "status_code": 200,
        "body": {
            "primary": "google",
            "methods": [
                {
                    "id": "google",
                    "kind": "redirect",
                    "label": "Continue with Google",
                    "enabled": True,
                },
                {
                    "id": "email_password",
                    "kind": "credentials",
                    "label": "Continue with email",
                    "enabled": True,
                },
            ],
        },
    }

    response = api_client.get(input_data["path"])
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "GET /api/v1/auth/methods"
    assert actual_output == expected_output
    assert response.headers["cache-control"] == "public, max-age=300"


def test_m3_api_003_dashboard_snapshot_rejects_unauthenticated_request(
    api_client: TestClient,
) -> None:
    endpoint = "GET /api/v1/dashboard/snapshot"
    input_data = {"method": "GET", "path": "/api/v1/dashboard/snapshot"}
    expected_output = {
        "status_code": 401,
        "body": {
            "error": {
                "code": "authentication_error",
                "message": "Missing bearer token.",
            }
        },
    }

    response = api_client.get(input_data["path"])
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "GET /api/v1/dashboard/snapshot"
    assert actual_output == expected_output


def test_m3_api_004_partial_booking_cancellation_returns_cancelled_day_count(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import amenities as amenities_router

    endpoint = "POST /api/v1/amenity-bookings/cancel"
    input_data = {
        "occurrenceIds": ["booking-day-1", "booking-day-3"],
        "reasonCode": "schedule_change",
        "reason": "Only selected dates should be cancelled.",
    }
    expected_output = {
        "status_code": 200,
        "body": {"message": "2 booking day(s) cancelled."},
    }
    captured_input: dict[str, object] = {}

    def cancel_selected_days(_: object, request: CancelBookingRequest) -> int:
        captured_input.update(request.model_dump(mode="json", by_alias=True))
        return 2

    api_client.app.dependency_overrides[get_request_client] = lambda: object()
    monkeypatch.setattr(
        amenities_router.amenities_service,
        "cancel_bookings",
        cancel_selected_days,
    )

    response = api_client.post(
        "/api/v1/amenity-bookings/cancel",
        json=input_data,
        headers=_csrf_headers(api_client),
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/amenity-bookings/cancel"
    assert captured_input == input_data
    assert actual_output == expected_output


def test_m3_api_005_refresh_timeout_returns_service_unavailable(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import auth as auth_router
    from app.core.web_session import cookie_name

    endpoint = "POST /api/v1/auth/refresh"
    input_data = {"refresh_cookie": "refresh-token"}
    expected_output = {
        "status_code": 503,
        "body": {
            "error": {
                "code": "auth_provider_timeout",
                "message": (
                    "The authentication provider did not respond in time. "
                    "Please try again."
                ),
            }
        },
    }

    def stalled_refresh(_: str) -> None:
        time.sleep(0.05)

    monkeypatch.setattr(
        auth_router.auth_service,
        "refresh_session",
        stalled_refresh,
    )
    api_client.cookies.set(cookie_name("refresh"), input_data["refresh_cookie"])

    response = api_client.post(
        "/api/v1/auth/refresh",
        headers=_csrf_headers(api_client),
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/auth/refresh"
    assert actual_output == expected_output


@pytest.mark.skipif(
    not _RUN_FAILURE_DEMO,
    reason=(
        "Set HOMEBANDHU_MILESTONE3_FAILURE_DEMO=1 to reproduce the documented "
        "OpenAPI/runtime 422 mismatch for the submission screenshot."
    ),
)
def test_m3_api_006_failure_demo_documented_422_matches_runtime(
    api_client: TestClient,
) -> None:
    endpoint = "POST /api/v1/auth/password/sign-in"
    input_data: dict[str, object] = {}

    specification = api_client.app.openapi()
    documented_schema = specification["paths"][
        "/api/v1/auth/password/sign-in"
    ]["post"]["responses"]["422"]["content"]["application/json"]["schema"]
    component_name = documented_schema["$ref"].rsplit("/", 1)[-1]
    expected_body_keys = set(
        specification["components"]["schemas"][component_name]["properties"]
    )

    response = api_client.post(
        "/api/v1/auth/password/sign-in",
        json=input_data,
        headers=_csrf_headers(api_client),
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert response.status_code == 422
    assert expected_body_keys <= set(actual_output["body"]), (
        f"API endpoint: {endpoint}\n"
        f"Input: {input_data}\n"
        f"Expected output: HTTP 422 with body keys "
        f"{sorted(expected_body_keys)}\n"
        f"Actual output: {actual_output}\n"
        "Result: FAILED - the generated OpenAPI schema and runtime error "
        "envelope do not match."
    )
