"""Work orders: triage, scheduling, assignment, and the resident's answer.

Step 4 of ``docs/plans/SERVICE_OPERATIONS_PLAN.md``. One sentence is the whole
of what it has to get right: **a person cannot be in two places at once.** That
is enforced by ``work_order_assignments_no_overlap`` in ``0036``, not here --
this module translates vocabulary, decides what a caller is asking for, and
turns a row into a DTO.

**There is no authorization decision in this file.** Every RPC underneath checks
``can_supervise_department`` or ``is_own_membership`` for itself, and every read
goes through a view whose policy is ``can_read_work_order``. A check repeated
here would be a second statement of the same rule with nothing keeping the two
in step, and the one that drifts is always the one nobody is testing.

**The resident's two routes resolve the work order from the complaint**, rather
than taking an id. A resident should not have to have read a work order id to
answer a question that was put to them, and an endpoint that accepts one has to
answer what happens when it names a different complaint's job. Resolving it from
the complaint makes that question unaskable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.work_order_schemas import (
    AssignWorkOrderRequest,
    Candidate,
    CancelWorkOrderRequest,
    CreateWorkOrderRequest,
    RescheduleWorkOrderRequest,
    ScheduleRequest,
    ScheduleResponseRequest,
    UpdateWorkOrderRequest,
    WorkOrder,
    WorkOrderAssignment,
    WorkOrderDetail,
)
from app.repositories import work_orders_repository as repo
from supabase import Client

#: What a job may be about. Mirrors ``work_orders_subject_kind_check``.
_SUBJECT_KINDS = ("resident", "facility")

#: Mirrors ``work_orders_priority_check``, which is now the same three words
#: ``complaints_priority_check`` uses -- see the header of ``0036``.
_PRIORITIES = ("low", "medium", "high")

#: The resident's two possible answers. ``withdrawn`` is not among them: a
#: resident who has changed their mind declines, and a supervisor who has is the
#: one who cancels.
_RESPONSES = ("confirmed", "declined")

#: The states a proposed visit can still be answered from. Anything else has
#: either been settled or called off.
_OPEN_STATES = ("draft", "awaiting_resident", "offered", "scheduled", "in_progress")


def _text(value: object) -> str | None:
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _iso(value: datetime | None) -> str | None:
    """A datetime as PostgREST wants it, or ``None``.

    Pydantic has already parsed and validated it; this only re-renders it, so a
    naive value stays naive rather than being silently stamped with the server's
    timezone -- ``timestamptz`` applies the connection's zone to a naive literal,
    and guessing here would put the guess one layer further from where anyone
    would look for it.
    """
    return None if value is None else value.isoformat()


def _to_assignment(row: dict[str, Any]) -> WorkOrderAssignment:
    return WorkOrderAssignment(
        id=row["id"],
        work_order_id=row["work_order_id"],
        staff_assignment_id=_text(row.get("staff_assignment_id")),
        status=str(row.get("status") or "offered"),
        worker_name=_text(row.get("worker_name")),
        worker_phone_e164=_text(row.get("worker_phone_e164")),
        worker_membership_id=_text(row.get("worker_membership_id")),
        worker_provider_id=_text(row.get("worker_provider_id")),
        scheduled_start_at=row.get("scheduled_start_at"),
        scheduled_end_at=row.get("scheduled_end_at"),
        offered_at=row.get("offered_at"),
        responded_at=row.get("responded_at"),
        decline_reason=_text(row.get("decline_reason")),
        is_auto_assigned=bool(row.get("is_auto_assigned")),
        is_forced=bool(row.get("is_forced")),
    )


def _to_work_order(row: dict[str, Any]) -> WorkOrder:
    return WorkOrder(
        id=row["id"],
        community_id=row["community_id"],
        complaint_id=_text(row.get("complaint_id")),
        complaint_title=_text(row.get("complaint_title")),
        complaint_category=_text(row.get("complaint_category")),
        department_id=_text(row.get("department_id")),
        department_name=_text(row.get("department_name")),
        skill_id=_text(row.get("skill_id")),
        skill_name=_text(row.get("skill_name")),
        status=str(row.get("status") or "draft"),
        priority=str(row.get("priority") or "medium"),
        subject_kind=str(row.get("subject_kind") or "resident"),
        location_text=_text(row.get("location_text")),
        scheduled_start_at=row.get("scheduled_start_at"),
        scheduled_end_at=row.get("scheduled_end_at"),
        resident_deadline_at=row.get("resident_deadline_at"),
        failed_attempt_count=int(row.get("failed_attempt_count") or 0),
        cancelled_reason=_text(row.get("cancelled_reason")),
        assignee_name=_text(row.get("assignee_name")),
        staff_assignment_id=_text(row.get("staff_assignment_id")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _to_schedule_request(row: dict[str, Any]) -> ScheduleRequest:
    status = str(row.get("status") or "draft")
    return ScheduleRequest(
        work_order_id=row["id"],
        complaint_id=_text(row.get("complaint_id")),
        status=status,
        department_name=_text(row.get("department_name")),
        skill_name=_text(row.get("skill_name")),
        location_text=_text(row.get("location_text")),
        scheduled_start_at=row.get("scheduled_start_at"),
        scheduled_end_at=row.get("scheduled_end_at"),
        respond_by=row.get("resident_deadline_at"),
        awaiting_response=status == "awaiting_resident",
        assignee_name=_text(row.get("assignee_name")),
    )


def _read_back(client: Client, *, work_order_id: str) -> WorkOrder:
    """Re-read the job the write just touched.

    Every write returns the row rather than the request, for the reason the
    hiring surface gives too: the view supplies the department name, the skill
    name and the current assignee, none of which the caller sent. A 404 after a
    successful write means the caller wrote something they may not read, which
    is worth surfacing rather than papering over.
    """
    row = repo.get_work_order(client, work_order_id=work_order_id)
    if row is None:
        raise NotFoundError("No such work order.", code="work_order_not_found")
    return _to_work_order(row)


def _read_back_detail(client: Client, *, work_order_id: str) -> WorkOrderDetail:
    order = _read_back(client, work_order_id=work_order_id)
    return WorkOrderDetail(
        **order.model_dump(),
        assignments=[
            _to_assignment(row)
            for row in repo.list_assignments(client, work_order_id=work_order_id)
        ],
    )


def _validated_subject_kind(value: str | None) -> str | None:
    if value is None:
        return None
    kind = value.strip().lower()
    if kind not in _SUBJECT_KINDS:
        raise ValidationError(
            "subjectKind must be 'resident' or 'facility'.",
            code="unknown_subject_kind",
        )
    return kind


def _validated_priority(value: str | None) -> str | None:
    if value is None:
        return None
    priority = value.strip().lower()
    if priority not in _PRIORITIES:
        raise ValidationError(
            "priority must be 'low', 'medium' or 'high'.", code="unknown_priority"
        )
    return priority


# ---------------------------------------------------------------------------
# The supervisor's side
# ---------------------------------------------------------------------------


def create(
    client: Client, *, complaint_id: str, body: CreateWorkOrderRequest
) -> WorkOrder:
    """Raise work against a complaint. The triage fork.

    No slot means a draft, and the complaint stays a conversation. A slot on a
    ``resident`` job means the resident is asked; on a ``facility`` job there is
    nobody to ask and it goes straight to ``offered``.
    """
    work_order_id = repo.create_work_order(
        client,
        complaint_id=complaint_id,
        department_id=body.department_id,
        skill_id=body.skill_id,
        subject_kind=_validated_subject_kind(body.subject_kind) or "resident",
        location_text=body.location_text,
        scheduled_start_at=_iso(body.scheduled_start_at),
        scheduled_end_at=_iso(body.scheduled_end_at),
        note=body.note,
    )
    return _read_back(client, work_order_id=work_order_id)


def get_detail(client: Client, *, work_order_id: str) -> WorkOrderDetail:
    """One job with its assignment history."""
    return _read_back_detail(client, work_order_id=work_order_id)


def candidates(
    client: Client, *, work_order_id: str, include_excluded: bool = False
) -> list[Candidate]:
    return [Candidate(**row) for row in repo.candidates(
        client, work_order_id=work_order_id, include_excluded=include_excluded
    )]


def list_for_department(
    client: Client, *, department_id: str, status: str | None
) -> list[WorkOrder]:
    """The department's queue."""
    return [
        _to_work_order(row)
        for row in repo.list_for_department(
            client, department_id=department_id, status=status
        )
    ]


