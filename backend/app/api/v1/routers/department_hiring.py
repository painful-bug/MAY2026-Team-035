"""Hiring, leaving and employee management, from the department's side.

Every route names a department in the path, so authentication alone cannot
authorize it. The HTTP layer establishes identity and CSRF; SQL/RLS applies the
department-specific predicate. Hiring uses ``can_hire_for_department`` so an
active roster-ranked manager works and admins are fallback only when no manager
exists. Departures and other roster operations retain their broader existing
``can_manage_department`` semantics.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import (
    require_admin_or_manager,
    require_csrf_unsafe,
    require_hiring_actor,
)
from app.api.deps import get_request_client
from app.core.exceptions import ValidationError
from app.core.supabase_client import get_service_client
from app.domain.common_schemas import MessageResult
from app.domain.hiring_schemas import (
    BlacklistRequest,
    CoverageItem,
    DecideApplicationRequest,
    DecideDepartureRequest,
    HireableProvider,
    InviteRequest,
    InviteStaffRequest,
    ReassignItemRequest,
    RemoveMemberRequest,
    RequestDepartureRequest,
    ScheduleItem,
    ServiceApplication,
    StaffDeparture,
    StaffDepartureDetail,
    StaffInvitation,
    StaffMemberDetail,
    UpdateStaffInvitationRequest,
)
from app.services import hiring_service as service
from supabase import Client

router = APIRouter(
    prefix="/departments",
    tags=["department-hiring"],
    dependencies=[Depends(require_csrf_unsafe)],
)

_HIRING_DEPENDENCIES = [Depends(require_hiring_actor)]
_MANAGEMENT_DEPENDENCIES = [Depends(require_admin_or_manager)]


@router.get(
    "/{department_id}/applications",
    response_model=list[ServiceApplication],
    summary="This department's applications and invitations",
    dependencies=_HIRING_DEPENDENCIES,
)
async def list_applications(
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
    status_filter: str | None = Query(None, alias="status", max_length=20),
) -> list[ServiceApplication]:
    """The inbox, newest first.

    **Both directions, deliberately.** A manager looking at who wants to work
    here also needs to see the invitations already out, or they will send a
    second one to somebody they invited last week and get a `409` they cannot
    explain.

    Filter with `?status=pending` for the queue; the unfiltered list is the
    history, which is where a rejection stays visible after it stops being
    actionable.
    """
    return service.list_department_applications(
        client, department_id=department_id, status=status_filter
    )


@router.get(
    "/{department_id}/candidates",
    response_model=list[HireableProvider],
    summary="Service people this department could hire",
    dependencies=_HIRING_DEPENDENCIES,
)
async def list_candidates(
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
    query: str | None = Query(None, alias="q", max_length=120),
    limit: int = Query(20, ge=1, le=20),
    offset: int = Query(0, ge=0),
) -> list[HireableProvider]:
    """The candidate search, nearest first.

    The mirror of `GET /worker/communities/search`: same three rules seen from
    the other end. Holds a skill this department's categories need, not
    blacklisted here, not already on this roster — and not already a member of
    the community in some other capacity, because the hire would be refused and
    offering a dead end is worse than an empty list.

    `matchingSkillNames` is the subset that put them on this list, which is not
    the same as `skillNames`. Showing only the second would leave a manager
    wondering why an electrician is being offered for a plumbing department.

    `hasOpenApplication` lets the screen offer *view* rather than a second
    invitation the unique index would refuse.
    """
    return service.search_candidates(
        client,
        department_id=department_id,
        query=query,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{department_id}/invitations",
    response_model=ServiceApplication,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a service person to this department",
    dependencies=_HIRING_DEPENDENCIES,
)
async def invite(
    body: InviteRequest,
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> ServiceApplication:
    """Offer someone a place on the roster, as a team member.

    **Rank is not a parameter and neither is shift** (product-owner ruling,
    2026-08-11). A service person hired through this surface joins as a
    `member`; managers and supervisors are provisioned by email through
    `POST .../staff-invitations` and never registered as providers in the first
    place. `staff_assignments.shift` describes nothing the system reads — work
    reaches a worker through the dispatch sweep or a supervisor's assignment,
    and a guard's rota is `security_shifts`.

    `jobTitle` is the one term on offer, and the person accepting sees it.

    **The invited person is notified**, which they were not until `0041`. This
    docstring used to say the opposite, and gave the schema as the reason:
    `notifications.recipient_membership_id` was `not null`, and somebody who has
    not been hired here holds no membership to address. That column is nullable
    now and `notify_profile` addresses the person, so a
    `service_applications_notify_invited` trigger tells them. The invitation also
    still appears on their `GET /worker/applications` screen, which remains the
    authoritative read.
    """
    return service.invite(client, department_id=department_id, body=body)


@router.post(
    "/{department_id}/applications/{application_id}/decide",
    response_model=ServiceApplication,
    summary="Accept or reject an application",
    dependencies=_HIRING_DEPENDENCIES,
)
async def decide(
    body: DecideApplicationRequest,
    department_id: str = Path(...),
    application_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> ServiceApplication:
    """Answer a pending application. **The hire happens here.**

    Accepting writes three rows in one transaction: a `community_memberships`
    row carrying the `worker` or `security` role, a `staff_assignments` row
    carrying the terms and pointing at both, and the decision itself. Either all
    three exist or none does — a membership with no roster row is somebody who
    can sign in and has no job, and no client retry would repair it.

    Which role is issued comes from `departments.kind`: a security department
    hires `security`, everything else hires `worker`. Both values have been in
    `membership_role` since the baseline and nothing has ever issued either.

    **Always at rank `member`.** This request carries no `rank` and no `shift`
    (ruling of 2026-08-11 — see `POST .../invitations`), so the RPC's own
    default applies. `jobTitle` is supplied here rather than at application
    time, because on an application nobody has offered one yet.

    Three distinct refusals share the `409`: the row was **already decided**
    (two managers clicked accept, the row is locked, and the second one loses);
    the provider is **blacklisted**, re-checked at the moment of hiring rather
    than only at application; or they are **already a member** of this
    community, since one person holds one live membership per community.
    """
    return service.decide(client, application_id=application_id, body=body)


@router.post(
    "/{department_id}/members/{staff_id}/remove",
    response_model=MessageResult,
    summary="Remove someone from this department",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def remove_member(
    body: RemoveMemberRequest,
    department_id: str = Path(...),
    staff_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Take someone off the roster and end their membership.

    **Deactivates, never deletes.** Complaints record staff by name, so removing
    the row would turn every past assignment into an unexplained string — the
    rule `0019` A7 already committed to for typed roster names, applied to hired
    people too.

    Ending the membership is what actually removes their access; the row is what
    keeps the history readable. **They may apply again**, which is the whole
    difference between this and `POST .../blacklist`.

    **A `POST` and not a `DELETE`, for two reasons.** Nothing is deleted, so the
    verb would be describing something that does not happen. And `reason` is a
    note one person writes about another that reaches them in a notification: a
    `DELETE` cannot carry a body, and the alternative — a query parameter —
    would put it in every access log between here and the database.
    """
    service.remove_member(client, staff_id=staff_id, body=body)
    return MessageResult(message="Staff member removed.")


