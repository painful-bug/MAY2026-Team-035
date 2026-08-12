"""The resident half of the complaint surface.

Separate from ``routers/complaints.py``, which is the admin workstream's file and
holds the two writes the admin screens perform (``PATCH /complaints/{id}`` and
``POST /complaints/{id}/comments``). Nothing here duplicates either: that router
has no complaint *read* at all, because the admin queue arrives inside
``GET /dashboard/snapshot``.

**Two guards, and the difference matters.** Reading, raising and marking read are
open to any active member. Reopening and confirming a resolution are
``resident``-only -- not because an admin could not press the button, but because
those two writes are the resident's verdict on the association's work, and an
admin confirming their own team's resolution on someone else's behalf is a record
that says something untrue. The database refuses it as well: both RPCs check
``is_own_membership`` against the person who raised the complaint, so the role
guard here is the early, clear error rather than the boundary.

**Every response is the complaint.** The three writes return the same
``ComplaintDetail`` a read returns, rather than an acknowledgement, because each
of them changes something the client could not compute -- a database-set SLA, a
restarted deadline, a status only the RPC decides.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import (
    get_active_membership,
    get_request_client,
    require_membership_role,
)
from app.domain.common_schemas import MessageResult, Page
from app.domain.resident_complaint_schemas import (
    ComplaintDetail,
    ComplaintSummary,
    ConfirmResolutionRequest,
    RaiseComplaintRequest,
    ReopenComplaintRequest,
)
from app.domain.schemas import MembershipContext
from app.services import resident_complaints_service as service
from supabase import Client

router = APIRouter(tags=["complaints"], dependencies=[Depends(require_csrf_unsafe)])

_resident_only = require_membership_role("resident")


@router.get(
    "/complaints",
    response_model=Page[ComplaintSummary],
    summary="List my complaints",
)
async def list_my_complaints(
    complaint_status: str | None = Query(
        None,
        alias="status",
        description="`Pending` | `In Progress` | `Resolved` | `Cancelled`.",
    ),
    category: str | None = Query(None, description="Exact category match."),
    unread: bool = Query(False, description="Only complaints with unseen changes."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> Page[ComplaintSummary]:
    """The caller's own complaints, newest first.

    **Always the caller's own, whatever their role.** An admin calling this gets
    the complaints they personally raised, not the community queue — that is
    `GET /dashboard/snapshot`. One route that returns a resident's list to one
    caller and the whole association's to another is the shape §5.1 exists to
    prevent.

    An unrecognised `status` is a `422`, not an empty page: a filter typo must
    not be indistinguishable from *you have no resolved complaints*.

    `status` matches on what a complaint **displays as**, not on one stored
    value. Two stored statuses render as `Resolved` and two as `In Progress`, so
    filtering by the word shown in the list returns every row the list shows
    under it.
    """
    return service.list_mine(
        client,
        membership_id=membership.id,
        status=complaint_status,
        category=category,
        unread_only=unread,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/complaints",
    response_model=ComplaintDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Raise a complaint",
)
async def raise_complaint(
    body: RaiseComplaintRequest,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> ComplaintDetail:
    """File a complaint against the caller's own membership.

    **The expected resolution time is computed here, not sent.** High → 24h,
    Medium → 48h, Low → 72h, applied by the database on insert. The rule used to
    live in a store slice, where a resident could have sent themselves a
    one-minute deadline and where the admin portal could not see it at all.

    Raising a complaint notifies every active admin and manager of the
    community — the first write in this backend to emit a notification, and the
    reason the notification substrate was built before this step.

    Attachments are **not** accepted yet, and since 2026-08-12 the form no
    longer collects them either -- promising a resident their photo reached
    somebody would be worse than not asking. `media` stays in the schema for
    the day an upload endpoint exists.
    """
    return service.raise_complaint(client, membership_id=membership.id, body=body)


@router.get(
    "/complaints/{complaint_id}",
    response_model=ComplaintDetail,
    summary="One of my complaints",
)
async def get_complaint(
    complaint_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> ComplaintDetail:
    """One complaint with its timeline and public comment thread.

    A complaint that exists but belongs to someone else is a `404`, identical to
    one that does not exist. The lookup filters on the membership rather than
    checking afterwards, so there is no code path in which the two could be
    told apart by response time or shape.

    **Internal comments never appear here.** The RLS policy in `0031` is what
    makes that true — the row does not arrive, so no later refactor of this API
    can accidentally include it. The repository also filters on `visibility`,
    which changes nothing about what is returned and makes the rule visible to
    someone reading the query rather than the policy.

    The timeline and the thread are bounded. When a complaint has more history
    than fits, the **recent** end is what is kept and `hasOlderEvents` /
    `hasOlderComments` say so — a bounded read that reports completeness it
    never checked is the one kind of truncation a client cannot detect.
    """
    return service.get_mine(
        client, membership_id=membership.id, complaint_id=complaint_id
    )


@router.post(
    "/complaints/{complaint_id}/reopen",
    response_model=ComplaintDetail,
    dependencies=[Depends(_resident_only)],
    summary="Reopen a resolved complaint",
)
async def reopen_complaint(
    body: ReopenComplaintRequest,
    complaint_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> ComplaintDetail:
    """Send a resolved complaint back, with a reason.

    Only from `Resolved`; anything else is a `422`. **The SLA clock restarts**,
    because a reopened complaint carrying its original deadline would be overdue
    the instant it reopened — a failure nobody committed.

    Any rating and feedback already recorded are cleared. They described a
    resolution that is no longer being claimed.

    Notifies the community's admins and managers.
    """
    return service.reopen(
        client,
        membership_id=membership.id,
        complaint_id=complaint_id,
        body=body,
    )


@router.post(
    "/complaints/{complaint_id}/resolution",
    response_model=ComplaintDetail,
    dependencies=[Depends(_resident_only)],
    summary="Confirm a resolution",
)
async def confirm_resolution(
    body: ConfirmResolutionRequest,
    complaint_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> ComplaintDetail:
    """Accept the resolution and rate it, which closes the complaint.

    **`Resolved` is what the association says; closed is what the resident
    agrees.** The baseline's enum has carried both since the beginning and
    nothing has used the distinction — `PATCH /complaints/{id}` treats them as
    one terminal state. Here they stop being synonyms: only this endpoint
    closes a complaint.

    The rating is required; the feedback is not.
    """
    return service.confirm_resolution(
        client,
        membership_id=membership.id,
        complaint_id=complaint_id,
        body=body,
    )


@router.post(
    "/complaints/{complaint_id}/read",
    response_model=MessageResult,
    summary="Clear the unread marker",
)
async def mark_complaint_read(
    complaint_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Record that the caller has seen the complaint as it now stands.

    Per membership, so an admin opening a complaint cannot clear the resident's
    marker. `complaint_read_state` has been in the schema since the baseline
    with nothing writing to it; this is the writer, and `isUnread` on the
    complaint is what it turns off.

    Idempotent, and a `200` whether or not a marker was there to clear.
    """
    service.mark_read(
        client, membership_id=membership.id, complaint_id=complaint_id
    )
    return MessageResult(message="Complaint marked read.")