def list_for_complaint(client: Client, *, complaint_id: str) -> list[WorkOrder]:
    """Every job raised against one complaint."""
    return [
        _to_work_order(row)
        for row in repo.list_for_complaint(client, complaint_id=complaint_id)
    ]


def update(
    client: Client, *, work_order_id: str, body: UpdateWorkOrderRequest
) -> WorkOrder:
    """Edit what the job is."""
    repo.update_work_order(
        client,
        work_order_id=work_order_id,
        skill_id=body.skill_id,
        subject_kind=_validated_subject_kind(body.subject_kind),
        location_text=body.location_text,
        priority=_validated_priority(body.priority),
    )
    return _read_back(client, work_order_id=work_order_id)


def assign(
    client: Client, *, work_order_id: str, body: AssignWorkOrderRequest
) -> WorkOrderDetail:
    """Put a named person on the job, and book their hour.

    Two RPCs behind one route, chosen by ``force`` and by nothing else. The
    default path is ``assign_work_order`` **unchanged**: an offer the worker may
    decline, with the schedule rules and the 409s it has always had.

    ``force`` routes to ``force_assign_work_order``, which is the dispatch
    engine's own force-assign with the picking taken out and a supervisor's
    guard put in: an ``is_forced`` accepted assignment the worker cannot decline.
    The branch is here and not in SQL because the two are different decisions --
    "ask this person" and "send this person" -- and one function that did either
    depending on a flag would have two sets of refusals sharing one name.
    """
    if body.force:
        repo.force_assign_work_order(
            client,
            work_order_id=work_order_id,
            staff_assignment_id=body.staff_assignment_id,
            scheduled_start_at=_iso(body.scheduled_start_at),
            scheduled_end_at=_iso(body.scheduled_end_at),
        )
        return _read_back_detail(client, work_order_id=work_order_id)

    repo.assign_work_order(
        client,
        work_order_id=work_order_id,
        staff_assignment_id=body.staff_assignment_id,
        scheduled_start_at=_iso(body.scheduled_start_at),
        scheduled_end_at=_iso(body.scheduled_end_at),
    )
    return _read_back_detail(client, work_order_id=work_order_id)


