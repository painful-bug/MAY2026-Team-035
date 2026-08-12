"""A service person's own registration.

Two things are tested, and the first is the one that matters.

**That these routes need no membership.** Every other write surface in this API
resolves an active community membership first. These must not, because a person
who has registered but been hired nowhere holds no membership -- and a guard that
required one would 403 them out of exactly the screens that let them apply for
work. The fixture here therefore overrides *only* identity, leaving
``get_active_membership`` live: if a membership guard is ever added to one of
these routes, the resolver runs against the sentinel client and the test fails
rather than the product quietly becoming un-hireable.

**That the response is the database's answer, not the request echoed back.**
Three fields on a profile are not the caller's to choose -- ``skillNames`` comes
from the catalogue, ``communityCount`` is counted from live memberships, and
``serviceRadiusKm`` defaults in SQL -- so a write is asserted by what comes back
differing from what went in.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_request_client
from app.api.v1.routers import service_providers as router_module
from app.domain.schemas import Principal
from app.services import service_providers_service

SKILLS = "/api/v1/skills"
PROVIDERS = "/api/v1/service-providers"
ME = "/api/v1/service-providers/me"
MY_SKILLS = "/api/v1/service-providers/me/skills"
MY_AVAILABILITY = "/api/v1/service-providers/me/availability"

PROFILE_ID = "provider-profile-id"


def overview_row(**overrides: Any) -> dict[str, Any]:
    """One ``service_provider_overview`` row, as PostgREST would return it."""
    base: dict[str, Any] = {
        "id": "provider-id",
        "profile_id": PROFILE_ID,
        "display_name": "Ravi Kumar",
        "headline": "Plumber, 12 years",
        "bio": None,
        "phone_e164": "+919876543210",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "service_radius_km": 15,
        "status": "active",
        "is_available": True,
        "skill_ids": ["skill-plumbing"],
        "skill_names": ["Plumbing"],
        "community_count": 2,
        "created_at": "2026-08-09T09:00:00Z",
        "updated_at": "2026-08-09T09:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def provider_client(api_client: TestClient) -> TestClient:
    """A signed-in caller with **no membership override**.

    Deliberately not ``resident_api_client``: that fixture also overrides
    ``get_active_membership``, which would hide a membership guard creeping onto
    one of these routes rather than expose it.
    """
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
def providers(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository. Records arguments, returns what is staged."""
    captured: dict = {
        "row": overview_row(),
        # What `_CANDIDATE_SELECT` actually asks PostgREST for. Spelled as its
        # own row rather than reusing `overview_row()` so that a test asserting
        # "no coordinates on the wire" is testing the *service*, not a fixture
        # that helpfully removed them.
        "candidate_row": {
            key: value
            for key, value in overview_row().items()
            if key not in ("profile_id", "latitude", "longitude", "updated_at")
        },
        "skill_count": 1,
        "is_available": True,
    }

    def fake_get_by_profile(client: Any, *, profile_id: str) -> dict[str, Any] | None:
        captured["profile_id"] = profile_id
        return captured["row"]

    def fake_list_skills(client: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "skill-plumbing",
                "name": "Plumbing",
                "category": "maintenance",
                "description": "Leaks, taps, drainage, sanitary fittings.",
            }
        ]

    def fake_save_profile(client: Any, **kwargs: Any) -> str:
        captured["saved"] = kwargs
        return "provider-id"

    def fake_register_profile(client: Any, **kwargs: Any) -> str:
        captured["registered"] = kwargs
        return "provider-id"

    def fake_set_skills(client: Any, *, skill_ids: list[str]) -> int:
        captured["skill_ids"] = skill_ids
        return captured["skill_count"]

    def fake_set_availability(client: Any, *, is_available: bool) -> bool:
        captured["requested_availability"] = is_available
        return captured["is_available"]

    def fake_get_by_id(client: Any, *, provider_id: str) -> dict[str, Any] | None:
        captured["requested_provider_id"] = provider_id
        return captured["candidate_row"]

    repo = service_providers_service.repo
    monkeypatch.setattr(repo, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(repo, "get_by_profile", fake_get_by_profile)
    monkeypatch.setattr(repo, "list_skills", fake_list_skills)
    monkeypatch.setattr(repo, "save_profile", fake_save_profile)
    monkeypatch.setattr(repo, "register_profile", fake_register_profile)
    monkeypatch.setattr(repo, "set_skills", fake_set_skills)
    monkeypatch.setattr(repo, "set_availability", fake_set_availability)
    yield captured


def test_api_124_the_skill_catalogue_is_readable_by_any_signed_in_caller(
    provider_client: TestClient, providers: dict
) -> None:
    """`GET /skills` needs identity and nothing else -- no membership, no
    registration. Someone deciding whether to register has to see the trades
    before they have either."""
    endpoint = "GET /api/v1/skills"
    expected_output = {"status_code": 200, "first_name": "Plumbing"}

    response = provider_client.get(SKILLS)
    actual_output = {
        "status_code": response.status_code,
        "first_name": response.json()[0]["name"],
    }

    assert actual_output == expected_output, endpoint


def test_api_125_registering_returns_the_profile_the_database_settled_on(
    provider_client: TestClient, providers: dict, csrf_headers: dict[str, str]
) -> None:
    """The response carries `skillNames` and `communityCount`, which the request
    never contained. Echoing the request back would return everything except the
    answers."""
    endpoint = "POST /api/v1/service-providers"
    input_data = {
        "displayName": " Ravi Kumar ",
        "phone": "+919876543210",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "serviceRadiusKm": 15,
        "skillIds": ["skill-plumbing"],
    }
    expected_output = {
        "status_code": 201,
        "skill_names": ["Plumbing"],
        "community_count": 2,
        "service_radius_km": 15.0,
        "registered_name": "Ravi Kumar",
        "registered_skills": ["skill-plumbing"],
    }

    response = provider_client.post(PROVIDERS, json=input_data, headers=csrf_headers)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "skill_names": body["skillNames"],
        "community_count": body["communityCount"],
        "service_radius_km": body["serviceRadiusKm"],
        "registered_name": providers["registered"]["display_name"],
        "registered_skills": providers["registered"]["skill_ids"],
    }

    assert actual_output == expected_output, endpoint


