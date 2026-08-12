"""Data access for complaint edits and comments.

Both writes touch more than one table -- the complaint row plus its append-only
timeline -- so both go through an RPC rather than a pair of PostgREST calls that
could half-succeed.

Both RPCs are created by ``0020_complaint_events_on_baseline.sql``, which
replaced the quarantined ``0013_complaint_events.sql``.

One thing to know when reading ``status``: it is the baseline's
``complaint_status`` ENUM, which has no ``reopened`` member. Reopening stores
``open`` and records a ``status_changed`` event carrying the previous value, so
the reopen count is answerable from the timeline rather than from the column.
"""

from __future__ import annotations

from datetime import datetime

from app.core.pg_errors import translate
from supabase import Client


def staff_detail(client: Client, *, complaint_id: str) -> dict[str, object]:
    try:
        response = client.rpc(
            "staff_complaint_detail", {"p_complaint_id": complaint_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not load the complaint.") from exc
    return response.data or {"complaint": {}, "events": []}


def update_complaint(
    client: Client,
    *,
    complaint_id: str,
    status: str | None,
    assignee_label: str | None,
    assigned_to: str | None,
    progress_percent: int | None,
    due_at: datetime | None,
    update_note: str | None,
    actor_membership: str | None,
    actor_label: str | None,
) -> None:
    """Apply an edit and write its timeline entries, atomically (RPC)."""
    try:
        client.rpc(
            "update_complaint",
            {
                "p_complaint_id": complaint_id,
                "p_status": status,
                "p_assignee_label": assignee_label,
                "p_assigned_to": assigned_to,
                "p_progress_percent": progress_percent,
                "p_due_at": due_at.isoformat() if due_at else None,
                "p_update_note": update_note,
                "p_actor_membership": actor_membership,
                "p_actor_label": actor_label,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update the complaint.") from exc


def add_comment(
    client: Client,
    *,
    complaint_id: str,
    body: str,
    visibility: str,
    author_membership: str | None,
    author_label: str | None,
) -> str | None:
    """Add a comment and its timeline entry, atomically (RPC)."""
    try:
        response = client.rpc(
            "add_complaint_comment",
            {
                "p_complaint_id": complaint_id,
                "p_body": body,
                "p_visibility": visibility,
                "p_author_membership": author_membership,
                "p_author_label": author_label,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not add the comment.") from exc
    return response.data if isinstance(response.data, str) else None
