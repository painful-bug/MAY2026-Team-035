"""The supervisor's triage dashboard: one read and one verb.

**What these tests can and cannot prove.** The bucketing itself --- *live*,
*engaged*, taken up but undispatched --- is `supervisor_triage_snapshot` in
`20260822120000`, and it is Postgres. It is stubbed here, so nothing below shows
that a job with an outstanding offer lands in `assignedPending` rather than
`takenUp`. No test in this suite can: it has no database. That half is
`tests/test_supervisor_triage_migration.py`, statically, and the SQL editor after
the file is applied.

What they do prove is the half that is Python, and it is the half where a mistake
is silent:

* the four arrays are rendered **in the order and grouping the RPC returned
  them**. The frozen contract says the server buckets and the client does not
  re-derive, and a service that filtered here would be a fifth definition of
  *engaged* that nobody would think to look for;
* the storage vocabulary is translated exactly once, through
  `app/domain/vocabularies.py`, so `high` reaches the screen as `High` and
  `acknowledged` as `In Progress` --- the same words every other complaint
  surface sends;
* `POST /complaints/{id}/take-up` **declares no request body**, which is not a
  stylistic preference: the house `post()` helper on the frontend always sends
  `{}`, and a required model would turn every press of the button into a 422;
* every refusal comes out of the database. The 409 in particular carries the
  RPC's own sentence, naming whoever already holds the complaint, because
  "already taken up" with no name sends a supervisor to ask around an office.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.services import supervisor_triage_service

SNAPSHOT = "/api/v1/departments/department-id/triage-snapshot"
TAKE_UP = "/api/v1/complaints/complaint-id/take-up"


def complaint_row(**overrides: Any) -> dict[str, Any]:
    """One row as the RPC projects it: storage vocabulary, snake_case."""
    base: dict[str, Any] = {
        "id": "complaint-id",
        "title": "Kitchen tap leaking",
        "category": "Plumbing",
        "priority": "high",
        "status": "open",
        "location": "Flat B-402",
        "raised_by": "Meera Nair",
        "unit_code": "B-402",
        "created_at": "2026-08-22T09:00:00Z",
        "due_at": "2026-08-24T09:00:00Z",
        "returned_to_pool_at": None,
        "reopened_count": 0,
        "rerouted_at": None,
        "taken_up_at": None,
        "taken_up_by_name": None,
        "live_work_order_count": 0,
        "open_request_id": None,
    }
    base.update(overrides)
    return base


def work_order_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "work-order-id",
        "complaint_id": "complaint-id",
        "complaint_title": "Kitchen tap leaking",
        "complaint_category": "Plumbing",
        "priority": "medium",
        "status": "scheduled",
        "assignee_name": "Ravi Kumar",
        "scheduled_start_at": "2026-08-23T10:00:00Z",
        "scheduled_end_at": "2026-08-23T11:00:00Z",
        "started_at": None,
        "inherited_at": None,
        "location_text": "Flat B-402",
        "skill_name": "Plumber",
        "created_at": "2026-08-22T09:30:00Z",
    }
    base.update(overrides)
    return base


def snapshot_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "department_id": "department-id",
        "new_complaints": [complaint_row()],
        "taken_up": [],
        "assigned_pending": [],
        "in_progress": [],
    }
    base.update(overrides)
    return base


@pytest.fixture
def supervisor(worker_api_client: TestClient) -> TestClient:
    """A department supervisor, as the API sees one: membership role ``worker``.

    There is nothing else to set. Rank lives on ``staff_assignments`` and never
    reaches the request, which is the design and the reason the router guard has
    to admit every worker and let ``can_supervise_department`` decide.
    """
    return worker_api_client


@pytest.fixture
def triage(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository under the live service."""
    captured: dict = {"payload": snapshot_payload()}

    def fake_snapshot(client: Any, *, department_id: str) -> dict[str, Any]:
        captured["read"] = department_id
        return captured["payload"]

    def fake_take_up(client: Any, *, complaint_id: str) -> None:
        captured["taken_up"] = complaint_id

    repo = supervisor_triage_service.repo
    monkeypatch.setattr(repo, "triage_snapshot", fake_snapshot)
    monkeypatch.setattr(repo, "take_up_complaint", fake_take_up)
    yield captured


