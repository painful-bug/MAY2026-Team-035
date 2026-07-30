"""Data access for residents, admins and registration requests.

Reads and simple writes go through the caller-scoped client so RLS applies.
Anything spanning two tables goes through an RPC (see migration 0012) -- PostgREST
has no client-side transaction, so a two-statement "operation" from here is two
transactions and can half-succeed.
"""

from __future__ import annotations

from datetime import datetime

from app.core.exceptions import NotFoundError
from app.core.pg_errors import translate
from supabase import Client

_PROFILES = "profiles"
_MEMBERSHIPS = "community_memberships"
_REQUESTS = "registration_requests"

_MEMBER_SELECT = (
    "id, profile_id, role, status, designation, joined_at,"
    "profiles!inner(full_name, email, phone, apartment_id, status)"
)


def list_admins(client: Client, community_id: str) -> list[dict]:
    """All admins of the community, newest first.

    Not paginated: an association has a committee, not a directory. If that ever
    stops being true this becomes a paged endpoint like the others.
    """
    response = (
        client.table(_MEMBERSHIPS)
        .select(_MEMBER_SELECT)
        .eq("community_id", community_id)
        .eq("role", "ADMIN")
        .order("joined_at", desc=True)
        .execute()
    )
    return response.data or []


def get_membership(client: Client, community_id: str, membership_id: str) -> dict:
    """Fetch one membership with its profile, or raise."""
    response = (
        client.table(_MEMBERSHIPS)
        .select(_MEMBER_SELECT)
        .eq("community_id", community_id)
        .eq("id", membership_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Member not found.")
    return rows[0]


def get_membership_id_for_profile(
    client: Client, community_id: str, profile_id: str
) -> str | None:
    """Resolve the caller's own membership id -- used to record who reviewed what."""
    response = (
        client.table(_MEMBERSHIPS)
        .select("id")
        .eq("community_id", community_id)
        .eq("profile_id", profile_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0]["id"] if rows else None


def update_profile_fields(client: Client, profile_id: str, fields: dict) -> None:
    """Patch name/email/phone on a profile. No-op when ``fields`` is empty."""
    if not fields:
        return
    try:
        client.table(_PROFILES).update(fields).eq("id", profile_id).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update the resident.") from exc


def update_membership_fields(
    client: Client, community_id: str, membership_id: str, fields: dict
) -> None:
    """Patch membership-level fields (currently only ``designation``)."""
    if not fields:
        return
    try:
        (
            client.table(_MEMBERSHIPS)
            .update(fields)
            .eq("id", membership_id)
            .eq("community_id", community_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update the member.") from exc


def list_registration_requests(
    client: Client,
    community_id: str,
    *,
    status: str,
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """Page through registration requests with the given status."""
    response = (
        client.table(_REQUESTS)
        .select(
            "id, full_name, email, phone, requested_unit_code, status, created_at",
            count="exact",
        )
        .eq("community_id", community_id)
        .eq("status", status)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def approve_registration_request(
    client: Client,
    *,
    request_id: str,
    token_hash: str,
    code_hash: str,
    expires_at: datetime,
    reviewer_membership_id: str | None,
    created_by: str,
) -> dict:
    """Approve a request and mint its invitation, atomically (RPC).

    Returns the invitation id plus the applicant details needed to build the
    one-time link.
    """
    try:
        response = client.rpc(
            "approve_registration_request",
            {
                "p_request_id": request_id,
                "p_token_hash": token_hash,
                "p_code_hash": code_hash,
                "p_expires_at": expires_at.isoformat(),
                "p_reviewer_membership_id": reviewer_membership_id,
                "p_created_by": created_by,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not approve the request.") from exc

    rows = response.data or []
    if not rows:
        # The function returns a row on success, so an empty result means the
        # request vanished between the guard and the call.
        raise NotFoundError("Registration request not found.")
    return rows[0]


def reject_registration_request(
    client: Client,
    *,
    request_id: str,
    reason: str | None,
    reviewer_membership_id: str | None,
) -> None:
    """Reject a pending request (RPC)."""
    try:
        client.rpc(
            "reject_registration_request",
            {
                "p_request_id": request_id,
                "p_reason": reason,
                "p_reviewer_membership_id": reviewer_membership_id,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not reject the request.") from exc


def deactivate_membership(client: Client, membership_id: str) -> None:
    """Deactivate a membership and end its open residency, atomically (RPC)."""
    try:
        client.rpc(
            "deactivate_membership", {"p_membership_id": membership_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not remove the member.") from exc
