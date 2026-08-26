"""A worker's calendar, their leave, and the week they are willing to work.

Same guard as ``worker_jobs.py`` and the same reasoning: authenticated only, with
``0039``'s views and functions resolving *mine* from ``auth.uid()``. Nothing here
takes a worker id, a provider id or a community id.

**Everything on this surface is global across the caller's communities.** Leave
is written against their ``service_providers`` record rather than against a roster
row, which is the distinction ``0036`` 3 added the column for: a plumber on
holiday is on holiday in all four societies, and asking them to say so four times
is how three of them end up booking him.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_current_user, get_request_client
from app.domain.schemas import Principal
from app.domain.worker_schemas import (
    AvailabilityRule,
    CalendarEntry,
    CreateUnavailabilityRequest,
    SetAvailabilityRulesRequest,
    UnavailabilityBlock,
)
from app.services import worker_service as service
from supabase import Client

router = APIRouter(
    prefix="/worker",
    tags=["worker-schedule"],
    dependencies=[Depends(require_csrf_unsafe)],
)


@router.get(
    "/calendar",
    response_model=list[CalendarEntry],
    summary="My week, jobs and leave together",
)
def get_calendar(
    starts_from: datetime = Query(..., alias="from"),
    starts_to: datetime = Query(..., alias="to"),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> list[CalendarEntry]:
    """Everything occupying the caller's time in one range, earliest first.

    **One list, two kinds.** A calendar that returned jobs and made the client
    fetch leave separately would draw a worker as free on a day they had booked
    off, for as long as the second request took to arrive. `kind` is what a
    client switches on to draw them differently.

    Both bounds are required. An unbounded calendar read is a request for
    everything a worker has ever done, which no screen wants and which gets
    slower every month.

    Declined offers and cancelled jobs are **not** here. A calendar is a claim
    about where somebody will be, and a job they turned down is not one.

    No colours: the community id is on every job entry and plan D15 derives the
    colour from a hash of it, so the same society is the same colour on every
    device with nothing stored.
    """
    return service.calendar(client, starts_from=starts_from, starts_to=starts_to)


@router.get(
    "/unavailability",
    response_model=list[UnavailabilityBlock],
    summary="When I have said I am not available",
)
def list_unavailability(
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
    starts_from: datetime | None = Query(None, alias="from"),
    starts_to: datetime | None = Query(None, alias="to"),
) -> list[UnavailabilityBlock]:
    """The caller's own blocks, earliest first.

    The range filter matches on **overlap** rather than on start: a fortnight of
    leave that a one-week calendar is sitting in the middle of belongs in that
    week's answer, and filtering by start alone would drop exactly the block that
    matters most.

    `scope` says whether a block is the caller's own — everywhere they work — or
    was recorded against one roster row. Only the first can be written here; the
    second exists for a name typed onto a roster by an admin, who has no account
    of their own.
    """
    return service.list_unavailability(
        client, starts_from=starts_from, starts_to=starts_to
    )


@router.post(
    "/unavailability",
    response_model=UnavailabilityBlock,
    status_code=status.HTTP_201_CREATED,
    summary="Mark a window unavailable",
)
def add_unavailability(
    body: CreateUnavailabilityRequest,
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> UnavailabilityBlock:
    """Block out a window, in every community that employs the caller.

    **Overlapping blocks are allowed.** Two rows saying "not available" say the
    same thing rather than contradicting each other — the dispatch sweep reads
    them with `not exists` — and refusing them would refuse a perfectly sensible
    *away all week, especially Tuesday*.

    This does not cancel anything already accepted. A booking a resident has been
    told about is not retracted by a calendar edit; cancelling a scheduled visit
    is the supervisor's act and carries its own notification.

    | Status | Code | Cause |
    |---|---|---|
    | 404 | `not_found` | You have not registered as a service provider |
    | 422 | `validation_error` | The block ends before it starts |
    """
    return service.add_unavailability(client, body=body)


@router.delete(
    "/unavailability/{block_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="I am available after all",
)
def delete_unavailability(
    block_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Response:
    """Remove one of the caller's own blocks.

    A block that never existed and one belonging to somebody else get the same
    `404`, which is the posture every route on this surface takes with an id.

    `204` rather than the deleted row: unlike a withdrawn application, an
    unavailable block that is gone leaves nothing on the screen it came from.
    """
    service.delete_unavailability(client, block_id=block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/availability-rules",
    response_model=list[AvailabilityRule],
    summary="The week I am willing to work",
)
def list_availability_rules(
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> list[AvailabilityRule]:
    """The caller's declared working hours, weekday order.

    **An empty list means always available**, not never. That is how
    `dispatch_candidates` reads it, and the opposite reading would make every
    newly hired worker invisible to the engine until somebody filled in a form —
    the kind of failure nobody would diagnose.

    `weekday` is 0–6 with Sunday at 0, matching Postgres `extract(dow ...)`,
    which is what the sweep compares against.
    """
    return service.list_availability_rules(client)


@router.put(
    "/availability-rules",
    response_model=list[AvailabilityRule],
    summary="Set the week I am willing to work",
)
def set_availability_rules(
    body: SetAvailabilityRulesRequest,
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> list[AvailabilityRule]:
    """Replace the whole working week.

    **A `PUT` of the set, not add and remove**, for the reason
    `PUT /service-providers/me/skills` gives: the screen is a week with seven
    rows on it, and two tabs editing different days against a delta API is a lost
    update nobody notices until somebody is booked on their day off.

    Sending an empty list is legal and means *always available* — which is what
    never having filled the form in already meant.

    Rules already accepted work are not re-checked against the new week. A
    commitment made on Tuesday is not undone by deciding on Wednesday that
    Tuesdays are off.
    """
    return service.set_availability_rules(client, body=body)
