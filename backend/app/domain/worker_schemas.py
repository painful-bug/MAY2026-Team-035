"""Wire models for the worker portal: jobs, the calendar, and the working week.

**Two job shapes, and the split is about privacy rather than payload size.**
``WorkerJob`` is a card in a list; ``WorkerJobDetail`` adds the complaint's own
description and the resident's name, flat and phone number. A worker on their way
to a flat needs all four, and a worker scrolling a month of past jobs needs none
of them -- so the list query does not select them and the detail query does. The
same reasoning ``work_order_schemas.py`` gives for its own two shapes, applied to
a field that would be worth minimising even if it were free.

**The stored vocabulary is the wire vocabulary**, as it is for work orders and
for the same reason: nothing has ever rendered a worker's job, so there is no
shipped word to reconcile with and a translation table would be inventing the
divergence it exists to absorb.

Nothing here carries a colour. Plan D15 derives a community's colour from a hash
of its id on the client, so the same society is the same colour on every device
with no column, no migration and no setting for anybody to disagree about.
"""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import Field, model_validator

from app.domain.common_schemas import CamelModel
from app.domain.hiring_schemas import ServiceEngagement
from app.domain.service_provider_schemas import ServiceProviderProfile


class WorkerJob(CamelModel):
    """One job as it appears in the worker's list."""

    #: The assignment, not the work order. Two workers can hold two assignments
    #: on one job -- one accepted, one withdrawn -- and this is the identity of
    #: the row that belongs to the caller.
    assignment_id: str
    work_order_id: str
    staff_assignment_id: str | None = None
    #: ``offered`` | ``accepted`` | ``declined`` | ``withdrawn`` | ``completed``
    #: | ``failed``. What the *caller* did, which is not the same question as
    #: what became of the job.
    assignment_status: str
    #: ``draft`` | ``awaiting_resident`` | ``offered`` | ``scheduled`` |
    #: ``in_progress`` | ``completed`` | ``failed`` | ``cancelled``.
    work_order_status: str
    priority: str = "medium"
    #: ``resident`` (somebody's home) or ``facility`` (a common area).
    subject_kind: str = "resident"
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    offered_at: datetime | None = None
    responded_at: datetime | None = None
    decline_reason: str | None = None
    #: True when the dispatcher booked this rather than the worker accepting it.
    #: The card reads differently for a job you were given and one you took.
    is_auto_assigned: bool = False
    community_id: str
    community_name: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    department_kind: str | None = None
    complaint_id: str | None = None
    complaint_title: str | None = None
    complaint_category: str | None = None
    skill_name: str | None = None
    location_text: str | None = None
    failed_attempt_count: int = 0
    cancelled_reason: str | None = None


class WorkerJobDetail(WorkerJob):
    """One job, with what the worker needs in order to turn up at it."""

    complaint_description: str | None = None
    #: Null on a ``facility`` job, where there is no door and nobody to meet.
    resident_name: str | None = None
    resident_phone_e164: str | None = None
    resident_unit_code: str | None = None


class CalendarEntry(CamelModel):
    """One block of the worker's time, whatever it is made of.

    Jobs and leave in one list because a calendar is one list. ``kind`` is what a
    client switches on to draw them differently, and ``communityId`` is what it
    hashes for the colour -- null on leave, which belongs to the person rather
    than to any of the societies employing them.
    """

    #: ``job`` or ``unavailable``.
    kind: str
    #: The assignment id or the unavailability id, depending on ``kind``.
    id: str
    starts_at: datetime
    ends_at: datetime | None = None
    title: str
    subtitle: str | None = None
    community_id: str | None = None
    community_name: str | None = None
    #: Only on a ``job``: lets the client link straight to the detail screen.
    work_order_id: str | None = None
    status: str | None = None


class UnavailabilityBlock(CamelModel):
    """A window the worker is not available in."""

    id: str
    starts_at: datetime
    ends_at: datetime
    reason: str | None = None
    #: ``provider`` (everywhere they work) or ``roster`` (one department only).
    #: Only the first can be written through this API; the second exists for a
    #: name typed onto a roster, who has no account to write with.
    scope: str = "provider"
    department_name: str | None = None
    created_at: datetime | None = None


