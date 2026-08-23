"""The worker portal's job surface.

Same guard property as ``test_worker_communities.py``, and here it is the
property most worth pinning: the fixture overrides **only** identity and leaves
``get_active_membership`` live, so a membership guard creeping onto one of these
routes runs the resolver against the sentinel client and fails. A guard on this
surface would read the role off whichever community happens to be the caller's
default, and a plumber who lives in one society and works in three others would
lose their own job list to it -- silently, and only for the people it matters
most for. See ``docs/plans/SERVICE_OPERATIONS_PROGRESS.md`` 4.16.

Beyond that, four things the migration alone cannot promise: that the list and
the detail carry different fields on purpose, that every verb answers with the
row the database settled on rather than the request, that an unregistered caller
gets a snapshot rather than an error, and that the notification badge is counted
across every community the caller works in.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_request_client
from app.core.exceptions import ConflictError
from app.domain.schemas import Principal
from app.services import worker_service

SNAPSHOT = "/api/v1/worker/snapshot"
JOBS = "/api/v1/worker/jobs"
JOB = "/api/v1/worker/jobs/work-order-id"
OPEN_JOBS = "/api/v1/worker/open-jobs"

PROFILE_ID = "worker-profile-id"
PROVIDER_ID = "provider-id"


def job_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "assignment_id": "assignment-id",
        "work_order_id": "work-order-id",
        "staff_assignment_id": "staff-id",
        "assignment_status": "offered",
        "work_order_status": "offered",
        "priority": "medium",
        "subject_kind": "resident",
        "scheduled_start_at": "2026-08-11T09:00:00Z",
        "scheduled_end_at": "2026-08-11T10:00:00Z",
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
        "complaint_description": "The kitchen tap has dripped for a week.",
        "resident_name": "Asha Menon",
        "resident_phone_e164": "+919812345678",
        "resident_unit_code": "B-204",
    }
    base.update(overrides)
    return base


def open_job_row(**overrides: Any) -> dict[str, Any]:
    """One board row as `worker_open_jobs` returns it: keyed on the work
    order, with the caller's own roster row alongside so the client never
    guesses it."""
    base: dict[str, Any] = {
        "work_order_id": "work-order-id",
        "complaint_id": "complaint-id",
        "complaint_title": "Leaking tap",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "community_id": "community-id",
        "community_name": "Green Meadows",
        "skill_id": "skill-id",
        "skill_name": "Plumbing",
        "priority": "medium",
        "subject_kind": "resident",
        "scheduled_start_at": None,
        "scheduled_end_at": None,
        "created_at": "2026-08-22T09:00:00Z",
        "staff_assignment_id": "staff-id",
    }
    base.update(overrides)
    return base


def provider_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": PROVIDER_ID,
        "profile_id": PROFILE_ID,
        "display_name": "Ravi Kumar",
        "headline": "Plumber, 12 years",
        "bio": "",
        "phone_e164": "+919876543210",
        "latitude": None,
        "longitude": None,
        "service_radius_km": 15,
        "status": "active",
        "is_available": True,
        "skill_ids": [],
        "skill_names": ["Plumbing"],
        "community_count": 2,
        "created_at": "2026-08-01T09:00:00Z",
        "updated_at": "2026-08-01T09:00:00Z",
    }
    base.update(overrides)
    return base


def engagement_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "staff_assignment_id": "staff-id",
        "community_id": "community-id",
        "community_name": "Green Meadows",
        "community_city": "Kochi",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "department_kind": "service",
        "membership_id": "membership-one",
        "membership_role": "worker",
        "rank": "member",
        "job_title": "Plumber",
        "shift": "Day",
        "status": "active",
        "started_at": "2026-07-01",
        "ended_at": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def worker_client(api_client: TestClient) -> TestClient:
    """Signed in, with **no membership override**. See the module docstring."""
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
def jobs(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repositories under the live service."""
    captured: dict = {
        "rows": [job_row()],
        "open_rows": [open_job_row()],
        "claim_error": None,
        "detail": job_row(),
        "provider_row": provider_row(),
        "engagements": [engagement_row()],
        # The membership-keyed read, which only the no-provider path uses.
        # Empty by default so the marketplace empty state stays exactly what it
        # was: no provider and nothing employing you.
        "staff_engagements": [],
        "departures": [],
        "unread": 4,
        "calls": [],
    }

    def fake_list_jobs(client: Any, **kwargs: Any) -> list[dict[str, Any]]:
        captured["calls"].append(("list", kwargs))
        return captured["rows"]

    def fake_get_job(client: Any, *, work_order_id: str) -> dict[str, Any] | None:
        captured["calls"].append(("get", work_order_id))
        return captured["detail"]

    def fake_accept(client: Any, *, work_order_id: str) -> str:
        captured["calls"].append(("accept", work_order_id))
        return "assignment-id"

    def fake_list_open_jobs(client: Any) -> list[dict[str, Any]]:
        captured["calls"].append(("open-jobs", None))
        return captured["open_rows"]

    def fake_claim(client: Any, *, work_order_id: str) -> str:
        captured["calls"].append(("claim", work_order_id))
        if captured["claim_error"] is not None:
            raise captured["claim_error"]
        return "assignment-id"

    def fake_decline(client: Any, *, work_order_id: str, reason: str | None) -> str:
        captured["calls"].append(("decline", reason))
        return "assignment-id"

    def fake_start(client: Any, *, work_order_id: str) -> None:
        captured["calls"].append(("start", work_order_id))

    def fake_complete(client: Any, *, work_order_id: str, notes: str | None) -> None:
        captured["calls"].append(("complete", notes))

    def fake_failure(client: Any, *, work_order_id: str, reason: str) -> None:
        captured["calls"].append(("unable", reason))

    def fake_get_by_profile(client: Any, *, profile_id: str) -> dict[str, Any] | None:
        return captured["provider_row"]

    def fake_engagements(
        client: Any, *, service_provider_id: str, active_only: bool
    ) -> list[dict[str, Any]]:
        return captured["engagements"]

    def fake_staff_engagements(
        client: Any, *, profile_id: str, active_only: bool
    ) -> list[dict[str, Any]]:
        captured["staff_engagements_for"] = profile_id
        return captured["staff_engagements"]

    def fake_departures(
        client: Any, *, staff_ids: list[str], status: str | None = "pending"
    ) -> list[dict[str, Any]]:
        captured["departures_asked_for"] = list(staff_ids)
        return captured["departures"]

    def fake_unread(client: Any, *, profile_id: str) -> int:
        captured["unread_for"] = profile_id
        return captured["unread"]

    repo = worker_service.repo
    monkeypatch.setattr(repo, "list_jobs", fake_list_jobs)
    monkeypatch.setattr(repo, "get_job", fake_get_job)
    monkeypatch.setattr(repo, "accept_offer", fake_accept)
    monkeypatch.setattr(repo, "list_open_jobs", fake_list_open_jobs)
    monkeypatch.setattr(repo, "claim_job", fake_claim)
    monkeypatch.setattr(repo, "decline_offer", fake_decline)
    monkeypatch.setattr(repo, "start_job", fake_start)
    monkeypatch.setattr(repo, "complete_job", fake_complete)
    monkeypatch.setattr(repo, "report_failure", fake_failure)
    monkeypatch.setattr(
        worker_service.service_providers_service.repo,
        "get_by_profile",
        fake_get_by_profile,
    )
    monkeypatch.setattr(
        worker_service.hiring_service.repo, "list_engagements", fake_engagements
    )
    monkeypatch.setattr(
        worker_service.hiring_service.repo,
        "list_engagements_for_profile",
        fake_staff_engagements,
    )
    # The no-provider branch reaches for the service client. Nothing in this
    # suite has a database behind it, and the repository above is replaced
    # anyway -- so the client is a sentinel rather than a real one.
    monkeypatch.setattr(worker_service, "get_service_client", lambda: object())
    monkeypatch.setattr(
        worker_service.hiring_service.repo, "departures_for_staff", fake_departures
    )
    monkeypatch.setattr(
        worker_service.notifications_repo, "unread_count", fake_unread
    )
    yield captured


