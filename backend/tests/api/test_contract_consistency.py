"""Opt-in check for an API contract inconsistency identified during testing."""

import os

import pytest
from fastapi.testclient import TestClient

_RUN_CONTRACT_CHECK = (
    os.getenv("HOMEBANDHU_RUN_CONTRACT_CHECK", "").strip() == "1"
)


@pytest.mark.skipif(
    not _RUN_CONTRACT_CHECK,
    reason=(
        "Set HOMEBANDHU_RUN_CONTRACT_CHECK=1 to reproduce the known "
        "OpenAPI/runtime 422 contract mismatch before applying the fix."
    ),
)
def test_api_016_openapi_422_schema_matches_runtime(
    api_client: TestClient,
    csrf_headers: dict[str, str],
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
        headers=csrf_headers,
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
        "Result: FAILED - initial testing identified a mismatch between the "
        "generated OpenAPI schema and runtime error envelope."
    )
