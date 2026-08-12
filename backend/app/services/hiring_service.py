"""Hiring: applying, inviting, deciding, removing, barring.

Step 2 of ``docs/plans/SERVICE_OPERATIONS_PLAN.md``, and one sentence is the
whole of what it has to get right: **accepting creates a membership and a roster
row atomically.** That happens in ``decide_service_application`` (``0035`` 7),
not here -- this module translates vocabulary, decides what a caller is asking
for, and turns a row into a DTO.

Two functions serve both sides of a negotiation, which mirrors the one table and
the one view underneath. ``decide`` is called by a manager answering an
application and by a provider answering an invitation; the RPC works out which
of them is entitled to answer this particular row from its ``direction``, and
that check lives there rather than here because it is an authorization decision
and authorization decisions belong next to the data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.hiring_schemas import (
    ApplyRequest,
    BlacklistRequest,
    CoverageItem,
    DecideApplicationRequest,
    DecideDepartureRequest,
    DepartmentRef,
    DepartureItem,
    HireableProvider,
    InviteRequest,
    InviteStaffRequest,
    ReassignItemRequest,
    RemoveMemberRequest,
    ScheduleItem,
    ServiceableCommunity,
    ServiceApplication,
    ServiceEngagement,
    StaffDeparture,
    StaffDepartureDetail,
    StaffInvitation,
    StaffMemberDetail,
    UpdateStaffInvitationRequest,
)
from app.repositories import hiring_repository as repo
from app.repositories import service_providers_repository as providers_repo

# One definition of how a roster row becomes a wire shape. The employee page
# renders the same row the roster tab does; a second mapping here would be the
# two-lists-that-drift problem the staff vocabulary already taught us about.
from app.services.departments_service import _to_staff as _to_staff_member
from supabase import Client

#: There is no rank vocabulary here any more.
#:
#: ``_RANK_TO_STORAGE`` mapped the wire words -- including ``head``, the
#: department screens' name for the person holding ``manager`` -- onto the
#: stored three. Both callers stopped sending a rank on 2026-08-11 (see
#: ``InviteRequest``), so the table and its lookup were deleted rather than left
#: as an unreachable translation somebody would later trust. The stored
#: vocabulary itself is unchanged and still lives in the check constraint on
#: ``staff_assignments.rank``.

#: What a decision endpoint accepts. ``withdrawn`` is deliberately absent: it is
#: reached by ``DELETE``, because withdrawing is retracting your own request and
#: not answering somebody else's.
_DECISIONS = ("accepted", "rejected")

#: A departure is approved or rejected. Not the same words as ``_DECISIONS``,
#: and deliberately: an application ends up in a *state* (``accepted``), while a
#: departure is an *act* somebody performs (``approve``). Sharing one vocabulary
#: between the two would mean one of them was named for the other's grammar.
_DEPARTURE_DECISIONS = ("approve", "reject")

#: The two things a handover can move. Validated here so a typo comes back as a
#: 422 naming both, rather than as a 422 from the RPC's own ``22P02``.
_ITEM_KINDS = ("work_order", "security_shift")


def _text(value: object) -> str | None:
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _names(value: object) -> list[str]:
    return [str(item) for item in (value or [])]


def _departments(value: object) -> list[DepartmentRef]:
    """The search's ``departments`` jsonb, which arrives already decoded."""
    return [
        DepartmentRef(id=str(item["id"]), name=str(item.get("name") or ""))
        for item in (value or [])
        if isinstance(item, dict) and item.get("id")
    ]


def _number(value: object) -> float | None:
    return None if value is None else float(value)