def test_api_185_the_list_filters_on_two_different_states(
    worker_client: TestClient, jobs: dict
) -> None:
    """`assignmentStatus` asks what is being asked of me and `status` asks what
    is happening to the job. A withdrawn assignment on a job that went ahead
    without you is visible under the first and invisible under the second, and
    collapsing them into one filter loses the question a worker is actually
    asking."""
    endpoint = "GET /api/v1/worker/jobs"
    expected_output = {
        "status_code": 200,
        "filters": {"work_order_status": "in_progress", "assignment_status": "offered"},
    }

    response = worker_client.get(
        JOBS, params={"status": "in_progress", "assignmentStatus": "offered"}
    )
    _, kwargs = jobs["calls"][0]
    actual_output = {
        "status_code": response.status_code,
        "filters": {
            "work_order_status": kwargs["work_order_status"],
            "assignment_status": kwargs["assignment_status"],
        },
    }

    assert actual_output == expected_output, endpoint


def test_api_186_the_list_withholds_what_only_the_detail_needs(
    worker_client: TestClient, jobs: dict
) -> None:
    """The resident's name, flat and number are on the job a worker is on their
    way to and not on a month of finished ones. The split is in the select list,
    so this asserts the response shape rather than the query."""
    endpoint = "GET /api/v1/worker/jobs vs /jobs/{id}"
    expected_output = {"in_list": False, "in_detail": True}

    listed = worker_client.get(JOBS).json()[0]
    detail = worker_client.get(JOB).json()
    actual_output = {
        "in_list": "residentPhoneE164" in listed,
        "in_detail": detail.get("residentPhoneE164") == "+919812345678",
    }

    assert actual_output == expected_output, endpoint


