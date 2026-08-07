"""The notification feed.

The durable layer of §10.1, and the only one of the three a client can ask about
after the fact. The SSE frame tells a connected tab that something happened; the
push reaches a locked phone once; this is where either one is confirmed, and it
is what a resident who was offline for a day reads.

**Any active member, not residents only.** An admin gets notifications too --
``complaint.raised``, ``access_request.created`` -- and a feed that refused them
would mean building a second one later.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_active_membership, get_request_client
from app.domain.notification_schemas import NotificationFeed, NotificationReadResult
from app.domain.schemas import MembershipContext
from app.services import notifications_service
from supabase import Client

router = APIRouter(tags=["notifications"], dependencies=[Depends(require_csrf_unsafe)])


@router.get(
    "/notifications",
    response_model=NotificationFeed,
    summary="List the caller's notifications",
)
async def list_notifications(
    unread: bool = Query(
        False,
        description=(
            "Return only unread notifications. `unread` in the response counts "
            "the whole feed either way."
        ),
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> NotificationFeed:
    """The caller's own notifications, newest first.

    **The recipient is the resolved membership, and there is no parameter for
    it.** That is the ordinary tenancy rule here, but it is doubled in this case:
    ``notifications`` carries an RLS policy of its own
    (``is_own_membership``), so even a query that asked for someone else's rows
    would come back empty.

    ``unread`` in the response counts the entire feed rather than this page,
    because it is what a badge renders. Paging it would make the badge report a
    different number as the resident scrolled.
    """
    return notifications_service.list_feed(
        client,
        membership_id=membership.id,
        unread_only=unread,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationReadResult,
    summary="Mark one notification read",
)
async def mark_notification_read(
    notification_id: str,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> NotificationReadResult:
    """Mark one notification read, and report the unread count that is left.

    **404 for both a missing notification and someone else's.** The two are not
    distinguished on purpose: telling a caller that an id exists but is not
    theirs is how an id space gets enumerated.

    Idempotent -- marking an already-read notification read is a 200, and the
    original ``read_at`` is kept rather than moved.
    """
    return notifications_service.mark_read(
        client,
        membership_id=membership.id,
        notification_id=notification_id,
    )


@router.post(
    "/notifications/read-all",
    response_model=NotificationReadResult,
    summary="Mark every notification read",
)
async def mark_all_notifications_read(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> NotificationReadResult:
    """Clear the badge.

    ``marked`` is how many rows actually moved, so calling this twice returns a
    second answer of ``0`` rather than an error. ``unread`` is re-read afterwards
    instead of assumed to be zero: a notification can arrive between the update
    and the count, and a badge told "0" while one is already waiting stays wrong
    until the next fetch.
    """
    return notifications_service.mark_all_read(client, membership_id=membership.id)
