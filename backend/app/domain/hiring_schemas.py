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


# ---------------------------------------------------------------------------
# A hired service person is always a ``member``, and there is no shift.
#
# Both models below used to carry ``rank`` and ``shift``. A product-owner
# ruling on 2026-08-11 removed them from this path:
#
#   "the only people added from servicemen are technicians (member). no
#    supervisors or managers are hired this way. there is no shift or anything.
#    there is no shift system. job assignment is only on demand as the auto
#    assign or supervisor does."
#
# The two halves of that are separate facts and both are load-bearing:
#
# * **Rank.** Leadership does not come from the hiring path at all -- an admin
#   or a manager creates a manager or a supervisor by email
#   (``staff_invitations``, ``0049``), and that person never registered as a
#   service provider. Somebody hired *here* registered themselves and applied,
#   and they join as a ``member``. A promotion afterwards is
#   ``PATCH /departments/{id}/staff/{staffId}``, which is a different decision
#   with a different guard.
#
# * **Shift.** ``staff_assignments.shift`` is a descriptive text column from
#   ``0019``'s typed-roster era. **Nothing schedules from it** -- work reaches a
#   worker through the dispatch sweep (``0037``) or a supervisor's assignment,
#   and a guard's actual rota is ``security_shifts`` (``0040``), a different
#   table with real timestamps. Collecting a word like "Day" at hire time
#   described nothing and was read by nothing.
#
# The column and ``0035``'s ``p_rank``/``p_shift`` parameters both stay -- this
# is a narrowing of what the API accepts, not a schema change, and it needed no
# migration because ``decide_service_application`` already defaults an omitted
# rank to ``member`` and leaves an omitted shift null.
# ---------------------------------------------------------------------------


class InviteRequest(CamelModel):
    """A manager inviting one provider onto the roster.

    ``jobTitle`` is the only term on offer, and it is free text with
    suggestions rather than a closed list -- ``staff_assignments.job_title`` has
    no check constraint, so a society with a lift technician or a pool attendant
    can say so without a migration.
    """

    service_provider_id: str
    message: str | None = Field(default=None, max_length=2000)
    job_title: str | None = Field(default=None, max_length=120)


class DecideApplicationRequest(CamelModel):
    """Answer a pending negotiation.

    ``jobTitle`` is supplied here rather than at application time, because on an
    application nobody has offered anything yet -- the manager names it at the
    moment they say yes. On an *invitation* it is already in the row and this
    request cannot change it.
    """

    #: ``accepted`` or ``rejected``.
    decision: str
    job_title: str | None = Field(default=None, max_length=120)
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


class StaffInvitation(CamelModel):
    """A manager or supervisor created but not yet signed in.

    **There is no token and no code.** Leadership has no registration flow: an
    administrator types a name and an email, and that person is admitted the
    first time they sign in with that address. The trade-off -- one factor, and
    whoever holds the mailbox becomes the manager -- is stated in ``0049``'s
    header and in ``docs/design/STAFF_PROVISIONING_DESIGN.md`` rather than
    softened. The resident invite's mandatory token is untouched; this is a
    separate table for exactly that reason.

    ``rank`` is ``manager`` or ``supervisor`` only. ``member`` is absent because
    that rank is reached solely by hiring a registered service provider.
    """

    id: str
    department_id: str
    email: str
    name: str
    phone: str | None = None
    rank: str
    job_title: str | None = None
    #: ``pending`` | ``claimed`` | ``revoked``.
    status: str
    #: When they first signed in. Null until they do.
    claimed_at: datetime | None = None
    created_at: datetime


class InviteStaffRequest(CamelModel):
    """Create a manager or a supervisor.

    ``email`` is required and is the whole mechanism: it is what the person's
    Google sign-in is matched against. A typo here does not fail loudly -- it
    produces an invitation nobody can claim -- which is why the department
    screen shows pending invitations rather than assuming they land.
    """

    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)
    #: A closed set on the wire, not just in the RPC. Two values, and both are
    #: refused by `staff_invitations_rank_check` if they ever disagree -- but a
    #: 422 from the schema tells the form which words are legal, where a round
    #: trip to Postgres only tells it that this one was not.
    rank: Literal["manager", "supervisor"]
    phone: str | None = Field(None, max_length=32)
    job_title: str | None = Field(None, max_length=60)


class UpdateStaffInvitationRequest(CamelModel):
    """Correct an unclaimed invitation.

    This is the answer the product owner gave on 2026-08-12 to the one way a
    single-factor invitation fails: the admin mistypes the address, nobody can
    claim it, and nothing tells anybody. Rather than add a second factor, the
    mistake is made correctable once the pending list makes it visible.

    **Every field is optional and ``None`` means "leave it alone".** A form that
    patches only the email cannot blank the job title by not sending it. The two
    nullable fields accept ``""`` as "clear this"; ``email``, ``name`` and
    ``rank`` have no clear, because an invitation without them binds nothing,
    names nobody, or admits at no rank.

    ``rank`` is editable for the same reason ``email`` is -- choosing
    *supervisor* when you meant *manager* is a keyboard mistake of exactly the
    same kind. The **department is not**, and its absence here is load-bearing:
    it is what ``can_manage_department`` authorizes against, so a move would let
    the manager of one department mint staff into another. That is
    revoke-and-reissue, under the authority of wherever it is going.
    """

    email: str | None = Field(None, min_length=3, max_length=254)
    name: str | None = Field(None, min_length=1, max_length=120)
    rank: Literal["manager", "supervisor"] | None = None
    phone: str | None = Field(None, max_length=32)
    job_title: str | None = Field(None, max_length=60)