def test_api_187_accepting_answers_with_the_row_the_database_settled_on(
    worker_client: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The whole point of accepting is the status afterwards, and only the
    re-read knows it: the request carried no status and the RPC returns an id.
    Echoing the request back would show `offered` on a job that is now
    `scheduled`."""
    endpoint = "POST /api/v1/worker/jobs/{id}/accept"
    expected_output = {"status_code": 200, "work_order_status": "scheduled"}

    jobs["detail"] = job_row(
        assignment_status="accepted", work_order_status="scheduled"
    )
    response = worker_client.post(f"{JOB}/accept", headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "work_order_status": response.json()["workOrderStatus"],
    }

    assert actual_output == expected_output, endpoint


def test_api_188_somebody_elses_job_is_a_404_and_not_a_403(
    worker_client: TestClient, jobs: dict
) -> None:
    """The view returns nothing for a job the caller holds no assignment on, and
    a 403 would confirm that the id exists. Every route on this surface answers
    the same way for the same reason."""
    endpoint = "GET /api/v1/worker/jobs/{id}"
    expected_output = {"status_code": 404, "code": "worker_job_not_found"}

    jobs["detail"] = None
    response = worker_client.get(JOB)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_189_a_failed_visit_must_say_why_and_a_declined_offer_need_not(
    worker_client: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The asymmetry is deliberate. A worker who was asked and is not free owes
    nobody an explanation; a worker who went and could not do the work is
    reporting something the next person has to act on, and "could not be done"
    with nothing after it guarantees a second wasted visit."""
    endpoint = "POST /api/v1/worker/jobs/{id}/unable vs /decline"
    expected_output = {"unable_without_reason": 422, "decline_without_reason": 200}

    unable = worker_client.post(f"{JOB}/unable", json={}, headers=csrf_headers)
    decline = worker_client.post(f"{JOB}/decline", json={}, headers=csrf_headers)
    actual_output = {
        "unable_without_reason": unable.status_code,
        "decline_without_reason": decline.status_code,
    }

    assert actual_output == expected_output, endpoint


def test_api_190_an_unregistered_caller_gets_a_snapshot_not_a_404(
    worker_client: TestClient, jobs: dict
) -> None:
    """This endpoint is the empty state. A null `provider` means "show the
    registration form" and an empty `communities` means "show the community
    search" -- both answered by one response rather than by a client
    interpreting two failures. `GET /service-providers/me` still 404s, because
    there the question is different."""
    endpoint = "GET /api/v1/worker/snapshot"
    expected_output = {"status_code": 200, "provider": None, "communities": []}

    jobs["provider_row"] = None
    response = worker_client.get(SNAPSHOT)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "provider": body["provider"],
        "communities": body["communities"],
    }

    assert actual_output == expected_output, endpoint


def test_an_invited_supervisor_gets_their_engagement_with_no_provider_row(
    worker_client: TestClient, jobs: dict
) -> None:
    """The defect live testing found. `claim_staff_invitations` writes a
    membership and a roster row and no `service_providers` row, so an invited
    supervisor is *unregistered* by every provider-keyed read -- and the
    snapshot used to return on the spot, empty. The portal read that as "show
    the marketplace registration form" and the Complaints screen, which decides
    supervisor access from `communities[].rank`, had nothing to decide from.

    `provider: null` and a populated `communities` are now an ordinary answer:
    the two questions -- *do you have a marketplace profile* and *does anybody
    employ you* -- are asked separately because for leadership they have
    different answers."""
    endpoint = "GET /api/v1/worker/snapshot"
    expected_output = {
        "status_code": 200,
        "provider": None,
        "ranks": ["supervisor"],
        "department_names": ["Plumbing"],
        "asked_about": PROFILE_ID,
    }

    jobs["provider_row"] = None
    jobs["staff_engagements"] = [
        engagement_row(rank="supervisor", job_title="Supervisor", shift=None)
    ]
    response = worker_client.get(SNAPSHOT)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "provider": body["provider"],
        "ranks": [row["rank"] for row in body["communities"]],
        "department_names": [row["departmentName"] for row in body["communities"]],
        "asked_about": jobs["staff_engagements_for"],
    }

    assert actual_output == expected_output, endpoint


