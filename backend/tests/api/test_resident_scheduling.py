"""The resident's answer to a proposed visit.

Two routes, and the interesting property of both is what they do **not** accept:
a work-order id. The job is resolved from the complaint, so naming somebody
else's is not expressible rather than merely refused -- and the tests below
assert that by checking what the repository is asked for, since an endpoint that
took an id would have to be tested for every way of misusing it.

The other thing under test is the choice of *which* job. A complaint may carry
several over its life; the resident cares about the newest live one, and
returning simply the newest would let a cancelled retry hide the visit that
replaced it.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AuthorizationError, ConflictError
from app.services import work_orders_service

SCHEDULE_REQUEST = "/api/v1/complaints/complaint-id/schedule-request"
SCHEDULE = "/api/v1/complaints/complaint-id/schedule"

SLOT_START = "2026-08-12T10:00:00Z"
SLOT_END = "2026-08-12T11:00:00Z"


def work_order_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "work-order-id",
        "community_id": "community-id",
        "complaint_id": "complaint-id",
        "complaint_title": "Kitchen tap leaking",
        "complaint_category": "Plumbing",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "skill_id": "skill-id",
        "skill_name": "Plumber",
        "status": "awaiting_resident",
        "priority": "medium",
        "subject_kind": "resident",
        "location_text": "Flat B-402",
        "scheduled_start_at": SLOT_START,
        "scheduled_end_at": SLOT_END,
        "resident_deadline_at": "2026-08-11T10:00:00Z",
        "failed_attempt_count": 0,
        "cancelled_reason": None,
        "assignee_name": None,
        "staff_assignment_id": None,
        "created_at": "2026-08-10T09:00:00Z",
        "updated_at": "2026-08-10T09:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def scheduling(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository under the live service."""
    captured: dict = {"for_complaint": [work_order_row()]}

    def fake_for_complaint(
        client: Any, *, complaint_id: str
    ) -> list[dict[str, Any]]:
        captured["asked_for"] = complaint_id
        return captured["for_complaint"]

    def fake_respond(client: Any, **kwargs: Any) -> None:
        captured["answered"] = kwargs

    repo = work_orders_service.repo
    monkeypatch.setattr(repo, "list_for_complaint", fake_for_complaint)
    monkeypatch.setattr(repo, "respond_to_schedule", fake_respond)
    yield captured


def test_api_176_the_proposal_is_looked_up_by_complaint_not_by_job_id(
    resident_api_client: TestClient, scheduling: dict
) -> None:
    """The only id in the request path is the complaint's. A resident should not
    have to have read a work-order id to answer a question that was put to them,
    and an endpoint that accepted one would have to decide what happens when it
    names a different complaint's job."""
    endpoint = "GET /api/v1/complaints/complaint-id/schedule-request"
    expected_output = {
        "status_code": 200,
        "asked_for": "complaint-id",
        "work_order_id": "work-order-id",
        "awaiting": True,
    }

    response = resident_api_client.get(SCHEDULE_REQUEST)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "asked_for": scheduling["asked_for"],
        "work_order_id": body["workOrderId"],
        "awaiting": body["awaitingResponse"],
    }

    assert actual_output == expected_output, endpoint


def test_api_177_a_cancelled_retry_does_not_hide_the_visit_that_replaced_it(
    resident_api_client: TestClient, scheduling: dict
) -> None:
    """Newest **live** one, not simply newest. The rows come back newest first,
    and the first terminal one is skipped -- otherwise a job cancelled an hour
    ago would be what the resident sees while a technician is on the way."""
    endpoint = "GET /api/v1/complaints/complaint-id/schedule-request"
    expected_output = {
        "status_code": 200,
        "work_order_id": "live",
        "status": "scheduled",
    }

    scheduling["for_complaint"] = [
        work_order_row(id="dead", status="cancelled"),
        work_order_row(id="live", status="scheduled", assignee_name="Ravi Kumar"),
    ]
    response = resident_api_client.get(SCHEDULE_REQUEST)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "work_order_id": body["workOrderId"],
        "status": body["status"],
    }

    assert actual_output == expected_output, endpoint


def test_api_178_a_complaint_with_no_live_job_is_a_404(
    resident_api_client: TestClient, scheduling: dict
) -> None:
    """Nothing proposed, or everything proposed cancelled. Both are the same
    answer, and both are a 404 rather than an empty body -- a screen that got
    `null` would have to decide whether that meant "not yet" or "never"."""
    endpoint = "GET /api/v1/complaints/complaint-id/schedule-request"
    expected_output = {"status_code": 404, "code": "schedule_request_not_found"}

    scheduling["for_complaint"] = [work_order_row(status="cancelled")]
    response = resident_api_client.get(SCHEDULE_REQUEST)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_179_the_answer_is_confirmed_or_declined_and_nothing_else(
    resident_api_client: TestClient, scheduling: dict, csrf_headers: dict[str, str]
) -> None:
    """Declining is not a counter-proposal and there is no third answer. A
    resident who has changed their mind declines; a supervisor who has is the
    one who cancels."""
    endpoint = "POST /api/v1/complaints/complaint-id/schedule"
    expected_output = {
        "status_code": 422,
        "code": "unknown_schedule_response",
        "reached_repository": False,
    }

    response = resident_api_client.post(
        SCHEDULE, json={"response": "maybe"}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
        "reached_repository": "answered" in scheduling,
    }

    assert actual_output == expected_output, endpoint


