"""The notification feed: the durable half of §10's three layers.

``docs/design/RESIDENT_BACKEND_DESIGN.md`` §5.8 and §10.1. The rule the whole
design rests on:

    Every user-visible event writes a `notifications` row first. SSE and Web
    Push are two *deliveries* of that row, never the record of it.

SSE is at-most-once and connection-scoped, and a push may simply not arrive. A
resident whose phone was locked when a visitor reached the gate must still find
out, so the row is the truth and this module is how it is read.

**Rendering happens once, here.** ``render`` turns a stored ``payload`` into the
three strings a human sees, and both transports call it -- the feed row through
``_to_item`` and the lock-screen line through ``push_service``. That is a rule
from §10.8, not a convenience: two renderers means the notification in the list
and the notification on the lock screen can tell different stories about the same
event, and the resident has no way to know which one is stale.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.domain.notification_schemas import (
    NotificationFeed,
    NotificationItem,
    NotificationReadResult,
)
from app.repositories import notifications_repository as repo
from supabase import Client

#: Rendered when a notification arrives with no title of its own. The kinds are
#: the vocabulary in §10.3; the strings are what a resident sees if the RPC that
#: wrote the row said nothing.
#:
#: This exists because the writers are not all built yet. Steps 4-6 add the RPCs
#: that call `notify_member`, and a kind whose author forgot a title should
#: produce a dull feed row rather than a blank one -- an empty line in a feed
#: reads as a bug in the app, which is a worse first impression than a generic
#: sentence.
_FALLBACK_TITLES: dict[str, str] = {
    "complaint.status_changed": "Your complaint was updated",
    "complaint.commented": "New comment on your complaint",
    "complaint.resolved": "Your complaint was resolved",
    "complaint.raised": "A complaint was raised",
    "complaint.reopened": "A complaint was reopened",
    "complaint.resolution_confirmed": "A resident confirmed a resolution",
    "visitor.approval_requested": "A visitor is waiting at the gate",
    "visitor.checked_in": "Your visitor has arrived",
    "amenity.booking_decided": "Your booking request was decided",
    "amenity.booking_requested": "A new booking request",
    "invoice.issued": "You have a new bill",
    "invoice.due_soon": "A bill is due soon",
    "notice.published": "New notice from your community",
    "payment.succeeded": "Payment successful",
    "payment.failed": "Payment failed",
    "payment.recorded": "A payment was recorded",
    "access_request.created": "Someone asked to join",
}

#: The last resort. A kind nobody has seen before still renders a row, because
#: the alternative -- hiding it -- means a notification the system decided to
#: send and the resident never learns exists.
_GENERIC_TITLE = "Update from your community"


def _text(value: object) -> str:
    """A payload field as a string, and never ``None``."""
    return str(value).strip() if value not in (None, "") else ""


def render(kind: str, payload: dict[str, Any] | None) -> tuple[str, str, str]:
    """``(title, body, url)`` for one notification.

    The **only** place a notification becomes words. Reads three keys and no
    others, which is also how §10.8's one hard rule is enforced: the visitor
    security code may never appear in a push body, and it cannot, because
    nothing here copies a field it was not asked for. A writer that puts a
    secret in ``payload`` under any other key finds it stays in the database.
    """
    data = payload if isinstance(payload, dict) else {}
    title = _text(data.get("title")) or _FALLBACK_TITLES.get(kind, _GENERIC_TITLE)
    return title, _text(data.get("body")), _text(data.get("url"))


def _to_item(row: dict[str, Any]) -> NotificationItem:
    kind = _text(row.get("kind"))
    title, body, url = render(kind, row.get("payload"))
    return NotificationItem(
        id=row["id"],
        kind=kind,
        title=title,
        body=body,
        url=url,
        # Computed by the view rather than from `read_at` here, so that "unread"
        # is decided in one place for every reader of this data.
        is_unread=bool(row.get("is_unread")),
        created_at=row["created_at"],
    )


def list_feed(
    client: Client,
    *,
    membership_id: str,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> NotificationFeed:
    """One page of the caller's feed, plus the unread total.

    Paged, unlike the amenity catalogue: a feed grows without bound and the
    screen that reads it shows the newest handful. ``unread`` counts the whole
    feed rather than the page, which is why it takes its own query -- a badge
    that said "3" because the first page happened to hold three unread rows
    would be wrong the moment anyone scrolled.
    """
    offset = (page - 1) * page_size
    rows, total = repo.list_feed(
        client,
        membership_id=membership_id,
        unread_only=unread_only,
        offset=offset,
        limit=page_size,
    )
    items = [_to_item(row) for row in rows]
    return NotificationFeed(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(items) < total,
        unread=repo.unread_count(client, membership_id=membership_id),
    )


def mark_read(
    client: Client, *, membership_id: str, notification_id: str
) -> NotificationReadResult:
    """Mark one notification read.

    The RPC returns false both for a notification that does not exist and for one
    belonging to somebody else, and this raises the same 404 either way. That is
    deliberate: distinguishing them would let a caller enumerate ids and learn
    which ones are real.

    Idempotent. Marking an already-read notification read is a 200 with
    ``marked: 1`` -- the client asked for a state and got it, and a client that
    double-taps should not see an error.
    """
    if not repo.mark_read(client, notification_id=notification_id):
        raise NotFoundError("Notification not found.")
    return NotificationReadResult(
        marked=1,
        unread=repo.unread_count(client, membership_id=membership_id),
    )


def mark_all_read(client: Client, *, membership_id: str) -> NotificationReadResult:
    """Clear the badge.

    ``unread`` is re-read rather than assumed to be zero. A notification can
    arrive between the update and this count, and reporting zero when one is
    already waiting would leave the badge wrong until the next fetch.
    """
    marked = repo.mark_all_read(client, membership_id=membership_id)
    return NotificationReadResult(
        marked=marked,
        unread=repo.unread_count(client, membership_id=membership_id),
    )
