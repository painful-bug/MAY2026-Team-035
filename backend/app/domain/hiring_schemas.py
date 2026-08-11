"""Wire models for hiring: applications, invitations, candidates, engagements.

One negotiation is one shape on the wire, whichever end is looking at it. A
manager's inbox row and a provider's applications row are the same
``ServiceApplication`` -- the database serves both from one view for the same
reason (``0035`` 5), and two projections would only be two places for the two
sides to describe one negotiation differently.

``direction`` is what tells a client which buttons to render: an ``applied`` row
is answered by the department and withdrawn by the provider, an ``invited`` row
the other way round. Deriving that from the caller's role would need the client
to know its own role in each community it is looking at, which is exactly the
thing a cross-community screen does not have.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.domain.common_schemas import CamelModel
from app.domain.department_schemas import StaffMember


class ServiceApplication(CamelModel):
    """One negotiation between a department and a service person."""

    id: str
    community_id: str
    community_name: str | None = None
    department_id: str
    department_name: str | None = None
    department_kind: str | None = None
    service_provider_id: str
    provider_display_name: str | None = None
    provider_headline: str | None = None
    provider_phone_e164: str | None = None
    provider_skill_names: list[str] = Field(default_factory=list)
    #: ``applied`` (the provider opened it) or ``invited`` (the department did).
    direction: str
    #: ``pending`` | ``accepted`` | ``rejected`` | ``withdrawn`` | ``expired``.
    status: str
    message: str | None = None
    #: The terms on offer. Null on an application until somebody decides it.
    rank: str | None = None
    job_title: str | None = None
    shift: str | None = None
    decision_note: str | None = None
    decided_at: datetime | None = None
    #: Straight-line kilometres between the provider and the community.
    #: Proximity search excludes rows without the coordinates needed to compute it.
    distance_km: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApplyRequest(CamelModel):
    """A provider applying to one department."""

    department_id: str
    message: str | None = Field(default=None, max_length=2000)


class InviteRequest(CamelModel):
    """A manager inviting one provider, with the terms on offer."""

    service_provider_id: str
    message: str | None = Field(default=None, max_length=2000)
    #: ``manager`` | ``supervisor`` | ``member``. The stored vocabulary; the
    #: department's ``head`` is the person holding ``manager``.
    rank: str = "member"
    job_title: str | None = Field(default=None, max_length=120)
    shift: str | None = Field(default=None, max_length=40)


class DecideApplicationRequest(CamelModel):
    """Answer a pending negotiation.

    The terms are accepted here rather than supplied at application time,
    because on an application nobody has offered any yet -- the manager names
    them at the moment they say yes. On an *invitation* they are already in the
    row and this request cannot change them: a provider accepting cannot promote
    themselves by sending ``rank``.
    """

    #: ``accepted`` or ``rejected``.
    decision: str
    rank: str | None = None
    job_title: str | None = Field(default=None, max_length=120)
    shift: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=500)


class ProviderDecisionRequest(CamelModel):
    """A professional accepting or declining an invitation; terms are read-only."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["accepted", "rejected"]
    note: str | None = Field(default=None, max_length=500)


class HireableProvider(CamelModel):
    """A service person this department could hire, with why they match."""

    id: str
    display_name: str
    headline: str | None = None
    phone_e164: str | None = None
    status: str
    is_available: bool = True
    service_radius_km: float | None = None
    distance_km: float | None = None
    #: The subset of their trades this department's categories actually need.
    #: Separate from ``skillNames`` because the reason a candidate is on this
    #: list is not the same as everything they can do.
    matching_skill_names: list[str] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)
    community_count: int = 0
    #: True when a negotiation with this department is already open, so the
    #: screen offers "view" instead of a second invitation the unique index
    #: would refuse.
    has_open_application: bool = False


class DepartureItem(CamelModel):
    """One thing still booked in a departing person's name.

    Jobs and shifts in one shape, because a handover works through one list. The
    two are told apart by ``kind`` and not by which array they arrived in: a
    department that runs both would otherwise need a screen that knew, in
    advance, which halves of the list it was going to get.
    """

    #: ``work_order`` or ``security_shift``.
    kind: str
    #: The row to hand over — a ``work_order_assignments`` id or a
    #: ``security_shifts`` id. What ``POST .../reassign`` takes.
    item_id: str
    #: The work order behind an assignment, or the post behind a shift. For
    #: display and for linking; never for reassignment.
    reference_id: str | None = None
    title: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str


class CoverageItem(DepartureItem):
    """One conflicting item with who could take it.

    The manager's match button. ``candidateCount`` of zero **is** the answer
    "there are none" — it renders as a statement, not an error. Names are
    capped at the dispatch ranking's top five.
    """

    candidate_count: int = 0
    candidate_names: list[str] = Field(default_factory=list)


class ScheduleItem(DepartureItem):
    """One entry on an employee's schedule.

    Same shape as a handover item on purpose — a job is a job whichever list
    it appears in — but the query behind it keeps finished work, because a
    schedule page shows what happened, not only what looms.
    """


