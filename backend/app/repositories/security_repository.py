"""Data access for gate operations.

Reads go through the four views in ``0040`` 8, plus ``security_posts``
directly -- a view that selects every column of one table is a synonym, and the
read policy is on the table either way. Every write goes through one of the
twelve SECURITY DEFINER functions in 9 to 12; none of the six tables carries an
insert, update or delete policy, so there is no path from this process to a row
those functions did not write.

**Every write takes the caller's membership id and no community id.** The
community is derived from the membership inside Postgres, after
``is_own_membership`` has confirmed it is the caller's -- so the id names which
gate the caller is standing at and cannot grant access to one they do not hold.
``ADMIN_DASHBOARD_DESIGN.md`` 10 is the rule; this is the shape it takes when a
caller may legitimately hold two.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_POSTS = "security_posts"
_SHIFTS = "security_shift_overview"
_MOVEMENTS = "material_movement_overview"
_TANKERS = "water_tanker_log_overview"
_INCIDENTS = "security_incident_overview"

#: Listed rather than ``*`` throughout, so a column added to a view later does
#: not silently widen a response -- the rule ``worker_repository`` states, and
#: the reason ``security_incident_overview`` can safely carry a membership id
#: that no response model exposes.
_POST_SELECT = (
    "id, community_id, department_id, name, location_text, latitude, longitude, "
    "is_active, created_at, updated_at"
)

_SHIFT_SELECT = (
    "id, community_id, department_id, post_id, post_name, staff_assignment_id, "
    "guard_name, guard_phone_e164, guard_job_title, guard_rank, starts_at, "
    "ends_at, status, notes, created_at, updated_at"
)

_MOVEMENT_SELECT = (
    "id, community_id, direction, description, quantity, unit, is_returnable, "
    "expected_return_at, returned_at, carrier_name, vehicle_number, unit_id, "
    "unit_code, post_id, post_name, notes, recorded_at, is_outstanding, "
    "is_overdue"
)

_TANKER_SELECT = (
    "id, community_id, supplier_name, tanker_number, volume_litres, driver_name, "
    "driver_phone_e164, arrived_at, departed_at, post_id, post_name, notes, "
    "is_on_site"
)

_INCIDENT_SELECT = (
    "id, community_id, category, severity, status, summary, details, "
    "location_text, post_id, post_name, occurred_at, resolved_at, "
    "reported_by_name, created_at, updated_at"
)


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def list_posts(
    client: Client, *, include_inactive: bool = False
) -> list[dict[str, Any]]:
    """Every post the caller's policy lets them see, by name."""
    query = client.table(_POSTS).select(_POST_SELECT)
    if not include_inactive:
        query = query.eq("is_active", True)
    return query.order("name").execute().data or []


def list_shifts(
    client: Client,
    *,
    starts_from: str | None = None,
    starts_to: str | None = None,
    status: str | None = None,
    post_id: str | None = None,
    shift_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Shifts overlapping a window, soonest first.

    The range matches on **overlap** rather than on start, for the reason
    ``worker_repository.list_unavailability`` gives: a night shift that began
    yesterday evening is the one a guard on duty at 1 a.m. is looking at, and
    filtering by start would drop exactly the row that matters.

    ``shift_id`` narrows to one row and is the only filter that answers a
    question the window cannot. Every other filter subsets a range the caller
    already chose; this one is for a caller who arrived holding an id and does
    not know which range it falls in.
    """
    query = client.table(_SHIFTS).select(_SHIFT_SELECT)
    if starts_to:
        query = query.lte("starts_at", starts_to)
    if starts_from:
        query = query.gte("ends_at", starts_from)
    if status:
        query = query.eq("status", status)
    if post_id:
        query = query.eq("post_id", post_id)
    if shift_id:
        query = query.eq("id", shift_id)
    return query.order("starts_at").limit(limit).execute().data or []


def list_movements(
    client: Client,
    *,
    starts_from: str | None = None,
    starts_to: str | None = None,
    direction: str | None = None,
    outstanding: bool | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Register entries, newest first."""
    query = client.table(_MOVEMENTS).select(_MOVEMENT_SELECT)
    if starts_from:
        query = query.gte("recorded_at", starts_from)
    if starts_to:
        query = query.lte("recorded_at", starts_to)
    if direction:
        query = query.eq("direction", direction)
    if outstanding is not None:
        query = query.eq("is_outstanding", outstanding)
    return query.order("recorded_at", desc=True).limit(limit).execute().data or []


def list_tankers(
    client: Client,
    *,
    starts_from: str | None = None,
    starts_to: str | None = None,
    on_site: bool | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Tanker entries, newest first."""
    query = client.table(_TANKERS).select(_TANKER_SELECT)
    if starts_from:
        query = query.gte("arrived_at", starts_from)
    if starts_to:
        query = query.lte("arrived_at", starts_to)
    if on_site is not None:
        query = query.eq("is_on_site", on_site)
    return query.order("arrived_at", desc=True).limit(limit).execute().data or []


def list_incidents(
    client: Client,
    *,
    starts_from: str | None = None,
    starts_to: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Incidents, newest first."""
    query = client.table(_INCIDENTS).select(_INCIDENT_SELECT)
    if starts_from:
        query = query.gte("occurred_at", starts_from)
    if starts_to:
        query = query.lte("occurred_at", starts_to)
    if status:
        query = query.eq("status", status)
    if severity:
        query = query.eq("severity", severity)
    return query.order("occurred_at", desc=True).limit(limit).execute().data or []


def list_roster(client: Client, *, membership_id: str) -> list[dict[str, Any]]:
    """Active security-department staff, for the shift form's guard picker.

    The one read on this surface that goes through an RPC rather than a view:
    the answer depends on who is asking (``gate_admin_community_for`` raises
    ``HB403`` for anyone below security manager), and a view cannot refuse.
    """
    try:
        response = client.rpc(
            "security_roster", {"p_membership_id": membership_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not read the roster.") from exc
    rows = response.data or []
    return rows if isinstance(rows, list) else [rows]


def get_post(client: Client, *, post_id: str) -> dict[str, Any] | None:
    rows = (
        client.table(_POSTS).select(_POST_SELECT).eq("id", post_id).limit(1)
        .execute().data or []
    )
    return rows[0] if rows else None


def get_shift(client: Client, *, shift_id: str) -> dict[str, Any] | None:
    rows = (
        client.table(_SHIFTS).select(_SHIFT_SELECT).eq("id", shift_id).limit(1)
        .execute().data or []
    )
    return rows[0] if rows else None


def get_movement(client: Client, *, movement_id: str) -> dict[str, Any] | None:
    rows = (
        client.table(_MOVEMENTS).select(_MOVEMENT_SELECT).eq("id", movement_id)
        .limit(1).execute().data or []
    )
    return rows[0] if rows else None


def get_tanker(client: Client, *, log_id: str) -> dict[str, Any] | None:
    rows = (
        client.table(_TANKERS).select(_TANKER_SELECT).eq("id", log_id).limit(1)
        .execute().data or []
    )
    return rows[0] if rows else None


def get_incident(client: Client, *, incident_id: str) -> dict[str, Any] | None:
    rows = (
        client.table(_INCIDENTS).select(_INCIDENT_SELECT).eq("id", incident_id)
        .limit(1).execute().data or []
    )
    return rows[0] if rows else None


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------


def upsert_post(client: Client, *, membership_id: str, payload: dict[str, Any]) -> str:
    """Create or change a post (RPC). Returns the post id."""
    try:
        response = client.rpc(
            "upsert_security_post", {"p_membership_id": membership_id, **payload}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not save that post.") from exc
    return str(response.data or "")


def schedule_shift(
    client: Client, *, membership_id: str, payload: dict[str, Any]
) -> str:
    """Put a guard on a post (RPC). Returns the shift id."""
    try:
        response = client.rpc(
            "schedule_security_shift", {"p_membership_id": membership_id, **payload}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not schedule that shift.") from exc
    return str(response.data or "")


def update_shift(
    client: Client, *, membership_id: str, shift_id: str, payload: dict[str, Any]
) -> None:
    """Change a shift (RPC)."""
    try:
        client.rpc(
            "update_security_shift",
            {"p_membership_id": membership_id, "p_shift_id": shift_id, **payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update that shift.") from exc


def record_movement(
    client: Client, *, membership_id: str, payload: dict[str, Any]
) -> str:
    """Write a register entry (RPC). Returns the entry id."""
    try:
        response = client.rpc(
            "record_material_movement", {"p_membership_id": membership_id, **payload}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not record that movement.") from exc
    return str(response.data or "")


def mark_returned(
    client: Client, *, membership_id: str, movement_id: str, returned_at: str | None
) -> None:
    """The returnable item came back (RPC). Idempotent."""
    try:
        client.rpc(
            "mark_material_returned",
            {
                "p_membership_id": membership_id,
                "p_movement_id": movement_id,
                "p_returned_at": returned_at,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not record that return.") from exc


def record_tanker(
    client: Client, *, membership_id: str, payload: dict[str, Any]
) -> str:
    """Log a tanker (RPC). Returns the log id."""
    try:
        response = client.rpc(
            "record_water_tanker", {"p_membership_id": membership_id, **payload}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not log that tanker.") from exc
    return str(response.data or "")


def update_tanker(
    client: Client, *, membership_id: str, log_id: str, payload: dict[str, Any]
) -> None:
    """Record a departure or correct a volume (RPC)."""
    try:
        client.rpc(
            "update_water_tanker",
            {"p_membership_id": membership_id, "p_log_id": log_id, **payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update that entry.") from exc


def record_incident(
    client: Client, *, membership_id: str, payload: dict[str, Any]
) -> str:
    """File an incident (RPC). Returns the incident id."""
    try:
        response = client.rpc(
            "record_security_incident", {"p_membership_id": membership_id, **payload}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not file that incident.") from exc
    return str(response.data or "")


def update_incident(
    client: Client, *, membership_id: str, incident_id: str, payload: dict[str, Any]
) -> None:
    """Acknowledge or resolve an incident (RPC)."""
    try:
        client.rpc(
            "update_security_incident",
            {
                "p_membership_id": membership_id,
                "p_incident_id": incident_id,
                **payload,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update that incident.") from exc


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


def verify_credential(
    client: Client,
    *,
    membership_id: str,
    credential_hash: str,
    presented_at: str | None,
) -> dict[str, Any]:
    """May this person in (RPC).

    A set-returning function, so PostgREST hands back a list of one. An empty
    list would mean the function returned no row, which it cannot -- every branch
    of ``verify_gate_credential`` returns one -- so an empty answer is treated as
    a refusal rather than as a success with missing fields.
    """
    try:
        response = client.rpc(
            "verify_gate_credential",
            {
                "p_membership_id": membership_id,
                "p_hash": credential_hash,
                "p_at": presented_at,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not verify that code.") from exc
    rows = response.data or []
    if isinstance(rows, dict):
        return rows
    return rows[0] if rows else {}


def offline_bundle(
    client: Client, *, membership_id: str, hours: int
) -> list[dict[str, Any]]:
    """The passes a gate may need while disconnected (RPC)."""
    try:
        response = client.rpc(
            "gate_offline_bundle",
            {"p_membership_id": membership_id, "p_hours": hours},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not build that bundle.") from exc
    rows = response.data or []
    return rows if isinstance(rows, list) else [rows]


def reconcile_entry(
    client: Client,
    *,
    membership_id: str,
    source_client_id: str,
    credential_hash: str,
    presented_at: str,
    claimed_verdict: str | None,
) -> dict[str, Any]:
    """Replay one queued admission (RPC). Idempotent on the device's own id."""
    try:
        response = client.rpc(
            "reconcile_offline_entry",
            {
                "p_membership_id": membership_id,
                "p_source_client_id": source_client_id,
                "p_hash": credential_hash,
                "p_claimed_at": presented_at,
                "p_claimed_verdict": claimed_verdict,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not reconcile that entry.") from exc
    rows = response.data or []
    if isinstance(rows, dict):
        return rows
    return rows[0] if rows else {}
