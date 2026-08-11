"""A service person finding work.

The same guard property ``test_service_providers.py`` pins, for the same reason:
the fixture overrides **only** identity and leaves ``get_active_membership``
live, so a membership guard creeping onto one of these routes runs the resolver
against the sentinel client and fails the test. This is the surface a provider
uses *because* nobody has hired them yet; requiring a membership here would make
the product un-hireable, and that failure would be invisible in a test that
stubbed the membership out.

Beyond the guard, three things are asserted that the migration alone cannot
promise: that both directions of a negotiation arrive in one list, that
withdrawing reaches the RPC as ``withdrawn`` rather than as a delete, and that
an unregistered caller is a 404 rather than an empty list.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_request_client
from app.domain.schemas import Principal
from app.services import hiring_service

COMMUNITIES = "/api/v1/worker/communities"
SEARCH = "/api/v1/worker/communities/search"
APPLICATIONS = "/api/v1/worker/applications"

PROFILE_ID = "provider-profile-id"
PROVIDER_ID = "provider-id"


def application_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "application-id",
        "community_id": "community-id",
        "community_name": "Green Meadows",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "department_kind": "service",
        "service_provider_id": PROVIDER_ID,
        "provider_display_name": "Ravi Kumar",
        "provider_headline": "Plumber, 12 years",
        "provider_phone_e164": "+919876543210",
        "provider_skill_names": ["Plumbing"],
        "direction": "applied",
        "status": "pending",
        "message": "Available weekday mornings.",
        "rank": None,
        "job_title": None,
        "shift": None,
        "decision_note": None,
        "decided_at": None,
        "distance_km": 4.2,
        "created_at": "2026-08-09T09:00:00Z",
        "updated_at": "2026-08-09T09:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def provider_client(api_client: TestClient) -> TestClient:
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
def hiring(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace both repositories under the live service."""
    captured: dict = {
        "provider_row": {"id": PROVIDER_ID, "profile_id": PROFILE_ID},
        "applications": [application_row()],
        "engagements": [],
        "communities": [],
        "departures": [],
    }

    def fake_get_by_profile(client: Any, *, profile_id: str) -> dict[str, Any] | None:
        captured["profile_id"] = profile_id
        return captured["provider_row"]

    def fake_list_for_provider(
        client: Any, *, service_provider_id: str, status: str | None
    ) -> list[dict[str, Any]]:
        captured["listed_provider"] = service_provider_id
        captured["listed_status"] = status
        return captured["applications"]

    def fake_list_engagements(
        client: Any, *, service_provider_id: str, active_only: bool
    ) -> list[dict[str, Any]]:
        captured["active_only"] = active_only
        return captured["engagements"]

    def fake_search_communities(
        client: Any, *, query: str | None, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        captured["search"] = {"query": query, "limit": limit, "offset": offset}
        return captured["communities"]

    def fake_apply(client: Any, *, department_id: str, message: str | None) -> str:
        captured["applied_to"] = department_id
        captured["applied_message"] = message
        return "application-id"

    def fake_decide(client: Any, *, application_id: str, **kwargs: Any) -> str:
        captured["decided"] = {"id": application_id, **kwargs}
        return application_id

    def fake_get_application(
        client: Any, *, application_id: str
    ) -> dict[str, Any] | None:
        return captured["applications"][0] if captured["applications"] else None

    def fake_departures_for_staff(
        client: Any, *, staff_ids: list[str], status: str | None = "pending"
    ) -> list[dict[str, Any]]:
        captured["departures_asked_for"] = list(staff_ids)
        return captured["departures"]

    def fake_request_departure(
        client: Any,
        *,
        staff_id: str,
        reason: str | None,
        effective_at: str | None = None,
    ) -> str:
        captured["requested"] = {
            "staff_id": staff_id,
            "reason": reason,
            "effective_at": effective_at,
        }
        return "departure-id"

    def fake_cancel_departure(client: Any, *, departure_id: str) -> None:
        captured["cancelled"] = departure_id

    def fake_get_departure(
        client: Any, *, departure_id: str
    ) -> dict[str, Any] | None:
        return captured["departures"][0] if captured["departures"] else None

    repo = hiring_service.repo
    monkeypatch.setattr(repo, "departures_for_staff", fake_departures_for_staff)
    monkeypatch.setattr(repo, "request_departure", fake_request_departure)
    monkeypatch.setattr(repo, "cancel_departure", fake_cancel_departure)
    monkeypatch.setattr(repo, "get_departure", fake_get_departure)
    monkeypatch.setattr(
        hiring_service.providers_repo, "get_by_profile", fake_get_by_profile
    )
    monkeypatch.setattr(repo, "list_applications_for_provider", fake_list_for_provider)
    monkeypatch.setattr(repo, "list_engagements", fake_list_engagements)
    monkeypatch.setattr(repo, "search_communities", fake_search_communities)
    monkeypatch.setattr(repo, "apply_to_department", fake_apply)
    monkeypatch.setattr(repo, "decide_application", fake_decide)
    monkeypatch.setattr(repo, "get_application", fake_get_application)
    yield captured


def test_api_136_the_applications_list_carries_both_directions(
    provider_client: TestClient, hiring: dict
) -> None:
    """An application sent and an invitation received are one row shape with a
    different `direction`, and a client switches on it to decide whether to
    render 'withdraw' or 'accept / decline'. Two lists would make a provider
    check two screens to learn whether anyone wants them."""
    endpoint = "GET /api/v1/worker/applications"
    expected_output = {"status_code": 200, "directions": ["applied", "invited"]}

    hiring["applications"] = [
        application_row(id="a1", direction="applied"),
        application_row(id="a2", direction="invited"),
    ]
    response = provider_client.get(APPLICATIONS)
    actual_output = {
        "status_code": response.status_code,
        "directions": [row["direction"] for row in response.json()],
    }

    assert actual_output == expected_output, endpoint


def test_api_137_an_unregistered_caller_is_a_404_not_an_empty_list(
    provider_client: TestClient, hiring: dict
) -> None:
    """"You have not registered" is a different answer from "nobody has hired
    you", and the dashboard routes on the difference -- one sends them to the
    registration form, the other to the community search."""
    endpoint = "GET /api/v1/worker/communities"
    expected_output = {"status_code": 404, "code": "service_provider_not_found"}

    hiring["provider_row"] = None
    response = provider_client.get(COMMUNITIES)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_138_the_community_search_needs_no_registration_and_no_membership(
    provider_client: TestClient, hiring: dict
) -> None:
    """The search resolves the caller inside the RPC, so it neither 404s an
    unregistered caller nor 403s one who belongs to no community. An empty list
    is the honest answer to 'which communities need trades you have not told us
    about'."""
    endpoint = "GET /api/v1/worker/communities/search"
    expected_output = {"status_code": 200, "body": [], "limit": 20, "offset": 0}

    hiring["provider_row"] = None
    response = provider_client.get(SEARCH)
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
        "limit": hiring["search"]["limit"],
        "offset": hiring["search"]["offset"],
    }

    assert actual_output == expected_output, endpoint