def test_api_370_the_board_names_the_roster_row_and_keeps_the_null_slot(
    worker_client: TestClient, jobs: dict
) -> None:
    """Two promises the frozen interface makes. `staffAssignmentId` is the
    caller's own roster row, returned so the frontend never guesses which of a
    multi-community worker's rows a claim rides on. And a null slot passes
    through as null rather than being dropped or defaulted -- ruling C3 says
    an unscheduled job is on the board with a "time to be set" marker, and the
    marker is the client's to draw from exactly this null."""
    endpoint = "GET /api/v1/worker/open-jobs"
    expected_output = {
        "status_code": 200,
        "staff_assignment_id": "staff-id",
        "scheduled_start_at": None,
        "complaint_title": "Leaking tap",
    }

    response = worker_client.get(OPEN_JOBS)
    listed = response.json()[0]
    actual_output = {
        "status_code": response.status_code,
        "staff_assignment_id": listed["staffAssignmentId"],
        "scheduled_start_at": listed["scheduledStartAt"],
        "complaint_title": listed["complaintTitle"],
    }

    assert actual_output == expected_output, endpoint


def test_api_371_claiming_answers_with_the_row_the_database_settled_on(
    worker_client: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """The same contract as accepting, and it matters more here: the claim is
    the race the board creates on purpose, and only the re-read knows the job
    the caller now holds is `scheduled` -- possibly with no slot yet, which is
    C3's shape rather than an error."""
    endpoint = "POST /api/v1/worker/jobs/{id}/claim"
    expected_output = {
        "status_code": 200,
        "work_order_status": "scheduled",
        "scheduled_start_at": None,
        "claimed_first": ("claim", "work-order-id"),
    }

    jobs["detail"] = job_row(
        assignment_status="accepted",
        work_order_status="scheduled",
        scheduled_start_at=None,
        scheduled_end_at=None,
    )
    response = worker_client.post(f"{JOB}/claim", headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "work_order_status": response.json()["workOrderStatus"],
        "scheduled_start_at": response.json()["scheduledStartAt"],
        "claimed_first": jobs["calls"][0],
    }

    assert actual_output == expected_output, endpoint


def test_api_372_losing_the_claim_race_is_a_409_in_the_servers_words(
    worker_client: TestClient, jobs: dict, csrf_headers: dict[str, str]
) -> None:
    """First come, first served (C2) means somebody loses, ordinarily. The RPC
    locks the work order before it reads anything, so the loser is told
    *somebody has already taken this job* -- a sentence the card can print --
    rather than shown an exclusion-constraint violation."""
    endpoint = "POST /api/v1/worker/jobs/{id}/claim"
    expected_output = {
        "status_code": 409,
        "code": "conflict",
        "message": "Somebody has already taken this job.",
    }

    jobs["claim_error"] = ConflictError(
        "Somebody has already taken this job.", code="conflict"
    )
    response = worker_client.post(f"{JOB}/claim", headers=csrf_headers)
    body = response.json()["error"]
    actual_output = {
        "status_code": response.status_code,
        "code": body["code"],
        "message": body["message"],
    }

    assert actual_output == expected_output, endpoint


def test_api_191_the_badge_counts_every_community_the_caller_works_in(
    worker_client: TestClient, jobs: dict
) -> None:
    """The one place a user can see the multi-membership seam. A count scoped to
    a default community would silently drop the notifications from the two
    societies a plumber is not currently 'in'.

    Since `0041` the count is asked of the *person*, which is what makes that
    true for a provider whose engagements are still being decided -- a badge
    assembled from a list of memberships is empty for somebody who holds none,
    and an unhired provider with an unanswered application is exactly who has
    something waiting."""
    endpoint = "GET /api/v1/worker/snapshot"
    expected_output = {"asked_about": PROFILE_ID, "unread": 4}

    jobs["engagements"] = [
        engagement_row(membership_id="membership-one"),
        engagement_row(
            staff_assignment_id="staff-two",
            community_id="community-two",
            membership_id="membership-two",
        ),
    ]
    response = worker_client.get(SNAPSHOT)
    actual_output = {
        "asked_about": jobs["unread_for"],
        "unread": response.json()["unreadNotifications"],
    }

    assert actual_output == expected_output, endpoint
