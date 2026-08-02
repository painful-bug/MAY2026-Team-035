"""Community-settings validation API cases."""

from fastapi.testclient import TestClient


def test_api_015_settings_rejects_timezone_with_whitespace(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
) -> None:
    endpoint = "PUT /api/v1/settings"
    input_data = {"timezone": "Asia / Kolkata"}
    expected_output = {
        "status_code": 422,
        "error_code": "request_validation_error",
    }

    response = admin_api_client.put(
        "/api/v1/settings",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "PUT /api/v1/settings"
    assert actual_output["status_code"] == expected_output["status_code"]
    assert actual_output["body"]["error"]["code"] == expected_output["error_code"]