def test_api_139_applying_reads_the_negotiation_back_rather_than_echoing_it(
    provider_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """The response carries the community name, the provider's skills and the
    distance -- none of which the request contained. Echoing the request back
    would return everything except what the screen renders."""
    endpoint = "POST /api/v1/worker/applications"
    input_data = {"departmentId": "department-id", "message": "Weekday mornings."}
    expected_output = {
        "status_code": 201,
        "community_name": "Green Meadows",
        "distance_km": 4.2,
        "forwarded_department": "department-id",
    }

    response = provider_client.post(APPLICATIONS, json=input_data, headers=csrf_headers)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "community_name": body["communityName"],
        "distance_km": body["distanceKm"],
        "forwarded_department": hiring["applied_to"],
    }

    assert actual_output == expected_output, endpoint


def test_api_140_withdrawing_reaches_the_rpc_as_a_decision_not_a_delete(
    provider_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """`DELETE` is the verb the screen wants; `withdrawn` is what the database
    records. Nothing is removed -- the row stays on the list with a new status,
    which is why the route returns it rather than a 204."""
    endpoint = "DELETE /api/v1/worker/applications/application-id"
    expected_output = {
        "status_code": 200,
        "decision": "withdrawn",
        "application_id": "application-id",
    }

    response = provider_client.delete(
        f"{APPLICATIONS}/application-id", headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "decision": hiring["decided"]["decision"],
        "application_id": hiring["decided"]["id"],
    }

    assert actual_output == expected_output, endpoint


def test_api_141_applying_without_the_csrf_pair_is_refused(
    provider_client: TestClient, hiring: dict
) -> None:
    """No membership guard on this router, so CSRF is the only thing standing
    between a cross-site form post and an application somebody did not make."""
    endpoint = "POST /api/v1/worker/applications"
    expected_output = {"status_code": 403, "reached_repository": False}

    response = provider_client.post(APPLICATIONS, json={"departmentId": "d1"})
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "applied_to" in hiring,
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# Leaving
#
# The three properties the migration cannot promise on its own: that the roster
# row travels in the path rather than being guessed from the session, that the
# engagement list carries the open request so one screen can render both verbs,
# and that cancelling something that is not open is a 404 rather than a
# reassuring 200.
# ---------------------------------------------------------------------------


def departure_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "departure-id",
        "community_id": "community-id",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "department_kind": "service",
        "staff_assignment_id": "staff-id",
        "service_provider_id": PROVIDER_ID,
        "membership_id": "membership-one",
        "display_name": "Ravi Kumar",
        "rank": "member",
        "job_title": "Plumber",
        "initiated_by": "worker",
        "status": "pending",
        "reason": "Moving cities.",
        "decision_note": None,
        "decided_at": None,
        "open_commitment_count": 3,
        "created_at": "2026-08-10T09:00:00Z",
        "updated_at": "2026-08-10T09:00:00Z",
    }
    base.update(overrides)
    return base


