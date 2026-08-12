"""The worker's calendar, their leave, and the week they will work.

Three properties here are decisions rather than plumbing, and each would survive
a refactor that broke it: the calendar is one list of two kinds, its range filter
matches on **overlap** rather than on start, and the working week is replaced
whole rather than edited.

The overlap one is the least obvious and the most load-bearing. A fortnight of
leave that a one-week calendar sits in the middle of starts before the window and
ends after it, so a filter on ``starts_at`` alone would drop exactly the block
that matters most -- and the worker would be shown as free on a week they had
booked off.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_request_client
from app.domain.schemas import Principal
from app.services import worker_service

CALENDAR = "/api/v1/worker/calendar"
UNAVAILABILITY = "/api/v1/worker/unavailability"
RULES = "/api/v1/worker/availability-rules"

PROFILE_ID = "worker-profile-id"

WINDOW = {"from": "2026-08-10T00:00:00Z", "to": "2026-08-17T00:00:00Z"}


def job_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "assignment_id": "assignment-id",
        "work_order_id": "work-order-id",
        "staff_assignment_id": "staff-id",
        "assignment_status": "accepted",
        "work_order_status": "scheduled",
        "priority": "medium",
        "subject_kind": "resident",
        "scheduled_start_at": "2026-08-12T09:00:00Z",
        "scheduled_end_at": "2026-08-12T10:00:00Z",
        "offered_at": "2026-08-10T09:00:00Z",
        "responded_at": None,
        "decline_reason": None,
        "is_auto_assigned": False,
        "community_id": "community-id",
        "community_name": "Green Meadows",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "department_kind": "service",
        "complaint_id": "complaint-id",
        "complaint_title": "Leaking tap",
        "complaint_category": "Plumbing",
        "skill_name": "Plumbing",
        "location_text": "B-204",
        "failed_attempt_count": 0,
        "cancelled_reason": None,
    }
    base.update(overrides)
    return base


def block_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "block-id",
        "starts_at": "2026-08-11T00:00:00Z",
        "ends_at": "2026-08-13T00:00:00Z",
        "reason": "Family wedding",
        "scope": "provider",
        "department_name": None,
        "created_at": "2026-08-01T09:00:00Z",
    }
    base.update(overrides)
    return base


def rule_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "rule-id",
        "weekday": 1,
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "effective_from": "2026-08-01",
        "effective_to": None,
        "scope": "provider",
        "department_name": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def worker_client(api_client: TestClient) -> TestClient:
    """Signed in, with no membership override -- see ``test_worker_jobs.py``."""
    principal = Principal(
        user_id=PROFILE_ID,
        email="ravi@example.com",
        email_verified=True,
        full_name="Ravi Kumar",
    )
    api_client.app.dependency_overrides[get_current_user] = lambda: principal
    api_client.app.dependency_overrides[get_request_client] = lambda: object()
    return api_client


@pytest.fixture
def schedule(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    captured: dict = {
        "jobs": [job_row()],
        "blocks": [block_row()],
        "rules": [rule_row()],
        "calls": [],
    }

    def fake_list_jobs(client: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return captured["jobs"]

    def fake_list_unavailability(client: Any, **kwargs: Any) -> list[dict[str, Any]]:
        captured["calls"].append(("unavailability", kwargs))
        return captured["blocks"]

    def fake_list_rules(client: Any) -> list[dict[str, Any]]:
        return captured["rules"]

    def fake_add(
        client: Any, *, starts_at: str, ends_at: str, reason: str | None
    ) -> str:
        captured["calls"].append(("add", starts_at, ends_at, reason))
        return "block-id"

    def fake_delete(client: Any, *, block_id: str) -> None:
        captured["calls"].append(("delete", block_id))

    def fake_set_rules(client: Any, *, rules: list[dict[str, Any]]) -> int:
        captured["calls"].append(("set_rules", rules))
        return len(rules)

    repo = worker_service.repo
    monkeypatch.setattr(repo, "list_jobs", fake_list_jobs)
    monkeypatch.setattr(repo, "list_unavailability", fake_list_unavailability)
    monkeypatch.setattr(repo, "list_availability_rules", fake_list_rules)
    monkeypatch.setattr(repo, "add_unavailability", fake_add)
    monkeypatch.setattr(repo, "delete_unavailability", fake_delete)
    monkeypatch.setattr(repo, "set_availability_rules", fake_set_rules)
    yield captured


def test_api_192_the_calendar_is_one_list_of_two_kinds_in_time_order(
    worker_client: TestClient, schedule: dict
) -> None:
    """A calendar that returned jobs and made the client fetch leave separately
    would draw a worker as free on a day they had booked off, for as long as the
    second request took to arrive."""
    endpoint = "GET /api/v1/worker/calendar"
    expected_output = {
        "status_code": 200,
        "kinds": ["unavailable", "job"],
    }

    response = worker_client.get(CALENDAR, params=WINDOW)
    actual_output = {
        "status_code": response.status_code,
        "kinds": [entry["kind"] for entry in response.json()],
    }

    assert actual_output == expected_output, endpoint


def test_api_193_the_calendar_omits_what_is_not_a_claim_about_the_future(
    worker_client: TestClient, schedule: dict
) -> None:
    """A declined offer and a cancelled job are both history. A calendar is a
    claim about where somebody will be, and neither of those is one."""
    endpoint = "GET /api/v1/worker/calendar"
    expected_output = {"job_entries": 0}

    schedule["jobs"] = [
        job_row(assignment_status="declined"),
        job_row(assignment_id="a2", work_order_status="cancelled"),
    ]
    response = worker_client.get(CALENDAR, params=WINDOW)
    actual_output = {
        "job_entries": sum(
            1 for entry in response.json() if entry["kind"] == "job"
        )
    }

    assert actual_output == expected_output, endpoint


def test_api_194_the_leave_filter_matches_on_overlap_not_on_start(
    worker_client: TestClient, schedule: dict
) -> None:
    """The block that matters most to a week is the fortnight it sits inside,
    which starts before the window opens. Filtering `starts_at` against both
    bounds would drop precisely that one."""
    endpoint = "GET /api/v1/worker/unavailability"
    expected_output = {
        "status_code": 200,
        "bounds": {
            "ends_after": "2026-08-10T00:00:00+00:00",
            "starts_before": "2026-08-17T00:00:00+00:00",
        },
    }

    response = worker_client.get(UNAVAILABILITY, params=WINDOW)
    _, kwargs = schedule["calls"][0]
    actual_output = {
        "status_code": response.status_code,
        "bounds": {
            "ends_after": kwargs["ends_after"],
            "starts_before": kwargs["starts_before"],
        },
    }

    assert actual_output == expected_output, endpoint


def test_api_195_removing_a_block_answers_204_with_no_body(
    worker_client: TestClient, schedule: dict, csrf_headers: dict[str, str]
) -> None:
    """Unlike a withdrawn application, a block that is gone leaves nothing on the
    screen it came from, so there is no row to return."""
    endpoint = "DELETE /api/v1/worker/unavailability/{id}"
    expected_output = {"status_code": 204, "body": "", "deleted": "block-id"}

    response = worker_client.delete(f"{UNAVAILABILITY}/block-id", headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "body": response.text,
        "deleted": schedule["calls"][0][1],
    }

    assert actual_output == expected_output, endpoint


def test_api_196_the_working_week_is_replaced_whole_in_the_rpcs_vocabulary(
    worker_client: TestClient, schedule: dict, csrf_headers: dict[str, str]
) -> None:
    """The RPC reads its jsonb with `rule->>'startTime'`, so the service has to
    send camelCase into the database even though every other repository argument
    is snake_case. Getting this wrong casts null to time and fails at the
    insert, a long way from the endpoint."""
    endpoint = "PUT /api/v1/worker/availability-rules"
    expected_output = {
        "status_code": 200,
        "sent": [
            {
                "weekday": 2,
                "startTime": "08:00:00",
                "endTime": "12:00:00",
                "effectiveFrom": None,
                "effectiveTo": None,
            }
        ],
    }

    response = worker_client.put(
        RULES,
        json={
            "rules": [
                {"weekday": 2, "startTime": "08:00:00", "endTime": "12:00:00"}
            ]
        },
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "sent": schedule["calls"][0][1],
    }

    assert actual_output == expected_output, endpoint


def test_api_197_a_backwards_window_is_refused_before_the_database_sees_it(
    worker_client: TestClient, schedule: dict, csrf_headers: dict[str, str]
) -> None:
    """The CHECK constraint is the guarantee; this is the sentence. A 422 naming
    the field beats a 422 carrying the repository's generic message, which is
    what the constraint's own 23514 would arrive as."""
    endpoint = "POST /api/v1/worker/unavailability"
    expected_output = {"status_code": 422}

    response = worker_client.post(
        UNAVAILABILITY,
        json={"startsAt": "2026-08-12T10:00:00Z", "endsAt": "2026-08-12T09:00:00Z"},
        headers=csrf_headers,
    )
    actual_output = {"status_code": response.status_code}

    assert actual_output == expected_output, endpoint
