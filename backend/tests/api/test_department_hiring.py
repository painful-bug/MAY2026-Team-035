"""Hiring, from the department's side.

The case that matters most in this module is ``api_143``, and it is about a
thing the tests cannot see. **Accepting an application writes a membership and a
roster row atomically**, and that happens inside
``decide_service_application`` -- one transaction, in Postgres, replaced here by
a stub. No in-process test can prove atomicity; what these cases can prove is
that the API never offers a path around it. So the assertions are about what
reaches the RPC and what does not: one call, carrying the terms, with the
decision the caller asked for and no second write beside it.

``api_145`` pins the other half of the same idea from the authorization side.
The router guard asks whether the caller manages *anything*; only
``can_manage_department`` in the database asks whether they manage *this*. A
test that stubbed the RPC and asserted a 200 would be asserting that the guard
we do not rely on passed.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AuthorizationError
from app.services import hiring_service

DEPARTMENT = "/api/v1/departments/department-id"
APPLICATIONS = f"{DEPARTMENT}/applications"
CANDIDATES = f"{DEPARTMENT}/candidates"
INVITATIONS = f"{DEPARTMENT}/invitations"
BLACKLIST = f"{DEPARTMENT}/blacklist"
REMOVE = f"{DEPARTMENT}/members/staff-id/remove"
DECIDE = f"{APPLICATIONS}/application-id/decide"

#: Spelled once. The literal is 90 characters and the line-length limit is 88.
DECIDE_ENDPOINT = "POST " + DECIDE


def application_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "application-id",
        "community_id": "community-id",
        "community_name": "Green Meadows",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "department_kind": "service",
        "service_provider_id": "provider-id",
        "provider_display_name": "Ravi Kumar",
        "provider_headline": "Plumber, 12 years",
        "provider_phone_e164": "+919876543210",
        "provider_skill_names": ["Plumbing"],
        "direction": "applied",
        "status": "accepted",
        "message": None,
        "rank": "member",
        "job_title": "Plumber",
        "shift": "Day",
        "decision_note": None,
        "decided_at": "2026-08-09T10:00:00Z",
        "distance_km": 4.2,
        "created_at": "2026-08-09T09:00:00Z",
        "updated_at": "2026-08-09T10:00:00Z",
    }
    base.update(overrides)
    return base


def candidate_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "provider-id",
        "display_name": "Ravi Kumar",
        "headline": "Plumber, 12 years",
        "phone_e164": "+919876543210",
        "status": "active",
        "is_available": True,
        "service_radius_km": 15,
        "distance_km": 4.2,
        "matching_skill_names": ["Plumbing"],
        "skill_names": ["Plumbing", "Carpentry"],
        "community_count": 2,
        "has_open_application": False,
    }
    base.update(overrides)
    return base


@pytest.fixture
def hiring(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository, recording every call."""
    captured: dict = {
        "applications": [application_row()],
        "candidates": [candidate_row()],
        "calls": [],
    }

    def fake_list_for_department(
        client: Any, *, department_id: str, status: str | None
    ) -> list[dict[str, Any]]:
        captured["listed"] = {"department_id": department_id, "status": status}
        return captured["applications"]

    def fake_search_candidates(client: Any, **kwargs: Any) -> list[dict[str, Any]]:
        captured["searched"] = kwargs
        return captured["candidates"]

    def fake_invite(client: Any, **kwargs: Any) -> str:
        captured["calls"].append("invite")
        captured["invited"] = kwargs
        return "application-id"

    def fake_decide(client: Any, *, application_id: str, **kwargs: Any) -> str:
        captured["calls"].append("decide")
        captured["decided"] = {"id": application_id, **kwargs}
        return "staff-id"

    def fake_remove(client: Any, *, staff_id: str, reason: str | None) -> None:
        captured["calls"].append("remove")
        captured["removed"] = {"staff_id": staff_id, "reason": reason}

    def fake_blacklist(client: Any, **kwargs: Any) -> None:
        captured["calls"].append("blacklist")
        captured["blacklisted"] = kwargs

    def fake_get_application(
        client: Any, *, application_id: str
    ) -> dict[str, Any] | None:
        return captured["applications"][0] if captured["applications"] else None

    repo = hiring_service.repo
    monkeypatch.setattr(
        repo, "list_applications_for_department", fake_list_for_department
    )
    monkeypatch.setattr(repo, "search_candidates", fake_search_candidates)
    monkeypatch.setattr(repo, "invite_provider", fake_invite)
    monkeypatch.setattr(repo, "decide_application", fake_decide)
    monkeypatch.setattr(repo, "remove_member", fake_remove)
    monkeypatch.setattr(repo, "blacklist_provider", fake_blacklist)
    monkeypatch.setattr(repo, "get_application", fake_get_application)
    yield captured


