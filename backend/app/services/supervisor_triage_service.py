"""The supervisor's triage dashboard: five sections in one read, and five verbs.

Thin, like every service over a definer RPC. **There is no authorization
decision in this file** -- ``can_supervise_department`` is asked inside every one
of the RPCs, and a copy of that rule here would be a second statement of it with
nothing keeping the two in step. The same goes for the refusals: whether a
complaint can be resolved with a job running, and whether its priority can go any
higher, are decided under a row lock in Postgres and not by a read taken a moment
earlier here.

**There is no bucketing decision either, and that is the load-bearing absence.**
``docs/plans/SUPERVISOR_TRIAGE_SPEC.md`` freezes the sections as a server-side
decision so that the definitions of *live*, *committed* and *taken up* exist
once. They are in ``20260822170000_supervisor_actions.sql`` 8; nothing below
re-derives them, and a future edit that starts filtering here should be read as
the beginning of a second answer.

What this module does own is the **vocabulary seam**. The RPC returns the stored
words -- ``low``, ``open`` -- because SQL translating a vocabulary would be a
second copy of ``app/domain/vocabularies.py`` free to disagree with it. The
translation to ``High`` and ``In Progress`` happens here, in the same call every
other complaint surface makes.
"""

from __future__ import annotations

from typing import Any

from app.domain.supervisor_triage_schemas import (
    AddComplaintNoteRequest,
    ComplaintThreadOpened,
    TriageComplaint,
    TriageSnapshot,
    TriageWorkOrder,
)
from app.domain.vocabularies import (
    complaint_priority_to_wire,
    complaint_status_to_wire,
)
from app.repositories import supervisor_triage_repository as repo
from supabase import Client


def _text(value: Any) -> str:
    """A projected field as a string, never ``None``."""
    return str(value).strip() if value not in (None, "") else ""


def _optional(value: Any) -> str | None:
    return _text(value) or None


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """One section of the RPC's object, defensively.

    ``jsonb_agg`` over an empty set is ``null``, which the RPC already coalesces
    to ``[]``. This is the second belt: a section that came back as anything but
    a list renders as empty rather than raising, because one malformed section
    should not take the other three off the screen with it.
    """
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _to_complaint(row: dict[str, Any]) -> TriageComplaint:
    return TriageComplaint(
        id=str(row["id"]),
        title=_text(row.get("title")),
        category=_text(row.get("category")),
        priority=complaint_priority_to_wire(row.get("priority")),
        status=complaint_status_to_wire(row.get("status")),
        location=_text(row.get("location")),
        raised_by=_text(row.get("raised_by")) or "A resident",
        unit_code=_optional(row.get("unit_code")),
        created_at=row.get("created_at"),
        due_at=row.get("due_at"),
        returned_to_pool_at=row.get("returned_to_pool_at"),
        reopened_count=int(row.get("reopened_count") or 0),
        rerouted_at=row.get("rerouted_at"),
        taken_up_at=row.get("taken_up_at"),
        taken_up_by_name=_optional(row.get("taken_up_by_name")),
        live_work_order_count=int(row.get("live_work_order_count") or 0),
        open_request_id=_optional(row.get("open_request_id")),
    )


def _to_work_order(row: dict[str, Any]) -> TriageWorkOrder:
    return TriageWorkOrder(
        id=str(row["id"]),
        complaint_id=_optional(row.get("complaint_id")),
        complaint_title=_text(row.get("complaint_title")),
        complaint_category=_text(row.get("complaint_category")),
        # A job's urgency *is* its complaint's, inherited by `create_work_order`
        # rather than copied by hand, so the same map answers both.
        priority=complaint_priority_to_wire(row.get("priority")),
        # Passed through, unlike the complaint's. Different noun, different
        # vocabulary -- `WorkOrder` has always sent the storage words.
        status=_text(row.get("status")) or "draft",
        assignee_name=_optional(row.get("assignee_name")),
        offered_to_name=_optional(row.get("offered_to_name")),
        scheduled_start_at=row.get("scheduled_start_at"),
        scheduled_end_at=row.get("scheduled_end_at"),
        started_at=row.get("started_at"),
        inherited_at=row.get("inherited_at"),
        location_text=_optional(row.get("location_text")),
        skill_name=_optional(row.get("skill_name")),
    )


def snapshot(client: Client, *, department_id: str) -> TriageSnapshot:
    """One department's dashboard: the five sections the RPC bucketed."""
    payload = repo.triage_snapshot(client, department_id=department_id)
    return TriageSnapshot(
        department_id=str(payload.get("department_id") or department_id),
        new_complaints=[
            _to_complaint(row) for row in _rows(payload, "new_complaints")
        ],
        taken_up=[_to_complaint(row) for row in _rows(payload, "taken_up")],
        open_requests=[
            _to_work_order(row) for row in _rows(payload, "open_requests")
        ],
        assigned_pending=[
            _to_work_order(row) for row in _rows(payload, "assigned_pending")
        ],
        in_progress=[
            _to_work_order(row) for row in _rows(payload, "in_progress")
        ],
    )


def take_up(client: Client, *, complaint_id: str) -> None:
    """A supervisor taking a new complaint up. Idempotent for the same person."""
    repo.take_up_complaint(client, complaint_id=complaint_id)


def resolve(client: Client, *, complaint_id: str) -> None:
    """The department marking a complaint resolved.

    No pre-read of the complaint's jobs. "Is anything running?" is asked inside
    the RPC, under a row lock, and asking it here first would be a second answer
    computed a moment earlier with the caller's RLS rather than the RPC's.
    """
    repo.resolve_complaint(client, complaint_id=complaint_id)


def raise_priority(client: Client, *, complaint_id: str) -> str:
    """Escalate one step and return the new priority in **wire** vocabulary.

    The RPC answers ``medium``/``high``; the message a supervisor reads says
    *Medium*/*High*, through the same table every other complaint surface uses.
    """
    return complaint_priority_to_wire(
        repo.raise_complaint_priority(client, complaint_id=complaint_id)
    )


def add_note(
    client: Client, *, complaint_id: str, body: AddComplaintNoteRequest
) -> str:
    """Append an internal note. Returns the timeline event's id."""
    return repo.add_complaint_note(
        client, complaint_id=complaint_id, note=body.note.strip()
    )


def open_chat(client: Client, *, complaint_id: str) -> ComplaintThreadOpened:
    """Open (or get) the complaint's chat thread."""
    return ComplaintThreadOpened(
        thread_id=repo.open_complaint_thread(client, complaint_id=complaint_id)
    )