def _to_application(row: dict[str, Any]) -> ServiceApplication:
    return ServiceApplication(
        id=row["id"],
        community_id=row["community_id"],
        community_name=_text(row.get("community_name")),
        department_id=row["department_id"],
        department_name=_text(row.get("department_name")),
        department_kind=_text(row.get("department_kind")),
        service_provider_id=row["service_provider_id"],
        provider_display_name=_text(row.get("provider_display_name")),
        provider_headline=_text(row.get("provider_headline")),
        provider_phone_e164=_text(row.get("provider_phone_e164")),
        provider_skill_names=_names(row.get("provider_skill_names")),
        direction=str(row.get("direction") or "applied"),
        status=str(row.get("status") or "pending"),
        message=_text(row.get("message")),
        rank=_text(row.get("rank")),
        job_title=_text(row.get("job_title")),
        shift=_text(row.get("shift")),
        decision_note=_text(row.get("decision_note")),
        decided_at=row.get("decided_at"),
        distance_km=_number(row.get("distance_km")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _to_candidate(row: dict[str, Any]) -> HireableProvider:
    return HireableProvider(
        id=row["id"],
        display_name=str(row.get("display_name") or ""),
        headline=_text(row.get("headline")),
        phone_e164=_text(row.get("phone_e164")),
        status=str(row.get("status") or "active"),
        is_available=bool(row.get("is_available")),
        service_radius_km=_number(row.get("service_radius_km")),
        distance_km=_number(row.get("distance_km")),
        matching_skill_names=_names(row.get("matching_skill_names")),
        skill_names=_names(row.get("skill_names")),
        community_count=int(row.get("community_count") or 0),
        has_open_application=bool(row.get("has_open_application")),
    )


def _to_engagement(row: dict[str, Any]) -> ServiceEngagement:
    return ServiceEngagement(
        staff_assignment_id=row["staff_assignment_id"],
        community_id=row["community_id"],
        community_name=_text(row.get("community_name")),
        community_city=_text(row.get("community_city")),
        department_id=row["department_id"],
        department_name=_text(row.get("department_name")),
        department_kind=_text(row.get("department_kind")),
        membership_id=_text(row.get("membership_id")),
        membership_role=_text(row.get("membership_role")),
        rank=str(row.get("rank") or "member"),
        job_title=_text(row.get("job_title")),
        shift=_text(row.get("shift")),
        status=str(row.get("status") or "active"),
        started_at=row.get("started_at"),
        ended_at=row.get("ended_at"),
    )


def _to_departure(row: dict[str, Any]) -> StaffDeparture:
    return StaffDeparture(
        id=row["id"],
        community_id=row["community_id"],
        department_id=row["department_id"],
        department_name=_text(row.get("department_name")),
        department_kind=_text(row.get("department_kind")),
        staff_assignment_id=row["staff_assignment_id"],
        service_provider_id=_text(row.get("service_provider_id")),
        membership_id=_text(row.get("membership_id")),
        display_name=_text(row.get("display_name")),
        rank=_text(row.get("rank")),
        job_title=_text(row.get("job_title")),
        initiated_by=str(row.get("initiated_by") or "worker"),
        status=str(row.get("status") or "pending"),
        reason=_text(row.get("reason")),
        requested_effective_at=row.get("requested_effective_at"),
        effective_at=row.get("effective_at"),
        decision_note=_text(row.get("decision_note")),
        decided_at=row.get("decided_at"),
        open_commitment_count=int(row.get("open_commitment_count") or 0),
        conflict_count=int(row.get("conflict_count") or 0),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _to_item(row: dict[str, Any]) -> DepartureItem:
    return DepartureItem(
        kind=str(row.get("item_kind") or ""),
        item_id=row["item_id"],
        reference_id=_text(row.get("reference_id")),
        title=str(row.get("title") or "Scheduled work"),
        starts_at=row.get("starts_at"),
        ends_at=row.get("ends_at"),
        status=str(row.get("item_status") or ""),
    )


def _my_provider_id(client: Client, *, profile_id: str) -> str:
    """The caller's own ``service_providers`` id, or 404.

    Resolved here rather than injected as a dependency because only the
    provider-side routes need it, and a dependency would read the row on every
    request whether or not the handler used it. See journal 4.4 -- the same
    call that kept ``worker_deps.py`` out of Step 1.
    """
    row = providers_repo.get_by_profile(client, profile_id=profile_id)
    if row is None:
        raise NotFoundError(
            "You have not registered as a service provider.",
            code="service_provider_not_found",
        )
    return str(row["id"])


# ---------------------------------------------------------------------------
# The provider's side
# ---------------------------------------------------------------------------


def search_communities(
    client: Client, *, query: str | None, limit: int, offset: int
) -> list[ServiceableCommunity]:
    """Communities that need one of the caller's trades, nearest first."""
    return [
        ServiceableCommunity(
            id=row["id"],
            name=str(row.get("name") or ""),
            city=_text(row.get("city")),
            state=_text(row.get("state")),
            community_type=_text(row.get("community_type")),
            distance_km=_number(row.get("distance_km")),
            matching_skill_names=_names(row.get("matching_skill_names")),
            departments=_departments(row.get("departments")),
        )
        for row in repo.search_communities(
            client, query=query, limit=limit, offset=offset
        )
    ]


def list_my_engagements(
    client: Client, *, profile_id: str, active_only: bool
) -> list[ServiceEngagement]:
    """Every community that employs the caller.

    A list rather than a single value, and that is the whole reason
    ``MembershipSet`` exists: a service person hired by three societies has three
    memberships and one calendar.
    """
    provider_id = _my_provider_id(client, profile_id=profile_id)
    engagements = [
        _to_engagement(row)
        for row in repo.list_engagements(
            client, service_provider_id=provider_id, active_only=active_only
        )
    ]

    # One extra read, not one per card. The alternative was widening
    # ``service_engagement_overview`` with a handover count, which would make
    # every reader of that view pay for a number only this screen wants.
    open_by_staff = {
        str(row["staff_assignment_id"]): _to_departure(row)
        for row in repo.departures_for_staff(
            client,
            staff_ids=[e.staff_assignment_id for e in engagements],
            status="pending",
        )
    }
    for engagement in engagements:
        engagement.departure = open_by_staff.get(engagement.staff_assignment_id)
    return engagements


def request_my_departure(
    client: Client,
    *,
    profile_id: str,
    staff_id: str,
    reason: str | None,
    effective_at: datetime | None = None,
) -> StaffDeparture:
    """Ask to leave one community, immediately or on a date.

    The roster row is named in the path rather than derived from the caller,
    because a service person hired by three societies is leaving exactly one of
    them and there is nothing in the session that says which. ``0043``'s RPC
    checks that the row is in fact theirs; ``0045`` added the date, and a past
    one comes back `422`.
    """
    _my_provider_id(client, profile_id=profile_id)
    departure_id = repo.request_departure(
        client,
        staff_id=staff_id,
        reason=reason,
        effective_at=effective_at.isoformat() if effective_at else None,
    )
    return _read_departure(client, departure_id=departure_id)


def cancel_my_departure(
    client: Client, *, profile_id: str, staff_id: str
) -> None:
    """Change your mind, and lift the freeze.

    Addressed by roster row rather than by departure id, because the screen that
    calls this is showing a community card and not a request: making it carry
    the id would mean the *cancel* button needed a read the *request* button
    did not.
    """
    _my_provider_id(client, profile_id=profile_id)
    rows = repo.departures_for_staff(client, staff_ids=[staff_id], status="pending")
    if not rows:
        raise NotFoundError(
            "You have no open request to leave that community.",
            code="departure_not_found",
        )
    repo.cancel_departure(client, departure_id=str(rows[0]["id"]))


def list_my_applications(
    client: Client, *, profile_id: str, status: str | None
) -> list[ServiceApplication]:
    """The caller's own negotiations, across every community."""
    provider_id = _my_provider_id(client, profile_id=profile_id)
    return [
        _to_application(row)
        for row in repo.list_applications_for_provider(
            client, service_provider_id=provider_id, status=status
        )
    ]


def apply(
    client: Client, *, profile_id: str, body: ApplyRequest
) -> ServiceApplication:
    """Apply to one department.

    ``profile_id`` is not passed to the RPC -- it resolves the provider from
    ``auth.uid()`` itself. It is taken here so the read-back is scoped to the
    caller rather than trusting the id the RPC returned to belong to them.
    """
    application_id = repo.apply_to_department(
        client, department_id=body.department_id, message=body.message
    )
    return _read_back(client, application_id=application_id)


def withdraw(
    client: Client, *, profile_id: str, application_id: str
) -> ServiceApplication:
    """Retract an application the caller opened.

    Same RPC as a decision, with ``withdrawn``. The RPC refuses a withdrawal from
    the side that did not open the negotiation, so a manager cannot make an
    application disappear by calling it withdrawn instead of rejected -- the
    rejection is a record, and this would erase it.
    """
    repo.decide_application(
        client, application_id=application_id, decision="withdrawn"
    )
    return _read_back(client, application_id=application_id)


# ---------------------------------------------------------------------------
# The department's side
# ---------------------------------------------------------------------------


def list_department_applications(
    client: Client, *, department_id: str, status: str | None
) -> list[ServiceApplication]:
    """The department's inbox: applications received and invitations sent."""
    return [
        _to_application(row)
        for row in repo.list_applications_for_department(
            client, department_id=department_id, status=status
        )
    ]


def search_candidates(
    client: Client,
    *,
    department_id: str,
    query: str | None,
    limit: int,
    offset: int,
) -> list[HireableProvider]:
    """Service people this department could hire, nearest first."""
    return [
        _to_candidate(row)
        for row in repo.search_candidates(
            client,
            department_id=department_id,
            query=query,
            limit=limit,
            offset=offset,
        )
    ]


def invite(
    client: Client, *, department_id: str, body: InviteRequest
) -> ServiceApplication:
    """Invite one provider onto this department's roster, as a ``member``.

    The rank is a constant rather than a parameter, per the 2026-08-11 ruling
    recorded on ``InviteRequest``: leadership is provisioned by email
    (``staff_invitations``), and somebody who registered as a service provider
    and is being offered work joins as a team member. ``p_rank`` is still
    passed explicitly rather than left to the RPC's default, so the value this
    layer intends is visible at the call site.
    """
    application_id = repo.invite_provider(
        client,
        department_id=department_id,
        service_provider_id=body.service_provider_id,
        message=body.message,
        rank="member",
        job_title=body.job_title,
        shift=None,
    )
    return _read_back(client, application_id=application_id)


def decide(
    client: Client, *, application_id: str, body: DecideApplicationRequest
) -> ServiceApplication:
    """Accept or reject a pending negotiation.

    Called by both sides. Which of them may answer *this* row is decided by the
    RPC from the row's ``direction``, and a caller on the wrong side gets a 403
    from Postgres rather than a check duplicated here that could drift from it.
    """
    decision = (body.decision or "").strip().lower()
    if decision not in _DECISIONS:
        raise ValidationError(
            "decision must be 'accepted' or 'rejected'.", code="unknown_decision"
        )

    # Rank and shift are not sent, and the RPC's own defaults are what fills
    # them: an omitted rank becomes `member`, an omitted shift stays null. See
    # `InviteRequest` for the ruling. Passing `None` rather than `"member"`
    # here -- unlike `invite` above -- because on an *invitation* the row
    # already carries terms and `coalesce(p_rank, v_app.rank, 'member')` must
    # be allowed to fall through to them.
    repo.decide_application(
        client,
        application_id=application_id,
        decision=decision,
        rank=None,
        job_title=body.job_title,
        shift=None,
        note=body.note,
    )
    return _read_back(client, application_id=application_id)


def remove_member(
    client: Client, *, staff_id: str, body: RemoveMemberRequest
) -> None:
    """Take someone off the roster and end their membership.

    Deactivates rather than deletes (``0019`` A7): complaints record staff by
    name, so a deleted roster row turns a past assignment into an unexplained
    string. Reapplication stays open -- that is the difference between this and
    blacklisting.

    **Refused with a 409 while anything is still booked in their name**
    (``0043`` 9). This route stays the one-click answer for the ordinary case --
    a name typed into the department form by mistake, somebody never dispatched
    -- and everybody else goes through a departure, which is what the count on
    the roster row is for.
    """
    repo.remove_member(client, staff_id=staff_id, reason=body.reason)


def blacklist(client: Client, *, department_id: str, body: BlacklistRequest) -> None:
    """Remove and bar, for the whole community.

    Community-wide and not per-department, because a community that will not
    have somebody back has decided that about the community; letting them
    reapply to the department next door would make the decision meaningless.
    Reversible -- ``blacklisted_service_providers`` carries ``revoked_at``.
    """
    repo.blacklist_provider(
        client,
        department_id=department_id,
        service_provider_id=body.service_provider_id,
        reason=body.reason,
    )


# ---------------------------------------------------------------------------
# Departures — the same two sides, one process
#
# The manager's four verbs. The worker's two live above, beside their
# engagements, because that is the screen they belong to.
# ---------------------------------------------------------------------------


def list_departures(
    client: Client, *, department_id: str, status: str | None
) -> list[StaffDeparture]:
    """This department's departures, newest first."""
    return [
        _to_departure(row)
        for row in repo.list_departures(
            client, department_id=department_id, status=status
        )
    ]


def get_departure(
    client: Client, *, service_client: Client, departure_id: str
) -> StaffDepartureDetail:
    """One departure with its handover list.

    **Two clients, on purpose.** The departure is read with the caller's own
    client, so the RLS policy decides whether they may see it at all; only then
    is the item list read with the service client, because
    ``staff_departure_items`` returns complaint titles and post names and is
    ``service_role`` only. The order is the authorisation: no items are read for
    a departure the caller could not see.
    """
    row = repo.get_departure(client, departure_id=departure_id)
    if row is None:
        raise NotFoundError("No such departure.", code="departure_not_found")

    departure = _to_departure(row)
    items = [
        _to_item(item)
        for item in repo.departure_items(
            service_client, staff_id=departure.staff_assignment_id
        )
    ]
    return StaffDepartureDetail(**departure.model_dump(), items=items)


def open_departure(
    client: Client,
    *,
    staff_id: str,
    reason: str | None,
    effective_at: datetime | None = None,
) -> StaffDeparture:
    """Start a departure for somebody on the roster.

    The manager's half of the same RPC the worker calls. Which of them opened it
    is recorded on the row, not inferred later from who decided it.
    """
    departure_id = repo.request_departure(
        client,
        staff_id=staff_id,
        reason=reason,
        effective_at=effective_at.isoformat() if effective_at else None,
    )
    return _read_departure(client, departure_id=departure_id)


def reassign_item(
    client: Client, *, departure_id: str, body: ReassignItemRequest
) -> None:
    """Move one job or shift off the departing person.

    Nothing is returned, because the interesting result is the *list* the caller
    is going to re-read anyway — and because an item that was an offer rather
    than a booking has no successor to report: nobody had accepted it, so it is
    withdrawn and the dispatch ping re-armed. Naming a successor for a question
    nobody answered would quietly turn it into a booking.
    """
    kind = str(body.kind or "").strip().lower()
    if kind not in _ITEM_KINDS:
        raise ValidationError(
            "A handover item is a work_order or a security_shift.",
            code="invalid_item_kind",
        )
    repo.reassign_item(
        client,
        departure_id=departure_id,
        kind=kind,
        item_id=body.item_id,
        staff_assignment_id=body.staff_assignment_id,
    )
    return None


def decide_departure(
    client: Client, *, departure_id: str, body: DecideDepartureRequest
) -> StaffDeparture:
    """Approve — at the requested date or a later one — or reject.

    ``0043`` refused approval while anything was booked; the 2026-08-10 ruling
    overturned that. Approval now releases booked work from the effective date
    onward back to the dispatch pool at queue priority 1, and either removes
    the person now (immediate) or arms the timekeeper (dated). The per-item
    hand-over stays available *before* the decision; it is no longer a
    precondition of it.
    """
    decision = str(body.decision or "").strip().lower()
    if decision not in _DEPARTURE_DECISIONS:
        raise ValidationError(
            "A departure is approved or rejected.", code="invalid_decision"
        )
    repo.decide_departure(
        client,
        departure_id=departure_id,
        decision=decision,
        note=body.note,
        effective_at=body.effective_at.isoformat() if body.effective_at else None,
    )
    return _read_departure(client, departure_id=departure_id)


def get_staff_member(
    client: Client, *, department_id: str, staff_id: str
) -> StaffMemberDetail:
    """One employee for the employee page: the roster row plus the departure
    heading its way (pending, or approved for a date still to come).

    The row mapping is `departments_service._to_staff` — one definition of how
    a roster row becomes a wire shape, not two that drift.
    """
    row = repo.get_staff_member(
        client, department_id=department_id, staff_id=staff_id
    )
    if row is None:
        raise NotFoundError("No such staff member.", code="staff_member_not_found")

    departure: StaffDeparture | None = None
    if row.get("departure_status"):
        open_rows = [
            _to_departure(dep)
            for dep in repo.departures_for_staff(
                client, staff_ids=[staff_id], status=None
            )
            if dep.get("status") in ("pending", "approved")
        ]
        # Newest relevant row: an approved departure whose date has passed is
        # history, and the view's departure_status already said which applies.
        departure = open_rows[-1] if open_rows else None

    member = _to_staff_member(row)
    return StaffMemberDetail(**member.model_dump(), departure=departure)


def staff_schedule(
    client: Client,
    *,
    service_client: Client,
    department_id: str,
    staff_id: str,
    starts_after: datetime | None,
    starts_before: datetime | None,
) -> list[ScheduleItem]:
    """One employee's jobs and shifts in a window.

    Two clients, the `get_departure` pattern: the roster row is read with the
    caller's own client first, so RLS decides whether they may see this person
    at all; only then does the service client read the calendar, because
    `staff_schedule_items` returns complaint titles and post names.
    """
    row = repo.get_staff_member(
        client, department_id=department_id, staff_id=staff_id
    )
    if row is None:
        raise NotFoundError("No such staff member.", code="staff_member_not_found")

    return [
        ScheduleItem(**_to_item(item).model_dump())
        for item in repo.staff_schedule(
            service_client,
            staff_id=staff_id,
            starts_after=starts_after.isoformat() if starts_after else None,
            starts_before=starts_before.isoformat() if starts_before else None,
        )
    ]


def departure_coverage(
    client: Client, *, service_client: Client, departure_id: str
) -> list[CoverageItem]:
    """The match button: each item this departure would strand, with up to
    five people who could take it.

    A zero ``candidateCount`` is the answer "there are none", rendered as a
    statement — the doc's own words: *"If there are none, it says so."* Order
    is the authorisation, as in `get_departure`.
    """
    row = repo.get_departure(client, departure_id=departure_id)
    if row is None:
        raise NotFoundError("No such departure.", code="departure_not_found")

    return [
        CoverageItem(
            **_to_item(item).model_dump(),
            candidate_count=int(item.get("candidate_count") or 0),
            candidate_names=[
                str(name) for name in (item.get("candidate_names") or [])
            ],
        )
        for item in repo.departure_coverage(
            service_client, departure_id=departure_id
        )
    ]


def _read_departure(client: Client, *, departure_id: str) -> StaffDeparture:
    """Re-read the departure a write just touched, for the ``_read_back`` reason."""
    row = repo.get_departure(client, departure_id=departure_id)
    if row is None:
        raise NotFoundError("No such departure.", code="departure_not_found")
    return _to_departure(row)


def _read_back(client: Client, *, application_id: str) -> ServiceApplication:
    """Re-read the negotiation the write just touched.

    Every write here returns the row rather than the request, for the reason the
    provider surface uses too: the view supplies the provider's name, their
    skills and the distance, none of which the caller sent. A 404 means the RLS
    policy hid the row, which after a successful write means the caller wrote
    something they may not read -- worth surfacing rather than papering over.
    """
    row = repo.get_application(client, application_id=application_id)
    if row is None:
        raise NotFoundError("No such application.", code="application_not_found")
    return _to_application(row)


# ---------------------------------------------------------------------------
# Leadership provisioning (0049)
#
# The asymmetry worth holding on to: everything above this line is about a
# service person who registered themselves and negotiated their way onto a
# roster. Everything below is about somebody who did neither -- an administrator
# typed their name, and they will be a manager the first time they sign in.
# ---------------------------------------------------------------------------


def _to_invitation(row: dict[str, Any]) -> StaffInvitation:
    return StaffInvitation(
        id=row["id"],
        department_id=row["department_id"],
        email=str(row.get("invitee_email") or ""),
        name=str(row.get("invitee_name") or ""),
        phone=row.get("invitee_phone_e164"),
        rank=str(row.get("rank") or ""),
        job_title=row.get("job_title"),
        status=str(row.get("status") or "pending"),
        claimed_at=row.get("claimed_at"),
        created_at=row["created_at"],
    )


def list_staff_invitations(
    client: Client, *, department_id: str, status: str | None = None
) -> list[StaffInvitation]:
    """Leadership invited into this department, claimed or not.

    The claimed ones are kept and returned: an administrator looking at a
    department needs to know that the manager they created has actually arrived,
    and a list that dropped them at the moment they signed in would answer a
    different question.
    """
    return [
        _to_invitation(row)
        for row in repo.list_staff_invitations(
            client, department_id=department_id, status=status
        )
    ]


def invite_staff_member(
    client: Client, *, department_id: str, body: InviteStaffRequest
) -> StaffInvitation:
    """Create a manager or supervisor, and read the row back.

    Read back rather than assembled from the request, because ``rank`` and
    ``email`` are normalised in the RPC -- lowercased, trimmed -- and echoing
    the request would show the caller what they typed rather than what will be
    matched against at sign-in. On this endpoint that difference is the whole
    feature.
    """
    invitation_id = repo.invite_staff_member(
        client,
        department_id=department_id,
        email=body.email,
        name=body.name,
        rank=body.rank,
        phone=body.phone,
        job_title=body.job_title,
    )
    rows = repo.list_staff_invitations(
        client, department_id=department_id, status=None
    )
    for row in rows:
        if str(row.get("id")) == invitation_id:
            return _to_invitation(row)
    raise NotFoundError("That invitation could not be read back.")


def update_staff_invitation(
    client: Client,
    *,
    department_id: str,
    invitation_id: str,
    body: UpdateStaffInvitationRequest,
) -> StaffInvitation:
    """Correct an unclaimed invitation, and read the row back.

    Read back for the same reason ``invite_staff_member`` reads back, only more
    so: the point of this endpoint is to fix an address, and echoing the request
    would show the admin what they typed rather than the normalised value that
    will actually be matched at sign-in. On a screen whose whole job is "is this
    right now?", that is the difference between confirming and assuming.
    """
    repo.update_staff_invitation(
        client,
        invitation_id=invitation_id,
        email=body.email,
        name=body.name,
        rank=body.rank,
        phone=body.phone,
        job_title=body.job_title,
    )
    rows = repo.list_staff_invitations(
        client, department_id=department_id, status=None
    )
    for row in rows:
        if str(row.get("id")) == invitation_id:
            return _to_invitation(row)
    raise NotFoundError("That invitation could not be read back.")


def revoke_staff_invitation(client: Client, *, invitation_id: str) -> None:
    """Withdraw an unclaimed invitation."""
    repo.revoke_staff_invitation(client, invitation_id=invitation_id)
