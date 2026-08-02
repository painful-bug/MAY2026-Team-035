"""Resident access-request and administrator-decision API cases."""

import pytest
from fastapi.testclient import TestClient

from app.domain.schemas import AccessRequestCommunity, AccessRequestResponse


def test_api_005_resident_creates_access_request(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import access_requests as access_router

    endpoint = "POST /api/v1/access-requests"
    input_data = {
        "community_id": "community-id",
        "requested_unit_id": "unit-id",
        "requested_relationship": "tenant",
        "phone": "+919876543210",
    }
    expected_output = {
        "status_code": 201,
        "body": {
            "id": "request-id",
            "community": {"id": "community-id", "name": "Palm Residency"},
            "status": "pending",
            "requested_relationship": "tenant",
            "requested_unit_id": "unit-id",
            "applicant_name": "Test Resident",
            "applicant_email": "resident@example.com",
            "applicant_phone_e164": "+919876543210",
            "created_at": None,
            "reviewed_at": None,
            "rejection_reason": None,
        },
    }
    captured_input: dict[str, object] = {}

    def create_request(request: object, principal: object) -> AccessRequestResponse:
        captured_input.update(request.model_dump(mode="json"))
        assert principal.user_id == "resident-profile-id"
        return AccessRequestResponse(
            id="request-id",
            community=AccessRequestCommunity(
                id="community-id",
                name="Palm Residency",
            ),
            status="pending",
            requested_relationship="tenant",
            requested_unit_id="unit-id",
            applicant_name="Test Resident",
            applicant_email="resident@example.com",
            applicant_phone_e164="+919876543210",
        )

    monkeypatch.setattr(access_router.access_request_service, "create", create_request)

    response = resident_api_client.post(
        "/api/v1/access-requests",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/access-requests"
    assert captured_input == input_data
    assert actual_output == expected_output


def test_api_006_admin_approves_access_request(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import access_requests as access_router

    endpoint = "POST /api/v1/admin/access-requests/request-id/approve"
    input_data = {"unit_id": "unit-id", "relationship": "tenant"}
    expected_output = {
        "status_code": 200,
        "body": {
            "request_id": "request-id",
            "status": "approved",
            "membership_id": "resident-membership-id",
        },
    }
    captured_input: dict[str, object] = {}

    def approve_request(
        request_id: str,
        body: object,
        principal: object,
    ) -> dict[str, str]:
        captured_input.update(body.model_dump(mode="json"))
        assert request_id == "request-id"
        assert principal.user_id == "admin-profile-id"
        return expected_output["body"]

    monkeypatch.setattr(
        access_router.access_request_service,
        "approve",
        approve_request,
    )

    response = admin_api_client.post(
        "/api/v1/admin/access-requests/request-id/approve",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint.endswith("/request-id/approve")
    assert captured_input == input_data
    assert actual_output == expected_output