def reschedule(
    client: Client, *, work_order_id: str, body: RescheduleWorkOrderRequest
) -> WorkOrderDetail:
    """Move the visit. The assignment moves with it."""
    repo.reschedule_work_order(
        client,
        work_order_id=work_order_id,
        scheduled_start_at=_iso(body.scheduled_start_at) or "",
        scheduled_end_at=_iso(body.scheduled_end_at) or "",
        note=body.note,
    )
    return _read_back_detail(client, work_order_id=work_order_id)


def cancel(
    client: Client, *, work_order_id: str, body: CancelWorkOrderRequest
) -> WorkOrder:
    """Call the job off, and free the worker's slot."""
    repo.cancel_work_order(
        client, work_order_id=work_order_id, reason=body.reason
    )
    return _read_back(client, work_order_id=work_order_id)


# ---------------------------------------------------------------------------
# The resident's side
# ---------------------------------------------------------------------------


def _live_work_order(client: Client, *, complaint_id: str) -> dict[str, Any]:
    """The job on this complaint the resident currently cares about.

    Newest first, first non-terminal one wins. A complaint may carry several
    work orders -- a failed visit rescheduled, a reopened complaint sent to a
    different supervisor -- and all but one of them are history. Returning the
    newest *live* one rather than simply the newest keeps a cancelled retry from
    hiding the visit that replaced it.
    """
    for row in repo.list_for_complaint(client, complaint_id=complaint_id):
        if str(row.get("status") or "") in _OPEN_STATES:
            return row
    raise NotFoundError(
        "No visit has been scheduled for this complaint.",
        code="schedule_request_not_found",
    )


def get_schedule_request(client: Client, *, complaint_id: str) -> ScheduleRequest:
    """The visit proposed or booked against this complaint.

    Not only the ones awaiting an answer. A resident who has already confirmed
    still needs to see when somebody is coming and who -- and a screen that had
    to ask a second endpoint for that would show the confirmation blink out of
    existence the moment they pressed the button.
    """
    return _to_schedule_request(
        _live_work_order(client, complaint_id=complaint_id)
    )


def respond(
    client: Client, *, complaint_id: str, body: ScheduleResponseRequest
) -> ScheduleRequest:
    """Confirm or decline a proposed visit."""
    answer = (body.response or "").strip().lower()
    if answer not in _RESPONSES:
        raise ValidationError(
            "response must be 'confirmed' or 'declined'.",
            code="unknown_schedule_response",
        )

    row = _live_work_order(client, complaint_id=complaint_id)
    repo.respond_to_schedule(
        client, work_order_id=str(row["id"]), response=answer, note=body.note
    )
    return _to_schedule_request(
        _live_work_order(client, complaint_id=complaint_id)
    )
