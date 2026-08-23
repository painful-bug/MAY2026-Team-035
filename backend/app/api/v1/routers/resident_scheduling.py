"""The resident's half of scheduling: two routes, one question.

*"Somebody wants to come on Tuesday at ten. Does that suit you?"*

**For whoever lives there, both of them**, matching the precedent
``resident_complaints.py`` set for reopening and confirming a resolution: not
because staff could not press the button, but because this is the resident's
verdict about their own home, and somebody answering on their behalf is a record
that says something untrue. The database refuses it too --
``respond_to_work_order_schedule`` checks ``is_own_membership`` against whoever
raised the complaint -- so the guard here is the early, clear error rather
than the boundary.

The guard is ``require_resident_capability``, not ``require_membership_role(
"resident")``: an admin with a flat is the resident of that flat, and there is
only one membership row per person per community to say so. What is being
checked is an active ``unit_residencies`` row, which is the fact these routes
actually depend on; the role column never recorded it.

**Neither route takes a work-order id.** A resident should not have to have read
one to answer a question that was put to them, and an endpoint that accepted one
would have to decide what happens when it names a different complaint's job.
Resolving the job from the complaint makes that question unaskable.

Staff read the same job through ``GET /work-orders/{id}``, which is a wider
projection of the same row. The resident's carries when, where and who; it does
not carry the supervisor's membership id, the skill routing or the
failed-attempt count, which are the association's business about them rather
than theirs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_request_client, require_resident_capability
from app.domain.work_order_schemas import (
    ScheduleRequest,
    ScheduleResponseRequest,
    ScheduleTimeRequest,
)
from app.services import work_orders_service as service
from supabase import Client

#: Built once at import time because the factory returns a new closure per call
#: and FastAPI caches dependencies by identity.
_resident_capability = require_resident_capability()

router = APIRouter(
    tags=["resident-scheduling"],
    dependencies=[Depends(require_csrf_unsafe), Depends(_resident_capability)],
)


@router.get(
    "/complaints/{complaint_id}/schedule-request",
    response_model=ScheduleRequest,
    summary="The visit proposed for my complaint",
)
async def get_schedule_request(
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> ScheduleRequest:
    """When somebody is coming, and whether you still have to answer.

    **Not only the visits awaiting an answer.** A resident who has already
    confirmed still needs to see the time and, once somebody is booked, the
    name — and a screen that had to call a second endpoint for that would show
    the confirmation blink out of existence the moment they pressed the button.
    `awaitingResponse` is what tells the screen which of the two it is looking
    at.

    A complaint may carry several jobs over its life; this returns the newest
    **live** one. Returning simply the newest would let a cancelled retry hide
    the visit that replaced it.

    `respondBy` is when the association stops waiting and schedules anyway. It
    is populated the moment a time is proposed, so the deadline is visible from
    the first screen rather than arriving as a surprise.

    **`mode` says which question is being asked** (ruling F1, 2026-08-23).
    `approve` — the association proposed an hour, answer it with `POST
    …/schedule`. `pick` — nobody has chosen one, and the hour is yours to set
    with `POST …/schedule-time`; the proposed times are `null`. Both are
    `awaiting_resident`, because `work_orders_status_check` is a closed list and
    a new word there costs a constraint rebuild — the slot is the discriminator,
    and `mode` is that derivation made once, here, instead of on every screen.

    | Status | Code | Cause |
    |---|---|---|
    | 404 | `schedule_request_not_found` | Nothing proposed, or all of it cancelled |
    """
    return service.get_schedule_request(client, complaint_id=complaint_id)


@router.post(
    "/complaints/{complaint_id}/schedule",
    response_model=ScheduleRequest,
    summary="Confirm or decline a proposed visit",
)
async def respond_to_schedule(
    body: ScheduleResponseRequest,
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> ScheduleRequest:
    """Answer the question. `confirmed` or `declined`.

    Confirming releases the job to be assigned. Declining sends it back to the
    supervisor **and clears the time with it** — leaving a declined slot on the
    row would leave a calendar entry for a visit nobody agreed to. Either way
    the supervisor who proposed it is notified directly rather than the whole
    admin list: they asked the question and they are the one who has to act on
    the answer.

    Declining is not a counter-proposal, and that is a deliberate limit. There
    is no slot-options table and no "how about Thursday" field: the supervisor
    proposes, the resident accepts or does not, and a different time is a second
    proposal. If it turns out residents must choose between alternatives, that
    is a table then — and it will be a table with a reason.

    **You may answer once.** Once the job has left `awaiting_resident` — you
    confirmed, or the supervisor assigned somebody rather than keep waiting —
    this returns a `409`, and the reschedule after that point is the
    supervisor's alone.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | The visit was not proposed to you |
    | 404 | `schedule_request_not_found` | No live job on this complaint |
    | 409 | `conflict` | The visit is no longer waiting on you |
    | 422 | `validation_error` | `response` was not `confirmed` or `declined` |
    """
    return service.respond(client, complaint_id=complaint_id, body=body)


@router.post(
    "/complaints/{complaint_id}/schedule-time",
    response_model=ScheduleRequest,
    summary="Pick the time for a visit to my home",
)
async def set_schedule_time(
    body: ScheduleTimeRequest,
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> ScheduleRequest:
    """The resident says when. `startAt` and `endAt`, both required.

    The 2026-08-23 ruling F1: a job at somebody's home no longer arrives with an
    hour a supervisor guessed for them. It arrives as a request, like a hiring
    application reaching a manager, and the resident's answer is the hour
    itself. Setting it moves the job to `offered` — the open pile — and the
    supervisor is notified.

    **There is no decline here** (ruling F3). Pick-mode was never a proposal, so
    there is nothing to refuse; the decline button stays on the
    supervisor-proposed reschedule, which is what `POST …/schedule` answers. If
    twenty-four hours pass with no answer the dispatcher books the first hour a
    serviceman can take and assigns them, which is what the card says it will.

    **The two write routes are not interchangeable and refuse each other's
    jobs.** A job the association gave an hour returns a `409` here — answer
    that proposal instead — and a job with no hour cannot be `confirmed`.
    Sending the wrong one is a mistake with a sentence, not a silent overwrite
    of somebody else's intention.

    Responds `200` with the same body as `GET …/schedule-request`, re-read, so
    a screen sees the booking land rather than assuming it.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | This visit is not yours to schedule |
    | 404 | `schedule_request_not_found` | No live job on this complaint |
    | 409 | `conflict` | Nothing to schedule; the association proposed the time; or the hour is in the past |
    | 422 | `validation_error` | A missing end, or an end before its start |
    """
    return service.set_time(client, complaint_id=complaint_id, body=body)
