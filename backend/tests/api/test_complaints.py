"""Complaint workflow API cases.

The first two cases monkeypatch the service, which is the house pattern and the
right one for asserting routing, validation and status codes. It is also why two
real defects lived here undetected for months: the service called a repository
function that has never existed, and forwarded a `visibility` the database
rejects. **A test that replaces the thing under test cannot find a bug inside
it.**

So the last three cases deliberately let the real service run, replacing only the
repository beneath it. They are the ones that would have failed.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_request_client
from app.domain.complaint_schemas import AddCommentRequest, UpdateComplaintRequest


class _ProfileQuery:
    """The slice of the PostgREST builder `_actor_label` uses."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def select(self, *_: Any, **__: Any) -> "_ProfileQuery":
        return self

    def eq(self, *_: Any) -> "_ProfileQuery":
        return self

    def limit(self, *_: Any) -> "_ProfileQuery":
        return self

    def execute(self) -> Any:
        return type("Result", (), {"data": self._rows})()


class _FakeClient:
    def table(self, _name: str) -> _ProfileQuery:
        return _ProfileQuery([{"full_name": "Priya Nair"}])


@pytest.fixture
def live_service_client(admin_api_client: TestClient) -> TestClient:
    """An admin client whose Supabase handle answers `_actor_label`.

    The shared fixture's client is a bare `object()` sentinel that must never be
    called -- correct when the service is stubbed, useless when it is not.
    """
    admin_api_client.app.dependency_overrides[get_request_client] = _FakeClient
    return admin_api_client


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
        membership_id: str,
        complaint_id: str,
        body: UpdateComplaintRequest,
    ) -> None:
        captured_input.update(
            body.model_dump(mode="json", by_alias=True, exclude_unset=True)
        )
        assert user_id == "admin-profile-id"
        assert membership_id == "admin-membership-id"
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
        membership_id: str,
        complaint_id: str,
        body: AddCommentRequest,
    ) -> None:
        captured_input.update(body.model_dump(mode="json", by_alias=True))
        assert user_id == "resident-profile-id"
        assert membership_id == "resident-membership-id"
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


def test_api_133_a_comment_reaches_the_database_as_public_not_as_resident(
    live_service_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect this case exists for.

    `complaint_comments_visibility_check` allows `public` and `internal`. The
    request says `resident`, because that is what the frontend sends and what
    API.md documents. Forwarding it unmapped made every comment a 23514 -> 422 --
    and `test_api_010` above passed throughout, because it replaced the service
    that does the translating.
    """
    from app.services import complaints_service

    endpoint = "POST /api/v1/complaints/complaint-id/comments"
    input_data = {"message": "Plumber will visit at 4pm.", "visibility": "resident"}
    expected_output = {
        "status_code": 201,
        "visibility": "public",
        "author_membership": "admin-membership-id",
        "author_label": "Priya Nair",
    }
    captured: dict[str, Any] = {}

    def fake_add_comment(_: object, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(complaints_service.repo, "add_comment", fake_add_comment)

    response = live_service_client.post(
        "/api/v1/complaints/complaint-id/comments",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "visibility": captured.get("visibility"),
        "author_membership": captured.get("author_membership"),
        "author_label": captured.get("author_label"),
    }

    assert actual_output == expected_output, endpoint


def test_api_134_an_unknown_visibility_is_a_422_before_the_database_sees_it(
    live_service_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Previously a `409` -- the database's answer to a word it had never heard.

    Raised in the service now, so the error can name the field. The repository
    stub records whether it ran, which is how the case proves the RPC is never
    reached rather than merely that the status code is right.
    """
    from app.services import complaints_service

    endpoint = "POST /api/v1/complaints/complaint-id/comments"
    input_data = {"message": "Noted.", "visibility": "private"}
    expected_output = {
        "status_code": 422,
        "code": "unknown_visibility",
        "reached_repository": False,
    }
    captured: dict[str, Any] = {"reached": False}

    def fake_add_comment(_: object, **__: Any) -> None:
        captured["reached"] = True

    monkeypatch.setattr(complaints_service.repo, "add_comment", fake_add_comment)

    response = live_service_client.post(
        "/api/v1/complaints/complaint-id/comments",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
        "reached_repository": captured["reached"],
    }

    assert actual_output == expected_output, endpoint


def test_api_135_the_edit_carries_the_membership_the_request_already_resolved(
    live_service_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other defect. The service used to call a repository function that has
    never existed in this codebase, so both writes raised `AttributeError` on
    their second line. The membership now arrives from the dependency graph,
    which resolved it before the handler body ran."""
    from app.services import complaints_service

    endpoint = "PATCH /api/v1/complaints/complaint-id"
    input_data = {"status": "In Progress", "progress": 60}
    expected_output = {
        "status_code": 200,
        "status": "in_progress",
        "actor_membership": "admin-membership-id",
        "actor_label": "Priya Nair",
    }
    captured: dict[str, Any] = {}

    def fake_update_complaint(_: object, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(
        complaints_service.repo, "update_complaint", fake_update_complaint
    )

    response = live_service_client.patch(
        "/api/v1/complaints/complaint-id", json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "status": captured.get("status"),
        "actor_membership": captured.get("actor_membership"),
        "actor_label": captured.get("actor_label"),
    }

    assert actual_output == expected_output, endpoint
