"""Notices, the flat, and the numbers worth ringing.

Closes §5.6 and the *Notices and profile* rows of §6 in
``docs/design/RESIDENT_BACKEND_DESIGN.md``, and part of step 6.

Everything here is translation: the views do the filtering and the RPC does the
one write, for the reason §5.2 gives — a predicate that lives in SQL cannot be
forgotten by a service.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationError
from app.domain.common_schemas import Page
from app.domain.resident_home_schemas import (
    AddHouseholdPhoneRequest,
    HouseholdMember,
    ManagementContact,
    Notice,
)
from app.repositories import resident_home_repository as repo
from supabase import Client


def _text(value: object) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _to_notice(row: dict[str, Any]) -> Notice:
    return Notice(
        id=row["id"],
        title=_text(row.get("title")),
        body=_text(row.get("body")),
        category=_text(row.get("category")) or "General",
        urgency=_text(row.get("urgency")) or "Info",
        published_at=row["published_at"],
        author_name=row.get("author_name"),
    )


def _to_member(row: dict[str, Any]) -> HouseholdMember:
    return HouseholdMember(
        id=row["id"],
        source=_text(row.get("source")) or "member",
        full_name=_text(row.get("full_name")) or "Resident",
        phone_e164=row.get("phone_e164"),
        relationship=_text(row.get("relationship")),
        is_primary_contact=bool(row.get("is_primary_contact")),
        status=_text(row.get("status")) or "Active",
        since=row.get("since"),
    )


def _to_contact(row: dict[str, Any]) -> ManagementContact:
    return ManagementContact(
        id=row["id"],
        name=_text(row.get("name")),
        category=_text(row.get("category")) or "Management",
        description=_text(row.get("description")),
        phone_e164=row.get("phone_e164"),
        email=row.get("email"),
        opens_at=_text(row.get("opens_at")) or None,
        closes_at=_text(row.get("closes_at")) or None,
        head_name=row.get("head_name"),
        head_phone_e164=row.get("head_phone_e164"),
    )


def list_notices(
    client: Client,
    *,
    community_id: str,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[Notice]:
    """Published notices for the caller's community, newest first."""
    offset = max(page - 1, 0) * page_size
    rows, total = repo.list_notices(
        client,
        community_id=community_id,
        category=(category or "").strip() or None,
        offset=offset,
        limit=page_size,
    )
    items = [_to_notice(row) for row in rows]
    return Page(
        items=items,
        total=total,
        page=max(page, 1),
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


def get_household(client: Client, *, membership_id: str) -> list[HouseholdMember]:
    """Everyone and every number registered to the caller's flat.

    The flat comes from the residency rather than from the session, so that this
    read and `add_household_phone`'s write cannot disagree about which flat is
    the caller's.

    A caller with no flat gets an empty list rather than an error. A member of
    staff has a membership and no residency, and asking them about their
    household is a question with a legitimate answer of *nobody*.
    """
    unit_id = repo.find_unit_id(client, membership_id=membership_id)
    if not unit_id:
        return []
    rows = repo.list_household(client, unit_id=unit_id)
    return [_to_member(row) for row in rows]


def add_household_phone(
    client: Client, *, membership_id: str, body: AddHouseholdPhoneRequest
) -> list[HouseholdMember]:
    """Register another number against the caller's own flat, and return the list.

    The list comes back rather than the created row, because the screen renders a
    list and a client that has to merge one row into it can merge it wrongly.
    """
    if not body.phone_e164:
        raise ValidationError("A phone number is required.", code="phone_required")

    repo.add_household_phone(
        client,
        membership_id=membership_id,
        payload={
            "phone_e164": body.phone_e164,
            "full_name": body.full_name,
            "relationship": body.relationship,
        },
    )
    # Re-read through the same path the plain read uses, so the flat the RPC
    # resolved is the flat this returns.
    return get_household(client, membership_id=membership_id)


def list_contacts(client: Client, *, community_id: str) -> list[ManagementContact]:
    """The management and emergency directory (§5.6).

    Served from `departments`, so it is current for the same reason the admin's
    own screens are: somebody maintains it for their own purposes. The list
    `Profile.jsx` renders today is five numbers typed into a component, which is
    the stale-by-construction version of exactly what `US-2.9` asks for.
    """
    rows = repo.list_contacts(client, community_id=community_id)
    return [_to_contact(row) for row in rows]
