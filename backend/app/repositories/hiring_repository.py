"""Data access for hiring: applications, candidates, engagements.

Reads go through ``service_application_overview`` and
``service_engagement_overview``; every write goes through one of the five
SECURITY DEFINER functions in ``0035`` 7. Neither table carries an insert,
update or delete policy, so there is no path from this process to a row those
functions did not write.

**Every function here takes the caller's request client, never the service
client.** All five RPCs and the two search functions resolve the caller from
``auth.uid()``, which does not exist on the service client -- passing the wrong
one would not fail loudly, it would tell a signed-in caller to sign in.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_APPLICATIONS = "service_application_overview"
_ENGAGEMENTS = "service_engagement_overview"
_DEPARTURES = "staff_departure_overview"

#: Listed rather than ``*`` so a column added to the view later does not
#: silently widen the response.
_APPLICATION_SELECT = (
    "id, community_id, community_name, department_id, department_name, "
    "department_kind, service_provider_id, provider_display_name, "
    "provider_headline, provider_phone_e164, provider_skill_names, direction, "
    "status, message, rank, job_title, shift, decision_note, decided_at, "
    "distance_km, created_at, updated_at"
)

_ENGAGEMENT_SELECT = (
    "staff_assignment_id, community_id, community_name, community_city, "
    "department_id, department_name, department_kind, membership_id, "
    "membership_role, rank, job_title, shift, status, started_at, ended_at"
)


def list_applications_for_department(
    client: Client, *, department_id: str, status: str | None = None
) -> list[dict[str, Any]]:
    """The department's inbox, newest first.

    Both directions, deliberately. A manager looking at "who wants to work here"
    also needs to see the invitations their department has out, or they will
    send a second one to somebody already invited.
    """
    query = (
        client.table(_APPLICATIONS)
        .select(_APPLICATION_SELECT)
        .eq("department_id", department_id)
    )
    if status:
        query = query.eq("status", status)
    return query.order("created_at", desc=True).execute().data or []


def list_applications_for_provider(
    client: Client, *, service_provider_id: str, status: str | None = None
) -> list[dict[str, Any]]:
    """The provider's own negotiations, across every community.

    Not scoped to a community, and that is the point: a service person applying
    to four societies has one screen, and the RLS policy on
    ``service_applications`` is what makes it their four rather than everyone's.
    """
    query = (
        client.table(_APPLICATIONS)
        .select(_APPLICATION_SELECT)
        .eq("service_provider_id", service_provider_id)
    )
    if status:
        query = query.eq("status", status)
    return query.order("created_at", desc=True).execute().data or []


def get_application(client: Client, *, application_id: str) -> dict[str, Any] | None:
    """One negotiation, or ``None`` when the policy hides it from this caller."""
    rows = (
        client.table(_APPLICATIONS)
        .select(_APPLICATION_SELECT)
        .eq("id", application_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_engagements(
    client: Client, *, service_provider_id: str, active_only: bool = True
) -> list[dict[str, Any]]:
    """Where this provider works, one row per community."""
    query = (
        client.table(_ENGAGEMENTS)
        .select(_ENGAGEMENT_SELECT)
        .eq("service_provider_id", service_provider_id)
    )
    if active_only:
        query = query.eq("status", "active")
    return query.order("community_name").execute().data or []


def search_communities(
    client: Client, *, query: str | None, limit: int, offset: int
) -> list[dict[str, Any]]:
    """Communities that need one of the caller's trades (RPC, ``0034`` 9)."""
    try:
        response = client.rpc(
            "search_serviceable_communities",
            {"p_query": query, "p_limit": limit, "p_offset": offset},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not search for communities."
        ) from exc
    return response.data or []


