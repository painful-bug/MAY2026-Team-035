"""A service person finding work, leaving it, and the communities that employ them.

Seven routes, and the same guard as ``service_providers.py``: **authenticated
only, no membership requirement.** This is the surface a provider uses precisely
*because* nobody has hired them yet, so a membership guard would refuse them the
screens that exist to fix that. See ``docs/plans/SERVICE_OPERATIONS_PROGRESS.md``
4.4.

Nothing here takes a community id from the caller. The two searches and the
applications list are all scoped to the caller's own provider row -- resolved
from ``auth.uid()`` inside the RPCs and the RLS policy -- so there is no id in a
request body that could widen what a caller sees.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_current_user, get_request_client
from app.domain.common_schemas import MessageResult
from app.domain.hiring_schemas import (
    ApplyRequest,
    RequestDepartureRequest,
    ServiceableCommunity,
    ServiceApplication,
    ServiceEngagement,
    StaffDeparture,
)
from app.domain.schemas import Principal
from app.services import hiring_service as service
from supabase import Client

router = APIRouter(
    prefix="/worker",
    tags=["worker-communities"],
    dependencies=[Depends(require_csrf_unsafe)],
)


@router.get(
    "/communities",
    response_model=list[ServiceEngagement],
    summary="Communities that employ me",
)
async def list_my_communities(
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
    active_only: bool = Query(True, alias="activeOnly"),
) -> list[ServiceEngagement]:
    """Every roster the caller is on, across every community.

    **A list, not a value.** This is the surface the tenancy change in
    `app/api/deps.py` was made for: a plumber hired by three societies has three
    memberships and one working week, and every screen downstream of this one
    reads the union rather than a default community.

    An empty list is the answer that drives the dashboard's empty state -- a
    registered provider employed nowhere is shown the community search, not a
    blank calendar.
    """
    return service.list_my_engagements(
        client, profile_id=principal.user_id, active_only=active_only
    )


@router.get(
    "/communities/search",
    response_model=list[ServiceableCommunity],
    summary="Communities that need my trades",
)
async def search_communities(
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
    query: str | None = Query(None, alias="q", max_length=120),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ServiceableCommunity]:
    """Where the caller could apply, nearest first.

    Three rules, all applied in SQL: the community has a department whose
    categories need one of the caller's skills, it has not blacklisted them, and
    they are not already a member of it.

    **A community with no coordinates sorts last rather than being hidden**, and
    so does a provider with none. Somebody who has not filled in where they work
    is still somebody who can work.

    An empty result usually means the caller has no skills saved yet, not that
    no community needs them -- `PUT /service-providers/me/skills` is the fix, and
    a client showing this screen should say so.
    """
    return service.search_communities(
        client, query=query, limit=limit, offset=offset
    )


@router.get(
    "/applications",
    response_model=list[ServiceApplication],
    summary="My applications and invitations",
)
async def list_my_applications(
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
    status_filter: str | None = Query(None, alias="status", max_length=20),
) -> list[ServiceApplication]:
    """Both directions in one list, newest first.

    An application the caller sent and an invitation they received are the same
    row with a different `direction`, which is what a client should switch on to
    decide whether to render "withdraw" or "accept / decline".

    This used to be the *only* way a rejected applicant learned the outcome:
    `notifications.recipient_membership_id` was not nullable and someone who was
    rejected holds no membership in that community, so there was nobody to
    notify. `0041` re-addressed a notification to a **person** rather than to a
    membership, and both a rejection and an invitation are notified now. The
    list is still the record; it is no longer the delivery mechanism.
    """
    return service.list_my_applications(
        client, profile_id=principal.user_id, status=status_filter
    )


@router.post(
    "/applications",
    response_model=ServiceApplication,
    status_code=status.HTTP_201_CREATED,
    summary="Apply to a department",
)
async def apply(
    body: ApplyRequest,
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ServiceApplication:
    """Open an application to one department.

    **One open negotiation per department at a time**, enforced by a partial
    unique index rather than a read-then-write: applying twice is a `409`, not a
    duplicate row a manager has to reconcile. A *decided* application may be
    followed by a fresh one, which is what makes removal different from
    blacklisting.

    A blacklisted caller gets the same wording as an ordinary refusal. Telling
    someone they have been barred, and by whom, is the community's decision to
    communicate rather than this endpoint's to leak.
    """
    return service.apply(client, profile_id=principal.user_id, body=body)


@router.delete(
    "/applications/{application_id}",
    response_model=ServiceApplication,
    summary="Withdraw my application",
)
async def withdraw(
    application_id: str = Path(...),
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ServiceApplication:
    """Retract an application the caller opened.

    Returns the withdrawn row rather than `204`, because the screen that called
    this is a list and the row stays on it with a new status.

    **Only the side that opened a negotiation may withdraw it.** A manager
    cannot make an application disappear by withdrawing it instead of rejecting
    it -- a rejection is a record, and this would erase it.
    """
    return service.withdraw(
        client, profile_id=principal.user_id, application_id=application_id
    )


# ---------------------------------------------------------------------------
# Leaving
#
# Addressed by roster row and not by community, because a person can hold two
# rosters in one society only in theory and holds several societies in practice.
# The row is the thing being left.
# ---------------------------------------------------------------------------


@router.post(
    "/communities/{staff_id}/departure",
    response_model=StaffDeparture,
    status_code=status.HTTP_201_CREATED,
    summary="Ask to leave a community",
)
async def request_departure(
    body: RequestDepartureRequest,
    staff_id: str = Path(...),
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> StaffDeparture:
    """Ask the department's manager to release you, immediately or on a date.

    **Leaving is not something a service person can do alone** — the manager
    decides whether and when. `effectiveAt` is the day you want to stop; omit
    it to ask to leave immediately (a past date is a `422`). Until the manager
    decides, you keep working — but **no new work in this community whose slot
    starts on or after your intended date** will reach you, and an immediate
    request freezes the engine against you entirely. Other communities are
    unaffected.

    On approval, whatever is still booked in your name from the effective date
    onward goes back to the dispatch pool for reassignment — you do not have to
    empty your own book first. `conflictCount` on the response is how many
    items that would be.

    The department's managers *and its supervisors* are notified. Supervisors
    are notified because they are the ones who will do any early reassigning,
    and a supervisor is a rank on a roster rather than a membership role —
    which is why no existing notification helper could reach them.

    `409` when a request is already open on that roster row.
    """
    return service.request_my_departure(
        client,
        profile_id=principal.user_id,
        staff_id=staff_id,
        reason=body.reason,
        effective_at=body.effective_at,
    )


@router.delete(
    "/communities/{staff_id}/departure",
    response_model=MessageResult,
    summary="Withdraw my request to leave",
)
async def cancel_departure(
    staff_id: str = Path(...),
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Change your mind, and lift the freeze.

    Addressed by roster row rather than by departure id, because the screen
    calling this is showing a community card and not a request — making cancel
    carry an id would mean it needed a read that request did not.

    Available until a manager decides. After that the answer is a fresh
    application, which is what makes an approved departure different from a bar.
    """
    service.cancel_my_departure(
        client, profile_id=principal.user_id, staff_id=staff_id
    )
    return MessageResult(message="Request withdrawn.")
