"""The supervisor's landing surface: one dashboard read and the card's verbs.

**A router of its own rather than routes bolted onto ``complaint_routing.py`` or
``work_orders.py``.** Its operations straddle both: the snapshot answers with
complaints *and* work orders, and take-up, resolve, priority, notes and chat are
complaint verbs whose whole point is that they are not a dispatch. Putting them
under either existing tag would describe them as the thing they are deliberately
not -- ``complaint-routing`` is about *which department owns a complaint*, and
``work-orders`` is about turning one into a scheduled visit.

They are not on ``complaints.py`` either, and that is the same distinction from
the other side: everything there is the **admin's** surface, guarded by
``require_admin`` and community-wide. These are one department's, guarded by
``can_supervise_department``, and a supervisor is not an admin.

The one action that *is* a dispatch -- force-assigning a named worker -- stayed
in ``work_orders.py``, as a flag on the existing assign route. It writes a
work-order assignment, so it belongs beside the offer it overrides rather than
beside the triage verbs.

**The router guard is coarse and is meant to be**, for the reason
``work_orders.py`` gives at length: a department supervisor holds a ``worker``
membership with the ``supervisor`` *rank* on their roster row -- rank is not role,
``0035`` settled that -- so the only role filter that admits every legitimate
caller admits every worker. It turns "signed-in resident poking at department
ids" into a 403 before any query runs. It is not the boundary.

The boundary is ``can_supervise_department(uuid)`` inside Postgres, applied by
every one of the RPCs, which is the same posture and the same predicate
``GET /departments/{id}/complaints`` has always used. An id arriving in a URL is
never an authorization decision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_request_client, require_membership_role
from app.domain.common_schemas import MessageResult
from app.domain.supervisor_triage_schemas import (
    AddComplaintNoteRequest,
    ComplaintThreadOpened,
    TriageSnapshot,
)
from app.services import supervisor_triage_service as service
from supabase import Client

#: Everyone who could conceivably supervise a department. Built once at import
#: time, because ``require_membership_role`` returns a new closure per call and
#: FastAPI caches dependencies by identity.
_staff_only = require_membership_role("admin", "manager", "worker", "security")

router = APIRouter(
    tags=["supervisor-triage"],
    dependencies=[Depends(require_csrf_unsafe), Depends(_staff_only)],
)


@router.get(
    "/departments/{department_id}/triage-snapshot",
    response_model=TriageSnapshot,
    summary="The supervisor's dashboard, in one read",
)
def triage_snapshot(
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> TriageSnapshot:
    """Six sections, bucketed server-side, newest first within each.

    * `newComplaints` — storage status `open`, no take-up stamp, no live job.
    * `takenUp` — a supervisor pressed *Take up* and no job exists yet.
    * `awaitingResident` — the resident has been asked and has not answered:
      `awaiting_resident`, uncommitted. Nothing here is the supervisor's to
      move, which is why it stopped being an open request on 2026-08-23.
    * `openRequests` — a job is raised and nobody has committed to it: `draft`
      or `offered`.
    * `assignedPending` — a worker **accepted** it (or it is booked) and has not
      started.
    * `inProgress` — the worker pressed *Start*; `startedAt` says when.

    **The bucketing is the server's and the client never re-derives it.** *Live*
    (not completed, cancelled or failed) and *committed* (an `accepted`
    assignment, or work-order status `scheduled`) are defined once, in
    `supervisor_triage_snapshot`. Six definitions that must agree are one
    definition or they are six answers.

    **Furthest stage wins**, so a complaint appears exactly once across the six:
    as a complaint until a job exists, and as that job afterwards. An offered but
    unaccepted job is an *open request* and not assigned work — the 2026-08-22
    ruling A3, and the reason `offeredToName` exists beside `assigneeName`.

    One call rather than the N+1 the triage screen makes today — a department
    read followed by a work-order read per complaint, which four sections would
    have multiplied by four.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You do not supervise this department |
    | 404 | `not_found` | No such department |
    """
    return service.snapshot(client, department_id=department_id)


@router.post(
    "/complaints/{complaint_id}/take-up",
    response_model=MessageResult,
    summary="Take a new complaint up",
)
def take_up_complaint(
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """The supervisor saying *this one is mine to triage*.

    **Triage ownership, not dispatch.** `complaints.assigned_to_membership_id`
    stays the dead column the 2026-08-21 rulings made it; the complaint still
    belongs to the department, and who is actually going is still a work-order
    assignment. What this stamps is who is looking at it, so two supervisors do
    not both start arranging the same visit.

    It moves the storage status `open → acknowledged`, which the resident already
    reads as *In Progress*, and **only from `open`** — a complaint a worker has
    already started is not walked backwards by a triage button.

    **No request body**, and none is read: the acting supervisor is the session,
    and a body would be a place to name somebody else.

    **Nobody is notified.** A field changing with no action attached is the
    passive change `ARCHITECTURE.md`'s rule exists to suppress; the resident
    learns the same fact from the status their screen re-snapshots within a beat.

    Taking up your own again is a `200` no-op — a double-clicked button is not an
    error worth a message — while somebody else's is a `409` that **names them**,
    because "already taken up" without a name sends a supervisor to ask around an
    office.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | Not this department's supervisor |
    | 404 | `not_found` | No such complaint |
    | 409 | `conflict` | Somebody else holds it · it has no department yet |
    """
    service.take_up(client, complaint_id=complaint_id)
    return MessageResult(message="Complaint taken up.")


@router.post(
    "/complaints/{complaint_id}/resolve",
    response_model=MessageResult,
    summary="Mark a complaint resolved",
)
def resolve_complaint(
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """The department saying the work is done. **No request body.**

    One transaction. Every other **live** job on the complaint is called off —
    `draft`, `awaiting_resident`, `offered`, `scheduled` — its `offered` and
    `accepted` assignment rows withdrawn, and every affected worker notified
    with the reason *"Complaint resolved by the department"*. A worker who is
    holding an offer must not have to find out from an empty queue.

    **A job that is `in_progress` refuses the whole call** with a `409`.
    Somebody is inside a resident's flat; the honest answers are to let them
    finish or to cancel the visit, and both are somebody's deliberate act rather
    than a side effect of this button.

    It moves the complaint to `resolved` and **not** to `closed`: `closed` is
    what the *resident* says by confirming with a rating. The v0 aftermath is
    unchanged — confirm, reopen, the 48-hour reminder and the 72-hour auto-close
    all hang off `resolved` and all still fire, because the trigger that arms
    them watches the status this writes.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | Not this department's supervisor |
    | 404 | `not_found` | No such complaint |
    | 409 | `conflict` | A job is in progress · already settled · no department |
    """
    service.resolve(client, complaint_id=complaint_id)
    return MessageResult(message="Complaint resolved.")


@router.post(
    "/complaints/{complaint_id}/priority-raise",
    response_model=MessageResult,
    summary="Raise a complaint's priority one step",
)
def raise_complaint_priority(
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """`Low → Medium → High`, one step, one way. **No request body.**

    **One way is the design.** A supervisor who could lower a priority could
    quietly un-escalate something somebody else escalated, and that is a decision
    worth its own verb and its own audit line rather than a second use of this
    one. At `High` it is a `409` — there is nowhere further to go.

    **Priority is load-bearing, deliberately.** `High` is what arms the dispatch
    engine's automatic force-assign when every candidate has declined, and what
    shortens the manual dispatch window from 24 hours to 2. The complaint's live
    jobs move with it, because a job's urgency *is* its complaint's urgency —
    `create_work_order` never took a priority argument for the same reason.

    The SLA deadline is **not** recomputed. `expectedResolutionAt` is a promise
    already made to the resident, and moving it because the department
    reclassified the work would make a complaint overdue for a reason the
    resident never saw.

    Nobody is notified — a passive field change under `ARCHITECTURE.md`'s rule —
    but the timeline gains a `priority_changed` entry the resident can read.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | Not this department's supervisor |
    | 404 | `not_found` | No such complaint |
    | 409 | `conflict` | Already `High` · no department yet |
    """
    level = service.raise_priority(client, complaint_id=complaint_id)
    return MessageResult(message=f"Priority raised to {level}.")


@router.post(
    "/complaints/{complaint_id}/notes",
    response_model=MessageResult,
    status_code=status.HTTP_201_CREATED,
    summary="Add an internal note to a complaint",
)
def add_complaint_note(
    body: AddComplaintNoteRequest,
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """A permanent note on the complaint's timeline, **for staff and workers**.

    The resident does not see it. That is the product owner's own scoping — the
    people who read these were enumerated as staff and workers — and it is
    carried by a payload flag on the existing `note_added` event rather than by a
    new event word, so the admin's resident-visible *Update from management*
    notes (`PATCH /complaints/{id}` with `updateNote`) are untouched.

    **Append-only.** No edit, no delete: a timeline that can be rewritten is not
    a record of what happened.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | Not this department's supervisor |
    | 404 | `not_found` | No such complaint |
    | 409 | `conflict` | The complaint has no department yet |
    | 422 | `validation_error` | An empty note, or one over 2000 characters |
    """
    service.add_note(client, complaint_id=complaint_id, body=body)
    return MessageResult(message="Note added.")


@router.post(
    "/complaints/{complaint_id}/chat",
    response_model=ComplaintThreadOpened,
    summary="Open the complaint's chat thread",
)
def open_complaint_chat(
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> ComplaintThreadOpened:
    """Open — or get — the one chat thread about this complaint. **No body.**

    A real thread in the existing chat dock (`kind = 'complaint'`), not a
    comments panel: the resident reaches it from their ordinary thread list and
    the department reaches it from the card. **One per complaint.** A second
    supervisor pressing the button joins the thread that exists rather than
    forking one the resident would have to watch two of, which is why this is
    idempotent and why the client calls it every time instead of remembering.

    Reading and writing it are the raiser's and the **department's** — any
    supervisor of the complaint's department, not only whoever opened it. A
    `closed` or `cancelled` complaint locks the thread: it still reads, and a
    send answers `409`, exactly as a finished job's channel does.

    `200` rather than `201` on purpose: the common case is getting the thread
    that already exists, and a status code that alternated between the two would
    be describing the database's history rather than the caller's request.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | Not this department's supervisor |
    | 404 | `not_found` | No such complaint |
    | 409 | `conflict` | The complaint has no department, no raiser, or is your own |
    """
    return service.open_chat(client, complaint_id=complaint_id)
