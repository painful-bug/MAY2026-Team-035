"""Wire models for work orders: the job, its assignment, and its schedule.

**The stored vocabulary is the wire vocabulary here, and that is a decision.**
``app/domain/vocabularies.py`` exists because the frontend had already shipped
the words ``Pending`` and ``In Progress`` before the schema chose ``open`` and
``in_progress``, and neither side could move. Nothing has ever rendered a work
order, so there is no second vocabulary to reconcile -- adding a translation
table now would be inventing the divergence it exists to absorb.

Two shapes, not one. ``WorkOrder`` is a list row; ``WorkOrderDetail`` adds the
assignment history, which is several rows per job and is the difference between
"who is on this" and "who has been on this". A supervisor deciding whether to
reassign needs the second one; a queue of forty jobs does not.

The resident sees neither. ``ScheduleRequest`` is their projection and carries
what somebody deciding whether a time suits them needs -- when, where, which
department -- and not the supervisor's membership id, the skill routing or the
failed-attempt count, which are the association's business about them rather
than theirs.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.domain.common_schemas import CamelModel


class WorkOrderAssignment(CamelModel):
    """One offer of a job to one person, and what became of it."""

    id: str
    work_order_id: str
    staff_assignment_id: str | None = None
    #: ``offered`` | ``accepted`` | ``declined`` | ``withdrawn`` | ``completed``
    #: | ``failed``.
    status: str
    worker_name: str | None = None
    worker_phone_e164: str | None = None
    worker_membership_id: str | None = None
    worker_provider_id: str | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    offered_at: datetime | None = None
    responded_at: datetime | None = None
    decline_reason: str | None = None
    #: True when the dispatcher assigned this rather than a supervisor. Always
    #: false until step 5 exists; the column is here because the worker's screen
    #: reads differently for a job they were given and one they were offered.
    is_auto_assigned: bool = False
    is_forced: bool = False


class WorkOrder(CamelModel):
    """A scheduled piece of work against a complaint."""

    id: str
    community_id: str
    complaint_id: str | None = None
    complaint_title: str | None = None
    complaint_category: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    skill_id: str | None = None
    skill_name: str | None = None
    #: ``draft`` | ``awaiting_resident`` | ``offered`` | ``scheduled`` |
    #: ``in_progress`` | ``completed`` | ``failed`` | ``cancelled``.
    status: str
    #: ``low`` | ``medium`` | ``high``. Inherited from the complaint at
    #: creation, so a job's urgency and the complaint's cannot drift apart by
    #: accident.
    priority: str
    #: ``resident`` (at somebody's home, so the time needs confirming) or
    #: ``facility`` (a common area, so it does not).
    subject_kind: str
    location_text: str | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    #: When an unanswered schedule request stops being worth waiting for.
    resident_deadline_at: datetime | None = None
    failed_attempt_count: int = 0
    cancelled_reason: str | None = None
    #: The current holder: the accepted assignment, or null while nobody has it.
    assignee_name: str | None = None
    staff_assignment_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkOrderDetail(WorkOrder):
    """One job with every offer ever made on it, newest first."""

    assignments: list[WorkOrderAssignment] = Field(default_factory=list)


class Candidate(CamelModel):
    staff_assignment_id: str
    membership_id: str
    service_provider_id: str | None = None
    display_name: str
    has_adjacent_job: bool = False
    open_jobs: int = 0
    distance_km: float | None = None
    away_until: datetime | None = None
    excluded: bool = False


class _SlotFields(CamelModel):
    """Both ends of a proposed visit, or neither.

    Validated here rather than only in the RPC because ``0036`` signals a
    half-slot with ``22004``, which ``pg_errors`` maps to a 422 carrying the
    repository's generic message -- true, and no help in naming which of two
    fields is missing. The CHECK constraint stays the guarantee; this is the
    sentence.
    """

    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None

    @model_validator(mode="after")
    def _check_slot(self) -> _SlotFields:
        start, end = self.scheduled_start_at, self.scheduled_end_at
        if (start is None) != (end is None):
            raise ValueError(
                "scheduledStartAt and scheduledEndAt must be sent together."
            )
        if start is not None and end is not None and end <= start:
            raise ValueError("scheduledEndAt must be after scheduledStartAt.")
        return self


class CreateWorkOrderRequest(_SlotFields):
    """Supervisor triage: raise work against a complaint.

    **Omitting the slot is the other half of the fork**, not an incomplete
    request. A supervisor who wants to talk to the resident first creates a
    draft and keeps the conversation in ``POST /complaints/{id}/comments``;
    supplying a time is what turns the complaint into a visit.
    """

    #: Defaults to the complaint's own department. Sending one is for the case
    #: where triage is what decides who owns the complaint.
    department_id: str | None = None
    #: Defaults to the skill mapped to the complaint's category (``0034``).
    skill_id: str | None = None
    subject_kind: str = "resident"
    location_text: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=1000)


class UpdateWorkOrderRequest(CamelModel):
    """Edit what the job is. Not when it is, and not what state it is in.

    Times go through ``/reschedule`` and states through their own routes,
    because each carries a rule and a notification that a general-purpose
    ``PATCH`` is exactly the shape to skip.
    """

    skill_id: str | None = None
    subject_kind: str | None = None
    location_text: str | None = Field(default=None, max_length=500)
    priority: str | None = None


class AssignWorkOrderRequest(_SlotFields):
    """Put a named person on the job.

    The slot is optional and defaults to the job's own. Sending one assigns and
    reschedules in a single write, which is the common case: the supervisor
    picked the person and the hour at the same moment.
    """

    staff_assignment_id: str


class RescheduleWorkOrderRequest(CamelModel):
    """Move the visit. Both ends required -- this is not a partial edit."""

    scheduled_start_at: datetime
    scheduled_end_at: datetime
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check_order(self) -> RescheduleWorkOrderRequest:
        if self.scheduled_end_at <= self.scheduled_start_at:
            raise ValueError("scheduledEndAt must be after scheduledStartAt.")
        return self


class CancelWorkOrderRequest(CamelModel):
    """Call the job off."""

    #: Required, and it reaches both the worker and the resident in a
    #: notification. A cancellation nobody can explain is the one that generates
    #: the phone call this feature exists to prevent.
    reason: str = Field(..., min_length=3, max_length=500)


class ScheduleRequest(CamelModel):
    """A proposed visit, as the resident sees it."""

    work_order_id: str
    complaint_id: str | None = None
    status: str
    department_name: str | None = None
    skill_name: str | None = None
    location_text: str | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    #: When the association stops waiting for an answer and schedules anyway.
    respond_by: datetime | None = None
    #: Whether this is still waiting on them. False once they have answered, so
    #: the screen can show the outcome without re-deriving it from ``status``.
    awaiting_response: bool = False
    assignee_name: str | None = None


class ScheduleResponseRequest(CamelModel):
    """The resident's answer to a proposed visit."""

    #: ``confirmed`` or ``declined``.
    response: str
    note: str | None = Field(default=None, max_length=500)
