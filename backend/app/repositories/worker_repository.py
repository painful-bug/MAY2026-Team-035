"""Data access for the worker portal.

Reads go through the three views in ``0039`` 1; every write goes through one of
the eight SECURITY DEFINER functions in 3 and 4. Neither
``work_order_assignments`` nor either availability table carries a write policy,
so there is no path from this process to a row those functions did not write.

**Nothing here takes a worker id, and no query filters by one.** The views apply
``is_own_staff_assignment`` and ``profile_id = auth.uid()`` themselves, so "mine"
is decided in Postgres and cannot be widened by anything this module passes. That
is also why every function takes the caller's request client: on the service
client there is no ``auth.uid()``, and the views would return nothing at all --
which would look like a worker with no jobs rather than like a bug.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from postgrest.exceptions import APIError

from app.core.pg_errors import translate
from supabase import Client

_JOBS = "my_worker_job"
_UNAVAILABILITY = "my_worker_unavailability"
_RULES = "my_worker_availability_rule"

#: The list card. Listed rather than ``*`` so a column added to the view later
#: does not silently widen the response -- and, here, so the resident's name and
#: number stay out of a payload that does not need them. See
#: ``app/domain/worker_schemas.py``.
_JOB_SELECT = (
    "assignment_id, work_order_id, staff_assignment_id, assignment_status, "
    "work_order_status, priority, subject_kind, scheduled_start_at, "
    "scheduled_end_at, offered_at, responded_at, decline_reason, "
    "is_auto_assigned, is_forced, community_id, community_name, department_id, "
    "department_name, department_kind, complaint_id, complaint_title, "
    "complaint_category, skill_name, location_text, failed_attempt_count, "
    "cancelled_reason"
)
_LEGACY_JOB_SELECT = _JOB_SELECT.replace(
    "is_auto_assigned, is_forced", "is_auto_assigned"
)

_UNAVAILABILITY_SELECT = (
    "id, starts_at, ends_at, reason, scope, department_name, created_at"
)

_RULE_SELECT = (
    "id, weekday, start_time, end_time, effective_from, effective_to, scope, "
    "department_name"
)


def _job_rows(query: Callable[[str], Any]) -> list[dict[str, Any]]:
    """Read either version of the worker view while the v2 migration rolls out."""
    try:
        return query(_JOB_SELECT).execute().data or []
    except APIError as exc:
        if exc.code != "42703" or "my_worker_job.is_forced" not in exc.message:
            raise
    return [
        {**row, "is_forced": False}
        for row in (query(_LEGACY_JOB_SELECT).execute().data or [])
    ]


def list_jobs(
    client: Client,
    *,
    work_order_status: str | None = None,
    assignment_status: str | None = None,
    starts_from: str | None = None,
    starts_to: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """The caller's jobs, soonest first with the untimed underneath.

    ``nullsfirst=False`` for the reason the supervisor's queue gives: an offer
    with no slot yet is not the most urgent thing on the screen, and sorting
    nulls first would put it above the visit happening in an hour.
    """
    def query(columns: str) -> Any:
        result = client.table(_JOBS).select(columns)
        if work_order_status:
            result = result.eq("work_order_status", work_order_status)
        if assignment_status:
            result = result.eq("assignment_status", assignment_status)
        if starts_from:
            result = result.gte("scheduled_start_at", starts_from)
        if starts_to:
            result = result.lte("scheduled_start_at", starts_to)
        result = result.order("scheduled_start_at", desc=False, nullsfirst=False).order(
            "offered_at", desc=True
        )
        return result.limit(limit) if limit else result

    return _job_rows(query)


def get_job(client: Client, *, work_order_id: str) -> dict[str, Any] | None:
    """One job with its contact details, or ``None`` when it is not the caller's.

    ``None`` and *no such job* are the same answer on purpose: a work-order id
    the caller has nothing to do with should not be confirmed as existing, which
    is the posture the RPCs in ``0039`` 3 take with their own 404s.
    """
    def query(columns: str) -> Any:
        return (
            client.table(_JOBS)
            .select(
                f"{columns}, complaint_description, resident_name, "
                "resident_phone_e164, resident_unit_code"
            )
            .eq("work_order_id", work_order_id)
            .order("offered_at", desc=True)
            .limit(1)
        )

    rows = _job_rows(query)
    return rows[0] if rows else None


def list_unavailability(
    client: Client, *, ends_after: str | None = None, starts_before: str | None = None
) -> list[dict[str, Any]]:
    """The caller's own leave, earliest first.

    The bounds are deliberately asymmetric: a block *overlaps* a window when it
    ends after the window starts and starts before the window ends. Filtering
    ``starts_at`` against both would drop the fortnight of leave a one-week
    calendar is sitting in the middle of.
    """
    query = client.table(_UNAVAILABILITY).select(_UNAVAILABILITY_SELECT)
    if ends_after:
        query = query.gte("ends_at", ends_after)
    if starts_before:
        query = query.lte("starts_at", starts_before)
    return query.order("starts_at").execute().data or []


def list_availability_rules(client: Client) -> list[dict[str, Any]]:
    """The caller's declared working week, in weekday order."""
    return (
        client.table(_RULES)
        .select(_RULE_SELECT)
        .order("weekday")
        .order("start_time")
        .execute()
        .data
        or []
    )


