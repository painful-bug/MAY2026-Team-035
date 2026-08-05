"""Authentication API cases."""

import time

import pytest
from fastapi.testclient import TestClient


def test_api_003_auth_methods_returns_configured_methods(
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


def test_api_004_refresh_timeout_returns_service_unavailable(
    api_client: TestClient,
    csrf_headers: dict[str, str],
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
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/auth/refresh"
    assert actual_output == expected_output


def test_api_005_email_confirmation_establishes_browser_session(
    api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import auth as auth_router
    from app.core.web_session import cookie_name
    from app.services.auth_service import SupabaseSession

    captured: dict[str, str] = {}

    def verify(token_hash: str, verification_type: str) -> SupabaseSession:
        captured.update(token_hash=token_hash, verification_type=verification_type)
        return SupabaseSession("confirmed-access", "confirmed-refresh", 3600)

    monkeypatch.setattr(auth_router.auth_service, "verify_email_token", verify)

    response = api_client.post(
        "/api/v1/auth/email/verify",
        json={"token_hash": "confirmation-token", "verification_type": "signup"},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Email verified."}
    assert captured == {"token_hash": "confirmation-token", "verification_type": "signup"}
    assert api_client.cookies.get(cookie_name("access")) == "confirmed-access"
    assert api_client.cookies.get(cookie_name("refresh")) == "confirmed-refresh"
