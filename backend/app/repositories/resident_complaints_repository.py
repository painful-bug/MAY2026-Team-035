"""Data access for the resident complaint surface.

Reads go through ``complaint_overview`` (``0031``); writes go through four
SECURITY DEFINER functions. That split is not stylistic. Every write here has to
touch the complaint row, its append-only timeline and -- since ``0031`` -- a
notification, and PostgREST has no client-side transaction. A repository that
did it in three calls could leave a complaint whose history has a gap, or one
nobody was told about.

**The ownership filter below is not the security boundary.** ``0031`` puts a
policy on ``complaints`` itself:

    complaints_read -- using (is_community_admin(community_id)
                              or is_own_membership(raised_by_membership_id))

so deleting the ``raised_by_membership_id`` predicate would not leak a
neighbour's complaint to a resident. It is there because *this endpoint* answers
a narrower question than the policy does -- "mine", not "everything I may see" --
and because an admin calling the same route should get their own complaints, not
the whole queue. Same arrangement as the notification feed: the API makes the
query narrow, the database makes it safe.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_OVERVIEW = "complaint_overview"
_EVENTS = "complaint_events"
_COMMENTS = "complaint_comments"

_SUMMARY_SELECT = (
    "id, title, category, status, priority, location, progress_percent,"
    "assignee_label, created_at, updated_at, last_activity_at,"
    "expected_resolution_at, resolved_at, is_overdue, is_unread,"
    "reopened_count, comment_count"
)

_DETAIL_SELECT = f"{_SUMMARY_SELECT}, description, resolution_rating, resident_feedback"

#: The timeline and the comment thread are read whole. A complaint accumulates
#: events at human speed -- a handful over its life -- so paging them would add a
#: parameter to every detail read for a case that does not arise. The bound is
#: here so "does not arise" is an expectation rather than an assumption.
_THREAD_LIMIT = 200

#: One row past the bound, so a full page can be told from an exactly-full one.
#: The amenity catalogue asks for ``count="exact"`` instead, because its envelope
#: has a ``total`` to fill; here the only question is *is anything missing*, and
#: a sentinel row answers it without making the database count.
_THREAD_PROBE = _THREAD_LIMIT + 1


def _bounded(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """Trim a probe read back to the bound and say whether it was trimmed."""
    if len(rows) > _THREAD_LIMIT:
        return rows[:_THREAD_LIMIT], True
    return rows, False


def list_mine(
    client: Client,
    *,
    membership_id: str,
    statuses: list[str] | None,
    category: str | None,
    unread_only: bool,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """One page of the caller's own complaints, newest first, with the total.

    ``statuses`` arrives already translated to storage vocabulary, and is a
    *list* because the translation is one-to-many: ``Resolved`` on the wire is
    ``resolved`` or ``closed`` in the column. This module does no vocabulary
    work, so a caller cannot reach the database with a word the enum has never
    heard of.
    """
    query = (
        client.table(_OVERVIEW)
        .select(_SUMMARY_SELECT, count="exact")
        .eq("raised_by_membership_id", membership_id)
    )
    if statuses:
        query = query.in_("status", statuses)
    if category:
        query = query.eq("category", category)
    if unread_only:
        query = query.eq("is_unread", True)

    response = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def get_mine(
    client: Client, *, membership_id: str, complaint_id: str
) -> dict[str, Any] | None:
    """One complaint of the caller's, or ``None``.

    ``None`` rather than an exception, so the service decides what a miss means.
    It always means 404 -- including when the row exists and belongs to someone
    else, which is why the membership predicate is part of the lookup rather
    than a check afterwards. A caller must not be able to tell "not yours" from
    "not there".
    """
    rows = (
        client.table(_OVERVIEW)
        .select(_DETAIL_SELECT)
        .eq("id", complaint_id)
        .eq("raised_by_membership_id", membership_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def timeline(
    client: Client, *, complaint_id: str
) -> tuple[list[dict[str, Any]], bool]:
    """The complaint's most recent events, newest first, and whether older
    ones were left behind.

    **Read newest-first even though a timeline is displayed oldest-first.** The
    order and the bound are not independent choices: ordering ascending and
    stopping at 200 keeps the *opening* of a long complaint and discards
    everything that has happened since. On the one screen where the bound would
    ever bite -- a complaint that has been running for months -- that is exactly
    inverted, and it fails quietly: the resident sees a complaint frozen at the
    day they raised it. The service reverses these rows for display.
    """
    return _bounded(
        client.table(_EVENTS)
        .select("id, event_type, actor_label, payload, created_at")
        .eq("complaint_id", complaint_id)
        .order("created_at", desc=True)
        .limit(_THREAD_PROBE)
        .execute()
        .data
        or []
    )


def comments(
    client: Client, *, complaint_id: str
) -> tuple[list[dict[str, Any]], bool]:
    """The most recent public comments, newest first, and whether older ones
    were left behind.

    Same reasoning as ``timeline``: the newest end of a conversation is the end
    worth keeping when only part of it fits.

    ``visibility`` is filtered here *and* by the RLS policy. The policy is what
    makes it true; this predicate is what makes it obvious to the next person
    reading the query, and it costs one indexed comparison.
    """
    return _bounded(
        client.table(_COMMENTS)
        .select("id, body, author_label, created_at")
        .eq("complaint_id", complaint_id)
        .eq("visibility", "public")
        .order("created_at", desc=True)
        .limit(_THREAD_PROBE)
        .execute()
        .data
        or []
    )


def raise_complaint(
    client: Client,
    *,
    membership_id: str,
    title: str,
    description: str,
    category: str,
    priority: str,
    location: str,
    department_id: str | None = None,
) -> str:
    """Create a complaint (RPC). Returns its id.

    ``department_id`` is the resident's guess at whose job this is, and it is
    only ever a fallback: the RPC resolves the category first and uses this
    when the category names no department. Passing ``None`` -- which is what
    "Not sure" sends -- is the ordinary case, not an error.
    """
    try:
        response = client.rpc(
            "raise_complaint",
            {
                "p_membership_id": membership_id,
                "p_title": title,
                "p_description": description,
                "p_category": category,
                "p_priority": priority,
                "p_location": location,
                "p_department_id": department_id,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not raise the complaint.") from exc
    return str(response.data)


def reopen(client: Client, *, complaint_id: str, reason: str) -> None:
    """Reopen a resolved complaint (RPC)."""
    try:
        client.rpc(
            "reopen_complaint",
            {"p_complaint_id": complaint_id, "p_reason": reason},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not reopen the complaint.") from exc


def confirm_resolution(
    client: Client, *, complaint_id: str, rating: int, feedback: str
) -> None:
    """Confirm a resolution with a rating (RPC)."""
    try:
        client.rpc(
            "confirm_complaint_resolution",
            {
                "p_complaint_id": complaint_id,
                "p_rating": rating,
                "p_feedback": feedback,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not confirm the resolution."
        ) from exc


def mark_read(client: Client, *, complaint_id: str, membership_id: str) -> None:
    """Clear the unread marker for this caller (RPC)."""
    try:
        client.rpc(
            "mark_complaint_read",
            {"p_complaint_id": complaint_id, "p_membership_id": membership_id},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not mark the complaint read."
        ) from exc
