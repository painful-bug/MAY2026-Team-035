"""The resident routes, seen from the admin who lives in the building.

`tests/test_resident_capability.py` pins the guard itself. This pins what the
guard did to the surface: which routes gained it, which deliberately did not,
and that an admin with a flat now reaches the handler on every route where the
answer is about their own home.

The residency lookup is a service-role read the API fixtures cannot satisfy, so
`tests/api/conftest.py` stubs it to *False* for the whole suite -- the fixture
memberships describe people with no flat, and only `resident_api_client` carries
a `unit_id`. `lives_here` is the opt-in for the caller this feature exists for.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.repositories import resident_complaints_repository
from app.services import work_orders_service

PATH = "/api/v1/complaints"


def row(**overrides: Any) -> dict[str, Any]:
    """A complete `complaint_overview` row, as PostgREST would return it."""
    base: dict[str, Any] = {
        "id": "complaint-id",
        "title": "Lift stuck between floors",
        "description": "The B-block lift has been stopping between 3 and 4.",
        "category": "Elevator",
        "status": "resolved",
        "priority": "high",
        "location": "B Block",
        "progress_percent": 100,
        "assignee_label": "Ravi Kumar",
        "created_at": "2026-08-01T09:00:00+00:00",
        "updated_at": "2026-08-02T09:00:00+00:00",
        "last_activity_at": "2026-08-02T09:00:00+00:00",
        "expected_resolution_at": "2026-08-02T09:00:00+00:00",
        "resolved_at": "2026-08-02T09:00:00+00:00",
        "is_overdue": False,
        "is_unread": False,
        "reopened_count": 0,
        "comment_count": 0,
        "resolution_rating": None,
        "resident_feedback": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def lives_here(monkeypatch: pytest.MonkeyPatch) -> None:
    """The caller holds an active `unit_residencies` row.

    Applied after the suite-wide `no_unit_residency` autouse fixture, so this
    `setattr` is the one that stands.
    """
    monkeypatch.setattr(deps, "_has_active_residency", lambda membership_id: True)


@pytest.fixture
def complaints(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace every repository call. Records names, returns what is staged."""
    captured: dict = {"calls": []}

    def record(name: str, result: Any):
        def fake(client: Any, **kwargs: Any) -> Any:
            captured["calls"].append((name, kwargs))
            return result

        return fake

    for name, result in {
        "list_mine": ([row()], 1),
        "get_mine": row(),
        "timeline": ([], False),
        "comments": ([], False),
        "raise_complaint": "new-complaint-id",
        "cancel_work": None,
        "reopen": None,
        "confirm_resolution": None,
        "mark_read": None,
    }.items():
        monkeypatch.setattr(resident_complaints_repository, name, record(name, result))
    return captured


