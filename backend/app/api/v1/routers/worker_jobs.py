"""A worker's own jobs, and the five things they can do to one.

**Authenticated only, with no membership guard**, and unlike the other surfaces
that say this, here it is a correction rather than a convenience.
``require_membership_role("worker", "security")`` reads the role off the caller's
*default* membership, and this is the one surface in the product that is
deliberately cross-community: a plumber hired by three societies and living in a
fourth has a default membership of ``resident``, and that guard would refuse them
their own job list. Widening it to *any* worker membership would still refuse a
department manager who is on a roster and has been offered a job.

The question a guard here would be reaching for is *does this caller hold this
assignment*, which is not a question about roles. It has exactly one
implementation -- ``is_own_staff_assignment`` in ``0036`` 4 -- and the views and
functions behind every route below all use it. See
``docs/plans/SERVICE_OPERATIONS_PROGRESS.md`` 4.16.

**The five verbs are five routes and not one ``PATCH`` of a status**, for the
reason ``work_orders.py`` gives about its own: each carries a different rule and
a different notification -- accepting withdraws four other offers, failing counts
an attempt and arms an escalation -- and a general-purpose status write is
precisely the shape that skips them.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_current_user, get_request_client
from app.domain.schemas import Principal
from app.domain.worker_schemas import (
    CompleteJobRequest,
    DeclineJobRequest,
    ReportJobFailureRequest,
    WorkerJob,
    WorkerJobDetail,
    WorkerSnapshot,
)
from app.services import worker_service as service
from supabase import Client

router = APIRouter(
    prefix="/worker",
    tags=["worker-jobs"],
    dependencies=[Depends(require_csrf_unsafe)],
)


@router.get(
    "/snapshot",
    response_model=WorkerSnapshot,
    summary="The worker dashboard aggregate",
)
async def worker_snapshot(
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> WorkerSnapshot:
    """Everything the worker's dashboard renders, in one call.

    **A null `provider` is not an error, it is the empty state.** A caller who
    has never registered gets a snapshot with nothing in it rather than a `404`,
    and a registered caller employed nowhere gets an empty `communities` — so the
    dashboard decides between "show the registration form", "show the community
    search" and "show the week" from one response instead of interpreting two
    failures.

    **`communities` is filled independently of `provider`.** `provider: null`
    with a non-empty `communities` is department leadership: a manager or
    supervisor an administrator created by email holds a membership and a roster
    row and no `service_providers` row, because leadership has no registration
    process. A client must therefore decide the registration form on `provider`
    **and** `communities[].rank` — an active `manager` or `supervisor`
    engagement is never sent to it, while `member` and no engagement at all
    still are, because coordinates and trades are how those people are found.

    `todayJobs` and `nextJob` answer different questions and both are needed: at
    six in the evening today's list is history, and what a worker wants then is
    tomorrow morning.

    `unreadNotifications` counts across **every** community the caller works in.
    It is the one place a user can see the multi-community seam this feature
    added to `app/api/deps.py`.

    Sequential reads, so `generatedAt` is when the payload was assembled rather
    than when any part of it was true — the same honesty `GET /resident/snapshot`
    prints about itself.
    """
    return service.snapshot(client, profile_id=principal.user_id)


@router.get(
    "/jobs",
    response_model=list[WorkerJob],
    summary="My jobs",
)
async def list_jobs(
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
    status_filter: str | None = Query(None, alias="status", max_length=24),
    assignment_status: str | None = Query(
        None, alias="assignmentStatus", max_length=24
    ),
    starts_from: datetime | None = Query(None, alias="from"),
    starts_to: datetime | None = Query(None, alias="to"),
) -> list[WorkerJob]:
    """Every offer and booking the caller holds, soonest first.

    Two filters because there are two states and they answer different
    questions. `?assignmentStatus=offered` is *what is being asked of me*;
    `?status=in_progress` is *what is happening to the job*. A withdrawn
    assignment on a job that went ahead without you is visible under the first
    and invisible under the second, which is the distinction a worker wondering
    "what happened to that one" is making.

    Unscheduled rows sort **last**, not first. An offer with no time yet is not
    the most urgent thing on the screen.
    """
    return service.list_jobs(
        client,
        status=status_filter,
        assignment_status=assignment_status,
        starts_from=starts_from,
        starts_to=starts_to,
    )


@router.get(
    "/jobs/{work_order_id}",
    response_model=WorkerJobDetail,
    summary="One job, with who to meet",
)
async def get_job(
    work_order_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> WorkerJobDetail:
    """The job, the complaint in full, and the resident's name, flat and number.

    Those last three are on this route and not on the list, deliberately. A
    worker on their way to a flat needs all of them and a worker scrolling a
    month of finished jobs needs none, so the list query does not select them.

    They are null on a `facility` job, where there is no door and nobody to meet.

    | Status | Code | Cause |
    |---|---|---|
    | 404 | `not_found` | No such job, or not one of yours — the same answer on
      purpose, so an id cannot be tested for existence |
    """
    return service.get_job(client, work_order_id=work_order_id)


@router.post(
    "/jobs/{work_order_id}/accept",
    response_model=WorkerJob,
    summary="Take an offered job",
)
async def accept_job(
    work_order_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> WorkerJob:
    """Accept, and book the hour.

    **This is the race the whole feature has been building toward.** The
    dispatcher offers one job to five people on purpose, so two of them tapping
    this within the same second is the ordinary case rather than the edge one.
    The RPC locks the work order before it reads anything: the second caller
    waits, re-reads a job that now says `scheduled`, and gets a `409` that says
    *somebody has already taken this job* rather than a constraint violation.

    Accepting withdraws every other offer on the job — withdrawn, not deleted,
    so "we asked five and Anil took it" survives.

    A second tap by the same worker is **not** a conflict. They already hold it,
    which is the answer they were asking for.

    | Status | Code | Cause |
    |---|---|---|
    | 404 | `not_found` | No such job, or you were never offered it |
    | 409 | `conflict` | Somebody took it · the offer is closed · you are booked |
    """
    return service.accept(client, work_order_id=work_order_id)


@router.post(
    "/jobs/{work_order_id}/decline",
    response_model=WorkerJob,
    summary="Say no to an offer",
)
async def decline_job(
    body: DeclineJobRequest,
    work_order_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> WorkerJob:
    """Decline, and nothing else happens.

    The job stays `offered`, the other four still hold their offers, and the
    auto-assign the dispatcher armed alongside the ping is still due. What
    changes is that the sweep now excludes you **from this job** — a worker who
    declined and was then auto-assigned the same job anyway is the outcome that
    would teach everybody to ignore the button.

    Declining next week's job is not declined by having declined this one: the
    exclusion is scoped to the work order, not to the person.

    `reason` is optional here and required on `/unable`, and the asymmetry is the
    point: a worker who was asked and is not free owes nobody an explanation,
    while a worker who went and could not do the work is reporting something the
    next person has to act on.

    **An accepted job cannot be declined.** By then a resident has been told a
    name and an hour; getting out of it is `/unable` or a call to the supervisor,
    both of which tell somebody.
    """
    return service.decline(client, work_order_id=work_order_id, body=body)


@router.post(
    "/jobs/{work_order_id}/start",
    response_model=WorkerJob,
    summary="I am on site",
)
async def start_job(
    work_order_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> WorkerJob:
    """Move the job to `in_progress` and tell the resident.

    Idempotent: a second tap on a job already in progress is not an error, it is
    a client that lost a response.

    The notification is one D9's amendment permits — this is not a progress bar
    ticking, it is somebody about to ring the doorbell.
    """
    return service.start(client, work_order_id=work_order_id)


@router.post(
    "/jobs/{work_order_id}/complete",
    response_model=WorkerJob,
    summary="The work is done",
)
async def complete_job(
    body: CompleteJobRequest,
    work_order_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> WorkerJob:
    """Close the job. **The complaint stays open.**

    Those look like one act and are not. A resident whose tap still drips after
    the visit has a complaint that is emphatically not resolved, and `0031`
    already gives them the button that says so. A worker's word is evidence, not
    a verdict.

    Accepted from `scheduled` as well as `in_progress`, and not out of leniency:
    somebody who fixed the tap and forgot to press *start* has done the work, and
    an API that refuses to record it teaches them the app is lying about what
    happened.

    `notes` reaches the resident in the notification, so it is written to be read
    by them rather than filed.
    """
    return service.complete(client, work_order_id=work_order_id, body=body)


@router.post(
    "/jobs/{work_order_id}/unable",
    response_model=WorkerJob,
    summary="The visit could not be completed",
)
async def report_job_failure(
    body: ReportJobFailureRequest,
    work_order_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> WorkerJob:
    """Report a failed visit. Counts the attempt and starts a clock.

    `reason` is required. *"Could not be done"* with nothing after it is the
    report that guarantees a second wasted visit: nobody downstream can tell
    "nobody was home" from "the part is out of stock", and those need opposite
    responses. It reaches the resident too, because half the reasons a visit
    fails are things only they can fix.

    Two hours later, if nobody has raised a replacement job, the dispatcher tells
    the department's manager — or the community's admins where the department has
    no manager. That is `failed_visit_escalation`, and this route is its only
    trigger.

    The answer to a failed visit is a **new** work order rather than an edit to
    this one, which is why this job stays `failed` afterwards and why the
    escalation asks whether a newer job exists rather than whether this one moved.
    """
    return service.report_failure(client, work_order_id=work_order_id, body=body)
