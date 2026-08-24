"""The supervisor's card actions: resolve, priority, notes, chat, force-assign,
take-up.

**What these tests can and cannot prove.** Every decision worth making lives in
`20260822170000_supervisor_actions.sql`: whether a running job blocks a resolve,
whether the priority has anywhere left to go, whether a second supervisor may
write in a thread the first one opened. Those are Postgres, they are stubbed
here, and the static battery in `tests/test_supervisor_actions_migration.py` is
the half that reads them.

What is proved below is the half that is Python, and it is the half where a
mistake is silent rather than loud:

* **the three body-less verbs declare no request model.** The house `post()`
  helper always sends `{}`, so a required model would answer 422 to every press
  of a button that has nothing to say -- the same trap take-up avoided, restated
  three times because it is three routes;
* **`force` routes to a different RPC and nothing else changes.** The default
  path must still call `assign_work_order` with exactly the arguments it always
  did: an offer that quietly became a booking would take a worker's right to
  decline away without any error anywhere;
* **the refusals come out of the database with their own sentences.** "Somebody
  is working on this right now" and "already at the highest priority" are what a
  supervisor reads, and `pg_errors` passes a custom code's message through
  untouched;
* **take-up is a third verb and not a third branch of assign** (2026-08-24
  ruling R8). It reaches `take_up_work_order` and neither of the other two RPCs,
  it carries the same optional slot, its body has no `staffAssignmentId` at all
  -- the holder is resolved from the session inside Postgres -- and it needs the
  CSRF pair, which matters more here than anywhere else on this surface: it is a
  bodyless POST that books somebody's day;
* **the staff detail read no longer refuses the department at the door.** The
  guard widened from `require_admin` to active membership because the RPC has
  always decided `is_community_admin OR can_supervise_department` for itself.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.services import (
    complaints_service,
    supervisor_triage_service,
    work_orders_service,
)

RESOLVE = "/api/v1/complaints/complaint-id/resolve"
PRIORITY = "/api/v1/complaints/complaint-id/priority-raise"
NOTES = "/api/v1/complaints/complaint-id/notes"
CHAT = "/api/v1/complaints/complaint-id/chat"
STAFF_DETAIL = "/api/v1/complaints/staff/complaints/complaint-id"
ASSIGN = "/api/v1/work-orders/work-order-id/assign"
TAKE_UP = "/api/v1/work-orders/work-order-id/take-up"


@pytest.fixture
def supervisor(worker_api_client: TestClient) -> TestClient:
    """A department supervisor, as the API sees one: membership role ``worker``.

    Rank lives on ``staff_assignments`` and never reaches the request, which is
    why the router guard has to admit every worker and let
    ``can_supervise_department`` decide.
    """
    return worker_api_client


@pytest.fixture
def actions(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository under the live service."""
    captured: dict = {"priority": "high"}

    def fake_resolve(client: Any, *, complaint_id: str) -> None:
        captured["resolved"] = complaint_id

    def fake_priority(client: Any, *, complaint_id: str) -> str:
        captured["raised"] = complaint_id
        return captured["priority"]

    def fake_note(client: Any, *, complaint_id: str, note: str) -> str:
        captured["note"] = {"complaint_id": complaint_id, "note": note}
        return "event-id"

    def fake_chat(client: Any, *, complaint_id: str) -> str:
        captured["chat"] = complaint_id
        return "thread-id"

    repo = supervisor_triage_service.repo
    monkeypatch.setattr(repo, "resolve_complaint", fake_resolve)
    monkeypatch.setattr(repo, "raise_complaint_priority", fake_priority)
    monkeypatch.setattr(repo, "add_complaint_note", fake_note)
    monkeypatch.setattr(repo, "open_complaint_thread", fake_chat)
    yield captured