@pytest.fixture
def scheduling(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace the work-order repository under the live scheduling service."""
    captured: dict = {}
    work_order = {
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
        "scheduled_start_at": "2026-08-12T10:00:00Z",
        "scheduled_end_at": "2026-08-12T11:00:00Z",
        "resident_deadline_at": "2026-08-11T10:00:00Z",
        "failed_attempt_count": 0,
        "cancelled_reason": None,
        "assignee_name": None,
        "staff_assignment_id": None,
        "created_at": "2026-08-10T09:00:00Z",
        "updated_at": "2026-08-10T09:00:00Z",
    }

    def fake_for_complaint(client: Any, *, complaint_id: str) -> list[dict[str, Any]]:
        return [work_order]

    def fake_respond(client: Any, **kwargs: Any) -> None:
        captured["answered"] = kwargs

    monkeypatch.setattr(work_orders_service.repo, "list_for_complaint", fake_for_complaint)
    monkeypatch.setattr(work_orders_service.repo, "respond_to_schedule", fake_respond)
    return captured


def names(captured: dict) -> list[str]:
    return [name for name, _ in captured["calls"]]


# ---------------------------------------------------------------------------
# The admin who lives in the building
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "body", "repository_call"),
    [
        (f"{PATH}/complaint-id/cancel", {"mode": "cancel", "reason": "Fixed itself"}, "cancel_work"),
        (f"{PATH}/complaint-id/reopen", {"reason": "Still broken"}, "reopen"),
        (f"{PATH}/complaint-id/resolution", {"rating": 5}, "confirm_resolution"),
    ],
)
def test_an_admin_with_a_flat_may_use_the_resident_verbs_on_it(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    complaints: dict,
    lives_here: None,
    path: str,
    body: dict[str, Any],
    repository_call: str,
) -> None:
    """The bug this change fixes. Cancelling work in your own flat, reopening
    and confirming a resolution are verdicts about a home; the person who both
    runs the association and lives there was refused all three, because one
    membership row cannot say `admin` and `resident` at once."""
    endpoint = f"POST {path}"
    expected_output = {"status_code": 200, "reached_repository": True}

    response = admin_api_client.post(path, json=body, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": repository_call in names(complaints),
    }

    assert actual_output == expected_output, endpoint


def test_an_admin_with_a_flat_may_raise_a_complaint_about_it(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    complaints: dict,
    lives_here: None,
) -> None:
    """`POST /complaints` owns the complaint by the raiser's own membership and
    shows it on their resident portal, which only means anything for a
    membership that lives somewhere."""
    endpoint = "POST /api/v1/complaints"
    expected_output = {"status_code": 201, "reached_repository": True}

    response = admin_api_client.post(
        PATH,
        json={"title": "Tap leaking", "category": "Plumbing"},
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "raise_complaint" in names(complaints),
    }

    assert actual_output == expected_output, endpoint


def test_an_admin_with_a_flat_may_answer_a_visit_proposed_to_them(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    scheduling: dict,
    lives_here: None,
) -> None:
    """The scheduling router carries the guard at router level, so both of its
    routes move together. `respond_to_work_order_schedule` still checks
    `is_own_membership` in the same statement that would do the write -- this
    guard was only ever the early, clear error."""
    endpoint = "POST /api/v1/complaints/complaint-id/schedule"
    expected_output = {"status_code": 200, "answered": True}

    response = admin_api_client.post(
        f"{PATH}/complaint-id/schedule",
        json={"response": "confirmed"},
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "answered": "answered" in scheduling,
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# Staff who live nowhere
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (PATH, {"title": "Tap leaking", "category": "Plumbing"}),
        (f"{PATH}/complaint-id/cancel", {"mode": "cancel", "reason": "No"}),
        (f"{PATH}/complaint-id/reopen", {"reason": "Still broken"}),
        (f"{PATH}/complaint-id/resolution", {"rating": 5}),
        (f"{PATH}/complaint-id/schedule", {"response": "confirmed"}),
    ],
)
def test_staff_who_live_nowhere_are_still_refused(
    manager_api_client: TestClient,
    csrf_headers: dict[str, str],
    complaints: dict,
    scheduling: dict,
    path: str,
    body: dict[str, Any],
) -> None:
    """The guard widened who counts as a resident; it did not stop asking. A
    department manager with no residency has no home for any of these to be
    about, and their complaints belong on `POST /complaints/admin-raise`."""
    endpoint = f"POST {path}"
    expected_output = {
        "status_code": 403,
        "code": "community_role_required",
        "message": "You do not have permission for this community action.",
        "reached_repository": False,
    }

    response = manager_api_client.post(path, json=body, headers=csrf_headers)
    error = response.json()["error"]
    actual_output = {
        "status_code": response.status_code,
        "code": error["code"],
        "message": error["message"],
        "reached_repository": bool(complaints["calls"]) or "answered" in scheduling,
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# What the guard must not have touched
# ---------------------------------------------------------------------------


def test_reading_stays_open_to_any_active_member(
    admin_api_client: TestClient, complaints: dict
) -> None:
    """`GET /complaints` and `GET /complaints/{id}` are scoped to the caller's
    own membership, so they answer "what have *you* raised" -- a question a
    member with no flat may still ask, and one whose answer is an empty list."""
    endpoint = "GET /api/v1/complaints and GET /api/v1/complaints/{id}"
    expected_output = {"list": 200, "detail": 200}

    actual_output = {
        "list": admin_api_client.get(PATH).status_code,
        "detail": admin_api_client.get(f"{PATH}/complaint-id").status_code,
    }

    assert actual_output == expected_output, endpoint


def test_marking_read_stays_open_to_any_active_member(
    admin_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    """The marker is per membership, so clearing your own says nothing about
    anybody's home and cannot touch the resident's."""
    endpoint = "POST /api/v1/complaints/complaint-id/read"
    expected_output = {"status_code": 200, "reached_repository": True}

    response = admin_api_client.post(
        f"{PATH}/complaint-id/read", headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "mark_read" in names(complaints),
    }

    assert actual_output == expected_output, endpoint


def test_a_resident_never_pays_for_the_residency_lookup(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The common caller short-circuits on the role. Asserted through the HTTP
    surface as well as in the unit tests because it is the property most easily
    lost by a later refactor that "simplifies" the two branches into one."""
    endpoint = "POST /api/v1/complaints"
    expected_output = {"status_code": 201, "looked_up": False}

    looked_up: list[str] = []
    monkeypatch.setattr(
        deps, "_has_active_residency", lambda membership_id: looked_up.append(membership_id) or True
    )
    response = resident_api_client.post(
        PATH,
        json={"title": "Tap leaking", "category": "Plumbing"},
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "looked_up": bool(looked_up),
    }

    assert actual_output == expected_output, endpoint


def test_csrf_is_still_checked_before_the_capability(
    admin_api_client: TestClient, complaints: dict, lives_here: None
) -> None:
    """A guard that admits more callers must not admit more origins."""
    endpoint = "POST /api/v1/complaints/complaint-id/reopen"
    expected_output = {"status_code": 403, "reached_repository": False}

    response = admin_api_client.post(
        f"{PATH}/complaint-id/reopen", json={"reason": "Still broken"}
    )
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": bool(complaints["calls"]),
    }

    assert actual_output == expected_output, endpoint
