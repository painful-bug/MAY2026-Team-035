"""Gate operations — posts, shifts, the registers, verification and exports.

**The guard here is the opposite of the worker portal's, and deliberately so.**
``worker_jobs.py`` and ``worker_schedule.py`` declare no role at all, because a
service person's surface is cross-community by construction. A gate is not: a
register entry, a shift and an incident are each a fact about exactly one
society. So this router goes back to the house shape, and the community is
resolved from the caller's own membership rather than accepted from a request
body — ``ADMIN_DASHBOARD_DESIGN.md`` §10.

``require_gate_membership`` is a local dependency rather than
``require_membership_role`` and the difference is small but real:
``require_membership_role`` reads the role off ``MembershipSet.default``, and a
guard who *lives* in one society and *works* the gate of another has a default
membership of ``resident``. Picking the first membership that holds a gate role
answers the question the route is actually asking. Its limit is stated honestly
below: a guard employed by two societies gets the first of the two, ordered by
``is_default_community``.

Two levels of permission underneath, both in ``0040`` §7 and neither restated
here: recording is any gate staff, and the roster is the security manager's.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_membership_set, get_request_client
from app.core.exceptions import AuthorizationError
from app.domain.schemas import MembershipContext, MembershipSet
from app.domain.security_schemas import (
    CreateShiftRequest,
    GateVerification,
    GateVerifyRequest,
    MaterialMovement,
    OfflineBundle,
    OfflineReconcileRequest,
    OfflineReconcileResult,
    RecordIncidentRequest,
    RecordMovementRequest,
    RecordTankerRequest,
    ReturnMovementRequest,
    RosterEntry,
    SecurityIncident,
    SecurityPost,
    SecurityShift,
    UpdateIncidentRequest,
    UpdateShiftRequest,
    UpdateTankerRequest,
    UpsertPostRequest,
    WaterTankerLog,
)
from app.services import security_service as service
from supabase import Client

#: `security` is a guard; `admin` and `manager` are the two roles that run a
#: community and its departments. A security *manager* is the first of these,
#: not the third — D3 made rank and role separate axes — so all three are here
#: and the finer distinction is `0040`'s to make.
_GATE_ROLES = ("security", "admin", "manager")

router = APIRouter(
    prefix="/security",
    tags=["security-operations"],
    dependencies=[Depends(require_csrf_unsafe)],
)


def require_gate_membership(
    memberships: MembershipSet = Depends(get_membership_set),
) -> MembershipContext:
    """The caller's membership at a gate they staff, or 403.

    Scans the set rather than taking ``.default``, because the two are different
    for exactly the population this router serves. The order is
    ``is_default_community desc, created_at`` — the order
    ``get_membership_set`` already applies — so a guard with two gates gets
    their default one. That is a real limit and there is no request field that
    could resolve it without becoming a community id in a body; if it ever
    matters, the honest fix is a header the client sets from a gate picker, and
    `0040` would still check it.
    """
    for membership in memberships.memberships:
        if membership.role in _GATE_ROLES:
            return membership
    raise AuthorizationError(
        "Only gate staff may use this.", code="community_role_required"
    )


# --------------------------------------------------------------------------
# Posts
# --------------------------------------------------------------------------


@router.get("/posts", response_model=list[SecurityPost], summary="Guard posts")
async def list_posts(
    _: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
    include_inactive: bool = Query(False, alias="includeInactive"),
) -> list[SecurityPost]:
    """Every post in the caller's community, by name.

    Inactive posts are hidden unless asked for. A post is deactivated rather
    than deleted, because a register entry recorded two years ago still names
    it and `US-3.6` is a story about reading records that old.
    """
    return service.list_posts(client, include_inactive=include_inactive)


@router.post(
    "/posts",
    response_model=SecurityPost,
    status_code=status.HTTP_201_CREATED,
    summary="Add a guard post",
)
async def create_post(
    body: UpsertPostRequest,
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> SecurityPost:
    """Create a post.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not a security manager of this community |
    | 409 | `conflict` | A live post already has that name here |
    | 422 | `post_name_required` | No name was given |
    """
    return service.save_post(client, membership_id=membership.id, body=body)


@router.patch(
    "/posts/{post_id}", response_model=SecurityPost, summary="Change a guard post"
)
async def update_post(
    body: UpsertPostRequest,
    post_id: str = Path(...),
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> SecurityPost:
    """Rename, relocate or deactivate a post.

    Every field is optional and an omitted one is left alone rather than
    blanked — a form with six fields and one change should not have to send the
    other five back.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not a security manager of this community |
    | 404 | `not_found` | No such post here |
    """
    return service.save_post(
        client, membership_id=membership.id, body=body, post_id=post_id
    )


# --------------------------------------------------------------------------
# Shifts
# --------------------------------------------------------------------------


@router.get("/shifts", response_model=list[SecurityShift], summary="The roster")
async def list_shifts(
    _: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
    starts_from: datetime | None = Query(None, alias="from"),
    starts_to: datetime | None = Query(None, alias="to"),
    shift_status: str | None = Query(None, alias="status"),
    post_id: str | None = Query(None, alias="postId"),
    shift_id: str | None = Query(None, alias="shiftId"),
) -> list[SecurityShift]:
    """Shifts overlapping the range, soonest first.

    The range matches on **overlap** rather than on start. A night shift that
    began at 22:00 yesterday is the shift a guard on duty at 01:00 is looking
    at, and filtering by start alone would drop exactly that row.

    **`shiftId` is here for arrivals from a notification.**
    `security_shift.assigned` (`0043`) links a guard to `/security/shifts`
    carrying the id of the shift handed to them, and `0045` lets a departure be
    scheduled weeks out — so that row is routinely outside whatever window the
    screen chose. Widening the window is not the answer: the list is capped at
    200 rows ordered by start, so a wider range on a busy gate can truncate away
    the very row that was asked for. One id, one row, no window.

    An unknown id is an **empty list, not a `404`** — the same answer as a
    window with nothing in it, so this cannot be used to test whether a shift
    exists somewhere the caller cannot see.
    """
    return service.list_shifts(
        client,
        starts_from=starts_from,
        starts_to=starts_to,
        status=shift_status,
        post_id=post_id,
        shift_id=shift_id,
    )


@router.post(
    "/shifts",
    response_model=SecurityShift,
    status_code=status.HTTP_201_CREATED,
    summary="Put a guard on a post",
)
async def create_shift(
    body: CreateShiftRequest,
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> SecurityShift:
    """Roster one guard onto one post for one window.

    **A guard cannot be in two places at once**, and that is a GiST exclusion
    constraint rather than a check in this process — the same construct
    `work_order_assignments` carries, for the same reason. The overlap is
    refused *by name* before the constraint refuses it by number, so the answer
    is a sentence rather than a `23P01`.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not a security manager of this community |
    | 404 | `not_found` | No such staff member or post here |
    | 409 | `conflict` | That guard is already on a shift then |
    | 422 | `validation_error` | The shift ends before it starts |
    """
    return service.create_shift(client, membership_id=membership.id, body=body)


@router.patch(
    "/shifts/{shift_id}", response_model=SecurityShift, summary="Change a shift"
)
async def update_shift(
    body: UpdateShiftRequest,
    shift_id: str = Path(...),
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> SecurityShift:
    """Move a shift, or start and end one.

    **A guard may send `status` alone for their own shift** — which is what
    *End Shift & Logout* does, a control `SecurityLayout.jsx` has offered since
    before this table existed. Any other field, or anybody else's shift, is the
    security manager's. `0040` decides which of the two applies from the shape
    of the request rather than from a flag the client sets, because a flag the
    client sets is a flag the client can lie about.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | Not yours, and you do not run the roster |
    | 404 | `not_found` | No such shift here |
    | 422 | `unknown_shift_status` | Not one of the five statuses |
    """
    return service.update_shift(
        client, membership_id=membership.id, shift_id=shift_id, body=body
    )


@router.get(
    "/roster",
    response_model=list[RosterEntry],
    summary="Guards the shift form may offer",
)
async def list_roster(
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> list[RosterEntry]:
    """Active security-department staff of the caller's community, by name.

    Exists for one form: `POST /security/shifts` needs a `staffAssignmentId`,
    and the security manager who fills it in — a `security` membership ranked
    `manager` or `supervisor` — cannot reach the hiring surface's roster reads,
    which guard on the *membership* role. `0047`'s function answers with the
    same predicate the shift write already trusts.

    Deliberately narrower than what the shift RPC accepts: only staff of
    departments whose `kind` is `security`. A picker that offered the plumbing
    roster would be offering a mistake.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not a security manager of this community |
    """
    return service.list_roster(client, membership_id=membership.id)


# --------------------------------------------------------------------------
# The material register — US-3.3
# --------------------------------------------------------------------------


@router.get(
    "/material-movements",
    response_model=list[MaterialMovement],
    summary="The inward/outward register",
)
async def list_movements(
    _: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
    starts_from: datetime | None = Query(None, alias="from"),
    starts_to: datetime | None = Query(None, alias="to"),
    direction: str | None = Query(None),
    outstanding: bool | None = Query(None),
) -> list[MaterialMovement]:
    """Register entries, newest first.

    `outstanding=true` is the report the returnable column exists for: things
    that went out and have not come back. `isOverdue` on each row is that same
    fact past its expected return date, derived in SQL rather than stored — a
    stored flag needs somebody to flip it at midnight and is wrong until they
    do.
    """
    return service.list_movements(
        client,
        starts_from=starts_from,
        starts_to=starts_to,
        direction=direction,
        outstanding=outstanding,
    )


@router.post(
    "/material-movements",
    response_model=MaterialMovement,
    status_code=status.HTTP_201_CREATED,
    summary="Record a material movement",
)
async def record_movement(
    body: RecordMovementRequest,
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> MaterialMovement:
    """Write one entry into the register. `US-3.3`.

    **`sourceClientId` makes this safe to retry.** A gate device that queued an
    entry while disconnected and lost its connection again mid-upload can send
    the whole queue a second time: the id it generated is unique per community,
    and a replay returns the original row rather than a conflict.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not on duty in this community |
    | 422 | `unknown_direction` | Not `inward` or `outward` |
    | 422 | `not_returnable` | A return date on a non-returnable item |
    """
    return service.record_movement(client, membership_id=membership.id, body=body)


@router.post(
    "/material-movements/{movement_id}/return",
    response_model=MaterialMovement,
    summary="A returnable item came back",
)
async def return_movement(
    body: ReturnMovementRequest,
    movement_id: str = Path(...),
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> MaterialMovement:
    """Close out a returnable entry.

    Idempotent: the second guard to press *returned* is telling the truth and
    the row already says so, so it is a `200` with the recorded time rather than
    a conflict about one.

    | Status | Code | Cause |
    |---|---|---|
    | 404 | `not_found` | No such entry here |
    | 409 | `conflict` | That entry was not recorded as returnable |
    """
    return service.mark_returned(
        client, membership_id=membership.id, movement_id=movement_id, body=body
    )


# --------------------------------------------------------------------------
# The tanker log — US-3.4
# --------------------------------------------------------------------------


@router.get(
    "/water-tankers",
    response_model=list[WaterTankerLog],
    summary="The water tanker log",
)
async def list_tankers(
    _: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
    starts_from: datetime | None = Query(None, alias="from"),
    starts_to: datetime | None = Query(None, alias="to"),
    on_site: bool | None = Query(None, alias="onSite"),
) -> list[WaterTankerLog]:
    """Tanker entries, newest arrival first. `onSite=true` is *still here*."""
    return service.list_tankers(
        client, starts_from=starts_from, starts_to=starts_to, on_site=on_site
    )


@router.post(
    "/water-tankers",
    response_model=WaterTankerLog,
    status_code=status.HTTP_201_CREATED,
    summary="Log a water tanker",
)
async def record_tanker(
    body: RecordTankerRequest,
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> WaterTankerLog:
    """One tanker at the gate. `US-3.4`.

    The number is stored upper-cased, because a plate written down by two guards
    on two shifts is one vehicle and a report that splits it into two is the
    report nobody trusts.

    `departedAt` may be sent now if the tanker has already left — the usual case
    is to omit it and `PATCH` later.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not on duty in this community |
    | 422 | `validation_error` | No tanker number |
    """
    return service.record_tanker(client, membership_id=membership.id, body=body)


@router.patch(
    "/water-tankers/{log_id}",
    response_model=WaterTankerLog,
    summary="Record a departure",
)
async def update_tanker(
    body: UpdateTankerRequest,
    log_id: str = Path(...),
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> WaterTankerLog:
    """The tanker left, or the volume was mis-keyed.

    | Status | Code | Cause |
    |---|---|---|
    | 404 | `not_found` | No such entry here |
    | 422 | `validation_error` | It cannot leave before it arrived |
    """
    return service.update_tanker(
        client, membership_id=membership.id, log_id=log_id, body=body
    )


# --------------------------------------------------------------------------
# Incidents
# --------------------------------------------------------------------------


@router.get(
    "/incidents", response_model=list[SecurityIncident], summary="Security incidents"
)
async def list_incidents(
    _: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
    starts_from: datetime | None = Query(None, alias="from"),
    starts_to: datetime | None = Query(None, alias="to"),
    incident_status: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
) -> list[SecurityIncident]:
    """Incidents, most recent first."""
    return service.list_incidents(
        client,
        starts_from=starts_from,
        starts_to=starts_to,
        status=incident_status,
        severity=severity,
    )


@router.post(
    "/incidents",
    response_model=SecurityIncident,
    status_code=status.HTTP_201_CREATED,
    summary="File a security incident",
)
async def record_incident(
    body: RecordIncidentRequest,
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> SecurityIncident:
    """Record something that happened.

    This replaces a real gap rather than adding a feature: the form already
    exists on the security dashboard and currently appends an interpolated
    *string* to an activity feed, which is the same defect
    `DECISIONS_NEEDED` B2 names on the complaint assignee.

    **`high` and `critical` notify the community's admins and managers**; `low`
    and `medium` are a record. That line is where `ARCHITECTURE.md`'s rule
    lands here — a thing that happened is not automatically a thing worth a
    notification.

    `category` is one of `Security concern`, `Medical emergency`, `Fire alarm`,
    `Unauthorized access`, `Property damage`, `Other`. An unrecognised one is a
    422 naming the six rather than a silent fall back to `Other`, because a
    typed category that quietly becomes *Other* is a report with a hole in it.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not on duty in this community |
    | 422 | `unknown_incident_category` | Not one of the six |
    | 422 | `unknown_severity` | Not one of the four |
    """
    return service.record_incident(client, membership_id=membership.id, body=body)


@router.patch(
    "/incidents/{incident_id}",
    response_model=SecurityIncident,
    summary="Acknowledge or resolve an incident",
)
async def update_incident(
    body: UpdateIncidentRequest,
    incident_id: str = Path(...),
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> SecurityIncident:
    """Move an incident along, or re-grade it.

    Moving it back off `resolved` clears `resolvedAt`, so the timestamp never
    outlives the status that justified it.

    | Status | Code | Cause |
    |---|---|---|
    | 404 | `not_found` | No such incident here |
    | 422 | `unknown_incident_status` | Not `open`, `acknowledged` or `resolved` |
    """
    return service.update_incident(
        client, membership_id=membership.id, incident_id=incident_id, body=body
    )


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


@router.post(
    "/gate/verify", response_model=GateVerification, summary="May this visitor in"
)
async def verify_credential(
    body: GateVerifyRequest,
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> GateVerification:
    """Check a scanned QR or a typed security code, and act on it.

    **This is the half of `US-3.1` that was missing.** `0032` has minted and
    stored `code_hash` and `pass_hash` since the visitor passes shipped, and
    until now nothing ever read one back — so a resident could issue a pass and
    a gate could not check it.

    **A refusal is a `200` with a verdict, not a `4xx`.** The guard asked a
    question and got an answer; making *that code is not recognised* an error
    status would split one act across the client's success and failure paths.
    The `4xx` codes here are about the guard, not the visitor.

    **The second scan is the way out.** Presenting the same credential again
    checks the visitor out, which is why there is no separate check-out call: at
    a barrier there is one action, and it is *scan*.

    | `verdict` | Means |
    |---|---|
    | `admitted` | Let them in. The resident is notified |
    | `departed` | They were already inside; now checked out |
    | `refused` | Cancelled, rejected, not yet approved, or already closed |
    | `not_yet_valid` | Valid, but later — `detail` says so |
    | `expired` | The window has passed |
    | `not_found` | No such code at this gate |

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not on duty in this community |
    | 422 | `validation_error` | Nothing was presented |
    """
    return service.verify(client, membership_id=membership.id, body=body)


@router.get(
    "/offline-bundle", response_model=OfflineBundle, summary="Cache for an outage"
)
async def offline_bundle(
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
    hours: int = Query(12, ge=1, le=48),
) -> OfflineBundle:
    """The passes this gate may need while disconnected. `US-3.5`.

    **Hashes only.** There is no plaintext code anywhere in this database to
    hand out — the resident saw theirs once, at creation. The device hashes what
    it scans with SHA-256 and compares locally.

    **The bundle is not signed, and that is a decision rather than an
    omission.** A signature the device verifies against a key the device holds
    is theatre: the same person who can edit the cache can delete the check
    beside it, because both are JavaScript on their machine. What makes an
    offline admission safe is that it is **provisional until reconciled** — see
    `POST /security/offline-reconcile`, which re-runs the real verification
    server-side and records its own verdict beside the device's claim.

    Honest about what this discloses: a list of live pass hashes for one
    community, and a six-digit code hashed with SHA-256 is a 10⁶ search space,
    so the hashing obscures nothing from whoever holds the file. That is
    acceptable *here* because the gate device is already authorised to admit
    exactly those visitors — and it is why this read is gate staff only and
    capped at 48 hours.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not on duty in this community |
    """
    return service.offline_bundle(
        client,
        membership_id=membership.id,
        community_id=membership.community_id,
        hours=hours,
    )


@router.post(
    "/offline-reconcile",
    response_model=OfflineReconcileResult,
    summary="Replay what the gate did offline",
)
async def offline_reconcile(
    body: OfflineReconcileRequest,
    membership: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
) -> OfflineReconcileResult:
    """Submit the queue an offline gate built, and get the server's verdicts.

    **Idempotent per entry, on the device's own `sourceClientId`.** A device
    that lost its connection mid-upload sends the whole queue again; entries
    already reconciled come back with `wasReplay: true` and their original
    verdict, untouched. That matters more here than anywhere else in this
    feature, because re-running the verification on a replay would check the
    visitor *out* — a second scan is a departure.

    **Every entry is its own transaction.** A queue of forty in which the
    eleventh is malformed reconciles the other thirty-nine, which is the whole
    point of reconciling rather than submitting: the device has already
    discarded its copy by then.

    A rejected entry is not an error either. It is a row in
    `offline_reconcile_log` holding the device's claim and the server's answer
    side by side, readable by the community's admins, and it is what makes an
    unsigned bundle safe.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not on duty in this community |
    | 422 | `validation_error` | An entry with no client id |
    """
    return service.reconcile(client, membership_id=membership.id, body=body)


# --------------------------------------------------------------------------
# Exports — US-3.6
# --------------------------------------------------------------------------


@router.get(
    "/exports/{dataset}",
    response_class=Response,
    summary="Download a register as CSV",
    responses={
        200: {
            "content": {"text/csv": {"schema": {"type": "string"}}},
            "description": "The dataset as RFC 4180 CSV, oldest row first.",
        }
    },
)
async def export_dataset(
    dataset: str = Path(...),
    _: MembershipContext = Depends(require_gate_membership),
    client: Client = Depends(get_request_client),
    starts_from: datetime | None = Query(None, alias="from"),
    starts_to: datetime | None = Query(None, alias="to"),
) -> Response:
    """One register as CSV. `US-3.6`.

    `dataset` is `material-movements`, `water-tankers`, `incidents` or
    `shifts`. **One route rather than four**, because the four differ in their
    columns and in nothing else: four routes would be four copies of the same
    range validation, the same `Content-Disposition` and the same writer, and
    the fifth dataset would arrive as a fifth copy.

    **Oldest row first**, unlike every list on this surface. A screen wants the
    most recent thing at the top; a spreadsheet opened for an audit reads
    forwards through time.

    **Retention needs no implementation and the story is still served.** Nothing
    this project writes is ever aged out, so *"six months, one year, or longer"*
    is answered by `from` and `to` rather than by a policy — which is why
    `US-3.6` moves on this endpoint alone.

    Cells beginning `=`, `+`, `-` or `@` are prefixed with an apostrophe. Those
    are formula leaders in every spreadsheet, and every one of them is reachable
    from a text field a guard types at the gate — so without it an export is a
    path from *anyone who can reach the barrier* to *code that runs when the
    manager opens the audit*.

    | Status | Code | Cause |
    |---|---|---|
    | 403 | `forbidden` | You are not on duty in this community |
    | 422 | `unknown_dataset` | Not one of the four |
    """
    body = service.export_csv(
        client, dataset=dataset, starts_from=starts_from, starts_to=starts_to
    )
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{dataset}.csv"',
        },
    )
