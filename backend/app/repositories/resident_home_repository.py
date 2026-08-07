"""Data access for the notice board, the flat and the contact directory.

Three views from `0033`, one RPC. The RPC exists because adding a number to a
flat has to resolve *which* flat from the caller's residency — a unit id in a
request body is a unit id somebody can change, and the point of this endpoint is
that a resident may edit their own flat's list and nobody else's.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_NOTICES = "resident_notice_overview"
_HOUSEHOLD = "household_overview"
_CONTACTS = "management_contact_overview"

_NOTICE_SELECT = "id, title, body, category, urgency, published_at, author_name"
_HOUSEHOLD_SELECT = (
    "id, source, full_name, phone_e164, relationship, is_primary_contact,status, since"
)
_CONTACT_SELECT = (
    "id, name, category, description, phone_e164, email, opens_at, closes_at,"
    "head_name, head_phone_e164"
)


def list_notices(
    client: Client,
    *,
    community_id: str,
    category: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """A page of published notices, newest first.

    The view already excludes drafts, and so does the policy. Two independent
    reasons, because a draft reaching a resident is an admin's half-written words
    published by accident.
    """
    query = (
        client.table(_NOTICES)
        .select(_NOTICE_SELECT, count="exact")
        .eq("community_id", community_id)
    )
    if category:
        query = query.eq("category", category)

    response = (
        query.order("published_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def find_unit_id(client: Client, *, membership_id: str) -> str | None:
    """The flat the caller currently lives in, from the residency itself.

    Not from the session. `MembershipContext.unit_id` is resolved once at
    sign-in, and this is the same fact read at the moment it is used — which
    matters because `add_unit_contact` resolves the flat the same way, and a
    write and a read disagreeing about which flat this is would be the one bug
    worth ruling out here.
    """
    rows = (
        client.table("unit_residencies")
        .select("unit_id")
        .eq("membership_id", membership_id)
        .is_("ended_at", "null")
        .order("is_primary_contact", desc=True)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0]["unit_id"] if rows else None


def list_household(client: Client, *, unit_id: str) -> list[dict[str, Any]]:
    """Everyone and every number registered to one flat.

    Not paginated: this is a household, and the number of people in a flat is not
    a quantity anybody needs a page control for.
    """
    return (
        client.table(_HOUSEHOLD)
        .select(_HOUSEHOLD_SELECT)
        .eq("unit_id", unit_id)
        .order("source")
        .order("full_name")
        .execute()
        .data
        or []
    )


def list_contacts(client: Client, *, community_id: str) -> list[dict[str, Any]]:
    """The community's contact directory, grouped by the category an admin typed."""
    return (
        client.table(_CONTACTS)
        .select(_CONTACT_SELECT)
        .eq("community_id", community_id)
        .order("category")
        .order("name")
        .execute()
        .data
        or []
    )


def add_household_phone(
    client: Client, *, membership_id: str, payload: dict[str, Any]
) -> str:
    """Register a number against the caller's own flat (RPC). Returns its id."""
    try:
        response = client.rpc(
            "add_unit_contact",
            {"p_membership_id": membership_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not add the number to your flat."
        ) from exc
    return str(response.data)
