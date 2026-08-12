"""Data access for the notification feed.

Reads go through ``notification_overview``; writes go through the two SECURITY
DEFINER functions in ``0030``, as amended by ``0041``. Both halves of that are
load-bearing here in a way they are not everywhere else in this codebase, because
``notifications`` is the first table this workstream touches that carries an
**RLS policy of its own**:

    notifications_read_own -- using (recipient_profile_id = auth.uid())

So the ``recipient_profile_id`` filter below is not the security boundary the way
the community filter is on the amenity catalogue. It is there to ask a narrower
question than the policy already answers, and if it were deleted the database
would still refuse to return anyone else's rows. That is the right way round: the
API is what makes the query efficient, the database is what makes it correct.

**The recipient is a person, not a membership** (``0041``). That is what lets a
service provider who has registered and not yet been hired have a feed at all --
they hold no membership anywhere, so under ``0030``'s shape there was no row that
could address them. It also collapses what used to be two counts into one: a
caller with memberships in four communities has one feed and one badge, rather
than four of each summed by the caller.

The same is true of the writes. ``mark_notification_read`` re-checks ownership
inside the function, so knowing a notification id is not enough to mark someone
else's read -- which is exactly the attack a plain PostgREST ``update`` filtered
in Python would allow the day someone forgets the second predicate.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_FEED = "notification_overview"

_FEED_SELECT = "id, kind, payload, read_at, is_unread, created_at"


def list_feed(
    client: Client,
    *,
    profile_id: str,
    unread_only: bool,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """One page of the caller's feed, newest first, with the total.

    Newest first is not a preference: a feed is read from the top and a resident
    who has been away for a week wants the visitor at the gate now, not the
    notice from last Tuesday.
    """
    query = (
        client.table(_FEED)
        .select(_FEED_SELECT, count="exact")
        .eq("recipient_profile_id", profile_id)
    )
    if unread_only:
        query = query.eq("is_unread", True)

    response = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def unread_count(client: Client, *, profile_id: str) -> int:
    """How many unread notifications the caller has, across the whole feed.

    A separate query rather than a field on the page, because the badge counts
    the feed and the page counts the page. Asked with ``head=True`` so PostgREST
    returns the count and no rows -- the number is the entire answer.

    One query for a caller in any number of communities. ``0041`` removed the
    variant that took a list of memberships and summed them: the worker portal
    needed it only because the recipient used to be a membership, and a badge
    assembled from several counts is a badge that can disagree with the feed it
    sits on.
    """
    response = (
        client.table(_FEED)
        .select("id", count="exact", head=True)
        .eq("recipient_profile_id", profile_id)
        .eq("is_unread", True)
        .execute()
    )
    return response.count or 0


def mark_read(client: Client, *, notification_id: str) -> bool:
    """Mark one notification read (RPC). False when it was not the caller's.

    False rather than an error, and the service turns it into a 404. A caller
    who guesses an id should not be able to learn from the response whether it
    exists.
    """
    try:
        response = client.rpc(
            "mark_notification_read", {"p_notification_id": notification_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not mark the notification read."
        ) from exc
    return bool(response.data)


def mark_all_read(client: Client) -> int:
    """Clear the badge (RPC). Returns how many rows moved.

    No argument. The RPC reads ``auth.uid()`` itself, so the set it clears and
    the set :func:`unread_count` counts are the same set by construction --
    ``0041`` closed the gap where the first was one membership's rows and the
    second was the whole feed.
    """
    try:
        response = client.rpc("mark_all_notifications_read", {}).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not mark the notifications read."
        ) from exc
    return int(response.data or 0)