@pytest.fixture
def jobs(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """The work-order repository, for the assign route's two paths."""
    captured: dict = {}

    def fake_get(client: Any, *, work_order_id: str) -> dict[str, Any]:
        return {
            "id": work_order_id,
            "community_id": "community-id",
            "complaint_id": "complaint-id",
            "status": "scheduled",
            "priority": "medium",
            "subject_kind": "resident",
            "failed_attempt_count": 0,
        }

    def fake_assignments(
        client: Any, *, work_order_id: str
    ) -> list[dict[str, Any]]:
        return []

    def fake_assign(client: Any, **kwargs: Any) -> str:
        captured["offered"] = kwargs
        return "assignment-id"

    def fake_force(client: Any, **kwargs: Any) -> str:
        captured["forced"] = kwargs
        return "assignment-id"

    def fake_take_up(client: Any, **kwargs: Any) -> str:
        captured["taken_up"] = kwargs
        return "assignment-id"

    repo = work_orders_service.repo
    monkeypatch.setattr(repo, "get_work_order", fake_get)
    monkeypatch.setattr(repo, "list_assignments", fake_assignments)
    monkeypatch.setattr(repo, "assign_work_order", fake_assign)
    monkeypatch.setattr(repo, "force_assign_work_order", fake_force)
    monkeypatch.setattr(repo, "take_up_work_order", fake_take_up)
    yield captured


# ---------------------------------------------------------------------------
# Resolve (ruling A2)
# ---------------------------------------------------------------------------


def test_api_353_resolving_needs_no_body_and_refuses_none(
    supervisor: TestClient, actions: dict, csrf_headers: dict[str, str]
) -> None:
    """**The route declares no request model**, for take-up's reason: the house
    `post()` helper always sends `{}`, and a required body would answer 422 to
    every press. Both an empty object and no body at all are a 200."""
    endpoint = "POST /api/v1/complaints/complaint-id/resolve"
    expected_output = {
        "status_code": 200,
        "with_empty_object": 200,
        "forwarded": "complaint-id",
        "message": "Complaint resolved.",
    }

    bare = supervisor.post(RESOLVE, headers=csrf_headers)
    with_body = supervisor.post(RESOLVE, json={}, headers=csrf_headers)
    actual_output = {
        "status_code": bare.status_code,
        "with_empty_object": with_body.status_code,
        "forwarded": actions["resolved"],
        "message": with_body.json()["message"],
    }

    assert actual_output == expected_output, endpoint


def test_api_354_a_running_job_refuses_the_resolve_in_the_rpc_s_own_words(
    supervisor: TestClient,
    actions: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ruling A2's refusal, and the reason nothing in Python pre-reads the jobs:
    "is anything running?" is asked under a row lock inside the RPC. A check here
    would be a second answer computed a moment earlier, against the caller's RLS
    rather than the RPC's, and it would disagree exactly when it mattered."""
    endpoint = "POST /api/v1/complaints/complaint-id/resolve"
    expected_output = {
        "status_code": 409,
        "code": "conflict",
        "message": (
            "Somebody is working on this right now. "
            "Finish or cancel the running job first."
        ),
    }

    def refuse(client: Any, **kwargs: Any) -> None:
        raise ConflictError(
            "Somebody is working on this right now. "
            "Finish or cancel the running job first.",
            code="conflict",
        )

    monkeypatch.setattr(
        supervisor_triage_service.repo, "resolve_complaint", refuse
    )
    response = supervisor.post(RESOLVE, json={}, headers=csrf_headers)
    error = response.json()["error"]
    actual_output = {
        "status_code": response.status_code,
        "code": error["code"],
        "message": error["message"],
    }

    assert actual_output == expected_output, endpoint


def test_api_355_an_unknown_complaint_is_a_404_and_a_stranger_s_is_a_403(
    supervisor: TestClient,
    actions: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both refusals reach the caller unflattened. A 403 rendered as a 500 --
    which is what an unmapped SQLSTATE does -- is the one failure a supervisor
    cannot act on, because the sentence the RPC wrote never arrives."""
    endpoint = "POST /api/v1/complaints/complaint-id/resolve"
    expected_output = {"missing": (404, "not_found"), "theirs": (403, "forbidden")}

    def missing(client: Any, **kwargs: Any) -> None:
        raise NotFoundError("No such complaint.", code="not_found")

    monkeypatch.setattr(
        supervisor_triage_service.repo, "resolve_complaint", missing
    )
    first = supervisor.post(RESOLVE, json={}, headers=csrf_headers)

    def theirs(client: Any, **kwargs: Any) -> None:
        raise AuthorizationError(
            "You do not work on this department's complaints.", code="forbidden"
        )

    monkeypatch.setattr(
        supervisor_triage_service.repo, "resolve_complaint", theirs
    )
    second = supervisor.post(RESOLVE, json={}, headers=csrf_headers)

    actual_output = {
        "missing": (first.status_code, first.json()["error"]["code"]),
        "theirs": (second.status_code, second.json()["error"]["code"]),
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------


def test_api_356_the_new_priority_comes_back_in_the_wire_vocabulary(
    supervisor: TestClient, actions: dict, csrf_headers: dict[str, str]
) -> None:
    """The RPC answers `high` and the supervisor reads *High*, through
    `app/domain/vocabularies.py` -- the one place this codebase maps a stored
    word to a rendered one. A `case` in SQL would be a second copy of that table
    in a language nobody would look in."""
    endpoint = "POST /api/v1/complaints/complaint-id/priority-raise"
    expected_output = {
        "status_code": 200,
        "message": "Priority raised to High.",
        "medium": "Priority raised to Medium.",
        "forwarded": "complaint-id",
    }

    high = supervisor.post(PRIORITY, json={}, headers=csrf_headers)
    actions["priority"] = "medium"
    medium = supervisor.post(PRIORITY, json={}, headers=csrf_headers)
    actual_output = {
        "status_code": high.status_code,
        "message": high.json()["message"],
        "medium": medium.json()["message"],
        "forwarded": actions["raised"],
    }

    assert actual_output == expected_output, endpoint


def test_api_357_a_complaint_already_at_high_is_a_409(
    supervisor: TestClient,
    actions: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One way only, and the top is a refusal rather than a silent no-op. A
    supervisor who pressed the button and saw nothing change would press it
    again; the sentence is what stops that."""
    endpoint = "POST /api/v1/complaints/complaint-id/priority-raise"
    expected_output = {
        "status_code": 409,
        "code": "conflict",
        "message": "This complaint is already at the highest priority.",
    }

    def refuse(client: Any, **kwargs: Any) -> str:
        raise ConflictError(
            "This complaint is already at the highest priority.", code="conflict"
        )

    monkeypatch.setattr(
        supervisor_triage_service.repo, "raise_complaint_priority", refuse
    )
    response = supervisor.post(PRIORITY, json={}, headers=csrf_headers)
    error = response.json()["error"]
    actual_output = {
        "status_code": response.status_code,
        "code": error["code"],
        "message": error["message"],
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# Internal notes (ruling A5)
# ---------------------------------------------------------------------------


def test_api_358_a_note_is_created_and_its_bounds_are_checked_before_the_database(
    supervisor: TestClient, actions: dict, csrf_headers: dict[str, str]
) -> None:
    """`201`, because a note is a thing that now exists on a timeline.

    The 1--2000 bound is stated twice on purpose: Pydantic answers an empty
    composer with a 422 naming the field, and `add_complaint_note_internal`
    answers `HB422` for any caller the API does not own. The note is trimmed
    here, so a body of spaces is refused rather than stored."""
    endpoint = "POST /api/v1/complaints/complaint-id/notes"
    expected_output = {
        "status_code": 201,
        "forwarded": "Tenant is away until Friday; access via the office.",
        "empty": 422,
        "too_long": 422,
    }

    created = supervisor.post(
        NOTES,
        json={"note": "  Tenant is away until Friday; access via the office.  "},
        headers=csrf_headers,
    )
    empty = supervisor.post(NOTES, json={"note": ""}, headers=csrf_headers)
    too_long = supervisor.post(
        NOTES, json={"note": "x" * 2001}, headers=csrf_headers
    )
    actual_output = {
        "status_code": created.status_code,
        "forwarded": actions["note"]["note"],
        "empty": empty.status_code,
        "too_long": too_long.status_code,
    }

    assert actual_output == expected_output, endpoint


def test_api_359_an_internal_note_never_reaches_the_resident_s_timeline() -> None:
    """Ruling A5, at the only layer that can enforce it.

    The RLS policy on `complaint_events` scopes rows to the complaint and not to
    a payload flag, so the row *does* reach this service -- and dropping it here
    is the whole of what keeps it off the resident's screen. The admin's
    resident-visible note carries no flag and must survive the same filter,
    which is the half of this test that would fail on an over-eager fix."""
    endpoint = "resident_complaints_service._is_hidden_from_resident"
    expected_output = {"internal": True, "admin_update": False, "priority": False}

    from app.services import resident_complaints_service as service

    actual_output = {
        "internal": service._is_hidden_from_resident(
            {"event_type": "note_added", "payload": {"note": "x", "internal": True}}
        ),
        "admin_update": service._is_hidden_from_resident(
            {"event_type": "note_added", "payload": {"note": "Plumber booked."}}
        ),
        "priority": service._is_hidden_from_resident(
            {"event_type": "priority_changed", "payload": {"from": "low", "to": "high"}}
        ),
    }

    assert actual_output == expected_output, endpoint


def test_api_374_take_up_stays_off_the_resident_s_timeline() -> None:
    """Ruling R14: `job_taken_up` is `job_force_assigned`'s situation exactly.

    `take_up_work_order` writes `job_assigned` beside it, so the resident
    already holds their fact -- somebody is coming, and this is their name.
    Which door the assignment came through is staffing, not service. The
    `job_assigned` half of this test is what would fail on an over-eager fix."""
    endpoint = "resident_complaints_service._is_hidden_from_resident"
    expected_output = {"taken_up": True, "assigned_beside_it": False}

    from app.services import resident_complaints_service as service

    actual_output = {
        "taken_up": service._is_hidden_from_resident(
            {"event_type": "job_taken_up", "payload": {"workOrderId": "wo-1"}}
        ),
        "assigned_beside_it": service._is_hidden_from_resident(
            {
                "event_type": "job_assigned",
                "payload": {"workOrderId": "wo-1", "takenUp": True},
            }
        ),
    }

    assert actual_output == expected_output, endpoint


def test_api_360_the_priority_timeline_line_is_the_approved_copy() -> None:
    """The resident-facing sentence, rendered from the payload's *stored* words.

    The RPC writes `{"from": "medium", "to": "high"}` because nothing in SQL
    translates a vocabulary; the sentence says *High* because
    `complaint_priority_to_wire` is asked here, in the same call every other
    complaint surface makes."""
    endpoint = "resident_complaints_service._event_message"
    expected_output = {
        "message": "The department raised the priority to High.",
        "label": "Priority raised",
    }

    from app.services import resident_complaints_service as service

    actual_output = {
        "message": service._event_message(
            "priority_changed", {"from": "medium", "to": "high"}
        ),
        "label": service._EVENT_LABELS["priority_changed"],
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# Chat (ruling A1)
# ---------------------------------------------------------------------------


def test_api_361_opening_a_chat_returns_only_the_thread_id(
    supervisor: TestClient, actions: dict, csrf_headers: dict[str, str]
) -> None:
    """`200` and `{ threadId }`, not the thread.

    The dock already fetches a thread and its messages from
    `GET /messages/threads/{id}`; returning the whole thing here would be a
    second projection of it, free to disagree with the first. `200` rather than
    `201` because the common case is *getting* the thread that exists -- a
    status code that alternated would describe the database's history rather
    than the caller's request."""
    endpoint = "POST /api/v1/complaints/complaint-id/chat"
    expected_output = {
        "status_code": 200,
        "body": {"threadId": "thread-id"},
        "forwarded": "complaint-id",
        "bare_post": 200,
    }

    response = supervisor.post(CHAT, json={}, headers=csrf_headers)
    bare = supervisor.post(CHAT, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
        "forwarded": actions["chat"],
        "bare_post": bare.status_code,
    }

    assert actual_output == expected_output, endpoint


def test_api_362_a_complaint_with_nobody_to_talk_to_is_a_409(
    supervisor: TestClient,
    actions: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A conflict and not a 404: the complaint exists, and what is missing is a
    second person to put in the thread. The same shape `open_work_order_thread`
    already uses for a job with no worker-and-resident pair."""
    endpoint = "POST /api/v1/complaints/complaint-id/chat"
    expected_output = {
        "status_code": 409,
        "message": "This complaint has nobody to talk to.",
    }

    def refuse(client: Any, **kwargs: Any) -> str:
        raise ConflictError("This complaint has nobody to talk to.", code="conflict")

    monkeypatch.setattr(
        supervisor_triage_service.repo, "open_complaint_thread", refuse
    )
    response = supervisor.post(CHAT, json={}, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "message": response.json()["error"]["message"],
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# The guard surface
# ---------------------------------------------------------------------------


def _every_action(client: TestClient, csrf: dict[str, str]) -> dict[str, int]:
    return {
        "resolve": client.post(RESOLVE, json={}, headers=csrf).status_code,
        "priority-raise": client.post(PRIORITY, json={}, headers=csrf).status_code,
        "notes": client.post(
            NOTES, json={"note": "Access via the office."}, headers=csrf
        ).status_code,
        "chat": client.post(CHAT, json={}, headers=csrf).status_code,
    }


def test_api_363_a_worker_membership_reaches_every_action(
    supervisor: TestClient, actions: dict, csrf_headers: dict[str, str]
) -> None:
    """The claim the whole surface rests on: a department supervisor holds a
    `worker` membership, rank is not role, and the coarse router guard therefore
    has to admit every worker. What they may do to *this* department's complaint
    is `can_supervise_department` in Postgres."""
    endpoint = "4 routes in app/api/v1/routers/supervisor_triage.py"
    expected_output = {
        "resolve": 200,
        "priority-raise": 200,
        "notes": 201,
        "chat": 200,
    }

    actual_output = _every_action(supervisor, csrf_headers)

    assert actual_output == expected_output, endpoint


def test_api_364_a_resident_reaches_none_of_them(
    resident_api_client: TestClient, actions: dict, csrf_headers: dict[str, str]
) -> None:
    """The other half of the same table. The person whose flat the leak is in has
    their own screens, and none of these is one of them -- refused before any
    query runs."""
    endpoint = "4 routes in app/api/v1/routers/supervisor_triage.py"
    expected_output = {
        "resolve": 403,
        "priority-raise": 403,
        "notes": 403,
        "chat": 403,
    }

    actual_output = _every_action(resident_api_client, csrf_headers)

    assert actual_output == expected_output, endpoint


def test_api_365_every_action_is_refused_without_the_csrf_pair(
    supervisor: TestClient, actions: dict
) -> None:
    """All four change something a resident or a worker can see, so CSRF is
    checked before the role guard has anything to say."""
    endpoint = "4 routes in app/api/v1/routers/supervisor_triage.py"
    expected_output = {
        "statuses": {
            "resolve": 403,
            "priority-raise": 403,
            "notes": 403,
            "chat": 403,
        },
        "reached_repository": False,
    }

    statuses = _every_action(supervisor, {})
    actual_output = {
        "statuses": statuses,
        "reached_repository": any(
            key in actions for key in ("resolved", "raised", "note", "chat")
        ),
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# The force flag (ruling A4)
# ---------------------------------------------------------------------------


def test_api_366_assigning_without_force_is_the_offer_flow_unchanged(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The default path must reach `assign_work_order` with exactly the arguments
    it always did, and must not reach the forced one at all.

    This is the assertion that matters most in the file. An offer that quietly
    became a booking would take a worker's right to decline away, and nothing
    anywhere would error."""
    endpoint = "POST /api/v1/work-orders/work-order-id/assign"
    expected_output = {
        "status_code": 200,
        "offered": {
            "work_order_id": "work-order-id",
            "staff_assignment_id": "staff-id",
            "scheduled_start_at": None,
            "scheduled_end_at": None,
        },
        "forced": False,
    }

    response = supervisor.post(
        ASSIGN, json={"staffAssignmentId": "staff-id"}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "offered": jobs["offered"],
        "forced": "forced" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_367_force_routes_to_the_force_assign_rpc_and_carries_the_slot(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """`force: true` is the supervisor's override of the consent model, and it
    carries the same optional slot the offer does -- the supervisor picked the
    person and the hour in one gesture, and a second call to set the time would
    be a booking that briefly had none."""
    endpoint = "POST /api/v1/work-orders/work-order-id/assign"
    expected_output = {
        "status_code": 200,
        "forced": {
            "work_order_id": "work-order-id",
            "staff_assignment_id": "staff-id",
            "scheduled_start_at": "2026-08-23T10:00:00+00:00",
            "scheduled_end_at": "2026-08-23T11:00:00+00:00",
        },
        "offered": False,
    }

    response = supervisor.post(
        ASSIGN,
        json={
            "staffAssignmentId": "staff-id",
            "force": True,
            "scheduledStartAt": "2026-08-23T10:00:00Z",
            "scheduledEndAt": "2026-08-23T11:00:00Z",
        },
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "forced": jobs["forced"],
        "offered": "offered" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_368_a_forced_assignment_still_refuses_a_double_booking(
    supervisor: TestClient,
    jobs: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forcing overrides the *worker's* consent, not physics. The overlap
    constraint is the same one the offer path meets, and the refusal names the
    person -- which is the whole reason the RPC checks it in words before the
    constraint checks it in `23P01`."""
    endpoint = "POST /api/v1/work-orders/work-order-id/assign"
    expected_output = {
        "status_code": 409,
        "message": "Ravi Kumar is already booked during that time.",
    }

    def refuse(client: Any, **kwargs: Any) -> str:
        raise ConflictError(
            "Ravi Kumar is already booked during that time.", code="conflict"
        )

    monkeypatch.setattr(
        work_orders_service.repo, "force_assign_work_order", refuse
    )
    response = supervisor.post(
        ASSIGN,
        json={"staffAssignmentId": "staff-id", "force": True},
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "message": response.json()["error"]["message"],
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# The widened staff detail guard
# ---------------------------------------------------------------------------


def test_api_369_the_staff_detail_read_admits_the_department_not_only_the_admin(
    supervisor: TestClient,
    admin_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The eye popup's read. `require_admin` was refusing a department's own
    supervisors at the door, before `staff_complaint_detail` -- which has decided
    `is_community_admin OR can_supervise_department` since it was written -- could
    be asked. Widening the router guard to active membership does not widen who
    may read anything: the RPC answers `HB404` to everybody else, and a stranger
    walking complaint ids still learns nothing."""
    endpoint = "GET /api/v1/complaints/staff/complaints/complaint-id"
    expected_output = {"supervisor": 200, "admin": 200}

    def fake_detail(client: Any, *, complaint_id: str) -> Any:
        from app.domain.complaint_schemas import StaffComplaintDetail

        return StaffComplaintDetail(complaint={"id": complaint_id}, events=[])

    monkeypatch.setattr(complaints_service, "staff_detail", fake_detail)
    actual_output = {
        "supervisor": supervisor.get(STAFF_DETAIL).status_code,
        "admin": admin_api_client.get(STAFF_DETAIL).status_code,
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# Take-up (2026-08-24, ruling R8)
# ---------------------------------------------------------------------------


def test_api_370_take_up_routes_to_its_own_rpc_and_carries_the_slot(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """A third verb, not a third branch of `assign`.

    The body has no `staffAssignmentId` and the RPC has no parameter for one:
    the holder is the caller's own leadership roster row, resolved inside
    Postgres from the session. So what Python must get right is the routing --
    `take_up_work_order` and neither of the other two -- and the slot, which is
    optional here for the same reason it is optional on assign: the supervisor
    picked the job and the hour in one gesture, and a second call to set the
    time would be a booking that briefly had none."""
    endpoint = "POST /api/v1/work-orders/work-order-id/take-up"
    expected_output = {
        "status_code": 200,
        "taken_up": {
            "work_order_id": "work-order-id",
            "scheduled_start_at": "2026-08-24T10:00:00+00:00",
            "scheduled_end_at": "2026-08-24T11:00:00+00:00",
        },
        "offered": False,
        "forced": False,
    }

    response = supervisor.post(
        TAKE_UP,
        json={
            "scheduledStartAt": "2026-08-24T10:00:00Z",
            "scheduledEndAt": "2026-08-24T11:00:00Z",
        },
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "taken_up": jobs["taken_up"],
        "offered": "offered" in jobs,
        "forced": "forced" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_371_take_up_needs_no_body_and_returns_the_read_back_detail(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """Sending nothing is the common press: the job already has its hour, and
    the supervisor is answering "who", not "when". Both slot fields default to
    null and reach the RPC as nulls, which is how it knows to keep the job's
    own slot.

    The response is the read-back detail rather than the assignment id the RPC
    returns -- the screen that pressed the button needs the job, and a client
    that had to re-fetch it would render a stale card for a beat."""
    endpoint = "POST /api/v1/work-orders/work-order-id/take-up"
    expected_output = {
        "status_code": 200,
        "taken_up": {
            "work_order_id": "work-order-id",
            "scheduled_start_at": None,
            "scheduled_end_at": None,
        },
        "body": {"id": "work-order-id", "status": "scheduled", "assignments": []},
    }

    response = supervisor.post(TAKE_UP, json={}, headers=csrf_headers)
    payload = response.json()
    actual_output = {
        "status_code": response.status_code,
        "taken_up": jobs["taken_up"],
        "body": {
            "id": payload["id"],
            "status": payload["status"],
            "assignments": payload["assignments"],
        },
    }

    assert actual_output == expected_output, endpoint


def test_api_372_a_caller_with_no_leadership_row_is_refused_in_the_rpcs_words(
    supervisor: TestClient,
    jobs: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The router guard admits every worker -- rank is not role and never
    reaches the request -- so the only thing standing between a technician and
    this verb is the RPC's `HB403`. `pg_errors` passes a custom code's message
    through untouched, which is the whole reason the RPC bothers to name the
    door instead of raising a bare refusal."""
    endpoint = "POST /api/v1/work-orders/work-order-id/take-up"
    expected_output = {
        "status_code": 403,
        "code": "forbidden",
        "message": "Only this department's supervisor or manager can take up a job.",
        "read_back": False,
    }

    def refuse(client: Any, **kwargs: Any) -> str:
        raise AuthorizationError(
            "Only this department's supervisor or manager can take up a job.",
            code="forbidden",
        )

    monkeypatch.setattr(work_orders_service.repo, "take_up_work_order", refuse)
    response = supervisor.post(TAKE_UP, json={}, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
        "message": response.json()["error"]["message"],
        "read_back": "taken_up" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_373_take_up_is_an_unsafe_request_and_needs_the_csrf_pair(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The router's `require_csrf_unsafe` dependency, restated on the newest
    route rather than assumed from the ones beside it. This verb books a
    person's day off one POST with **no body at all**, which is exactly the
    shape a cross-site form can submit -- and both halves of the pair are
    checked, because an attacker who can set a cookie can set one of them.
    Neither refusal reaches the repository."""
    endpoint = "POST /api/v1/work-orders/work-order-id/take-up"
    expected_output = {
        "no_origin": (403, "csrf_origin_invalid"),
        "no_token": (403, "csrf_invalid"),
        "reached_rpc": False,
    }

    bare = supervisor.post(TAKE_UP, json={})
    origin_only = supervisor.post(
        TAKE_UP, json={}, headers={"Origin": csrf_headers["Origin"]}
    )
    actual_output = {
        "no_origin": (bare.status_code, bare.json()["error"]["code"]),
        "no_token": (origin_only.status_code, origin_only.json()["error"]["code"]),
        "reached_rpc": "taken_up" in jobs,
    }

    assert actual_output == expected_output, endpoint