class CreateUnavailabilityRequest(CamelModel):
    """Mark a window unavailable, in every community that employs the caller."""

    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _check_window(self) -> CreateUnavailabilityRequest:
        if self.ends_at <= self.starts_at:
            raise ValueError("endsAt must be after startsAt.")
        return self


class AvailabilityRule(CamelModel):
    """One weekday window the worker will accept jobs in."""

    id: str | None = None
    #: 0-6 with Sunday at 0, matching Postgres ``extract(dow ...)`` -- which is
    #: what ``dispatch_candidates`` compares against, so the two cannot drift.
    weekday: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    effective_from: date | None = None
    effective_to: date | None = None
    scope: str = "provider"
    department_name: str | None = None

    @model_validator(mode="after")
    def _check_window(self) -> AvailabilityRule:
        if self.end_time <= self.start_time:
            raise ValueError("endTime must be after startTime.")
        return self


class SetAvailabilityRulesRequest(CamelModel):
    """Replace the whole working week.

    **A ``PUT`` of the set, not add and remove**, for the reason
    ``PUT /service-providers/me/skills`` gives: the screen is a week with seven
    rows on it, and two tabs editing different days against a delta API is a lost
    update nobody notices until somebody is booked on their day off.

    An empty list is legal and means *always available*, which is what having
    never filled the form in already meant to ``dispatch_candidates``.
    """

    rules: list[AvailabilityRule] = Field(default_factory=list, max_length=50)


class DeclineJobRequest(CamelModel):
    """Say no to an offer."""

    #: Optional, unlike the reason on a failed visit. A worker declining an offer
    #: owes nobody an explanation -- they were asked, and the honest answers are
    #: often "I am not free" -- while a worker who went and could not do the work
    #: is reporting something the next person has to act on.
    reason: str | None = Field(default=None, max_length=300)


class CompleteJobRequest(CamelModel):
    """The work is done."""

    #: Reaches the resident in the completion notification, so it is written to
    #: be read by them rather than filed.
    notes: str | None = Field(default=None, max_length=1000)


class ReportJobFailureRequest(CamelModel):
    """The visit did not happen."""

    #: Required. *"Could not be done"* with no reason is the report that
    #: guarantees a second wasted visit: nobody downstream can tell "nobody was
    #: home" from "the part is out of stock", and those need opposite responses.
    reason: str = Field(..., min_length=3, max_length=500)


class WorkerSnapshot(CamelModel):
    """Everything the worker's dashboard renders, in one call.

    **``provider`` being null is the whole empty state.** A caller who has never
    registered is sent to the registration form; a registered caller with no
    ``communities`` is sent to the community search. Both are answered by this one
    request rather than by a client trying two endpoints and interpreting a 404.

    There is no unread-message count, although the dashboard has a messages tab.
    Conversations shipped with no read receipts on purpose (`0038`), so there is
    nothing to count -- and inventing a count here would mean inventing the
    receipts underneath it.
    """

    provider: ServiceProviderProfile | None = None
    #: Every roster the caller is on, across every community.
    communities: list[ServiceEngagement] = Field(default_factory=list)
    #: Offers waiting on an answer, soonest first. The queue the dashboard opens
    #: on.
    pending_offers: list[WorkerJob] = Field(default_factory=list)
    #: Jobs whose slot starts today, in the server's timezone.
    today: list[WorkerJob] = Field(default_factory=list)
    #: The next accepted job from now, which is not always the first of
    #: ``today``: at six in the evening today's list is history.
    next_job: WorkerJob | None = None
    #: Accepted and not yet finished, however far out.
    open_job_count: int = 0
    #: The offline toggle, echoed here so the dashboard's switch does not need a
    #: second read to know which way to draw itself.
    is_available: bool = True
    #: Across every community the caller belongs to -- the one place the
    #: multi-membership seam is visible to a user.
    unread_notifications: int = 0
    generated_at: datetime | None = None