def test_api_213_the_roster_row_is_named_in_the_path_not_guessed(
    provider_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """A service person hired by three societies is leaving exactly one of them,
    and nothing in the session says which. Deriving the community from a default
    membership would resign them from whichever one sorted first."""
    endpoint = "POST /api/v1/worker/communities/{staffId}/departure"
    input_data = {"reason": "Moving cities."}
    expected_output = {
        "status_code": 201,
        "staff_id": "staff-two",
        "reason": "Moving cities.",
        "outstanding": 3,
    }

    hiring["departures"] = [departure_row(staff_assignment_id="staff-two")]
    response = provider_client.post(
        f"{COMMUNITIES}/staff-two/departure", json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "staff_id": hiring["requested"]["staff_id"],
        "reason": hiring["requested"]["reason"],
        "outstanding": response.json()["openCommitmentCount"],
    }

    assert actual_output == expected_output, endpoint


def test_api_221_a_leave_date_is_forwarded_and_not_reinterpreted(
    provider_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """The worker's popup picks *immediately* or *a date*; immediately is
    spelled by omitting the field. The service forwards the date as an ISO
    instant and adds nothing — deciding what the date means (the freeze, the
    release window) is `0045`'s job, in one place, in SQL."""
    endpoint = "POST /api/v1/worker/communities/{staffId}/departure"
    input_data = {"reason": "Moving cities.", "effectiveAt": "2026-09-01T00:00:00Z"}
    expected_output = {
        "status_code": 201,
        "effective_at": "2026-09-01T00:00:00+00:00",
    }

    hiring["departures"] = [departure_row()]
    response = provider_client.post(
        f"{COMMUNITIES}/staff-id/departure", json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "effective_at": hiring["requested"]["effective_at"],
    }

    assert actual_output == expected_output, endpoint


def test_api_214_each_community_card_carries_its_own_open_request(
    provider_client: TestClient, hiring: dict
) -> None:
    """One read, not one per card. The leave button on a community card says
    'request' or 'withdraw' depending on this field, and a provider on four
    rosters would otherwise cost four round trips to render one screen."""
    endpoint = "GET /api/v1/worker/communities"
    expected_output = {
        "status_code": 200,
        "asked_about": ["staff-id", "staff-two"],
        "departures": [3, None],
    }

    hiring["engagements"] = [
        {
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
        },
        {
            "staff_assignment_id": "staff-two",
            "community_id": "community-two",
            "community_name": "Palm Grove",
            "community_city": "Kochi",
            "department_id": "department-two",
            "department_name": "Electrical",
            "department_kind": "service",
            "membership_id": "membership-two",
            "membership_role": "worker",
            "rank": "member",
            "job_title": "Electrician",
            "shift": "Day",
            "status": "active",
            "started_at": "2026-07-01",
            "ended_at": None,
        },
    ]
    hiring["departures"] = [departure_row()]

    response = provider_client.get(COMMUNITIES)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "asked_about": hiring["departures_asked_for"],
        "departures": [
            row["departure"]["openCommitmentCount"] if row["departure"] else None
            for row in body
        ],
    }

    assert actual_output == expected_output, endpoint


def test_api_215_withdrawing_a_request_that_is_not_open_is_a_404(
    provider_client: TestClient, hiring: dict, csrf_headers: dict[str, str]
) -> None:
    """A 200 here would tell a provider their request was withdrawn when the
    manager had already approved it — and the next screen they see is the one
    that no longer lists the community."""
    endpoint = "DELETE /api/v1/worker/communities/{staffId}/departure"
    expected_output = {"status_code": 404, "reached_repository": False}

    hiring["departures"] = []
    response = provider_client.request(
        "DELETE", f"{COMMUNITIES}/staff-id/departure", headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "cancelled" in hiring,
    }

    assert actual_output == expected_output, endpoint