def search_candidates(
    client: Client,
    *,
    department_id: str,
    query: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Service people this department could hire (RPC, ``0035`` 6)."""
    try:
        response = client.rpc(
            "search_hireable_service_providers",
            {
                "p_department_id": department_id,
                "p_query": query,
                "p_limit": limit,
                "p_offset": offset,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not search for staff.") from exc
    return response.data or []


def apply_to_department(
    client: Client, *, department_id: str, message: str | None
) -> str:
    """Open an application (RPC). Returns its id."""
    try:
        response = client.rpc(
            "apply_to_department",
            {"p_department_id": department_id, "p_message": message},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not send your application."
        ) from exc
    return str(response.data or "")


def invite_provider(
    client: Client,
    *,
    department_id: str,
    service_provider_id: str,
    message: str | None,
    rank: str,
    job_title: str | None,
    shift: str | None,
) -> str:
    """Open an invitation (RPC). Returns its id."""
    try:
        response = client.rpc(
            "invite_service_provider",
            {
                "p_department_id": department_id,
                "p_service_provider_id": service_provider_id,
                "p_message": message,
                "p_rank": rank,
                "p_job_title": job_title,
                "p_shift": shift,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not send the invitation.") from exc
    return str(response.data or "")


def decide_application(
    client: Client,
    *,
    application_id: str,
    decision: str,
    rank: str | None = None,
    job_title: str | None = None,
    shift: str | None = None,
    note: str | None = None,
) -> str:
    """Accept, reject or withdraw (RPC).

    The one write in this feature that has to be atomic: accepting inserts a
    membership **and** a roster row **and** stamps the decision, in one
    transaction. Either the person is hired or nothing happened -- a membership
    with no roster row is someone who can sign in and has no job, and retrying
    would not fix it.
    """
    try:
        response = client.rpc(
            "decide_service_application",
            {
                "p_application_id": application_id,
                "p_decision": decision,
                "p_rank": rank,
                "p_job_title": job_title,
                "p_shift": shift,
                "p_note": note,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not record that decision."
        ) from exc
    return str(response.data or "")


def remove_member(client: Client, *, staff_id: str, reason: str | None) -> None:
    """Take someone off a roster and end their membership (RPC)."""
    try:
        client.rpc(
            "remove_department_member",
            {"p_staff_id": staff_id, "p_reason": reason},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not remove that staff member."
        ) from exc


_DEPARTURE_SELECT = (
    "id, community_id, department_id, department_name, department_kind, "
    "staff_assignment_id, service_provider_id, membership_id, display_name, "
    "rank, job_title, initiated_by, status, reason, requested_effective_at, "
    "effective_at, decision_note, decided_at, open_commitment_count, "
    "conflict_count, created_at, updated_at"
)


_STAFF_OVERVIEW = "department_staff_overview"
# The same projection `departments_repository._STAFF_SELECT` reads — the view
# is shared; the key is not. That module reads by community (the admin roster
# screen), this one by department (the hiring router's path scope).
_STAFF_MEMBER_SELECT = (
    "id, department_id, membership_id, service_provider_id, display_name,"
    "phone_e164, job_title, rank, shift, status, active_assignment_count,"
    "open_commitment_count, departure_status, departure_effective_at"
)


def get_staff_member(
    client: Client, *, department_id: str, staff_id: str
) -> dict[str, Any] | None:
    """One roster row, scoped to the department in the path.

    ``None`` for a row in another department as much as for a missing one —
    the employee page's path carries the department, and a URL that renders
    somebody from a different department is a link that lies.
    """
    rows = (
        client.table(_STAFF_OVERVIEW)
        .select(_STAFF_MEMBER_SELECT)
        .eq("department_id", department_id)
        .eq("id", staff_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_departures(
    client: Client, *, department_id: str, status: str | None = None
) -> list[dict[str, Any]]:
    """This department's departures, newest first."""
    query = (
        client.table(_DEPARTURES)
        .select(_DEPARTURE_SELECT)
        .eq("department_id", department_id)
    )
    if status:
        query = query.eq("status", status)
    return query.order("created_at", desc=True).execute().data or []


def get_departure(client: Client, *, departure_id: str) -> dict[str, Any] | None:
    """One departure, or ``None`` when the policy hides it from this caller."""
    rows = (
        client.table(_DEPARTURES)
        .select(_DEPARTURE_SELECT)
        .eq("id", departure_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def departures_for_staff(
    client: Client, *, staff_ids: list[str], status: str | None = "pending"
) -> list[dict[str, Any]]:
    """Open departures across several roster rows, in one read.

    The worker's engagement list is one card per community and each card has to
    know whether its leave button says *request* or *withdraw*. One ``in`` beats
    a query per card, and it beats widening ``service_engagement_overview`` --
    which would have made every read of that view compute a handover count no
    other caller wants.
    """
    if not staff_ids:
        return []
    query = (
        client.table(_DEPARTURES)
        .select(_DEPARTURE_SELECT)
        .in_("staff_assignment_id", staff_ids)
    )
    if status:
        query = query.eq("status", status)
    return query.execute().data or []


def departure_items(client: Client, *, staff_id: str) -> list[dict[str, Any]]:
    """Everything still booked in one roster row's name (RPC, ``0043`` 3).

    Takes the **service** client, unlike everything else in this module.
    ``staff_departure_items`` is ``service_role`` only because it returns
    complaint titles and post names, so the caller is authorised by the read of
    the departure that precedes this one rather than by the function itself.
    """
    try:
        response = client.rpc(
            "staff_departure_items", {"p_staff_id": staff_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not read the handover list."
        ) from exc
    return response.data or []


def request_departure(
    client: Client,
    *,
    staff_id: str,
    reason: str | None,
    effective_at: str | None = None,
) -> str:
    """Open a departure and freeze the engine against them (RPC).

    ``effective_at`` is the worker's intended leave date; ``None`` asks to
    leave immediately, and a past date comes back `422` from the RPC.
    """
    try:
        response = client.rpc(
            "request_staff_departure",
            {
                "p_staff_id": staff_id,
                "p_reason": reason,
                "p_effective_at": effective_at,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not open that departure."
        ) from exc
    return str(response.data or "")


def cancel_departure(client: Client, *, departure_id: str) -> None:
    """Withdraw an open departure and lift the freeze (RPC)."""
    try:
        client.rpc(
            "cancel_staff_departure", {"p_departure_id": departure_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not withdraw that departure."
        ) from exc


def decide_departure(
    client: Client,
    *,
    departure_id: str,
    decision: str,
    note: str | None,
    effective_at: str | None = None,
) -> None:
    """Approve or reject (RPC).

    Approval picks the leave date — the requested one when ``effective_at`` is
    ``None``, or the manager's later one — and releases booked work from that
    date onward back to the dispatch pool. Since the 2026-08-10 ruling an
    approval is **not** refused for outstanding items.
    """
    try:
        client.rpc(
            "decide_staff_departure",
            {
                "p_departure_id": departure_id,
                "p_decision": decision,
                "p_note": note,
                "p_effective_at": effective_at,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not decide that departure."
        ) from exc


def departure_coverage(client: Client, *, departure_id: str) -> list[dict[str, Any]]:
    """Each conflicting item with who could take it (RPC, ``0045`` 11).

    Takes the **service** client, like ``departure_items`` and for the same
    reason: the function returns roster names, so the caller is authorised by
    the departure read that precedes this one.
    """
    try:
        response = client.rpc(
            "departure_coverage", {"p_departure_id": departure_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not check coverage for that departure."
        ) from exc
    return response.data or []


def staff_schedule(
    client: Client,
    *,
    staff_id: str,
    starts_after: str | None = None,
    starts_before: str | None = None,
) -> list[dict[str, Any]]:
    """One employee's jobs and shifts in a window (RPC, ``0045`` 11).

    Service client; the router-side guard is the department read that resolves
    the roster row before asking for its calendar.
    """
    try:
        response = client.rpc(
            "staff_schedule_items",
            {
                "p_staff_id": staff_id,
                "p_from": starts_after,
                "p_to": starts_before,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not read that schedule."
        ) from exc
    return response.data or []


def reassign_item(
    client: Client,
    *,
    departure_id: str,
    kind: str,
    item_id: str,
    staff_assignment_id: str | None,
) -> str | None:
    """Move one job or shift to somebody else (RPC).

    A null ``staff_assignment_id`` means *take the best candidate the dispatch
    ranking returns*, which is the same ranking auto-assignment uses.
    """
    try:
        response = client.rpc(
            "reassign_departure_item",
            {
                "p_departure_id": departure_id,
                "p_item_kind": kind,
                "p_item_id": item_id,
                "p_staff_assignment_id": staff_assignment_id,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not hand that item over."
        ) from exc
    return str(response.data) if response.data else None


def blacklist_provider(
    client: Client, *, department_id: str, service_provider_id: str, reason: str
) -> None:
    """Remove and bar, community-wide (RPC)."""
    try:
        client.rpc(
            "blacklist_service_provider",
            {
                "p_department_id": department_id,
                "p_service_provider_id": service_provider_id,
                "p_reason": reason,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not blacklist that service provider."
        ) from exc