def test_api_340_the_four_sections_arrive_grouped_as_the_database_grouped_them(
    supervisor: TestClient, triage: dict
) -> None:
    """The frozen contract's load-bearing sentence: **bucketing is decided
    server-side**. Four rows go in, one per section, and each comes out in the
    section it went into --- nothing here re-derives *live* or *engaged*, which
    would be a second set of definitions free to disagree with the RPC's."""
    endpoint = "GET /api/v1/departments/department-id/triage-snapshot"
    expected_output = {
        "status_code": 200,
        "newComplaints": ["c-new"],
        "takenUp": ["c-taken"],
        "assignedPending": ["w-pending"],
        "inProgress": ["w-progress"],
    }

    triage["payload"] = snapshot_payload(
        new_complaints=[complaint_row(id="c-new")],
        taken_up=[
            complaint_row(
                id="c-taken",
                status="acknowledged",
                taken_up_at="2026-08-22T10:00:00Z",
                taken_up_by_name="Suresh Iyer",
            )
        ],
        assigned_pending=[work_order_row(id="w-pending")],
        in_progress=[
            work_order_row(
                id="w-progress",
                status="in_progress",
                started_at="2026-08-23T10:05:00Z",
            )
        ],
    )
    body = supervisor.get(SNAPSHOT).json()
    actual_output = {
        "status_code": 200,
        "newComplaints": [row["id"] for row in body["newComplaints"]],
        "takenUp": [row["id"] for row in body["takenUp"]],
        "assignedPending": [row["id"] for row in body["assignedPending"]],
        "inProgress": [row["id"] for row in body["inProgress"]],
    }

    assert actual_output == expected_output, endpoint


def test_api_341_the_stored_vocabulary_is_translated_exactly_once(
    supervisor: TestClient, triage: dict
) -> None:
    """`high` reaches the screen as `High` and `acknowledged` as `In Progress`,
    through `app/domain/vocabularies.py` --- the same table every other complaint
    surface uses. The RPC deliberately sends the stored words: a `case` in SQL
    turning `high` into `High` would be a second copy of that table, in a
    language where nobody would look for it.

    The **work order's** status is passed through unmapped, and that is not an
    inconsistency: `scheduled` is the work-order vocabulary, `WorkOrder` has
    always sent it, and a second spelling depending on which endpoint answered
    would be the real inconsistency."""
    endpoint = "GET /api/v1/departments/department-id/triage-snapshot"
    expected_output = {
        "status_code": 200,
        "complaint_priority": "High",
        "complaint_status": "In Progress",
        "work_order_priority": "Medium",
        "work_order_status": "scheduled",
    }

    triage["payload"] = snapshot_payload(
        new_complaints=[complaint_row(priority="high", status="acknowledged")],
        assigned_pending=[work_order_row(priority="medium", status="scheduled")],
    )
    response = supervisor.get(SNAPSHOT)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "complaint_priority": body["newComplaints"][0]["priority"],
        "complaint_status": body["newComplaints"][0]["status"],
        "work_order_priority": body["assignedPending"][0]["priority"],
        "work_order_status": body["assignedPending"][0]["status"],
    }

    assert actual_output == expected_output, endpoint