class StaffDeparture(CamelModel):
    """A request to leave a department roster."""

    id: str
    community_id: str
    department_id: str
    department_name: str | None = None
    department_kind: str | None = None
    staff_assignment_id: str
    service_provider_id: str | None = None
    membership_id: str | None = None
    display_name: str | None = None
    rank: str | None = None
    job_title: str | None = None
    #: ``worker`` when the person leaving opened it, ``manager`` when somebody
    #: opened it on their behalf. Their own row makes it a resignation even when
    #: the person pressing the button also manages the department.
    initiated_by: str
    #: ``pending`` | ``approved`` | ``rejected`` | ``cancelled``. There is no
    #: ``handover`` — that state is ``pending`` with a non-zero
    #: ``openCommitmentCount``.
    status: str
    reason: str | None = None
    #: When the worker wants to stop. Null means immediately.
    requested_effective_at: datetime | None = None
    #: When the manager decided they stop. Stamped at approval; the timekeeper
    #: removes them at this moment.
    effective_at: datetime | None = None
    decision_note: str | None = None
    decided_at: datetime | None = None
    #: Everything still booked in their name, dateless. Since the 2026-08-10
    #: ruling this no longer gates approval — it is what the roster tab shows.
    open_commitment_count: int = 0
    #: What the leave would actually strand: items from the requested (or
    #: decided) effective date onward, plus unscheduled ones. What approval
    #: releases to the pool, and what the manager's coverage check examines.
    conflict_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StaffDepartureDetail(StaffDeparture):
    """One departure with the handover list itself."""

    items: list[DepartureItem] = Field(default_factory=list)


class StaffMemberDetail(StaffMember):
    """One employee, as the employee page sees them.

    The roster row the tab already renders, plus the departure heading its way
    — pending, or approved for a date that has not arrived. The schedule is a
    separate windowed read (`GET .../schedule`) rather than a field here,
    because a calendar refetches when the window moves and the identity card
    does not.
    """

    departure: StaffDeparture | None = None


class RequestDepartureRequest(CamelModel):
    """Open a departure, from either side."""

    #: Only on the manager's route. The worker's route names their own roster
    #: row in the path, because they may hold several.
    staff_id: str | None = None
    reason: str | None = Field(default=None, max_length=500)
    #: When they want to stop. Omit for immediately; a past date is a `422`.
    effective_at: datetime | None = None


class DecideDepartureRequest(CamelModel):
    """Approve or reject a departure.

    Approving picks the leave date: the requested one when ``effectiveAt`` is
    omitted, or a later one at the manager's discretion. Booked work from that
    date onward is released back to the dispatch pool at queue priority 1.
    (Until 2026-08-10 approval was refused while anything was booked — that
    rule is overturned; the decision is the manager's, the pool absorbs.)
    """

    #: ``approve`` or ``reject``.
    decision: str
    note: str | None = Field(default=None, max_length=500)
    #: The manager's leave date. Omitted = the requested date, or now.
    effective_at: datetime | None = None


class ReassignItemRequest(CamelModel):
    """Move one job or shift off a departing person.

    Omitting ``staffAssignmentId`` is the ordinary case and means *take the best
    candidate the dispatch ranking returns* — the same ranking auto-assignment
    uses, which is what the product owner asked for. Naming one is the override
    for when a manager knows something the ranking does not.
    """

    #: ``work_order`` or ``security_shift``.
    kind: str
    item_id: str
    staff_assignment_id: str | None = None


class ServiceEngagement(CamelModel):
    """One community a service person works in."""

    staff_assignment_id: str
    community_id: str
    community_name: str | None = None
    community_city: str | None = None
    department_id: str
    department_name: str | None = None
    department_kind: str | None = None
    membership_id: str | None = None
    membership_role: str | None = None
    rank: str
    job_title: str | None = None
    shift: str | None = None
    status: str
    started_at: date | None = None
    ended_at: date | None = None
    #: The open departure on this roster row, when there is one. Carried on the
    #: engagement rather than fetched per row, because the worker's screen shows
    #: one card per community and needs to know on every one of them whether the
    #: leave button says "request" or "withdraw".
    departure: StaffDeparture | None = None


class DepartmentRef(CamelModel):
    """A department the caller could apply to, named and addressable."""

    id: str
    name: str


class ServiceableCommunity(CamelModel):
    """A community that needs one of the caller's trades and has not barred them."""

    id: str
    name: str
    city: str | None = None
    state: str | None = None
    community_type: str | None = None
    distance_km: float | None = None
    matching_skill_names: list[str] = Field(default_factory=list)
    #: Ids as well as names, because ``POST /worker/applications`` takes a
    #: ``departmentId`` and there is no other route to one: a provider who is
    #: not yet a member cannot read ``GET /departments``. Names alone made this
    #: a search result nobody could act on.
    departments: list[DepartmentRef] = Field(default_factory=list)


class BlacklistRequest(CamelModel):
    """Bar a provider from the whole community, not just this department."""

    service_provider_id: str
    #: Required, and stored. A bar with no stated reason cannot be reviewed
    #: later by whoever has to decide whether to revoke it.
    reason: str = Field(..., min_length=3, max_length=500)


class RemoveMemberRequest(CamelModel):
    """Take someone off a roster. Reapplication stays open."""

    reason: str | None = Field(default=None, max_length=500)
