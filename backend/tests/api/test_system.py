"""System and authorization-boundary API cases."""

from fastapi.testclient import TestClient


def test_api_001_health_check_returns_environment(api_client: TestClient) -> None:
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


def test_api_002_dashboard_snapshot_rejects_unauthenticated_request(
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
