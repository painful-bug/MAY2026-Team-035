"""Complaint workflow API cases."""

import pytest
from fastapi.testclient import TestClient

from app.domain.complaint_schemas import AddCommentRequest, UpdateComplaintRequest


def test_api_009_admin_updates_complaint_progress(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import complaints as complaints_router

    endpoint = "PATCH /api/v1/complaints/complaint-id"
    input_data = {
        "status": "In Progress",
        "progress": 60,
        "updateNote": "Electrician assigned and inspection started.",
    }
    expected_output = {
        "status_code": 200,
        "body": {"message": "Complaint updated."},
    }
    captured_input: dict[str, object] = {}

    def update_complaint(
        _: object,
        user_id: str,
        complaint_id: str,
        body: UpdateComplaintRequest,
    ) -> None:
        captured_input.update(
            body.model_dump(mode="json", by_alias=True, exclude_unset=True)
        )
        assert user_id == "admin-profile-id"
        assert complaint_id == "complaint-id"

    monkeypatch.setattr(
        complaints_router.complaints_service,
        "update_complaint",
        update_complaint,
    )

    response = admin_api_client.patch(
        "/api/v1/complaints/complaint-id",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "PATCH /api/v1/complaints/complaint-id"
    assert captured_input == input_data
    assert actual_output == expected_output


def test_api_010_resident_comments_on_complaint(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import complaints as complaints_router

    endpoint = "POST /api/v1/complaints/complaint-id/comments"
    input_data = {
        "message": "The issue is still visible near the entrance.",
        "visibility": "resident",
    }
    expected_output = {
        "status_code": 201,
        "body": {"message": "Comment added."},
    }
    captured_input: dict[str, object] = {}

    def add_comment(
        _: object,
        user_id: str,
        complaint_id: str,
        body: AddCommentRequest,
    ) -> None:
        captured_input.update(body.model_dump(mode="json", by_alias=True))
        assert user_id == "resident-profile-id"
        assert complaint_id == "complaint-id"

    monkeypatch.setattr(
        complaints_router.complaints_service,
        "add_comment",
        add_comment,
    )

    response = resident_api_client.post(
        "/api/v1/complaints/complaint-id/comments",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/complaints/complaint-id/comments"
    assert captured_input == input_data
    assert actual_output == expected_output
