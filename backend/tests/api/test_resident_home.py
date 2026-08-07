"""Notices, the flat, and the contact directory.

The assertion worth naming here is the household one. `household_overview` unions
two genuinely different things — people with accounts, and phone numbers that
belong to nobody in the system — and the prototype conflates them by
manufacturing a whole user row for a number. `source` is what keeps them apart on
the wire, so it is asserted rather than assumed.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.repositories import resident_home_repository

NOTICES = "/api/v1/notices"
HOUSEHOLD = "/api/v1/me/household"
PHONES = "/api/v1/me/household/phones"
CONTACTS = "/api/v1/directory/contacts"


def notice_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "notice-id",
        "title": "Water supply interruption",
        "body": "Tanks will be cleaned on Saturday.",
        "category": "Maintenance",
        "urgency": "Important",
        "published_at": "2026-08-03T09:00:00+00:00",
        "author_name": "Priya Nair",
    }
    base.update(overrides)
    return base


def member_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "membership-id",
        "source": "member",
        "full_name": "Anita Rao",
        "phone_e164": "+919999900001",
        "relationship": "Owner",
        "is_primary_contact": True,
        "status": "Active",
        "since": "2025-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def contact_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "department-id",
        "name": "Security",
        "category": "Security",
        "description": "Main gate",
        "phone_e164": "+919999911111",
        "email": "gate@example.com",
        "opens_at": "06:00:00",
        "closes_at": "22:00:00",
        "head_name": "Ravi Kumar",
        "head_phone_e164": "+919999922222",
    }
    base.update(overrides)
    return base


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch) -> dict:
    captured: dict = {
        "notices": [notice_row()],
        "household": [member_row()],
        "contacts": [contact_row()],
        "unit_id": "unit-id",
        "calls": [],
    }

    def fake_list_notices(client: Any, **kwargs: Any) -> tuple[list[dict], int]:
        captured["calls"].append(("list_notices", kwargs))
        rows = captured["notices"]
        return rows, len(rows)

    def fake_find_unit_id(client: Any, **kwargs: Any) -> str | None:
        captured["calls"].append(("find_unit_id", kwargs))
        return captured["unit_id"]

    def fake_list_household(client: Any, **kwargs: Any) -> list[dict]:
        captured["calls"].append(("list_household", kwargs))
        return captured["household"]

    def fake_list_contacts(client: Any, **kwargs: Any) -> list[dict]:
        captured["calls"].append(("list_contacts", kwargs))
        return captured["contacts"]

    def fake_add_phone(client: Any, **kwargs: Any) -> str:
        captured["calls"].append(("add_household_phone", kwargs))
        return "contact-id"

    for name, replacement in {
        "list_notices": fake_list_notices,
        "find_unit_id": fake_find_unit_id,
        "list_household": fake_list_household,
        "list_contacts": fake_list_contacts,
        "add_household_phone": fake_add_phone,
    }.items():
        monkeypatch.setattr(resident_home_repository, name, replacement)
    return captured


def only(captured: dict, name: str) -> dict[str, Any]:
    matches = [kwargs for call, kwargs in captured["calls"] if call == name]
    assert len(matches) == 1, f"expected one {name} call, saw {len(matches)}"
    return matches[0]


# ---------------------------------------------------------------------------
# The guards
# ---------------------------------------------------------------------------


def test_notices_require_a_session(api_client: TestClient) -> None:
    assert api_client.get(NOTICES).status_code == 401


def test_adding_a_phone_requires_csrf(
    resident_api_client: TestClient, home: dict
) -> None:
    response = resident_api_client.post(PHONES, json={"phoneE164": "+919999900002"})

    assert response.status_code == 403
    assert home["calls"] == []


# ---------------------------------------------------------------------------
# Notices
# ---------------------------------------------------------------------------


def test_notices_are_scoped_to_the_callers_community(
    resident_api_client: TestClient, home: dict
) -> None:
    resident_api_client.get(NOTICES)

    assert only(home, "list_notices")["community_id"] == "community-id"


def test_a_notice_carries_the_urgency_the_screen_renders(
    resident_api_client: TestClient, home: dict
) -> None:
    """The CHECK in `0018` stores lower case; `Notices.jsx` renders `Important`.
    Title-cased in the view, like every other vocabulary in this backend."""
    item = resident_api_client.get(NOTICES).json()["items"][0]

    assert item["urgency"] == "Important"
    assert item["category"] == "Maintenance"


def test_a_category_filter_is_passed_through(
    resident_api_client: TestClient, home: dict
) -> None:
    resident_api_client.get(f"{NOTICES}?category=Maintenance")

    assert only(home, "list_notices")["category"] == "Maintenance"


def test_a_blank_category_is_no_filter_at_all(
    resident_api_client: TestClient, home: dict
) -> None:
    resident_api_client.get(f"{NOTICES}?category=%20")

    assert only(home, "list_notices")["category"] is None


def test_there_is_no_resident_route_that_posts_a_notice(
    resident_api_client: TestClient, home: dict
) -> None:
    """Posting is an admin action and already exists elsewhere. A resident
    reaching it would be a resident publishing to the whole community."""
    assert resident_api_client.post(NOTICES, json={"title": "x"}).status_code in (
        403,
        405,
    )


# ---------------------------------------------------------------------------
# The flat
# ---------------------------------------------------------------------------


def test_the_household_is_read_for_the_flat_the_residency_names(
    resident_api_client: TestClient, home: dict
) -> None:
    """From the residency, not from the session -- so this read and the write
    below cannot disagree about which flat is the caller's."""
    resident_api_client.get(HOUSEHOLD)

    assert only(home, "find_unit_id")["membership_id"] == "resident-membership-id"
    assert only(home, "list_household")["unit_id"] == "unit-id"