def test_api_126_an_omitted_field_reaches_the_rpc_as_null_not_as_a_blank(
    provider_client: TestClient, providers: dict, csrf_headers: dict[str, str]
) -> None:
    """The RPC coalesces a null onto the stored value, so `None` is what makes a
    partial PATCH leave the other fields alone. Sending `""` would erase them."""
    endpoint = "PATCH /api/v1/service-providers/me"
    input_data = {}
    expected_output = {"status_code": 200, "bio": None, "latitude": None}

    response = provider_client.patch(ME, json=input_data, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "bio": providers["saved"]["bio"],
        "latitude": providers["saved"]["latitude"],
    }

    assert actual_output == expected_output, endpoint


def test_api_127_an_unregistered_caller_is_a_404_not_an_empty_profile(
    provider_client: TestClient, providers: dict
) -> None:
    """"You are not a service provider" is a different answer from "you are one
    with nothing filled in", and the dashboard routes on the difference."""
    endpoint = "GET /api/v1/service-providers/me"
    expected_output = {"status_code": 404, "code": "service_provider_not_found"}

    providers["row"] = None
    response = provider_client.get(ME)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_128_the_skill_count_comes_back_from_the_database_not_the_request(
    provider_client: TestClient, providers: dict, csrf_headers: dict[str, str]
) -> None:
    """Ids naming a retired or unknown skill are dropped by the RPC rather than
    rejected, so a client sending three and being told one has learned something
    true about its stale list."""
    endpoint = "PUT /api/v1/service-providers/me/skills"
    input_data = {"skillIds": ["skill-plumbing", "skill-retired", "skill-unknown"]}
    expected_output = {"status_code": 200, "skill_count": 1, "ids_forwarded": 3}

    response = provider_client.put(MY_SKILLS, json=input_data, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "skill_count": response.json()["skillCount"],
        "ids_forwarded": len(providers["skill_ids"]),
    }

    assert actual_output == expected_output, endpoint


