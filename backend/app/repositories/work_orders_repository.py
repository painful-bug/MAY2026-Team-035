"""Data access for work orders.

Reads go through ``work_order_overview`` and ``work_order_assignment_overview``;
every write goes through one of the six SECURITY DEFINER functions in ``0036``
6. Neither table carries an insert, update or delete policy, so there is no path
from this process to a row those functions did not write.

**Every function here takes the caller's request client, never the service
client.** All six RPCs resolve the caller from ``auth.uid()`` and refuse a
stranger; the service client has no ``auth.uid()``, so passing it would not fail
loudly -- it would tell a signed-in supervisor they do not supervise their own
department.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_WORK_ORDERS = "work_order_overview"
_ASSIGNMENTS = "work_order_assignment_overview"

#: Listed rather than ``*`` so a column added to the view later does not
#: silently widen the response.
_WORK_ORDER_SELECT = (
    "id, community_id, complaint_id, complaint_title, complaint_category, "
    "department_id, department_name, skill_id, skill_name, status, priority, "
    "subject_kind, location_text, scheduled_start_at, scheduled_end_at, "
    "resident_deadline_at, failed_attempt_count, cancelled_reason, "
    "assignee_name, staff_assignment_id, created_at, updated_at"
)

_ASSIGNMENT_SELECT = (
    "id, work_order_id, staff_assignment_id, status, worker_name, "
    "worker_phone_e164, worker_membership_id, worker_provider_id, "
    "scheduled_start_at, scheduled_end_at, offered_at, responded_at, "
    "decline_reason, is_auto_assigned"
)


def get_work_order(client: Client, *, work_order_id: str) -> dict[str, Any] | None:
    """One job, or ``None`` when the policy hides it from this caller."""
    rows = (
        client.table(_WORK_ORDERS)
        .select(_WORK_ORDER_SELECT)
        .eq("id", work_order_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_for_department(
    client: Client,
    *,
    department_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """The supervisor's queue: soonest first, unscheduled last.

    ``nullsfirst=False`` on the time, because a draft with no slot is not the
    most urgent thing on the screen -- it is the thing nobody has decided about
    yet, and it belongs under the visits that are actually happening today.
    """
    query = (
        client.table(_WORK_ORDERS)
        .select(_WORK_ORDER_SELECT)
        .eq("department_id", department_id)
    )
    if status:
        query = query.eq("status", status)
    return (
        query.order("scheduled_start_at", desc=False, nullsfirst=False)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


def list_for_complaint(
    client: Client, *, complaint_id: str
) -> list[dict[str, Any]]:
    """Every job raised against one complaint, newest first.

    A list and not one row: a failed visit is rescheduled and a reopened
    complaint goes to a different supervisor, and both are a second work order.
    """
    return (
        client.table(_WORK_ORDERS)
        .select(_WORK_ORDER_SELECT)
        .eq("complaint_id", complaint_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


def list_assignments(
    client: Client, *, work_order_id: str
) -> list[dict[str, Any]]:
    """Every offer made on one job, newest first."""
    return (
        client.table(_ASSIGNMENTS)
        .select(_ASSIGNMENT_SELECT)
        .eq("work_order_id", work_order_id)
        .order("offered_at", desc=True)
        .execute()
        .data
        or []
    )


def create_work_order(
    client: Client,
    *,
    complaint_id: str,
    department_id: str | None,
    skill_id: str | None,
    subject_kind: str,
    location_text: str | None,
    scheduled_start_at: str | None,
    scheduled_end_at: str | None,
    note: str | None,
) -> str:
    """Raise work against a complaint (RPC, ``0036`` 6). Returns its id."""
    try:
        response = client.rpc(
            "create_work_order",
            {
                "p_complaint_id": complaint_id,
                "p_department_id": department_id,
                "p_skill_id": skill_id,
                "p_subject_kind": subject_kind,
                "p_location_text": location_text,
                "p_scheduled_start_at": scheduled_start_at,
                "p_scheduled_end_at": scheduled_end_at,
                "p_note": note,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not raise that job.") from exc
    return str(response.data or "")


def update_work_order(
    client: Client,
    *,
    work_order_id: str,
    skill_id: str | None,
    subject_kind: str | None,
    location_text: str | None,
    priority: str | None,
) -> None:
    """Edit the descriptive fields of a job (RPC)."""
    try:
        client.rpc(
            "update_work_order",
            {
                "p_work_order_id": work_order_id,
                "p_skill_id": skill_id,
                "p_subject_kind": subject_kind,
                "p_location_text": location_text,
                "p_priority": priority,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update that job.") from exc


def reschedule_work_order(
    client: Client,
    *,
    work_order_id: str,
    scheduled_start_at: str,
    scheduled_end_at: str,
    note: str | None,
) -> None:
    """Move the visit (RPC). The accepted assignment moves with it."""
    try:
        client.rpc(
            "reschedule_work_order",
            {
                "p_work_order_id": work_order_id,
                "p_scheduled_start_at": scheduled_start_at,
                "p_scheduled_end_at": scheduled_end_at,
                "p_note": note,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not move that visit."
        ) from exc


def assign_work_order(
    client: Client,
    *,
    work_order_id: str,
    staff_assignment_id: str,
    scheduled_start_at: str | None,
    scheduled_end_at: str | None,
) -> str:
    """Put a named person on the job (RPC). Returns the assignment id.

    Two distinct 409s come out of here and both are worth the caller reading:
    the person is not on this department's roster, or they are already booked
    across the slot. The second is raised by name inside the RPC *and* enforced
    by ``work_order_assignments_no_overlap`` -- the check is the sentence, the
    constraint is the guarantee, and a race that beats the check surfaces as
    ``23P01``, which ``pg_errors`` also maps to a 409.
    """
    try:
        response = client.rpc(
            "assign_work_order",
            {
                "p_work_order_id": work_order_id,
                "p_staff_assignment_id": staff_assignment_id,
                "p_scheduled_start_at": scheduled_start_at,
                "p_scheduled_end_at": scheduled_end_at,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not assign that job."
        ) from exc
    return str(response.data or "")


def cancel_work_order(
    client: Client, *, work_order_id: str, reason: str
) -> None:
    """Call the job off (RPC). Withdraws the assignment with it."""
    try:
        client.rpc(
            "cancel_work_order",
            {"p_work_order_id": work_order_id, "p_reason": reason},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not cancel that job.") from exc


def respond_to_schedule(
    client: Client, *, work_order_id: str, response: str, note: str | None
) -> None:
    """The resident's answer to a proposed visit (RPC).

    The only write in this module a resident may make. The RPC checks
    ``is_own_membership`` against whoever raised the complaint, so a member of
    the same community holding somebody else's work order id gets a 403 rather
    than an answer recorded in their neighbour's name.
    """
    try:
        client.rpc(
            "respond_to_work_order_schedule",
            {
                "p_work_order_id": work_order_id,
                "p_response": response,
                "p_note": note,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not record your answer."
        ) from exc