def test_api_142_the_candidate_list_says_which_skills_matched(
    admin_api_client: TestClient, hiring: dict
) -> None:
    """`matchingSkillNames` is the subset that put a candidate on this list;
    `skillNames` is everything they do. Showing only the second leaves a manager
    wondering why an electrician is offered for a plumbing department."""
    endpoint = "GET /api/v1/departments/department-id/candidates"
    expected_output = {
        "status_code": 200,
        "matching": ["Plumbing"],
        "all_skills": ["Plumbing", "Carpentry"],
        "department_forwarded": "department-id",
    }

    response = admin_api_client.get(CANDIDATES)
    body = response.json()[0]
    actual_output = {
        "status_code": response.status_code,
        "matching": body["matchingSkillNames"],
        "all_skills": body["skillNames"],
        "department_forwarded": hiring["searched"]["department_id"],
    }

    assert actual_output == expected_output, endpoint


def test_api_143_accepting_makes_exactly_one_call_carrying_the_terms(
    admin_api_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """The hire. Membership and roster row are written together inside the RPC,
    so the only thing the API can promise is that it never writes them
    separately: one call, with the terms, and nothing beside it."""
    endpoint = DECIDE_ENDPOINT
    input_data = {"decision": "accepted", "jobTitle": "Plumber"}
    expected_output = {
        "status_code": 200,
        "calls": ["decide"],
        "decision": "accepted",
        "job_title": "Plumber",
        "status_returned": "accepted",
    }

    response = admin_api_client.post(
        DECIDE, json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "calls": hiring["calls"],
        "decision": hiring["decided"]["decision"],
        "job_title": hiring["decided"]["job_title"],
        "status_returned": response.json()["status"],
    }

    assert actual_output == expected_output, endpoint


def test_api_144_a_rank_sent_by_a_stale_client_cannot_promote_anybody(
    admin_api_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """Nobody is hired above `member` through the serviceman path.

    Until 2026-08-11 this request carried `rank`, and this case asserted that
    `head` was translated to the stored `manager`. The PO removed rank from
    this path entirely: leadership is provisioned by email, and somebody who
    registered as a service provider joins as a team member.

    A field the model no longer declares is **ignored**, not rejected -- Pydantic
    defaults to `extra='ignore'`. That is the right failure for this rule and it
    is why the case is worth keeping rather than deleting: a browser holding a
    cached bundle that still sends `rank: 'supervisor'` must not produce a
    supervisor. It forwards nothing, and the RPC's own default settles it.
    """
    endpoint = DECIDE_ENDPOINT
    input_data = {"decision": "accepted", "rank": "supervisor", "shift": "Day"}
    expected_output = {
        "status_code": 200,
        "rank_forwarded": None,
        "shift_forwarded": None,
    }

    response = admin_api_client.post(
        DECIDE, json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "rank_forwarded": hiring["decided"]["rank"],
        "shift_forwarded": hiring["decided"]["shift"],
    }

    assert actual_output == expected_output, endpoint


def test_api_145_a_manager_of_another_community_is_refused_by_the_database(
    admin_api_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
    , monkeypatch: pytest.MonkeyPatch
) -> None:
    """The router guard passes -- the caller manages something. Only
    `can_manage_department` knows they do not manage *this*, and it lives in
    Postgres, so the 403 arrives from the repository. Asserting the guard alone
    would be asserting the check we deliberately do not rely on."""
    endpoint = "POST /api/v1/departments/department-id/blacklist"
    input_data = {"serviceProviderId": "provider-id", "reason": "Repeated no-shows."}
    expected_output = {"status_code": 403, "code": "forbidden"}

    def refuse(client: Any, **kwargs: Any) -> None:
        raise AuthorizationError("You do not manage this department.", code="forbidden")

    monkeypatch.setattr(hiring_service.repo, "blacklist_provider", refuse)

    response = admin_api_client.post(BLACKLIST, json=input_data, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_146_withdrawn_is_not_a_decision_this_endpoint_accepts(
    admin_api_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """A manager withdrawing an application instead of rejecting it would erase
    the record that they refused somebody. Withdrawal belongs to the side that
    opened the negotiation, and it has its own route."""
    endpoint = DECIDE_ENDPOINT
    input_data = {"decision": "withdrawn"}
    expected_output = {
        "status_code": 422,
        "code": "unknown_decision",
        "reached_repository": False,
    }

    response = admin_api_client.post(
        DECIDE, json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
        "reached_repository": bool(hiring["calls"]),
    }

    assert actual_output == expected_output, endpoint


def test_api_147_blacklisting_requires_a_reason(
    admin_api_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """Whoever eventually decides whether to revoke a bar needs to know what it
    was for. An unexplained permanent decision is one nobody can review."""
    endpoint = "POST /api/v1/departments/department-id/blacklist"
    input_data = {"serviceProviderId": "provider-id"}
    expected_output = {"status_code": 422, "reached_repository": False}

    response = admin_api_client.post(BLACKLIST, json=input_data, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": bool(hiring["calls"]),
    }

    assert actual_output == expected_output, endpoint


def test_api_148_removal_carries_the_reason_in_the_body_not_the_url(
    admin_api_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """A POST rather than a DELETE, because nothing is deleted and because the
    reason is a note one person writes about another -- a query parameter would
    put it in every access log on the way."""
    endpoint = "POST /api/v1/departments/department-id/members/staff-id/remove"
    input_data = {"reason": "Contract ended."}
    expected_output = {
        "status_code": 200,
        "staff_id": "staff-id",
        "reason": "Contract ended.",
    }

    response = admin_api_client.post(REMOVE, json=input_data, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "staff_id": hiring["removed"]["staff_id"],
        "reason": hiring["removed"]["reason"],
    }

    assert actual_output == expected_output, endpoint


def test_api_149_a_resident_cannot_reach_the_hiring_surface(
    resident_api_client: TestClient, hiring: dict
) -> None:
    """The coarse guard doing its one job: a signed-in resident poking at
    department ids is refused before any query runs."""
    endpoint = "GET /api/v1/departments/department-id/applications"
    expected_output = {"status_code": 403, "reached_repository": False}

    response = resident_api_client.get(APPLICATIONS)
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "listed" in hiring,
    }

    assert actual_output == expected_output, endpoint


def test_api_150_an_invitation_offers_a_job_title_at_member_rank(
    admin_api_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """An invitation offers a *job title*, and always at rank `member`.

    It carried `rank` and `shift` until the 2026-08-11 ruling. Both are gone:
    leadership is provisioned by email through `staff-invitations` and never
    hired here, and `staff_assignments.shift` describes nothing the system
    reads -- work reaches a worker through the dispatch sweep or a supervisor,
    and a guard's rota is `security_shifts`.

    `rank` is asserted as the literal `member` rather than `None`: the service
    layer sends it explicitly so the value this API intends is visible at the
    call site rather than inherited from an RPC default nobody reading the
    Python would see.
    """
    endpoint = "POST /api/v1/departments/department-id/invitations"
    input_data = {
        "serviceProviderId": "provider-id",
        "jobTitle": "Plumber",
        "message": "We need a plumber on Tuesdays.",
    }
    expected_output = {
        "status_code": 201,
        "calls": ["invite"],
        "rank": "member",
        "shift": None,
        "job_title": "Plumber",
        "department_id": "department-id",
    }

    response = admin_api_client.post(
        INVITATIONS, json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "calls": hiring["calls"],
        "rank": hiring["invited"]["rank"],
        "shift": hiring["invited"]["shift"],
        "job_title": hiring["invited"]["job_title"],
        "department_id": hiring["invited"]["department_id"],
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# Departures
#
# The one property worth asserting here is the refusal: an approval with items
# outstanding must reach the caller as a 409, unchanged. Everything else in this
# feature exists to make that refusal survivable, so an API that quietly turned
# it into a partial success would have removed the feature and kept the code.
# ---------------------------------------------------------------------------

DEPARTURES = f"{DEPARTMENT}/departures"
DEPARTURE = f"{DEPARTURES}/departure-id"

#: Spelled once. Both literals are over the 88-character line limit inline.
DECIDE_DEPARTURE_ENDPOINT = "POST " + DEPARTURE + "/decide"
REASSIGN_ENDPOINT = "POST " + DEPARTURE + "/reassign"


def departure_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "departure-id",
        "community_id": "community-id",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "department_kind": "service",
        "staff_assignment_id": "staff-id",
        "service_provider_id": "provider-id",
        "membership_id": "membership-one",
        "display_name": "Ravi Kumar",
        "rank": "member",
        "job_title": "Plumber",
        "initiated_by": "worker",
        "status": "pending",
        "reason": "Moving cities.",
        "decision_note": None,
        "decided_at": None,
        "open_commitment_count": 2,
        "created_at": "2026-08-10T09:00:00Z",
        "updated_at": "2026-08-10T09:00:00Z",
    }
    base.update(overrides)
    return base


def staff_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "staff-id",
        "department_id": "department-id",
        "membership_id": "membership-one",
        "service_provider_id": "provider-id",
        "display_name": "Ravi Kumar",
        "phone_e164": None,
        "job_title": "Plumber",
        "rank": "member",
        "shift": "Day",
        "status": "active",
        "active_assignment_count": 1,
        "open_commitment_count": 2,
        "departure_status": "pending",
        "departure_effective_at": "2026-09-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def item_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "item_kind": "work_order",
        "item_id": "assignment-id",
        "reference_id": "work-order-id",
        "title": "Leaking tap in B-402",
        "starts_at": "2026-08-11T09:00:00Z",
        "ends_at": "2026-08-11T10:00:00Z",
        "item_status": "accepted",
    }
    base.update(overrides)
    return base


@pytest.fixture
def departures(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the departure half of the repository."""
    captured: dict = {
        "rows": [departure_row()],
        "items": [
            item_row(),
            item_row(item_kind="security_shift", item_id="shift-id"),
        ],
        "staff_row": staff_row(),
        "calls": [],
    }

    def fake_list(
        client: Any, *, department_id: str, status: str | None
    ) -> list[dict[str, Any]]:
        captured["listed"] = {"department_id": department_id, "status": status}
        return captured["rows"]

    def fake_get(client: Any, *, departure_id: str) -> dict[str, Any] | None:
        captured["calls"].append("get")
        return captured["rows"][0] if captured["rows"] else None

    def fake_items(client: Any, *, staff_id: str) -> list[dict[str, Any]]:
        captured["calls"].append("items")
        captured["items_for"] = staff_id
        return captured["items"]

    def fake_request(
        client: Any,
        *,
        staff_id: str,
        reason: str | None,
        effective_at: str | None = None,
    ) -> str:
        captured["calls"].append("request")
        captured["requested"] = {
            "staff_id": staff_id,
            "reason": reason,
            "effective_at": effective_at,
        }
        return "departure-id"

    def fake_reassign(client: Any, **kwargs: Any) -> str | None:
        captured["calls"].append("reassign")
        captured["reassigned"] = kwargs
        return "staff-two"

    def fake_get_staff_member(
        client: Any, *, department_id: str, staff_id: str
    ) -> dict[str, Any] | None:
        captured["calls"].append("staff")
        row = captured.get("staff_row")
        if row and row["department_id"] == department_id and row["id"] == staff_id:
            return row
        return None

    def fake_departures_for_staff(
        client: Any, *, staff_ids: list[str], status: str | None = "pending"
    ) -> list[dict[str, Any]]:
        return [
            r for r in captured["rows"] if r["staff_assignment_id"] in staff_ids
        ]

    def fake_schedule(
        client: Any,
        *,
        staff_id: str,
        starts_after: str | None = None,
        starts_before: str | None = None,
    ) -> list[dict[str, Any]]:
        captured["calls"].append("schedule")
        captured["schedule_window"] = {
            "staff_id": staff_id,
            "from": starts_after,
            "to": starts_before,
        }
        return captured["items"]

    def fake_coverage(client: Any, *, departure_id: str) -> list[dict[str, Any]]:
        captured["calls"].append("coverage")
        captured["coverage_for"] = departure_id
        return captured.get("coverage_rows", [])

    def fake_decide(
        client: Any,
        *,
        departure_id: str,
        decision: str,
        note: str | None,
        effective_at: str | None = None,
    ) -> None:
        captured["calls"].append("decide")
        captured["decided"] = {
            "id": departure_id,
            "decision": decision,
            "note": note,
            "effective_at": effective_at,
        }

    repo = hiring_service.repo
    monkeypatch.setattr(repo, "list_departures", fake_list)
    monkeypatch.setattr(repo, "get_departure", fake_get)
    monkeypatch.setattr(repo, "departure_items", fake_items)
    monkeypatch.setattr(repo, "request_departure", fake_request)
    monkeypatch.setattr(repo, "reassign_item", fake_reassign)
    monkeypatch.setattr(repo, "decide_departure", fake_decide)
    monkeypatch.setattr(repo, "get_staff_member", fake_get_staff_member)
    monkeypatch.setattr(repo, "departures_for_staff", fake_departures_for_staff)
    monkeypatch.setattr(repo, "staff_schedule", fake_schedule)
    monkeypatch.setattr(repo, "departure_coverage", fake_coverage)
    yield captured


def test_api_216_approval_no_longer_gates_on_the_handover_and_forwards_the_date(
    admin_api_client: TestClient, departures: dict, csrf_headers: dict[str, str]
) -> None:
    """Until 2026-08-10 this test asserted a 409 while anything was booked.
    The product owner overturned that rule: the decision is the manager's, and
    approval *releases* the booked work to the dispatch pool instead of being
    refused for it. What the service owes now is faithfulness — the manager's
    `effectiveAt` reaches the database as the same instant, and no commitment
    count is consulted on the way."""
    endpoint = DECIDE_DEPARTURE_ENDPOINT
    input_data = {"decision": "approve", "effectiveAt": "2026-09-01T00:00:00Z"}
    expected_output = {
        "status_code": 200,
        "decision_seen_by_database": "approve",
        "effective_at_seen_by_database": "2026-09-01T00:00:00+00:00",
    }

    response = admin_api_client.post(
        f"{DEPARTURE}/decide", json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "decision_seen_by_database": departures["decided"]["decision"],
        "effective_at_seen_by_database": departures["decided"]["effective_at"],
    }

    assert actual_output == expected_output, endpoint


def test_api_217_reassigning_without_a_successor_asks_for_the_best_candidate(
    admin_api_client: TestClient, departures: dict, csrf_headers: dict[str, str]
) -> None:
    """A null staff id is the *ordinary* case and means take whoever the dispatch
    ranking returns -- the same ranking auto-assignment uses. If the API filled
    in a default here, the handover would stop following the ranking the product
    owner asked it to follow."""
    endpoint = REASSIGN_ENDPOINT
    input_data = {"kind": "work_order", "itemId": "assignment-id"}
    expected_output = {
        "status_code": 200,
        "successor": None,
        "kind": "work_order",
        "item_id": "assignment-id",
    }

    response = admin_api_client.post(
        f"{DEPARTURE}/reassign", json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "successor": departures["reassigned"]["staff_assignment_id"],
        "kind": departures["reassigned"]["kind"],
        "item_id": departures["reassigned"]["item_id"],
    }

    assert actual_output == expected_output, endpoint


def test_api_218_an_unknown_item_kind_never_reaches_the_database(
    admin_api_client: TestClient, departures: dict, csrf_headers: dict[str, str]
) -> None:
    """Two kinds, named in one place. The RPC would refuse a third with its own
    `22P02`, but the message a caller gets from here names both alternatives --
    and no write is attempted for a request that cannot succeed."""
    endpoint = REASSIGN_ENDPOINT
    input_data = {"kind": "amenity_booking", "itemId": "assignment-id"}
    expected_output = {"status_code": 422, "calls": []}

    response = admin_api_client.post(
        f"{DEPARTURE}/reassign", json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "calls": departures["calls"],
    }

    assert actual_output == expected_output, endpoint


def test_api_219_the_handover_list_is_read_only_after_the_departure_is(
    admin_api_client: TestClient, departures: dict
) -> None:
    """Two clients, in order, and the order is the authorization.
    `staff_departure_items` is `service_role` only because it returns complaint
    titles; the caller's own client reads the departure first, so RLS decides
    whether they may see it at all. Reading the items first would hand a
    stranger a department's work list on a guessed uuid."""
    endpoint = "GET /api/v1/departments/department-id/departures/departure-id"
    expected_output = {
        "status_code": 200,
        "calls": ["get", "items"],
        "kinds": ["work_order", "security_shift"],
        "items_for": "staff-id",
    }

    response = admin_api_client.get(DEPARTURE)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "calls": departures["calls"],
        "kinds": [item["kind"] for item in body["items"]],
        "items_for": departures["items_for"],
    }

    assert actual_output == expected_output, endpoint


def test_api_220_a_departure_the_policy_hides_reads_no_items_at_all(
    admin_api_client: TestClient, departures: dict
) -> None:
    """The other half of api_219. A manager of another community reaches this
    handler -- the router guard only asks whether they manage *something* -- and
    the RLS policy returns no row. The 404 has to happen before the service
    client is used, or the guard is decorative."""
    endpoint = "GET /api/v1/departments/department-id/departures/departure-id"
    expected_output = {"status_code": 404, "calls": ["get"]}

    departures["rows"] = []
    response = admin_api_client.get(DEPARTURE)
    actual_output = {
        "status_code": response.status_code,
        "calls": departures["calls"],
    }

    assert actual_output == expected_output, endpoint


STAFF = "/api/v1/departments/department-id/staff/staff-id"


def test_api_222_the_employee_page_gets_the_roster_row_and_its_departure(
    admin_api_client: TestClient, departures: dict
) -> None:
    """One read for the identity card. The row is the same shape the roster tab
    renders — one mapping, not two that drift — and `departure` rides along
    when one is pending or approved-for-a-date, because the page the
    termination notification lands on has to show what it is deciding."""
    endpoint = "GET /api/v1/departments/{departmentId}/staff/{staffId}"
    expected_output = {
        "status_code": 200,
        "name": "Ravi Kumar",
        "departure_id": "departure-id",
        "departure_status": "pending",
    }

    response = admin_api_client.get(STAFF)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "name": body["name"],
        "departure_id": body["departure"]["id"],
        "departure_status": body["departureStatus"],
    }

    assert actual_output == expected_output, endpoint


def test_api_223_a_staff_id_from_another_department_is_a_404_not_a_leak(
    admin_api_client: TestClient, departures: dict
) -> None:
    """The path's department is a scope. The same roster row fetched under a
    different department's URL must not render — a link that shows somebody
    from another department is a link that lies, and the schedule read below it
    would leak complaint titles across department lines."""
    endpoint = "GET /api/v1/departments/{departmentId}/staff/{staffId}"
    expected_output = {"status_code": 404, "schedule_read": False}

    response = admin_api_client.get(
        "/api/v1/departments/department-two/staff/staff-id/schedule"
    )
    actual_output = {
        "status_code": response.status_code,
        "schedule_read": "schedule" in departures["calls"],
    }

    assert actual_output == expected_output, endpoint


def test_api_224_the_schedule_window_reaches_the_database_untouched(
    admin_api_client: TestClient, departures: dict
) -> None:
    """`from`/`to` are forwarded as the same instants the caller sent. The
    calendar decides its own window; a service that clamped or defaulted it
    would make the page's "next week" button a lie."""
    endpoint = "GET /api/v1/departments/{departmentId}/staff/{staffId}/schedule"
    expected_output = {
        "status_code": 200,
        "kinds": ["work_order", "security_shift"],
        "window": {
            "staff_id": "staff-id",
            "from": "2026-08-10T00:00:00+00:00",
            "to": "2026-08-17T00:00:00+00:00",
        },
    }

    response = admin_api_client.get(
        f"{STAFF}/schedule",
        params={"from": "2026-08-10T00:00:00Z", "to": "2026-08-17T00:00:00Z"},
    )
    actual_output = {
        "status_code": response.status_code,
        "kinds": [item["kind"] for item in response.json()],
        "window": departures["schedule_window"],
    }

    assert actual_output == expected_output, endpoint


def test_api_225_zero_coverage_is_an_answer_not_an_error(
    admin_api_client: TestClient, departures: dict
) -> None:
    """The doc's words: *"If there are none, it says so."* An item nobody can
    take comes back with `candidateCount: 0` and a 200 — the decision screen
    renders a statement, not an error state. And the departure is read with
    the caller's client before the service client computes anything (the
    api_219 ordering)."""
    endpoint = (
        "GET /api/v1/departments/{departmentId}/departures/{departureId}/coverage"
    )
    expected_output = {
        "status_code": 200,
        "counts": [2, 0],
        "first_names": ["Asha Nair", "Vikram Shah"],
        "calls": ["get", "coverage"],
    }

    departures["coverage_rows"] = [
        item_row(candidate_count=2, candidate_names=["Asha Nair", "Vikram Shah"]),
        item_row(
            item_kind="security_shift",
            item_id="shift-id",
            candidate_count=0,
            candidate_names=[],
        ),
    ]
    response = admin_api_client.get(f"{DEPARTURE}/coverage")
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "counts": [item["candidateCount"] for item in body],
        "first_names": body[0]["candidateNames"],
        "calls": departures["calls"],
    }

    assert actual_output == expected_output, endpoint