def test_api_180_confirming_forwards_the_resolved_job_and_the_answer(
    resident_api_client: TestClient, scheduling: dict, csrf_headers: dict[str, str]
) -> None:
    """The work-order id the RPC receives was resolved here from the complaint,
    never sent by the caller. The response is the re-read row, so a screen sees
    the confirmation land rather than having to assume it."""
    endpoint = "POST /api/v1/complaints/complaint-id/schedule"
    expected_output = {
        "status_code": 200,
        "forwarded": {
            "work_order_id": "work-order-id",
            "response": "confirmed",
            "note": None,
        },
    }

    response = resident_api_client.post(
        SCHEDULE, json={"response": "confirmed"}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "forwarded": scheduling["answered"],
    }

    assert actual_output == expected_output, endpoint


def test_api_181_answering_twice_is_the_rpc_s_409_and_not_a_recheck_here(
    resident_api_client: TestClient,
    scheduling: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service does not look at the status before calling. Whether the job
    is still waiting is a question about a row, and by the time this process had
    read it and decided, a supervisor could have assigned somebody -- so the
    check is inside the transaction that does the write."""
    endpoint = "POST /api/v1/complaints/complaint-id/schedule"
    expected_output = {
        "status_code": 409,
        "message": "This visit is no longer waiting on you.",
    }

    def refuse(client: Any, **kwargs: Any) -> None:
        raise ConflictError(
            "This visit is no longer waiting on you.", code="conflict"
        )

    monkeypatch.setattr(work_orders_service.repo, "respond_to_schedule", refuse)
    response = resident_api_client.post(
        SCHEDULE, json={"response": "confirmed"}, headers=csrf_headers
    )
    error = response.json()["error"]
    actual_output = {
        "status_code": response.status_code,
        "message": error["message"],
    }

    assert actual_output == expected_output, endpoint


def test_api_182_answering_somebody_else_s_proposal_is_the_rpc_s_403(
    resident_api_client: TestClient,
    scheduling: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`respond_to_work_order_schedule` checks `is_own_membership` against
    whoever raised the complaint. A neighbour in the same community passes every
    guard in this process and is refused there -- which is the whole reason the
    check is not duplicated here."""
    endpoint = "POST /api/v1/complaints/complaint-id/schedule"
    expected_output = {"status_code": 403, "code": "forbidden"}

    def refuse(client: Any, **kwargs: Any) -> None:
        raise AuthorizationError(
            "This visit was not proposed to you.", code="forbidden"
        )

    monkeypatch.setattr(work_orders_service.repo, "respond_to_schedule", refuse)
    response = resident_api_client.post(
        SCHEDULE, json={"response": "declined"}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_183_staff_cannot_answer_on_the_resident_s_behalf(
    admin_api_client: TestClient, scheduling: dict, csrf_headers: dict[str, str]
) -> None:
    """Matching the precedent `resident_complaints.py` set for reopening and
    confirming a resolution: not because an admin could not press the button,
    but because this is the resident's verdict about their own home, and an
    admin answering for them is a record that says something untrue.

    The guard is `require_resident_capability` since 2026-08-20, so what is
    refused here is an admin with **no flat of their own** -- which is what this
    fixture describes, and what `tests/api/conftest.py` stubs the residency
    lookup to say. The admin who does live in the building may answer, and
    `tests/api/test_resident_capability_guard.py` is where that is pinned."""
    endpoint = "POST /api/v1/complaints/complaint-id/schedule"
    expected_output = {"status_code": 403, "reached_repository": False}

    response = admin_api_client.post(
        SCHEDULE, json={"response": "confirmed"}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "answered" in scheduling,
    }

    assert actual_output == expected_output, endpoint


def test_api_184_answering_without_the_csrf_pair_is_refused(
    resident_api_client: TestClient, scheduling: dict
) -> None:
    """A cross-site form post confirming a visit somebody did not agree to is a
    small harm with a long tail -- a technician turns up to an empty flat and the
    slot is spent."""
    endpoint = "POST /api/v1/complaints/complaint-id/schedule"
    expected_output = {"status_code": 403, "reached_repository": False}

    response = resident_api_client.post(SCHEDULE, json={"response": "confirmed"})
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "answered" in scheduling,
    }

    assert actual_output == expected_output, endpoint