def test_api_129_the_offline_toggle_reports_what_the_database_settled_on(
    provider_client: TestClient, providers: dict, csrf_headers: dict[str, str]
) -> None:
    """Read back rather than echoed: a provider whose row is gone gets a 404 from
    the RPC, and one whose row is there gets the stored value."""
    endpoint = "PATCH /api/v1/service-providers/me/availability"
    input_data = {"isAvailable": False}
    expected_output = {"status_code": 200, "is_available": False, "requested": False}

    providers["is_available"] = False
    response = provider_client.patch(
        MY_AVAILABILITY, json=input_data, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "is_available": response.json()["isAvailable"],
        "requested": providers["requested_availability"],
    }

    assert actual_output == expected_output, endpoint


def test_api_130_a_write_without_the_csrf_pair_is_refused(
    provider_client: TestClient, providers: dict
) -> None:
    """These routes carry no membership guard, so CSRF is the only thing standing
    between a cross-site form post and someone's registration."""
    endpoint = "POST /api/v1/service-providers"
    input_data = {
        "displayName": "Ravi Kumar",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "skillIds": ["skill-plumbing"],
    }
    expected_output = {"status_code": 403}

    response = provider_client.post(PROVIDERS, json=input_data)
    actual_output = {"status_code": response.status_code}

    assert actual_output == expected_output, endpoint


@pytest.mark.parametrize(
    "payload",
    [
        {"displayName": "Ravi Kumar", "longitude": 77.5946, "skillIds": ["s1"]},
        {"displayName": "Ravi Kumar", "latitude": 12.9716, "skillIds": ["s1"]},
        {"displayName": "Ravi Kumar", "latitude": 12.9716, "longitude": 77.5946, "skillIds": []},
        {"displayName": "Ravi Kumar", "latitude": 12.9716, "longitude": 77.5946, "skillIds": ["s1", "s1"]},
        {"displayName": "Ravi Kumar", "latitude": 91, "longitude": 77.5946, "skillIds": ["s1"]},
        {"displayName": "Ravi Kumar", "latitude": 12.9716, "longitude": 77.5946, "serviceRadiusKm": 501, "skillIds": ["s1"]},
    ],
)
def test_registration_rejects_incomplete_or_invalid_location_and_skills(
    provider_client: TestClient,
    providers: dict,
    csrf_headers: dict[str, str],
    payload: dict[str, Any],
) -> None:
    response = provider_client.post(PROVIDERS, json=payload, headers=csrf_headers)

    assert response.status_code == 422
    assert "registered" not in providers


def test_skills_cannot_be_replaced_with_an_empty_set(
    provider_client: TestClient, providers: dict, csrf_headers: dict[str, str]
) -> None:
    response = provider_client.put(MY_SKILLS, json={"skillIds": []}, headers=csrf_headers)

    assert response.status_code == 422
    assert "skill_ids" not in providers