def test_api_342_the_three_reassignment_badges_survive_the_projection(
    supervisor: TestClient, triage: dict
) -> None:
    """`returnedToPoolAt`, `reopenedCount` and `reroutedAt` are the whole of
    section 1's "this is not as new as it looks", and `inheritedAt` is section
    3's. All four ride on facts the engine already recorded --- none is a new
    lifecycle state --- so the only way to lose one is to drop it in the
    projection, which is exactly what nothing would error on."""
    endpoint = "GET /api/v1/departments/department-id/triage-snapshot"
    expected_output = {
        "status_code": 200,
        "returnedToPoolAt": "2026-08-21T08:00:00Z",
        "reopenedCount": 2,
        "reroutedAt": "2026-08-20T08:00:00Z",
        "inheritedAt": "2026-08-22T07:00:00Z",
    }

    triage["payload"] = snapshot_payload(
        new_complaints=[
            complaint_row(
                returned_to_pool_at="2026-08-21T08:00:00Z",
                reopened_count=2,
                rerouted_at="2026-08-20T08:00:00Z",
            )
        ],
        assigned_pending=[work_order_row(inherited_at="2026-08-22T07:00:00Z")],
    )
    response = supervisor.get(SNAPSHOT)
    body = response.json()
    complaint = body["newComplaints"][0]
    actual_output = {
        "status_code": response.status_code,
        "returnedToPoolAt": complaint["returnedToPoolAt"].replace("+00:00", "Z"),
        "reopenedCount": complaint["reopenedCount"],
        "reroutedAt": complaint["reroutedAt"].replace("+00:00", "Z"),
        "inheritedAt": body["assignedPending"][0]["inheritedAt"].replace(
            "+00:00", "Z"
        ),
    }

    assert actual_output == expected_output, endpoint


def test_api_343_an_empty_department_is_four_empty_arrays_and_a_200(
    supervisor: TestClient, triage: dict
) -> None:
    """Never a 404 and never a partial body. A department with nothing on it has
    four empty sections, which is a thing the screen can render; a missing key
    would be a section that throws."""
    endpoint = "GET /api/v1/departments/department-id/triage-snapshot"
    expected_output = {
        "status_code": 200,
        "sections": {
            "newComplaints": [],
            "takenUp": [],
            "assignedPending": [],
            "inProgress": [],
        },
    }

    triage["payload"] = snapshot_payload(new_complaints=[])
    response = supervisor.get(SNAPSHOT)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "sections": {key: body[key] for key in expected_output["sections"]},
    }

    assert actual_output == expected_output, endpoint