def accept_offer(client: Client, *, work_order_id: str) -> str:
    """Take an offered job (RPC). Returns the assignment id.

    The ``409`` worth designing for is *somebody has already taken this job*: the
    RPC locks the work order first, so the loser of the race reads a job that is
    already ``scheduled`` and is told so in words.
    """
    try:
        response = client.rpc(
            "accept_work_order_offer", {"p_work_order_id": work_order_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not accept that job.") from exc
    return str(response.data or "")


def decline_offer(
    client: Client, *, work_order_id: str, reason: str | None
) -> str:
    """Say no to an offer (RPC). Returns the assignment id."""
    try:
        response = client.rpc(
            "decline_work_order_offer",
            {"p_work_order_id": work_order_id, "p_reason": reason},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not decline that job.") from exc
    return str(response.data or "")


def start_job(client: Client, *, work_order_id: str) -> None:
    """The worker is on site (RPC). Idempotent."""
    try:
        client.rpc("start_work_order", {"p_work_order_id": work_order_id}).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not start that job.") from exc


def complete_job(
    client: Client, *, work_order_id: str, notes: str | None
) -> None:
    """The work is done (RPC). Does not resolve the complaint."""
    try:
        client.rpc(
            "complete_work_order",
            {"p_work_order_id": work_order_id, "p_notes": notes},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not complete that job.") from exc


def report_failure(client: Client, *, work_order_id: str, reason: str) -> None:
    """The visit did not happen (RPC). Counts the attempt and escalates."""
    try:
        client.rpc(
            "report_work_order_failure",
            {"p_work_order_id": work_order_id, "p_reason": reason},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not report that visit.") from exc


def add_unavailability(
    client: Client, *, starts_at: str, ends_at: str, reason: str | None
) -> str:
    """Mark a window unavailable (RPC). Returns the block id."""
    try:
        response = client.rpc(
            "set_worker_unavailability",
            {"p_starts_at": starts_at, "p_ends_at": ends_at, "p_reason": reason},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not save that unavailable block."
        ) from exc
    return str(response.data or "")


def delete_unavailability(client: Client, *, block_id: str) -> None:
    """Remove one of the caller's own blocks (RPC)."""
    try:
        client.rpc(
            "delete_worker_unavailability", {"p_id": block_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not remove that unavailable block."
        ) from exc


def set_availability_rules(
    client: Client, *, rules: list[dict[str, Any]]
) -> int:
    """Replace the caller's working week (RPC). Returns how many rules they now hold."""
    try:
        response = client.rpc(
            "set_worker_availability_rules", {"p_rules": rules}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not save your working hours."
        ) from exc
    return int(response.data or 0)