def test_api_131_a_name_shorter_than_the_schema_allows_is_a_422(
    provider_client: TestClient, providers: dict, csrf_headers: dict[str, str]
) -> None:
    """Validated in pydantic as well as in the RPC. The duplicate is deliberate:
    the RPC's `22004` is the guarantee, and the 422 is the one that can point at
    the field."""
    endpoint = "POST /api/v1/service-providers"
    input_data = {"displayName": "R"}
    expected_output = {"status_code": 422, "code": "request_validation_error"}

    response = provider_client.post(PROVIDERS, json=input_data, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_132_the_router_calls_the_service_it_imported(
    provider_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards the wiring rather than the behaviour: a router that imported the
    module under a different name would pass every test above while calling
    nothing this suite has replaced."""
    endpoint = "GET /api/v1/service-providers/me"
    expected_output = {"status_code": 200, "display_name": "Stub"}

    def fake_get_mine(client: Any, *, profile_id: str) -> Any:
        return router_module.ServiceProviderProfile(
            **{**overview_row(), "display_name": "Stub", "phone": "", "headline": "",
               "bio": "", "skill_ids": [], "skill_names": [], "community_count": 0}
        )

    monkeypatch.setattr(router_module.service, "get_mine", fake_get_mine)
    response = provider_client.get(ME)
    actual_output = {
        "status_code": response.status_code,
        "display_name": response.json()["displayName"],
    }

    assert actual_output == expected_output, endpoint


# ---------------------------------------------------------------------------
# The candidate read (2026-08-11)
#
# The one route on this router about somebody other than the caller, and so the
# only one with a role guard. Every case below is about the difference between
# what the *view* would give up and what this endpoint chooses to.
# ---------------------------------------------------------------------------


def test_api_237_a_hiring_manager_reads_a_candidate_without_their_coordinates(
    manager_api_client: TestClient, providers: dict
) -> None:
    """The read behind every "open this person" click on the hiring surface.

    `latitude` and `longitude` are absent, and that is the case worth having:
    `service_providers_read` is `auth.uid() is not null`, so the view would hand
    a home coordinate to anybody signed in. `distanceKm` on the candidate list
    already answers where somebody is, measured from the community's own point,
    which is the question a manager actually has.
    """
    endpoint = "GET /api/v1/service-providers/{providerId}"
    expected_output = {
        "status_code": 200,
        "display_name": "Ravi Kumar",
        "skill_names": ["Plumbing"],
        "has_coordinates": False,
        "has_profile_id": False,
        "requested_id": "provider-id",
    }

    response = manager_api_client.get(f"{PROVIDERS}/provider-id")
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "display_name": body["displayName"],
        "skill_names": body["skillNames"],
        "has_coordinates": "latitude" in body or "longitude" in body,
        "has_profile_id": "profileId" in body,
        "requested_id": providers["requested_provider_id"],
    }

    assert actual_output == expected_output, endpoint


def test_api_238_a_resident_may_not_browse_the_service_directory(
    resident_api_client: TestClient, providers: dict
) -> None:
    """`require_admin_or_manager` is the whole point of this route existing
    separately from a plain view read.

    Postgres would return the row -- the read policy admits any signed-in
    caller, because a manager has to be able to find somebody they have never
    met. The guard here is what stops that being a directory of every
    tradesperson in the country, browsable by every resident with an account.
    """
    endpoint = "GET /api/v1/service-providers/{providerId}"
    expected_output = {"status_code": 403}

    response = resident_api_client.get(f"{PROVIDERS}/provider-id")
    actual_output = {"status_code": response.status_code}

    assert actual_output == expected_output, endpoint


def test_api_239_the_literal_me_still_reaches_the_caller_s_own_profile(
    provider_client: TestClient, providers: dict
) -> None:
    """Route ordering, asserted rather than assumed.

    `/service-providers/{providerId}` is declared after `/service-providers/me`
    precisely so FastAPI matches the literal first. Reversed, `me` would arrive
    as a provider id -- and because the new route carries a role guard, an
    unregistered service person would get a 403 on their own settings screen
    instead of the 404 that sends them to the registration form.
    """
    endpoint = "GET /api/v1/service-providers/me"
    expected_output = {"status_code": 200, "has_coordinates": True}

    response = provider_client.get(ME)
    actual_output = {
        "status_code": response.status_code,
        "has_coordinates": "latitude" in response.json(),
    }

    assert actual_output == expected_output, endpoint


def test_api_240_an_unknown_provider_id_is_a_404_not_an_empty_profile(
    manager_api_client: TestClient, providers: dict
) -> None:
    """Same reasoning as `GET /me`: "there is no such person" and "there is a
    person with nothing filled in" are different answers, and a screen that
    rendered the second for the first would show a blank card with a hire
    button on it."""
    endpoint = "GET /api/v1/service-providers/{providerId}"
    providers["candidate_row"] = None
    expected_output = {"status_code": 404, "code": "service_provider_not_found"}

    response = manager_api_client.get(f"{PROVIDERS}/nobody")
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint
