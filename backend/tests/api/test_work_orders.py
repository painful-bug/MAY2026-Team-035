"""Work orders, from the supervisor's side.

The plan's verification for this step is **"the overlap constraint rejects a
double-booking"**, and no in-process test can prove that: the constraint lives
in Postgres and these tests replace the repository. What they *can* prove is
everything around it -- that the API reaches the constraint rather than
routing around it, that the refusal it produces survives the translation layer
as a 409 with the RPC's own sentence, and that the state machine has no
transition reachable here that the RPC was not asked for.

Three assertions in this file are about **absence**, which is the harder kind to
notice going missing:

* ``PATCH /work-orders/{id}`` never forwards a status or a time. Both have their
  own routes because both carry a notification, and a general-purpose edit is
  exactly the shape that skips them.
* No route reads a caller-supplied id to decide who may act. Every 403 in this
  surface comes out of ``can_supervise_department`` in the database.
* Assigning forwards the job's own slot when the request omits one, rather than
  quietly writing a booking with no time -- which would be a booking the overlap
  constraint cannot see.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AuthorizationError, ConflictError
from app.services import work_orders_service

COMPLAINT_WORK_ORDERS = "/api/v1/complaints/complaint-id/work-orders"
DEPARTMENT_WORK_ORDERS = "/api/v1/departments/department-id/work-orders"
WORK_ORDER = "/api/v1/work-orders/work-order-id"
ASSIGN = f"{WORK_ORDER}/assign"
RESCHEDULE = f"{WORK_ORDER}/reschedule"
CANCEL = f"{WORK_ORDER}/cancel"

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


def assignment_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "assignment-id",
        "work_order_id": "work-order-id",
        "staff_assignment_id": "staff-id",
        "status": "accepted",
        "worker_name": "Ravi Kumar",
        "worker_phone_e164": "+919876500011",
        "worker_membership_id": "worker-membership-id",
        "worker_provider_id": "provider-id",
        "scheduled_start_at": SLOT_START,
        "scheduled_end_at": SLOT_END,
        "offered_at": "2026-08-10T09:30:00Z",
        "responded_at": "2026-08-10T09:30:00Z",
        "decline_reason": None,
        "is_auto_assigned": False,
    }
    base.update(overrides)
    return base


def candidate_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "staff_assignment_id": "staff-id",
        "membership_id": "worker-membership-id",
        "service_provider_id": "provider-id",
        "display_name": "Ravi Kumar",
        "has_adjacent_job": False,
        "open_jobs": 2,
        "distance_km": None,
        "away_until": None,
        "excluded": False,
    }
    base.update(overrides)
    return base


@pytest.fixture
def supervisor(admin_api_client: TestClient) -> TestClient:
    """An admin, who passes the coarse router guard.

    A department supervisor holds a ``worker`` membership and would pass it too;
    the fixture uses the admin because the router guard is not the thing under
    test here. Which of them may act on *this* department is decided by
    ``can_supervise_department`` in Postgres, and every test below that cares
    about it makes the repository raise.
    """
    return admin_api_client


@pytest.fixture
def jobs(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository under the live service."""
    captured: dict = {
        "work_order": work_order_row(),
        "for_department": [work_order_row()],
        "for_complaint": [work_order_row()],
        "assignments": [assignment_row()],
        "candidates": [candidate_row()],
    }

    def fake_get(client: Any, *, work_order_id: str) -> dict[str, Any] | None:
        captured["read"] = work_order_id
        return captured["work_order"]

    def fake_for_department(
        client: Any, *, department_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        captured["department_filter"] = {"id": department_id, "status": status}
        return captured["for_department"]

    def fake_for_complaint(
        client: Any, *, complaint_id: str
    ) -> list[dict[str, Any]]:
        captured["complaint_filter"] = complaint_id
        return captured["for_complaint"]

    def fake_assignments(
        client: Any, *, work_order_id: str
    ) -> list[dict[str, Any]]:
        return captured["assignments"]

    def fake_create(client: Any, **kwargs: Any) -> str:
        captured["created"] = kwargs
        return "work-order-id"

    def fake_update(client: Any, **kwargs: Any) -> None:
        captured["updated"] = kwargs

    def fake_assign(client: Any, **kwargs: Any) -> str:
        captured["assigned"] = kwargs
        return "assignment-id"

    def fake_reschedule(client: Any, **kwargs: Any) -> None:
        captured["rescheduled"] = kwargs

    def fake_cancel(client: Any, **kwargs: Any) -> None:
        captured["cancelled"] = kwargs

    def fake_candidates(client: Any, **kwargs: Any) -> list[dict[str, Any]]:
        captured["candidates_query"] = kwargs
        return captured["candidates"]

    repo = work_orders_service.repo
    monkeypatch.setattr(repo, "candidates", fake_candidates)
    monkeypatch.setattr(repo, "get_work_order", fake_get)
    monkeypatch.setattr(repo, "list_for_department", fake_for_department)
    monkeypatch.setattr(repo, "list_for_complaint", fake_for_complaint)
    monkeypatch.setattr(repo, "list_assignments", fake_assignments)
    monkeypatch.setattr(repo, "create_work_order", fake_create)
    monkeypatch.setattr(repo, "update_work_order", fake_update)
    monkeypatch.setattr(repo, "assign_work_order", fake_assign)
    monkeypatch.setattr(repo, "reschedule_work_order", fake_reschedule)
    monkeypatch.setattr(repo, "cancel_work_order", fake_cancel)
    yield captured


def test_api_160_triage_without_a_slot_is_a_request_not_an_omission(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The fork the whole feature turns on. A supervisor who wants to ask the
    resident something first sends no time, and both slot fields reach the RPC
    as `None` -- which is what produces a `draft` and notifies nobody. A request
    that silently substituted `now()` would propose a visit no human chose."""
    endpoint = "POST /api/v1/complaints/complaint-id/work-orders"
    expected_output = {"status_code": 201, "start": None, "end": None}

    jobs["work_order"] = work_order_row(
        status="draft", scheduled_start_at=None, scheduled_end_at=None
    )
    response = supervisor.post(
        COMPLAINT_WORK_ORDERS, json={}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "start": jobs["created"]["scheduled_start_at"],
        "end": jobs["created"]["scheduled_end_at"],
    }

    assert actual_output == expected_output, endpoint


def test_api_161_half_a_slot_is_refused_before_it_reaches_the_database(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """`0036` signals a half-slot with `22004`, which `pg_errors` maps to a 422
    carrying the repository's generic message -- true, and no help in naming
    which of two fields is missing. The model refuses it first so the caller is
    told, and the CHECK constraint stays the guarantee rather than the
    explanation."""
    endpoint = "POST /api/v1/complaints/complaint-id/work-orders"
    expected_output = {"status_code": 422, "reached_repository": False}

    response = supervisor.post(
        COMPLAINT_WORK_ORDERS,
        json={"scheduledStartAt": SLOT_START},
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "created" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_162_a_slot_that_ends_before_it_starts_is_refused(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The same reasoning one step further: a backwards range would build a
    `tstzrange` Postgres rejects outright, and the error that produces names the
    range rather than the field."""
    endpoint = "POST /api/v1/complaints/complaint-id/work-orders"
    expected_output = {"status_code": 422, "reached_repository": False}

    response = supervisor.post(
        COMPLAINT_WORK_ORDERS,
        json={"scheduledStartAt": SLOT_END, "scheduledEndAt": SLOT_START},
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "created" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_163_the_department_and_skill_are_derived_when_omitted(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """Both reach the RPC as `None` rather than being guessed here. The
    department comes from the complaint and the skill from its category, and
    both derivations live in SQL because that is where the rows are -- a Python
    lookup would be two more round trips and a second answer to a question
    `0034` already answered."""
    endpoint = "POST /api/v1/complaints/complaint-id/work-orders"
    expected_output = {"status_code": 201, "department": None, "skill": None}

    response = supervisor.post(
        COMPLAINT_WORK_ORDERS,
        json={"scheduledStartAt": SLOT_START, "scheduledEndAt": SLOT_END},
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "department": jobs["created"]["department_id"],
        "skill": jobs["created"]["skill_id"],
    }

    assert actual_output == expected_output, endpoint


def test_api_164_an_unknown_subject_kind_is_named_rather_than_passed_through(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """`subjectKind` decides whether anybody is asked to confirm the time, so a
    typo silently stored would be a resident never asked. The service checks it
    against the same two words `work_orders_subject_kind_check` allows."""
    endpoint = "POST /api/v1/complaints/complaint-id/work-orders"
    expected_output = {
        "status_code": 422,
        "code": "unknown_subject_kind",
        "reached_repository": False,
    }

    response = supervisor.post(
        COMPLAINT_WORK_ORDERS,
        json={"subjectKind": "communal"},
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
        "reached_repository": "created" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_165_a_job_the_policy_hides_is_a_404_not_a_403(
    supervisor: TestClient, jobs: dict
) -> None:
    """`can_read_work_order` hides a job the caller has no part in rather than
    refusing it, so a stranger walking work-order ids learns nothing from which
    refusals come back. The read is a 404 for a job that does not exist and a
    404 for one they may not see, and those are deliberately the same answer."""
    endpoint = "GET /api/v1/work-orders/work-order-id"
    expected_output = {"status_code": 404, "code": "work_order_not_found"}

    jobs["work_order"] = None
    response = supervisor.get(WORK_ORDER)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_166_the_detail_read_returns_the_whole_assignment_history(
    supervisor: TestClient, jobs: dict
) -> None:
    """Withdrawn and declined rows stay, because "we sent Ravi and he could not
    get in, so we sent Anil" is the question a supervisor actually asks. The
    *current* holder is the top-level `assigneeName`, which is a different
    field for a different question."""
    endpoint = "GET /api/v1/work-orders/work-order-id"
    expected_output = {
        "status_code": 200,
        "assignments": ["withdrawn", "accepted"],
        "assignee": "Ravi Kumar",
    }

    jobs["work_order"] = work_order_row(
        status="scheduled",
        assignee_name="Ravi Kumar",
        staff_assignment_id="staff-id",
    )
    jobs["assignments"] = [
        assignment_row(id="a2", status="withdrawn", worker_name="Anil Das"),
        assignment_row(id="a1", status="accepted"),
    ]
    response = supervisor.get(WORK_ORDER)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "assignments": [row["status"] for row in body["assignments"]],
        "assignee": body["assigneeName"],
    }

    assert actual_output == expected_output, endpoint


def test_api_167_the_patch_forwards_no_status_and_no_time(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The absence is the assertion. A status or a time arriving through a
    general-purpose edit would move the job without the notification and without
    the overlap check that `/assign` and `/reschedule` carry -- so the request
    model has no field for either, and unknown keys reach the repository as
    nothing at all."""
    endpoint = "PATCH /api/v1/work-orders/work-order-id"
    expected_output = {
        "status_code": 200,
        "forwarded": {"skill_id", "subject_kind", "location_text", "priority"},
    }

    response = supervisor.patch(
        WORK_ORDER,
        json={
            "locationText": "Flat B-403",
            "status": "completed",
            "scheduledStartAt": SLOT_START,
        },
        headers=csrf_headers,
    )
    forwarded = dict(jobs["updated"])
    forwarded.pop("work_order_id", None)
    actual_output = {
        "status_code": response.status_code,
        "forwarded": set(forwarded),
    }

    assert actual_output == expected_output, endpoint


def test_api_168_assigning_without_a_slot_forwards_the_job_s_own(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """Both slot fields reach the RPC as `None`, which is what tells `0036` to
    use the job's own times. The alternative -- writing a booking with no time
    -- would be a booking the exclusion constraint cannot see, because it is
    partial on `scheduled_start_at is not null`."""
    endpoint = "POST /api/v1/work-orders/work-order-id/assign"
    expected_output = {"status_code": 200, "start": None, "end": None}

    response = supervisor.post(
        ASSIGN, json={"staffAssignmentId": "staff-id"}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "start": jobs["assigned"]["scheduled_start_at"],
        "end": jobs["assigned"]["scheduled_end_at"],
    }

    assert actual_output == expected_output, endpoint


def test_api_169_a_double_booking_is_a_409_carrying_the_rpc_s_own_sentence(
    supervisor: TestClient,
    jobs: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal this step exists to produce. `0036` raises `HB409` naming the
    worker, `pg_errors` passes a custom code's message through to the caller,
    and the same 409 comes back if the constraint rather than the check catches
    it -- so a race and a mistake are indistinguishable to a client, which is
    correct. Nothing in Python decides this."""
    endpoint = "POST /api/v1/work-orders/work-order-id/assign"
    expected_output = {
        "status_code": 409,
        "code": "conflict",
        "message": "Ravi Kumar is already booked during that time.",
    }

    def refuse(client: Any, **kwargs: Any) -> str:
        raise ConflictError(
            "Ravi Kumar is already booked during that time.", code="conflict"
        )

    monkeypatch.setattr(work_orders_service.repo, "assign_work_order", refuse)
    response = supervisor.post(
        ASSIGN,
        json={
            "staffAssignmentId": "staff-id",
            "scheduledStartAt": SLOT_START,
            "scheduledEndAt": SLOT_END,
        },
        headers=csrf_headers,
    )
    error = response.json()["error"]
    actual_output = {
        "status_code": response.status_code,
        "code": error["code"],
        "message": error["message"],
    }

    assert actual_output == expected_output, endpoint


def test_api_170_the_403_comes_from_the_database_and_not_from_this_process(
    supervisor: TestClient,
    jobs: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fixture's caller is an admin, so the router guard admits them; the
    department check is `can_supervise_department` inside every RPC. A copy of
    that rule here would be a second statement of it with nothing keeping the
    two in step, and the one that drifts is always the one nobody is testing."""
    endpoint = "POST /api/v1/work-orders/work-order-id/cancel"
    expected_output = {"status_code": 403, "code": "forbidden"}

    def refuse(client: Any, **kwargs: Any) -> None:
        raise AuthorizationError(
            "You do not supervise this department.", code="forbidden"
        )

    monkeypatch.setattr(work_orders_service.repo, "cancel_work_order", refuse)
    response = supervisor.post(
        CANCEL, json={"reason": "Resident is away"}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_171_cancelling_without_a_reason_is_refused(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The reason reaches both the worker and the resident in a notification. A
    cancellation nobody can explain is the one that produces the phone call this
    feature exists to prevent, so it is required by the model as well as by the
    RPC."""
    endpoint = "POST /api/v1/work-orders/work-order-id/cancel"
    expected_output = {"status_code": 422, "reached_repository": False}

    response = supervisor.post(CANCEL, json={}, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "cancelled" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_172_rescheduling_requires_both_ends(
    supervisor: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """Unlike creation, this is not a partial edit: there is no such thing as
    moving the start of a visit and leaving its end where it was, because the
    assignment's range moves with it and a range needs two ends."""
    endpoint = "POST /api/v1/work-orders/work-order-id/reschedule"
    expected_output = {"status_code": 422, "reached_repository": False}

    response = supervisor.post(
        RESCHEDULE, json={"scheduledStartAt": SLOT_START}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "rescheduled" in jobs,
    }

    assert actual_output == expected_output, endpoint


def test_api_173_the_department_queue_forwards_its_status_filter_unwidened(
    supervisor: TestClient, jobs: dict
) -> None:
    """`?status=` narrows on top of the policy and never decides visibility. A
    supervisor asking for another department's queue gets an empty list from the
    policy rather than somebody else's work, which is why taking a department id
    from the path is safe here at all."""
    endpoint = "GET /api/v1/departments/department-id/work-orders?status=draft"
    expected_output = {
        "status_code": 200,
        "forwarded": {"id": "department-id", "status": "draft"},
    }

    response = supervisor.get(DEPARTMENT_WORK_ORDERS, params={"status": "draft"})
    actual_output = {
        "status_code": response.status_code,
        "forwarded": jobs["department_filter"],
    }

    assert actual_output == expected_output, endpoint


def test_api_174_a_complaint_may_carry_several_jobs(
    supervisor: TestClient, jobs: dict
) -> None:
    """A failed visit is rescheduled and a reopened complaint goes to a
    different supervisor, and both are a second work order rather than an edit
    to the first. This is the read that would have been impossible had the
    assignment been columns on `complaints` -- the smaller change the plan
    rejected in D5."""
    endpoint = "GET /api/v1/complaints/complaint-id/work-orders"
    expected_output = {"status_code": 200, "statuses": ["scheduled", "failed"]}

    jobs["for_complaint"] = [
        work_order_row(id="w2", status="scheduled"),
        work_order_row(id="w1", status="failed"),
    ]
    response = supervisor.get(COMPLAINT_WORK_ORDERS)
    actual_output = {
        "status_code": response.status_code,
        "statuses": [row["status"] for row in response.json()],
    }

    assert actual_output == expected_output, endpoint


def test_api_175_an_unsafe_call_without_the_csrf_pair_is_refused(
    supervisor: TestClient, jobs: dict
) -> None:
    """Every write on this router changes somebody's working day, so CSRF is
    checked before the role guard has anything to say."""
    endpoint = "POST /api/v1/work-orders/work-order-id/assign"
    expected_output = {"status_code": 403, "reached_repository": False}

    response = supervisor.post(ASSIGN, json={"staffAssignmentId": "staff-id"})
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "assigned" in jobs,
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# The department supervisor, who is who this surface is for
# ---------------------------------------------------------------------------
#
# Every test above authenticates as an admin, on the fixture's own reasoning:
# the router guard is not what those tests are about. That left the guard's
# *point* unproven — a service-department supervisor holds a ``worker``
# membership (``0035``: rank is not role, and ``claim_staff_invitations`` mints
# ``worker`` for a supervisor of a non-security department), and until
# 2026-08-21 no test in this file had ever sent one of these nine requests as
# that person.
#
# It mattered on the day the worker portal got a work-order screen. The
# assumption behind mounting it there is exactly this table, and an assumption
# is what the two tests below stop it being.


@pytest.fixture
def dispatcher(worker_api_client: TestClient) -> TestClient:
    """A department supervisor, as the API sees one: membership role ``worker``.

    There is nothing else to set. Rank lives on ``staff_assignments`` and never
    reaches the request -- which is the design, and the reason the router guard
    has to admit every worker and let ``can_supervise_department`` decide.
    """
    return worker_api_client


def _every_operation(client: TestClient, csrf: dict[str, str]) -> dict[str, int]:
    """All nine calls the triage screen makes, in one dict of status codes."""
    return {
        "POST /complaints/{id}/work-orders": client.post(
            COMPLAINT_WORK_ORDERS, json={}, headers=csrf
        ).status_code,
        "GET /complaints/{id}/work-orders": client.get(
            COMPLAINT_WORK_ORDERS
        ).status_code,
        "GET /departments/{id}/work-orders": client.get(
            DEPARTMENT_WORK_ORDERS
        ).status_code,
        "GET /work-orders/{id}": client.get(WORK_ORDER).status_code,
        "GET /work-orders/{id}/candidates": client.get(
            f"{WORK_ORDER}/candidates"
        ).status_code,
        "PATCH /work-orders/{id}": client.patch(
            WORK_ORDER, json={"priority": "high"}, headers=csrf
        ).status_code,
        "POST /work-orders/{id}/assign": client.post(
            ASSIGN, json={"staffAssignmentId": "staff-id"}, headers=csrf
        ).status_code,
        "POST /work-orders/{id}/reschedule": client.post(
            RESCHEDULE,
            json={"scheduledStartAt": SLOT_START, "scheduledEndAt": SLOT_END},
            headers=csrf,
        ).status_code,
        "POST /work-orders/{id}/cancel": client.post(
            CANCEL, json={"reason": "Resident is away"}, headers=csrf
        ).status_code,
    }


def test_api_337_a_worker_membership_reaches_every_work_order_operation(
    dispatcher: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The whole table, because a single call would leave eight untested and the
    one that drifts is always the one nobody looked at.

    A supervisor is a `worker` and passes the coarse guard; what they may do to
    *this* department is `can_supervise_department` in Postgres, which is
    stubbed here -- so what this proves is the half that is Python: no route in
    this router refuses them before the database is asked. That is precisely the
    claim the worker portal's new `/worker/work-orders` route rests on."""
    endpoint = "9 routes in app/api/v1/routers/work_orders.py"
    expected_output = {
        "POST /complaints/{id}/work-orders": 201,
        "GET /complaints/{id}/work-orders": 200,
        "GET /departments/{id}/work-orders": 200,
        "GET /work-orders/{id}": 200,
        "GET /work-orders/{id}/candidates": 200,
        "PATCH /work-orders/{id}": 200,
        "POST /work-orders/{id}/assign": 200,
        "POST /work-orders/{id}/reschedule": 200,
        "POST /work-orders/{id}/cancel": 200,
    }

    actual_output = _every_operation(dispatcher, csrf_headers)

    assert actual_output == expected_output, endpoint


def test_api_338_a_resident_reaches_none_of_them(
    resident_api_client: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The other half of the same table, and the reason the guard is there at
    all: it turns "signed-in resident poking at work-order ids" into a 403
    before any query runs. Widening the router to admit a supervisor did not
    widen it to admit the person whose flat the visit is in -- who has their own
    routes, in `resident_scheduling.py`."""
    endpoint = "9 routes in app/api/v1/routers/work_orders.py"
    expected_output = {
        "POST /complaints/{id}/work-orders": 403,
        "GET /complaints/{id}/work-orders": 403,
        "GET /departments/{id}/work-orders": 403,
        "GET /work-orders/{id}": 403,
        "GET /work-orders/{id}/candidates": 403,
        "PATCH /work-orders/{id}": 403,
        "POST /work-orders/{id}/assign": 403,
        "POST /work-orders/{id}/reschedule": 403,
        "POST /work-orders/{id}/cancel": 403,
    }

    actual_output = _every_operation(resident_api_client, csrf_headers)

    assert actual_output == expected_output, endpoint


def test_api_339_the_candidate_read_admits_the_supervisor_who_needs_it(
    dispatcher: TestClient, jobs: dict
) -> None:
    """Named on its own because the screen leans on it harder than the others.

    `GET /departments/{id}` is `require_admin_or_manager` and a supervisor
    cannot call it, so the roster the assign box offers does **not** come from
    the department read -- it comes from here, which admits them. If this route
    ever narrowed to match the departments router, the worker portal's assign
    box would go quietly empty rather than fail."""
    endpoint = "GET /api/v1/work-orders/work-order-id/candidates?includeExcluded=true"
    expected_output = {
        "status_code": 200,
        "names": ["Ravi Kumar"],
        "forwarded": {"work_order_id": "work-order-id", "include_excluded": True},
    }

    response = dispatcher.get(
        f"{WORK_ORDER}/candidates", params={"includeExcluded": "true"}
    )
    actual_output = {
        "status_code": response.status_code,
        "names": [row["displayName"] for row in response.json()],
        "forwarded": jobs["candidates_query"],
    }

    assert actual_output == expected_output, endpoint
