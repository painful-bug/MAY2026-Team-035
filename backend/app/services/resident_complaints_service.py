"""The resident's complaints: raising one, following it, and closing the loop.

Closes 3.2 and 3.3 of ``docs/design/RESIDENT_BACKEND_DESIGN.md`` and step 4 of
its build order. Three of the six operations here are the first writes in this
backend that **emit notifications**, which is the half of the step that could not
be built until ``0030`` existed.

**Where the work actually happens.** Almost nothing below decides anything. The
SLA is computed in ``raise_complaint``, the state transitions are refused in
``reopen_complaint`` and ``confirm_complaint_resolution``, ownership is checked
by ``is_own_membership``, and the notifications are written in the same
transaction as the change that caused them. This module translates vocabulary,
assembles the detail response, and renders a timeline entry into a sentence --
which is the correct amount for a service to do when the invariants live next to
the data (§5.2).

**The one thing it does decide** is what a timeline event *says*. That is a
rendering choice, it changes with the wording of the UI rather than with the
data, and a sentence stored in the database is a sentence that cannot be
corrected without a migration.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.common_schemas import Page
from app.domain.resident_complaint_schemas import (
    ComplaintComment,
    ComplaintDetail,
    ComplaintEvent,
    ComplaintSummary,
    CancelWorkRequest,
    ConfirmResolutionRequest,
    RaiseComplaintRequest,
    ReopenComplaintRequest,
)
from app.domain.vocabularies import (
    complaint_priority_to_storage,
    complaint_priority_to_wire,
    complaint_status_filter,
    complaint_status_to_wire,
)
from app.repositories import resident_complaints_repository as repo
from supabase import Client

#: What the resident sees when nobody has been put on the complaint yet. The
#: admin screen uses the same word, so the two views of one complaint agree.
_UNASSIGNED = "Unassigned"

#: Timeline labels. The keys are `complaint_events.event_type` values written by
#: `0020` and `0031`; an unknown type renders as the type itself rather than
#: disappearing, because a timeline that silently omits an entry is worse than
#: one with an ugly row -- the gap is invisible and the ugly row is a bug report.
_EVENT_LABELS = {
    "raised": "Complaint raised",
    "status_changed": "Status changed",
    "assigned": "Assigned",
    "progress_changed": "Progress updated",
    "due_date_changed": "Expected date changed",
    "note_added": "Update from management",
    "comment_added": "Comment added",
    "reopened": "Complaint reopened",
    "resolution_confirmed": "Resolution confirmed",
    # Written by `0036`. No migration was needed for these: `event_type` is
    # `text` with no CHECK (`0001`:70), so the timeline learns a new word by
    # being taught it here and nowhere else.
    "job_created": "Work raised",
    "job_scheduled": "Visit scheduled",
    "job_declined": "Visit declined",
    "job_assigned": "Technician assigned",
    "job_cancelled": "Visit cancelled",
    # Written by `0039`, from the worker's own side. There is deliberately no
    # `job_accepted`: a worker taking an offer writes `job_assigned`, because
    # from the resident's side the fact is the same fact -- somebody is now
    # coming, and this is their name. A second type would say it twice.
    "job_started": "Work started",
    "job_completed": "Work completed",
    "job_failed": "Visit unsuccessful",
    "returned_to_pool": "Sent back for re-evaluation",
    "auto_close_warning": "Reminder sent",
    "auto_closed": "Closed automatically",
    "job_force_assigned": "Assigned without offer (critical)",
    # Written by `20260824090000`'s `take_up_work_order`, and hidden from the
    # resident for `job_force_assigned`'s reason (ruling R14): the RPC writes
    # `job_assigned` beside it, which already carries the resident's fact.
    "job_taken_up": "Took up the job themselves",
    # Written by `20260822120000`'s `take_up_complaint`. It is here rather than
    # nowhere because an unknown type renders as its own raw word (see above),
    # and `taken_up` on a resident's timeline is the ugly row that comment
    # promises will become a bug report. The phrasing is `job_created`'s
    # deliberately: from the resident's side the fact is the same fact --
    # somebody in the department is now looking at this -- and naming the
    # supervisor would be the first resident-facing read in this codebase that
    # returns one.
    "taken_up": "Taken up by the department",
    # Written by `20260822170000`'s `raise_complaint_priority`, and the one new
    # event word amendment 2 cost -- `complaint_events_type_check` enumerates
    # them, so a word is a migration (the 2026-08-22 lesson, runbook 19). The
    # resident sees it because the *effect* is theirs: their complaint is being
    # treated as more urgent, which is the opposite of the kind of internal
    # bookkeeping the timeline hides.
    "priority_changed": "Priority raised",
}


def _text(value: object) -> str:
    """A payload field as a string, never ``None``."""
    return str(value).strip() if value not in (None, "") else ""


def _event_message(event_type: str, payload: dict[str, Any]) -> str:
    """One sentence describing what happened, from the event's own payload.

    Deliberately reads only the keys each event type is known to write. A
    generic dump of the payload would put whatever a future writer stored --
    including, one day, something that should not be shown to the person who
    raised the complaint -- straight onto the resident's screen.
    """
    if event_type == "status_changed":
        moved_from = complaint_status_to_wire(_text(payload.get("from")))
        moved_to = complaint_status_to_wire(_text(payload.get("to")))
        return f"Status changed from {moved_from} to {moved_to}."
    if event_type == "note_added":
        return _text(payload.get("note"))
    if event_type == "priority_changed":
        # The wire word, through the one table that maps them. The payload
        # carries the stored `medium`/`high`, because the RPC that writes it does
        # not translate vocabularies and nothing in SQL should.
        return (
            "The department raised the priority to "
            f"{complaint_priority_to_wire(_text(payload.get('to')))}."
        )
    if event_type == "reopened":
        return _text(payload.get("reason"))
    if event_type == "assigned":
        assignee = _text(payload.get("to"))
        return f"{assignee} was assigned to this complaint." if assignee else ""
    if event_type == "progress_changed":
        return f"Progress is now {_text(payload.get('to')) or '0'}%."
    if event_type == "resolution_confirmed":
        rating = _text(payload.get("rating"))
        feedback = _text(payload.get("feedback"))
        confirmed = f"You confirmed the resolution with a {rating}-star rating."
        return f"{confirmed} {feedback}".strip() if feedback else confirmed
    if event_type == "raised":
        return "The complaint was submitted to the management team."
    if event_type == "job_created":
        return "The department has taken this up."
    if event_type == "taken_up":
        # The payload names the department and the status it moved from, and
        # neither is said here. A resident asking "what is happening" is not
        # asking which internal status word changed.
        return "The department has taken this up."
    if event_type == "job_scheduled":
        when = _text(payload.get("startsAt"))
        if not when:
            return "A visit was scheduled."
        return (
            "A visit was rescheduled." if payload.get("rescheduled")
            else "A visit was proposed."
        ) + f" ({when})"
    if event_type == "job_declined":
        return "You declined the proposed time."
    if event_type == "job_assigned":
        assignee = _text(payload.get("assigneeName"))
        return f"{assignee} is coming." if assignee else "A technician was assigned."
    if event_type == "job_cancelled":
        return f"The visit was cancelled. {_text(payload.get('reason'))}".strip()
    if event_type == "job_started":
        who = _text(payload.get("assigneeName"))
        return f"{who} has started work." if who else "Work has started."
    if event_type == "job_completed":
        notes = _text(payload.get("notes"))
        done = "The work was completed."
        return f"{done} {notes}" if notes else done
    if event_type == "job_failed":
        # The reason is shown rather than summarised, because half the reasons a
        # visit fails are things only the resident can fix.
        why = _text(payload.get("reason"))
        return f"The visit could not be completed. {why}".strip()
    if event_type == "returned_to_pool":
        return "Sent back for re-evaluation — the team will assign someone else."
    if event_type == "auto_close_warning":
        return "Reminder sent: confirm or reopen."
    if event_type == "auto_closed":
        return "Closed automatically after no response."
    if event_type == "job_force_assigned":
        return "Assigned without offer (critical)."
    # `comment_added` says nothing here on purpose: the comment itself is in the
    # thread, and repeating it on the timeline would show it twice.
    return ""


def _is_hidden_from_resident(row: dict[str, Any]) -> bool:
    """Whether this timeline row is one the resident may not read.

    Three kinds, and they are hidden for three different reasons.

    ``comment_added``: ``0020`` writes one for *every* comment, internal ones
    included, because the timeline it was written for is admin-facing. The RLS
    policy on ``complaint_events`` scopes rows to the complaint, not to the
    comment's visibility, so those events do reach this surface.

    Leaving them in would put a row on the resident's timeline saying a comment
    exists, leading to a thread where nothing new is visible. That is a worse
    outcome than showing the comment would have been: it tells them something was
    said about their complaint and refuses to say what. The comment itself is
    already removed by the policy on ``complaint_comments``; this removes its
    shadow.

    ``job_force_assigned`` and ``job_taken_up``: internal dispatch mechanics.
    The resident already has the fact that matters -- somebody is coming, and
    this is their name -- from the ``job_assigned`` row each writer puts beside
    it. Which door the assignment came through (a forced pick, the supervisor
    taking it up themselves) is staffing, not service.

    ``note_added`` **carrying ``internal: true``**: the supervisor's own notes
    (2026-08-22, ruling A5). The product owner's scoping named staff and workers
    and not the resident. The flag is on the payload rather than in a second
    event word, so the admin's resident-visible *Update from management* notes --
    which carry no flag -- are untouched by this and still render.
    """
    event_type = _text(row.get("event_type"))
    if event_type in ("job_force_assigned", "job_taken_up"):
        return True
    payload = row.get("payload")
    data = payload if isinstance(payload, dict) else {}
    if event_type == "note_added":
        return data.get("internal") is True
    if event_type != "comment_added":
        return False
    return _text(data.get("visibility")) == "internal"


def _to_event(row: dict[str, Any]) -> ComplaintEvent:
    event_type = _text(row.get("event_type"))
    payload = row.get("payload")
    return ComplaintEvent(
        id=row["id"],
        type=event_type,
        label=_EVENT_LABELS.get(event_type, event_type),
        actor=_text(row.get("actor_label")) or "Management",
        message=_event_message(
            event_type, payload if isinstance(payload, dict) else {}
        ),
        created_at=row["created_at"],
    )


def _to_comment(row: dict[str, Any]) -> ComplaintComment:
    return ComplaintComment(
        id=row["id"],
        author=_text(row.get("author_label")) or "Management",
        message=_text(row.get("body")),
        created_at=row["created_at"],
    )


def _summary_fields(row: dict[str, Any]) -> dict[str, Any]:
    """The fields both the list row and the detail carry.

    One function so a value can never be derived two ways for the same
    complaint -- the failure that makes a detail screen disagree with the list
    it was opened from.
    """
    return {
        "id": row["id"],
        "title": _text(row.get("title")),
        "category": _text(row.get("category")) or "General",
        "status": complaint_status_to_wire(row.get("status")),
        "urgency": complaint_priority_to_wire(row.get("priority")),
        "location": _text(row.get("location")),
        "progress": int(row.get("progress_percent") or 0),
        "assignee": _text(row.get("assignee_label")) or _UNASSIGNED,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_activity_at": row.get("last_activity_at") or row["updated_at"],
        "expected_resolution_at": row.get("expected_resolution_at"),
        "resolved_at": row.get("resolved_at"),
        "is_overdue": bool(row.get("is_overdue")),
        "is_unread": bool(row.get("is_unread")),
        "reopened_count": int(row.get("reopened_count") or 0),
        "comment_count": int(row.get("comment_count") or 0),
    }


def _to_summary(row: dict[str, Any]) -> ComplaintSummary:
    return ComplaintSummary(**_summary_fields(row))


def _to_detail(
    row: dict[str, Any],
    *,
    events: list[dict[str, Any]],
    events_truncated: bool,
    thread: list[dict[str, Any]],
    thread_truncated: bool,
) -> ComplaintDetail:
    """Assemble the detail response, putting the two threads back in reading
    order.

    The repository reads both newest-first so that a bound keeps the recent end;
    a timeline is read downwards, so they are reversed exactly here -- once, in
    the layer that decides what the screen looks like.
    """
    return ComplaintDetail(
        **_summary_fields(row),
        description=_text(row.get("description")),
        resolution_rating=row.get("resolution_rating"),
        resident_feedback=_text(row.get("resident_feedback")),
        timeline=[
            _to_event(event)
            for event in reversed(events)
            if not _is_hidden_from_resident(event)
        ],
        comments=[_to_comment(comment) for comment in reversed(thread)],
        has_older_events=events_truncated,
        has_older_comments=thread_truncated,
    )


def list_mine(
    client: Client,
    *,
    membership_id: str,
    status: str | None = None,
    category: str | None = None,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> Page[ComplaintSummary]:
    """One page of the caller's own complaints, newest first.

    A status the vocabulary does not recognise is a 422 rather than an empty
    page. An empty page is what "you have no resolved complaints" looks like,
    and a filter typo must not be indistinguishable from a true answer.

    **The filter matches every stored status that renders as the word asked
    for**, which is why it is ``complaint_status_filter`` and not
    ``status_to_storage``. ``Resolved`` covers ``resolved`` and ``closed``;
    ``In Progress`` covers ``acknowledged`` and ``in_progress``. Using the
    write-side map here would have hidden rows the same list displays under the
    caller's own word -- a filter that is spelled correctly and still answers
    wrongly, which nobody reports because nothing about it looks broken.
    """
    stored_statuses = None
    if status:
        stored_statuses = complaint_status_filter(status)
        if stored_statuses is None:
            raise ValidationError(
                f"Unknown complaint status: {status}", code="unknown_status"
            )

    offset = max(page - 1, 0) * page_size
    rows, total = repo.list_mine(
        client,
        membership_id=membership_id,
        statuses=stored_statuses,
        category=(category or "").strip() or None,
        unread_only=unread_only,
        offset=offset,
        limit=page_size,
    )
    items = [_to_summary(row) for row in rows]
    return Page(
        items=items,
        total=total,
        page=max(page, 1),
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


def get_mine(
    client: Client, *, membership_id: str, complaint_id: str
) -> ComplaintDetail:
    """One of the caller's complaints, with its timeline and comment thread.

    Three queries rather than one embedded read. PostgREST could nest them, but
    the two child tables carry their own RLS policies and their own visibility
    rule, and an embedded select that silently returns fewer rows than expected
    because of a policy is the hardest kind of bug to see.
    """
    row = repo.get_mine(
        client, membership_id=membership_id, complaint_id=complaint_id
    )
    if row is None:
        raise NotFoundError("Complaint not found.", code="complaint_not_found")

    events, events_truncated = repo.timeline(client, complaint_id=complaint_id)
    thread, thread_truncated = repo.comments(client, complaint_id=complaint_id)
    return _to_detail(
        row,
        events=events,
        events_truncated=events_truncated,
        thread=thread,
        thread_truncated=thread_truncated,
    )


def raise_complaint(
    client: Client, *, membership_id: str, body: RaiseComplaintRequest
) -> ComplaintDetail:
    """File a complaint and return it as the detail screen will show it.

    The read-back is not ceremony. The response carries the SLA deadline the
    *database* computed, which is the number the resident is about to be held
    to and the one thing the client could not have known before asking. Echoing
    the submitted fields back would return everything except the answer.
    """
    priority = complaint_priority_to_storage(body.urgency)
    if priority is None:
        raise ValidationError(
            f"Unknown urgency: {body.urgency}", code="unknown_urgency"
        )

    complaint_id = repo.raise_complaint(
        client,
        membership_id=membership_id,
        title=body.title.strip(),
        description=body.description.strip(),
        category=body.category.strip(),
        priority=priority,
        location=body.location.strip(),
        department_id=body.department_id,
        skill_id=body.skill_id,
    )
    return get_mine(client, membership_id=membership_id, complaint_id=complaint_id)


def cancel_work(
    client: Client, *, membership_id: str, complaint_id: str, body: CancelWorkRequest
) -> ComplaintDetail:
    repo.cancel_work(
        client, complaint_id=complaint_id, mode=body.mode, reason=body.reason.strip() or None
    )
    return get_mine(client, membership_id=membership_id, complaint_id=complaint_id)


def reopen(
    client: Client,
    *,
    membership_id: str,
    complaint_id: str,
    body: ReopenComplaintRequest,
) -> ComplaintDetail:
    """Reopen a resolved complaint of the caller's.

    The ownership check is the RPC's, not this function's -- it holds the row
    and can refuse in the same statement that would have changed it. What this
    does is read the result back, so the client renders the restarted SLA rather
    than guessing at it.
    """
    repo.reopen(client, complaint_id=complaint_id, reason=body.reason.strip())
    return get_mine(client, membership_id=membership_id, complaint_id=complaint_id)


def confirm_resolution(
    client: Client,
    *,
    membership_id: str,
    complaint_id: str,
    body: ConfirmResolutionRequest,
) -> ComplaintDetail:
    """Accept a resolution with a 1-5 rating, closing the complaint."""
    repo.confirm_resolution(
        client,
        complaint_id=complaint_id,
        rating=body.rating,
        feedback=body.feedback.strip(),
    )
    return get_mine(client, membership_id=membership_id, complaint_id=complaint_id)


def mark_read(client: Client, *, membership_id: str, complaint_id: str) -> None:
    """Record that this caller has seen the complaint as it stands now."""
    repo.mark_read(
        client, complaint_id=complaint_id, membership_id=membership_id
    )