def test_a_caller_with_no_flat_gets_an_empty_list_not_an_error(
    resident_api_client: TestClient, home: dict
) -> None:
    """Staff have a membership and no residency. *Nobody* is a legitimate answer
    to "who lives in your flat"."""
    home["unit_id"] = None

    response = resident_api_client.get(HOUSEHOLD)

    assert response.status_code == 200
    assert response.json() == []


def test_a_member_and_a_contact_are_told_apart(
    resident_api_client: TestClient, home: dict
) -> None:
    """The prototype invents a whole user row for a phone number. A system that
    did that for real would put somebody in the member count who cannot sign in
    and never agreed to join."""
    home["household"] = [
        member_row(),
        member_row(
            id="contact-id",
            source="contact",
            full_name="Maid",
            status="Contact",
            relationship="Help",
            is_primary_contact=False,
        ),
    ]

    items = resident_api_client.get(HOUSEHOLD).json()

    assert [item["source"] for item in items] == ["member", "contact"]
    assert items[1]["status"] == "Contact"


def test_the_flat_is_not_accepted_from_the_request_body(
    resident_api_client: TestClient, csrf_headers: dict[str, str], home: dict
) -> None:
    """A unit id in a body is a unit id somebody can change. It is resolved from
    the caller's own residency inside the RPC, and nothing here forwards one."""
    resident_api_client.post(
        PHONES,
        json={"phoneE164": "+919999900002", "unitId": "someone-elses-flat"},
        headers=csrf_headers,
    )
    sent = only(home, "add_household_phone")

    assert "unit_id" not in sent["payload"]
    assert sent["membership_id"] == "resident-membership-id"


def test_adding_a_number_returns_the_whole_list(
    resident_api_client: TestClient, csrf_headers: dict[str, str], home: dict
) -> None:
    """The screen renders a list, and a client merging one row into it can merge
    it wrongly."""
    response = resident_api_client.post(
        PHONES, json={"phoneE164": "+919999900002"}, headers=csrf_headers
    )

    assert response.status_code == 200
    assert response.json()[0]["fullName"] == "Anita Rao"


def test_an_empty_phone_number_is_refused(
    resident_api_client: TestClient, csrf_headers: dict[str, str], home: dict
) -> None:
    response = resident_api_client.post(
        PHONES, json={"phoneE164": "  "}, headers=csrf_headers
    )

    assert response.status_code == 422
    assert home["calls"] == []


# ---------------------------------------------------------------------------
# The directory
# ---------------------------------------------------------------------------


def test_the_directory_is_the_communitys_departments(
    resident_api_client: TestClient, home: dict
) -> None:
    """§5.6. It stays current because admins maintain departments for reasons of
    their own -- which is the only kind of freshness that survives a committee."""
    items = resident_api_client.get(CONTACTS).json()

    assert only(home, "list_contacts")["community_id"] == "community-id"
    assert items[0]["name"] == "Security"
    assert items[0]["headName"] == "Ravi Kumar"


def test_the_directory_carries_a_category_and_no_emergency_flag(
    resident_api_client: TestClient, home: dict
) -> None:
    """Deciding which categories mean *emergency* by matching strings would be a
    classification invented in the backend, wrong the first time somebody writes
    "Emergencies"."""
    item = resident_api_client.get(CONTACTS).json()[0]

    assert item["category"] == "Security"
    assert "isEmergency" not in item