def test_api_344_a_department_the_caller_does_not_supervise_is_a_403(
    supervisor: TestClient,
    triage: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refusal, not an empty snapshot.

    An empty dashboard and a refused one look identical on a screen, and the
    difference is the whole content of the answer. The rule is
    `can_supervise_department` inside the RPC --- the same predicate
    `GET /departments/{id}/complaints` asks --- and nothing in Python restates
    it, because the copy that drifts is always the one nobody is testing."""
    endpoint = "GET /api/v1/departments/department-id/triage-snapshot"
    expected_output = {
        "status_code": 403,
        "code": "forbidden",
        "message": "You do not work on this department's complaints.",
    }

    def refuse(client: Any, **kwargs: Any) -> dict[str, Any]:
        raise AuthorizationError(
            "You do not work on this department's complaints.", code="forbidden"
        )

    monkeypatch.setattr(supervisor_triage_service.repo, "triage_snapshot", refuse)
    response = supervisor.get(SNAPSHOT)
    error = response.json()["error"]
    actual_output = {
        "status_code": response.status_code,
        "code": error["code"],
        "message": error["message"],
    }

    assert actual_output == expected_output, endpoint


def test_api_345_taking_up_needs_no_body_and_refuses_none(
    supervisor: TestClient, triage: dict, csrf_headers: dict[str, str]
) -> None:
    """**The route declares no request model at all**, and the frontend is why.

    The house `post()` helper always sends `{}`, even for a body-less endpoint
    (`workerApi.acceptJob` is the precedent). A required model would answer 422
    to every press of the button; a model with optional fields would be a place
    to name somebody else, and the acting supervisor is the session. Both an
    empty object and no body at all are a 200.
    """
    endpoint = "POST /api/v1/complaints/complaint-id/take-up"
    expected_output = {
        "status_code": 200,
        "with_empty_object": 200,
        "forwarded": "complaint-id",
        "message": "Complaint taken up.",
    }

    bare = supervisor.post(TAKE_UP, headers=csrf_headers)
    with_body = supervisor.post(TAKE_UP, json={}, headers=csrf_headers)
    actual_output = {
        "status_code": bare.status_code,
        "with_empty_object": with_body.status_code,
        "forwarded": triage["taken_up"],
        "message": with_body.json()["message"],
    }

    assert actual_output == expected_output, endpoint


def test_api_346_somebody_else_s_complaint_is_a_409_that_names_them(
    supervisor: TestClient,
    triage: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal this verb exists to produce well. `take_up_complaint` raises
    `HB409` naming the holder, `pg_errors` passes a custom code's message through
    untouched, and it reaches the screen --- because "already taken up" without a
    name sends a supervisor to ask around an office."""
    endpoint = "POST /api/v1/complaints/complaint-id/take-up"
    expected_output = {
        "status_code": 409,
        "code": "conflict",
        "message": "Suresh Iyer has already taken this complaint up.",
    }

    def refuse(client: Any, **kwargs: Any) -> None:
        raise ConflictError(
            "Suresh Iyer has already taken this complaint up.", code="conflict"
        )

    monkeypatch.setattr(supervisor_triage_service.repo, "take_up_complaint", refuse)
    response = supervisor.post(TAKE_UP, json={}, headers=csrf_headers)
    error = response.json()["error"]
    actual_output = {
        "status_code": response.status_code,
        "code": error["code"],
        "message": error["message"],
    }

    assert actual_output == expected_output, endpoint


def test_api_347_an_unknown_complaint_is_a_404_from_the_database(
    supervisor: TestClient,
    triage: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing in this process reads a complaint before writing to it. A lookup
    here would be a second answer to "does this exist", asked with the caller's
    RLS rather than the RPC's, and the two would disagree on exactly the rows
    that matter."""
    endpoint = "POST /api/v1/complaints/complaint-id/take-up"
    expected_output = {"status_code": 404, "code": "not_found"}

    def refuse(client: Any, **kwargs: Any) -> None:
        raise NotFoundError("No such complaint.", code="not_found")

    monkeypatch.setattr(supervisor_triage_service.repo, "take_up_complaint", refuse)
    response = supervisor.post(TAKE_UP, json={}, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_348_taking_up_without_the_csrf_pair_is_refused(
    supervisor: TestClient, triage: dict
) -> None:
    """It changes what a resident sees --- `open` becomes `acknowledged`, which
    their screen renders as *In Progress* --- so CSRF is checked before the role
    guard has anything to say."""
    endpoint = "POST /api/v1/complaints/complaint-id/take-up"
    expected_output = {"status_code": 403, "reached_repository": False}

    response = supervisor.post(TAKE_UP, json={})
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "taken_up" in triage,
    }

    assert actual_output == expected_output, endpoint


def _both_operations(client: TestClient, csrf: dict[str, str]) -> dict[str, int]:
    return {
        "GET /departments/{id}/triage-snapshot": client.get(SNAPSHOT).status_code,
        "POST /complaints/{id}/take-up": client.post(
            TAKE_UP, json={}, headers=csrf
        ).status_code,
    }


def test_api_349_a_worker_membership_reaches_both_operations(
    supervisor: TestClient, triage: dict, csrf_headers: dict[str, str]
) -> None:
    """The claim the whole surface rests on. A department supervisor holds a
    `worker` membership --- rank is not role, `0035` settled that --- so the
    coarse router guard has to admit every worker, and what they may do to *this*
    department is `can_supervise_department` in Postgres. This proves the half
    that is Python: no route here refuses them before the database is asked."""
    endpoint = "2 routes in app/api/v1/routers/supervisor_triage.py"
    expected_output = {
        "GET /departments/{id}/triage-snapshot": 200,
        "POST /complaints/{id}/take-up": 200,
    }

    actual_output = _both_operations(supervisor, csrf_headers)

    assert actual_output == expected_output, endpoint


def test_api_350_a_resident_reaches_neither(
    resident_api_client: TestClient, triage: dict, csrf_headers: dict[str, str]
) -> None:
    """The other half of the same table, and the reason the guard is there at
    all: it turns "signed-in resident poking at department ids" into a 403 before
    any query runs. The person whose flat the leak is in has their own screens
    and this is not one of them."""
    endpoint = "2 routes in app/api/v1/routers/supervisor_triage.py"
    expected_output = {
        "GET /departments/{id}/triage-snapshot": 403,
        "POST /complaints/{id}/take-up": 403,
    }

    actual_output = _both_operations(resident_api_client, csrf_headers)

    assert actual_output == expected_output, endpoint


def test_api_351_an_admin_reaches_both_because_managing_implies_supervising(
    admin_api_client: TestClient, triage: dict, csrf_headers: dict[str, str]
) -> None:
    """`can_manage_department` implies `can_supervise_department` --- it is the
    first line of that predicate's body (`0036` 4) --- so an admin opening a
    department's dashboard is not a widening, it is the rule already written.
    Asserted because the router guard and the database predicate are two
    different lists and only one of them is in this repository's Python."""
    endpoint = "2 routes in app/api/v1/routers/supervisor_triage.py"
    expected_output = {
        "GET /departments/{id}/triage-snapshot": 200,
        "POST /complaints/{id}/take-up": 200,
    }

    actual_output = _both_operations(admin_api_client, csrf_headers)

    assert actual_output == expected_output, endpoint


def test_api_352_a_malformed_section_empties_itself_and_not_the_screen(
    supervisor: TestClient, triage: dict
) -> None:
    """The one piece of defensiveness in the service, and its bound.

    `jsonb_agg` over an empty set is `null`, which the RPC already coalesces to
    `[]`. If a section ever arrives as something else, it renders empty rather
    than raising --- because one malformed section should not take the other
    three off the screen with it. This is a fallback and not a contract: the RPC
    owns the shape."""
    endpoint = "GET /api/v1/departments/department-id/triage-snapshot"
    expected_output = {
        "status_code": 200,
        "takenUp": [],
        "newComplaints": ["complaint-id"],
    }

    triage["payload"] = snapshot_payload(taken_up=None)
    response = supervisor.get(SNAPSHOT)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "takenUp": body["takenUp"],
        "newComplaints": [row["id"] for row in body["newComplaints"]],
    }

    assert actual_output == expected_output, endpoint


def test_api_379_the_sixth_section_carries_the_jobs_waiting_on_a_resident(
    supervisor: TestClient, triage: dict
) -> None:
    """The 2026-08-23 ruling F1's dashboard half: a job the resident has been
    asked to put an hour on is not an *open request*. Nothing on it is the
    supervisor's to move -- they cannot pick the time and they are not meant to
    -- so listing it beside the work they can take up was showing them a queue
    that was not theirs.

    `openRequests` narrows to `draft` and `offered` in the same change, and the
    split is the RPC's: this asserts only that the seventh key is read and
    rendered as its own array, because a service that dropped it would leave the
    new section permanently and silently empty."""
    endpoint = "GET /api/v1/departments/department-id/triage-snapshot"
    expected_output = {
        "status_code": 200,
        "awaitingResident": ["w-awaiting"],
        "openRequests": ["w-open"],
        "awaiting_status": "awaiting_resident",
    }

    triage["payload"] = snapshot_payload(
        awaiting_resident=[
            work_order_row(
                id="w-awaiting",
                status="awaiting_resident",
                assignee_name=None,
                scheduled_start_at=None,
                scheduled_end_at=None,
            )
        ],
        open_requests=[work_order_row(id="w-open", status="draft")],
    )
    response = supervisor.get(SNAPSHOT)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "awaitingResident": [row["id"] for row in body["awaitingResident"]],
        "openRequests": [row["id"] for row in body["openRequests"]],
        "awaiting_status": body["awaitingResident"][0]["status"],
    }

    assert actual_output == expected_output, endpoint
