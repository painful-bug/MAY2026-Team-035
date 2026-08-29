"""Work orders, from the supervisor's side.

**The router guard is coarse and is meant to be.** A department supervisor holds
a ``worker`` membership with the ``supervisor`` rank on their roster row -- rank
is not role, and ``0035`` settled that deliberately -- so the only role-level
filter that admits every legitimate caller admits every worker too. It is here
to turn "signed-in resident poking at work-order ids" into a 403 before any
query runs, and to keep the OpenAPI description of who these routes are for
honest. It is not the boundary.

The boundary is ``can_supervise_department(uuid)`` inside Postgres, applied by
every RPC here and, through ``can_read_work_order``, by the RLS policy behind
every read. A worker calling ``POST /work-orders/{id}/cancel`` on their own job
passes the guard above and is refused by the database -- the posture
``docs/design/ADMIN_DASHBOARD_DESIGN.md`` 10 asks for: an id arriving in a URL
is never an authorization decision.

**Six routes and one asymmetry worth stating.** Everything here is the
supervisor's: creating the job, editing it, assigning it, moving it, calling it
off. The resident may confirm a proposed time and may decline it
(``resident_scheduling.py``) and may do neither afterwards -- **the reschedule
after assignment is the supervisor's alone**, because by then it is a change to
two people's days and only one of them is on this screen.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_request_client, require_membership_role
from app.domain.work_order_schemas import (
    AssignWorkOrderRequest,
    Candidate,
    CancelWorkOrderRequest,
    CreateWorkOrderRequest,
    RescheduleWorkOrderRequest,
    TakeUpWorkOrderRequest,
    UpdateWorkOrderRequest,
    WorkOrder,
    WorkOrderDetail,
)
from app.services import work_orders_service as service
from supabase import Client

#: Everyone who could conceivably supervise a department. Built once at import
#: time, because ``require_membership_role`` returns a new closure per call and
#: FastAPI caches dependencies by identity.
_staff_only = require_membership_role("admin", "manager", "worker", "security")

router = APIRouter(
    tags=["work-orders"],
    dependencies=[Depends(require_csrf_unsafe), Depends(_staff_only)],
)


@router.post(
    "/complaints/{complaint_id}/work-orders",
    response_model=WorkOrder,
    status_code=status.HTTP_201_CREATED,
    summary="Raise work against a complaint",
)
def create_work_order(
    body: CreateWorkOrderRequest,
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> WorkOrder:
    """Supervisor triage. **This is the fork the feature turns on.**

    Sending no `scheduledStartAt` creates a `draft`: the supervisor wants to ask
    the resident something first, and the conversation carries on in
    `POST /complaints/{id}/comments` exactly as it does today. Nothing is
    proposed and nobody is notified.

    Sending a slot proposes a visit. On a `resident` job that means
    `awaiting_resident` and a notification asking them to confirm; on a
    `facility` job there is nobody whose door is being knocked on, so it goes
    straight to `offered`.

    `departmentId` and `skillId` are both optional and both derived when
    omitted — the department from the complaint, the skill from the category
    (`0034` gave `complaint_categories` a `skill_id` precisely so nobody has to
    answer "which trade is this" twice). `priority` is not a field at all: a
    job's urgency **is** the complaint's urgency, and a second copy is a second
    thing to keep in step.

    A complaint may carry several work orders over its life, one live at a time
    — a failed visit's replacement or a reopened complaint's new job comes after
    the previous job ends, never alongside it. Each of those is a second job
    rather than an edit to the first, and the raise is refused while any job on
    the complaint is still `draft`, `awaiting_resident`, `offered`, `scheduled`
    or `in_progress`.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | Not your department, or another community's |
    | 404 | `not_found` | No such complaint |
    | 409 | `conflict` | The complaint names no department and none was supplied |
    | 409 | `conflict` | A job on this complaint is still live |
    | 422 | `validation_error` | Half a slot, a backwards slot, or a bad `subjectKind` |
    """
    return service.create(client, complaint_id=complaint_id, body=body)


@router.get(
    "/complaints/{complaint_id}/work-orders",
    response_model=list[WorkOrder],
    summary="Every job raised against one complaint",
)
def list_complaint_work_orders(
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> list[WorkOrder]:
    """The complaint's work history, newest first.

    Read rather than derived from the timeline: `complaint_events` records that
    a job was scheduled, which is the right shape for a narrative and the wrong
    one for "is anybody coming on Tuesday".
    """
    return service.list_for_complaint(client, complaint_id=complaint_id)


@router.get(
    "/departments/{department_id}/work-orders",
    response_model=list[WorkOrder],
    summary="This department's work queue",
)
def list_department_work_orders(
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
    status_filter: str | None = Query(None, alias="status", max_length=24),
) -> list[WorkOrder]:
    """Soonest first, with the unscheduled underneath.

    A draft with no time is not the most urgent thing on the screen — it is the
    thing nobody has decided about yet, and sorting nulls first would put it
    above the visit happening in an hour.

    Filter with `?status=awaiting_resident` for the jobs waiting on somebody
    else, or `?status=draft` for the ones waiting on you.
    """
    return service.list_for_department(
        client, department_id=department_id, status=status_filter
    )


@router.get(
    "/work-orders/{work_order_id}",
    response_model=WorkOrderDetail,
    summary="One job, with its assignment history",
)
def get_work_order(
    work_order_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> WorkOrderDetail:
    """The job and every offer ever made on it.

    `assignments` is a history, not a holder: withdrawn and declined rows stay,
    because "we sent Ravi and he could not get in, so we sent Anil" is the
    answer to the question a supervisor actually asks. The **current** holder is
    the top-level `assigneeName`, which is null while nobody has it.

    Four populations can read this and they see it for four different reasons —
    the community's admins, the department's supervisors, the worker holding an
    assignment, and the resident whose complaint it answers. That rule is
    `can_read_work_order` in `0036` 4, stated once and used by both the policy
    and the endpoints.
    """
    return service.get_detail(client, work_order_id=work_order_id)


@router.get(
    "/work-orders/{work_order_id}/candidates",
    response_model=list[Candidate],
    summary="Eligible workers for a work-order offer",
)
def work_order_candidates(
    work_order_id: str = Path(...),
    include_excluded: bool = Query(False, alias="includeExcluded"),
    client: Client = Depends(get_request_client),
) -> list[Candidate]:
    return service.candidates(
        client, work_order_id=work_order_id, include_excluded=include_excluded
    )


@router.patch(
    "/work-orders/{work_order_id}",
    response_model=WorkOrder,
    summary="Edit what the job is",
)
def update_work_order(
    body: UpdateWorkOrderRequest,
    work_order_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> WorkOrder:
    """Change the trade, the place, the kind or the urgency.

    **Not the time and not the state.** Those have their own routes because each
    of them carries a rule and a notification — a reschedule moves a worker's
    booking and tells two people, a cancellation frees a slot — and a
    general-purpose `PATCH` is precisely the shape that skips them.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You do not supervise that department |
    | 404 | `not_found` | No such work order |
    | 409 | `conflict` | The job is completed or cancelled |
    """
    return service.update(client, work_order_id=work_order_id, body=body)


@router.post(
    "/work-orders/{work_order_id}/assign",
    response_model=WorkOrderDetail,
    summary="Put a named person on the job",
)
def assign_work_order(
    body: AssignWorkOrderRequest,
    work_order_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> WorkOrderDetail:
    """Offer somebody the job, and propose their hour.

    Writes an **offered** assignment. The worker must accept before the visit is
    booked; the existing 409 rules remain unchanged.

    **`force: true` is the supervisor's override** (2026-08-22 ruling A4) and
    changes nothing else about this route. It writes an `is_forced` assignment
    straight to `accepted` — the worker cannot decline it, and their card already
    hides the button for a forced row — through the same mechanics the dispatch
    engine uses when every candidate has declined a critical job. Omitting the
    flag, or sending `false`, is the offer flow byte for byte.

    **Assigning a job that is still `awaiting_resident` is allowed**, and that
    is deliberate rather than an oversight. It is the hand-operated form of the
    resident timeout the dispatcher will later fire, so a supervisor whose
    resident has gone quiet has a lever today rather than after the next step
    lands.

    Any previous acceptance is **withdrawn, not deleted** — one holder at a
    time, and the history of who was booked and unbooked survives.

    The `409` worth designing for is the double-booking. `0036` refuses it by
    name (*"Ravi is already booked during that time"*) and
    `work_order_assignments_no_overlap` refuses it again in the schema; the
    first is the sentence, the second is the guarantee, and a race that beats
    the check still comes back a `409`.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You do not supervise that department |
    | 404 | `not_found` | No such work order, or no such roster entry |
    | 409 | `conflict` | Already booked · not on this roster · no time set · closed |
    """
    return service.assign(client, work_order_id=work_order_id, body=body)


@router.post(
    "/work-orders/{work_order_id}/take-up",
    response_model=WorkOrderDetail,
    summary="Take the job yourself",
)
def take_up_work_order(
    body: TakeUpWorkOrderRequest,
    work_order_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> WorkOrderDetail:
    """**The department's manual valve** (2026-08-24 ruling R8).

    Since 2026-08-23 a job may only be offered, auto-booked or claimed by staff
    hired from the servicemen pool — rank `member`. That is the right rule and
    it leaves one gap: a thin department, on a day its technician is away, has
    work nobody in the system may hold. This is the way out, and it is
    deliberately a separate button rather than a relaxation of the rule.

    **There is no `staffAssignmentId` and there will not be one.** The holder is
    the caller's own active `manager` or `supervisor` roster row on this job's
    department, resolved inside the database from the session. A caller who
    holds no such row is refused — including a community admin, who has no
    roster row, no calendar and no trade, and whose booking nobody could keep.
    The most this route can do is give the caller work.

    Everything after that is `assign`'s: the slot is optional and defaults to
    the job's own, the previous holder is **withdrawn, not deleted**, the job
    moves to `scheduled`, the resident is told somebody is coming, and the
    double-booking `409` is the same one — taking a job up overrides nobody's
    consent, and certainly not physics.

    The timeline gains **two** entries: `job_assigned`, because from the
    resident's side the fact is the same fact, and `job_taken_up` beside it,
    because from the department's side it is not — this job did not go through
    the pool, and the record says so without anybody having to infer it from a
    rank. Both name the caller. The department is notified; the caller is not,
    having just pressed the button.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You hold no active supervisor or manager row on this department |
    | 404 | `not_found` | No such work order |
    | 409 | `conflict` | The job is closed · you are already booked across that hour |
    """
    return service.take_up(client, work_order_id=work_order_id, body=body)


@router.post(
    "/work-orders/{work_order_id}/reschedule",
    response_model=WorkOrderDetail,
    summary="Move the visit",
)
def reschedule_work_order(
    body: RescheduleWorkOrderRequest,
    work_order_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> WorkOrderDetail:
    """Change when it happens. **The supervisor's alone.**

    The accepted assignment moves with the job, which is what re-checks the
    overlap constraint: putting a booked worker onto an hour they already have
    is the same double-booking as assigning them there in the first place.

    Where it lands depends on whether anybody holds it. A job **already
    assigned** stays `scheduled` and the resident is *told*; sending it back to
    `awaiting_resident` would strand a worker who has the slot in their calendar
    on an answer that may never come. A job nobody holds goes back to
    `awaiting_resident` on a `resident` job — the resident agreed to a different
    hour, so they are asked again — or to `offered` on a `facility` one.
    """
    return service.reschedule(client, work_order_id=work_order_id, body=body)


@router.post(
    "/work-orders/{work_order_id}/cancel",
    response_model=WorkOrder,
    summary="Call the job off",
)
def cancel_work_order(
    body: CancelWorkOrderRequest,
    work_order_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> WorkOrder:
    """Terminal, and it takes the assignment with it.

    A cancelled job that left an accepted assignment standing would block an
    hour in a worker's calendar for work nobody is going to do — which is the
    kind of bug that shows up as "the dispatcher says everyone is busy".

    `reason` is required and reaches both the worker and the resident in a
    notification. A cancellation nobody can explain is the one that produces the
    phone call this feature exists to prevent.

    **A `POST` and not a `DELETE`.** Nothing is deleted — the row is the record
    of what was scheduled and why it was not — and `DELETE` cannot carry the
    reason, while a query parameter would put it in every access log between
    here and the database.
    """
    return service.cancel(client, work_order_id=work_order_id, body=body)
