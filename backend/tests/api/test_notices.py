"""Notice publication API cases."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.domain.notice_schemas import CreateNoticeRequest, NoticeCreated


def test_api_011_admin_publishes_notice(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import notices as notices_router

    endpoint = "POST /api/v1/notices"
    input_data = {
        "title": "Water supply maintenance",
        "description": "Supply will pause between 10 AM and noon.",
        "category": "Maintenance",
        "urgency": "Important",
    }
    expected_output = {
        "status_code": 201,
        "body": {
            "id": "notice-id",
            **input_data,
            "publishedAt": "2026-08-02T10:00:00Z",
            "createdAt": "2026-08-02T10:00:00Z",
        },
    }
    captured_input: dict[str, object] = {}

    def create_notice(
        _: object,
        *,
        community_id: str,
        membership_id: str,
        body: CreateNoticeRequest,
    ) -> NoticeCreated:
        captured_input.update(body.model_dump(mode="json", by_alias=True))
        assert community_id == "community-id"
        assert membership_id == "admin-membership-id"
        timestamp = datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)
        return NoticeCreated(
            id="notice-id",
            **body.model_dump(),
            published_at=timestamp,
            created_at=timestamp,
        )

    monkeypatch.setattr(
        notices_router.notices_service,
        "create_notice",
        create_notice,
    )

    response = admin_api_client.post(
        "/api/v1/notices",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/notices"
    assert captured_input == input_data
    assert actual_output == expected_output


def test_api_012_notice_rejects_empty_title(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
) -> None:
    endpoint = "POST /api/v1/notices"
    input_data = {"title": "", "description": "A valid description."}
    expected_output = {
        "status_code": 422,
        "error_code": "request_validation_error",
    }

    response = admin_api_client.post(
        "/api/v1/notices",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/notices"
    assert actual_output["status_code"] == expected_output["status_code"]
    assert actual_output["body"]["error"]["code"] == expected_output["error_code"]