@router.post(
    "/{department_id}/blacklist",
    response_model=MessageResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bar a service person from this community",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def blacklist(
    body: BlacklistRequest,
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Remove, and bar from applying again.

    **Community-wide, not department-wide**, even though a department id is what
    identifies the caller's authority to do it. A community that will not have
    somebody back has decided that about the community; letting them reapply to
    the department next door would make the decision meaningless.

    It is not `blacklisted_residents`. That table is keyed on a profile and is
    enforced inside `search_joinable_communities`, so reusing it would bar this
    person from *living* here as a side effect. A plumber a community will not
    hire has not been refused a flat.

    Three things happen in order: every active roster row they hold in this
    community is removed, every pending negotiation is rejected, and the bar is
    recorded. A bar that left them still working here would not be one.

    `reason` is required and stored, because whoever eventually decides whether
    to revoke it needs to know what it was for. The row carries `revokedAt`, so
    this is reversible.
    """
    service.blacklist(client, department_id=department_id, body=body)
    return MessageResult(message="Service provider blacklisted.")


# ---------------------------------------------------------------------------
# Departures
#
# Five routes for one sentence: *only when everything has been handed over to
# other workers can the leave be approved.* Four of them exist to make that one
# refusal survivable — you cannot gate an approval on an empty list without
# giving somebody a way to empty it.
# ---------------------------------------------------------------------------


@router.get(
    "/{department_id}/departures",
    response_model=list[StaffDeparture],
    summary="Departures from this department",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def list_departures(
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
    status_filter: str | None = Query(None, alias="status", max_length=20),
) -> list[StaffDeparture]:
    """Who is leaving, and how much of their handover is left.

    `openCommitmentCount` is on every row, because it is the only thing that
    decides whether the approve button does anything. A departure with a
    non-zero count is a **handover in progress**; there is no separate status
    for that, deliberately, since a status derived from a count is a status that
    can disagree with the count.

    Unfiltered this returns settled departures too, newest first, which is what
    makes it an answer to *why is this roster shorter than last month*.
    """
    return service.list_departures(
        client, department_id=department_id, status=status_filter
    )


@router.get(
    "/{department_id}/departures/{departure_id}",
    response_model=StaffDepartureDetail,
    summary="One departure and its handover list",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def get_departure(
    department_id: str = Path(...),
    departure_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> StaffDepartureDetail:
    """The list of everything still booked in that person's name.

    **Jobs and shifts in one array**, told apart by `kind`, because a handover
    works through one list — a department that runs both would otherwise need a
    screen that knew in advance which halves it was going to get.

    Nothing here is filtered to the future. A scheduled job whose slot was
    yesterday and which nobody closed is exactly what a departing worker leaves
    behind, and hiding it would let the departure be approved while the job
    still sat in their name.
    """
    return service.get_departure(
        client, service_client=get_service_client(), departure_id=departure_id
    )


@router.post(
    "/{department_id}/departures",
    response_model=StaffDeparture,
    status_code=status.HTTP_201_CREATED,
    summary="Start a handover for someone on this roster",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def open_departure(
    body: RequestDepartureRequest,
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> StaffDeparture:
    """Open a departure on somebody's behalf, immediately or for a date.

    The manager's half of the same process a worker starts from their own
    portal, and which of them opened it is **recorded on the row** rather than
    inferred afterwards from who decided it. `effectiveAt` is the intended last
    day; omitted means immediately.

    **The engine stops offering them work at or after the intended date from
    this moment** — entirely, when the departure is immediate. Without that,
    the handover is a treadmill: a supervisor reassigns three jobs and the
    dispatcher hands the same person two more while they are doing it.

    The person being moved off is notified. A worker opening their own departure
    is not — they know.
    """
    if not body.staff_id:
        raise ValidationError(
            "Name the roster row this departure is about.", code="staff_id_required"
        )
    return service.open_departure(
        client,
        staff_id=body.staff_id,
        reason=body.reason,
        effective_at=body.effective_at,
    )


@router.post(
    "/{department_id}/departures/{departure_id}/reassign",
    response_model=MessageResult,
    summary="Hand one job or shift to somebody else",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def reassign_item(
    body: ReassignItemRequest,
    department_id: str = Path(...),
    departure_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Move one item off the departing person.

    **Omitting `staffAssignmentId` is the ordinary case** and means *take the
    best candidate the dispatch ranking returns* — the same ranking
    auto-assignment uses, ordering by whoever already has a job in this
    community that day, then by who is least loaded, then by who is nearest.
    Naming somebody is the override for when a manager knows something the
    ranking does not.

    A **supervisor** may do this; only a manager may approve the departure
    itself. Handover is the work; ending somebody's employment is not.

    An item that is an *offer* rather than a booking is withdrawn and the
    dispatch ping re-armed instead of being handed to a named successor —
    nobody had accepted it, and picking somebody would silently turn a question
    into a booking.

    `409` when nobody in the department is free for that slot. The job is not
    cancelled and the departure is not approved anyway: the three real options —
    pick somebody, reschedule, cancel — are endpoints that already exist, and a
    manager looking at one unmovable job is the right place for this to stop.
    """
    service.reassign_item(client, departure_id=departure_id, body=body)
    return MessageResult(message="Handed over.")


@router.post(
    "/{department_id}/departures/{departure_id}/decide",
    response_model=StaffDeparture,
    summary="Approve or reject a departure",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def decide_departure(
    body: DecideDepartureRequest,
    department_id: str = Path(...),
    departure_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> StaffDeparture:
    """The decision — whether they leave, and when.

    **Approving picks the leave date**: the requested one when `effectiveAt` is
    omitted, or a later one at the manager's discretion (the floor is now).
    Booked work from that date onward is **released back to the dispatch pool
    at a queue priority just below urgent** for reassignment by the ordinary
    mechanics; work before the date stays with the leaver. An immediate
    approval releases everything and removes them now; a dated one arms a
    timekeeper that removes them at the date — and until then the engine gives
    them nothing new.

    *Until 2026-08-10 approval was refused with a `409` while anything was
    booked. That rule is overturned — a product-owner ruling: the decision is
    the manager's, and the pool absorbs the work.* The per-item
    `POST .../reassign` hand-over remains available before deciding.

    **A manager, not a supervisor.** Supervisors run the handover because that
    is the work; ending somebody's employment is a different decision.
    """
    return service.decide_departure(
        client, departure_id=departure_id, body=body
    )


@router.get(
    "/{department_id}/staff/{staff_id}",
    response_model=StaffMemberDetail,
    summary="One employee, with any departure heading their way",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def get_staff_member(
    department_id: str = Path(...),
    staff_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> StaffMemberDetail:
    """The employee page's identity read.

    The roster row the roster tab already renders — same view, same shape —
    plus `departure` when one is pending or approved for a date still to come.
    The schedule is `GET .../schedule`, separately, because a calendar
    refetches when its window moves and an identity card does not.

    `404` for a row in another department as much as for a missing one: the
    path's department is a scope, and a URL that renders somebody from a
    different department is a link that lies.
    """
    return service.get_staff_member(
        client, department_id=department_id, staff_id=staff_id
    )


@router.get(
    "/{department_id}/staff/{staff_id}/schedule",
    response_model=list[ScheduleItem],
    summary="One employee's jobs and shifts in a window",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def get_staff_schedule(
    department_id: str = Path(...),
    staff_id: str = Path(...),
    client: Client = Depends(get_request_client),
    service_client: Client = Depends(get_service_client),
    starts_after: datetime | None = Query(None, alias="from"),
    starts_before: datetime | None = Query(None, alias="to"),
) -> list[ScheduleItem]:
    """The schedule half of the employee page.

    Jobs and shifts in one list, finished work included — a schedule shows
    what happened, not only what looms. Unscheduled jobs always appear,
    whatever the window: work with no slot can land anywhere, which is also
    why a departure treats it as conflicting.

    **Two clients, in order, and the order is the authorization** — the roster
    row is read with the caller's own client first, so RLS decides whether
    they may see this person at all; the item read returns complaint titles
    and post names and is `service_role` only.
    """
    return service.staff_schedule(
        client,
        service_client=service_client,
        department_id=department_id,
        staff_id=staff_id,
        starts_after=starts_after,
        starts_before=starts_before,
    )


@router.get(
    "/{department_id}/departures/{departure_id}/coverage",
    response_model=list[CoverageItem],
    summary="Who could take each item this departure would strand",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def get_departure_coverage(
    department_id: str = Path(...),
    departure_id: str = Path(...),
    client: Client = Depends(get_request_client),
    service_client: Client = Depends(get_service_client),
) -> list[CoverageItem]:
    """The manager's match button.

    For every item still booked from the intended leave date onward, up to
    five people who could take it — ranked by the same sweep auto-assignment
    uses for jobs, and by lightest week for shifts. **A `candidateCount` of
    zero is the answer "there are none"**, rendered as a statement rather than
    an error, which is what the decision screen needs it to be.

    An unscheduled job also counts zero: the sweep cannot place work with no
    slot, and saying so beats pretending.
    """
    return service.departure_coverage(
        client, service_client=service_client, departure_id=departure_id
    )


# ---------------------------------------------------------------------------
# Leadership provisioning (0049)
#
# The other way into a department, and it is not the one above. Everything
# earlier in this file is about a service person who registered themselves and
# negotiated their way onto a roster. These three are about somebody who did
# neither: an administrator types a name and an email, and that person is a
# manager the first time they sign in with that address.
#
# There is no token and no acceptance step -- that is the ruling, not an
# omission. Servicemen are the only role in the service section with a
# registration flow of their own.
#
# The guard is `can_manage_department` inside the RPC, which is what lets a
# MANAGER create a SUPERVISOR without being an administrator.
# ---------------------------------------------------------------------------


@router.get(
    "/{department_id}/staff-invitations",
    response_model=list[StaffInvitation],
    summary="Leadership created for this department",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def list_staff_invitations(
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
    status_filter: str | None = Query(None, alias="status", max_length=20),
) -> list[StaffInvitation]:
    """Managers and supervisors created here, whether or not they have arrived.

    **Claimed ones are kept in the list.** An administrator needs to know that
    the manager they created has actually signed in, and a list that dropped
    each person at the moment they arrived would answer a different question --
    it would look identical whether somebody was still expected or had been
    working for a month.

    `claimedAt` is null until their first sign-in. A `pending` row that is weeks
    old is usually a mistyped address, and this list is the only place that is
    visible: nothing else fails when an email is wrong, because there is nothing
    to deliver.
    """
    return service.list_staff_invitations(
        client, department_id=department_id, status=status_filter
    )


@router.post(
    "/{department_id}/staff-invitations",
    response_model=StaffInvitation,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manager or supervisor",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def invite_staff_member(
    body: InviteStaffRequest,
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> StaffInvitation:
    """Provision leadership by email. **No invitation is sent and none is needed.**

    The email is not a delivery address, it is the **matching key**: whoever
    signs in with it is admitted to this department at that rank. Nothing is
    mailed, so a wrong address produces no bounce and no error -- only an
    invitation that stays `pending` forever, which is why the list above exists.

    `rank` is `manager` or `supervisor`. `member` is refused: that rank is
    reached only by hiring a registered service provider, which is the whole
    point of removing typed-in technicians from the department form.

    The membership role is **derived at sign-in**, not stored -- a manager
    becomes `manager`, a supervisor becomes `security` or `worker` depending on
    the department's kind. Deriving it late means a department that changes kind
    between now and then cannot mint a membership pointing at the wrong portal.

    Returns 409 when that address already belongs to this community, because the
    claim would fail on the same check and offering the invitation would be
    offering a dead end.
    """
    return service.invite_staff_member(
        client, department_id=department_id, body=body
    )


@router.patch(
    "/{department_id}/staff-invitations/{invitation_id}",
    response_model=StaffInvitation,
    summary="Correct an unclaimed invitation",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def update_staff_invitation(
    body: UpdateStaffInvitationRequest,
    department_id: str = Path(...),
    invitation_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> StaffInvitation:
    """Fix a mistyped address before anybody claims it.

    This exists because of how the endpoint above fails. Nothing is mailed, so a
    wrong email does not bounce -- the invitation simply sits `pending` and the
    person never arrives. The pending list is what makes that visible; this is
    what the admin does about it.

    **Omitted means unchanged.** Only the fields present in the body move, so a
    form that patches the email cannot blank the job title by not sending it.
    `phone` and `jobTitle` accept `""` to clear; `email`, `name` and `rank` do
    not, because an invitation without them binds nothing, names nobody, or
    admits at no rank.

    **`departmentId` is not in the body, and that is the point.** The department
    is what `can_manage_department` authorizes this call against, so allowing it
    to move would let the manager of one department mint staff into another
    without that department's manager being asked. Moving an invitation is
    revoke-and-reissue, under the authority of wherever it is going.

    Returns 409 once it has been claimed -- by then the address has already
    admitted somebody and editing it here would change nothing about who got in
    -- and 409 if the new address already belongs to the community or already
    has an open invitation.
    """
    return service.update_staff_invitation(
        client,
        department_id=department_id,
        invitation_id=invitation_id,
        body=body,
    )


@router.delete(
    "/{department_id}/staff-invitations/{invitation_id}",
    response_model=MessageResult,
    summary="Withdraw an unclaimed invitation",
    dependencies=_MANAGEMENT_DEPENDENCIES,
)
async def revoke_staff_invitation(
    department_id: str = Path(...),
    invitation_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Withdraw leadership that has not signed in yet.

    **Revoked, not deleted**: who created an invitation and when is worth
    keeping, and a mistyped address that was noticed and withdrawn is exactly
    the history somebody will want later.

    Returns 409 once it has been claimed. Removing somebody who has already
    started is a departure, not a withdrawal, and has its own five routes above
    for the good reason that their work has to go somewhere.
    """
    service.revoke_staff_invitation(client, invitation_id=invitation_id)
    return MessageResult(message="Invitation withdrawn.")
