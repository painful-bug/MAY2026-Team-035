"""Data access for departments, staff and complaint categories.

Reads go through the two views from migration 0014, which are declared
``security_invoker`` so RLS still applies to the caller. Every write goes through
an RPC: creating a department touches four tables, and PostgREST has no
client-side transaction, so doing it here would leave a department with no
categories the first time the second call failed.

Every object here is created by ``0019_departments_on_baseline.sql``, which
replaced the quarantined ``0014_departments.sql``.

Two consequences of the baseline worth knowing when reading rows back: a roster
entry may have no ``membership_id`` at all, because the department form collects
typed names rather than accounts; and ``status`` is ours while ``is_active`` is
theirs, kept equal by a trigger, so their ``dashboard_repository`` and this
module never disagree about whether a department is live.
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.core.pg_errors import translate
from supabase import Client

_DEPARTMENTS = "department_overview"
_STAFF = "department_staff_overview"
_DEPARTMENT_SELECT = (
    "id, name, description, contact_email, contact_phone_e164, opens_at, closes_at,"
    "sla_hours, kind, status, created_at, updated_at, head_name, head_staff_id,"
    "staff_count, active_complaint_count, resolved_complaint_count,"
    "overdue_complaint_count, category_ids, category_names"
)

_STAFF_SELECT = (
    "id, department_id, membership_id, display_name, phone_e164, job_title,"
    "rank, shift, status, active_assignment_count"
)


def list_departments(
    client: Client,
    community_id: str,
    *,
    search: str | None,
    status: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """Page through departments with their counts.

    The search is a single ``ilike`` against the view's precomputed
    ``search_text``. That column exists because the frontend searches name,
    description, head, email, category names *and* staff names at once
    (Departments.jsx:163), which no combination of PostgREST filters across
    embedded tables can express.
    """
    query = (
        client.table(_DEPARTMENTS)
        .select(_DEPARTMENT_SELECT, count="exact")
        .eq("community_id", community_id)
    )

    if status:
        query = query.eq("status", status)

    if search:
        # `%` and `_` are wildcards to ilike, and `,` `(` `)` are PostgREST's own
        # filter delimiters -- an unescaped one silently widens the query.
        safe = (
            search.replace("%", "").replace("_", "")
            .replace(",", " ").replace("(", " ").replace(")", " ")
            .strip()
            .lower()
        )
        if safe:
            query = query.ilike("search_text", f"%{safe}%")

    response = (
        query.order("name")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def get_department(client: Client, community_id: str, department_id: str) -> dict:
    """Fetch one department with its counts, or raise."""
    response = (
        client.table(_DEPARTMENTS)
        .select(_DEPARTMENT_SELECT)
        .eq("community_id", community_id)
        .eq("id", department_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Department not found.")
    return rows[0]


def list_staff(
    client: Client,
    community_id: str,
    department_ids: list[str],
    *,
    include_inactive: bool = False,
) -> list[dict]:
    """Roster rows for the given departments, in one query.

    Takes a list so the list endpoint can fetch every page's staff at once rather
    than issuing one query per department.
    """
    if not department_ids:
        return []

    query = (
        client.table(_STAFF)
        .select(_STAFF_SELECT)
        .eq("community_id", community_id)
        .in_("department_id", department_ids)
    )
    if not include_inactive:
        query = query.eq("status", "active")

    response = query.order("display_name").execute()
    return response.data or []


def get_staff_member(client: Client, community_id: str, staff_id: str) -> dict:
    """Fetch one roster entry, or raise."""
    response = (
        client.table(_STAFF)
        .select(_STAFF_SELECT)
        .eq("community_id", community_id)
        .eq("id", staff_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Staff member not found.")
    return rows[0]


def create_department(client: Client, community_id: str, payload: dict) -> str:
    """Create a department, its category claims, its roster and its head (RPC)."""
    try:
        response = client.rpc(
            "create_department",
            {"p_community_id": community_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not create the department."
        ) from exc

    # The function returns the new id as a scalar.
    department_id = response.data
    if isinstance(department_id, list):
        department_id = department_id[0] if department_id else None
    if not department_id:
        raise NotFoundError("Department was not created.")
    return str(department_id)


def update_department(client: Client, department_id: str, patch: dict) -> None:
    """Apply a partial update (RPC). Only the keys present in ``patch`` change."""
    try:
        client.rpc(
            "update_department",
            {"p_department_id": department_id, "p_patch": patch},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not update the department."
        ) from exc


def delete_department(client: Client, department_id: str) -> None:
    """Delete a department (RPC). Refuses while it owns open complaints."""
    try:
        client.rpc("delete_department", {"p_department_id": department_id}).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not delete the department."
        ) from exc


def insert_staff_member(
    client: Client, community_id: str, department_id: str, fields: dict
) -> str:
    """Add one person to a roster.

    A plain insert rather than an RPC, unlike everything else that writes here:
    it touches one table, so there is no partial state to protect against. The
    composite FK ``(department_id, community_id) -> departments`` still makes a
    cross-tenant row impossible, and RLS still requires an admin of that
    community.
    """
    row = {**fields, "community_id": community_id, "department_id": department_id}
    try:
        response = client.table("staff_assignments").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not add the staff member.") from exc

    rows = response.data or []
    if not rows:
        raise NotFoundError("Staff member was not created.")
    return rows[0]["id"]


def update_staff_member(
    client: Client, community_id: str, staff_id: str, fields: dict
) -> None:
    """Patch one roster entry. No-op when ``fields`` is empty."""
    if not fields:
        return
    try:
        (
            client.table("staff_assignments")
            .update(fields)
            .eq("id", staff_id)
            .eq("community_id", community_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not update the staff member."
        ) from exc


def remove_staff_member(client: Client, staff_id: str) -> None:
    """Take a member off the active roster (RPC). Deactivation, not deletion (A7)."""
    try:
        client.rpc("remove_department_staff", {"p_staff_id": staff_id}).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not remove the staff member."
        ) from exc
