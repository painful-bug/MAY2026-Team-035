"""Data access for complaints, their timeline, comments and attachments.

Reads use the caller-scoped client so RLS applies. Every write that touches more
than one table goes through an RPC -- see migration 0012's header for why.
"""

from __future__ import annotations

from datetime import datetime

from app.core.exceptions import NotFoundError
from app.core.pg_errors import translate
from supabase import Client

_COMPLAINTS = "complaints"
_EVENTS = "complaint_events"
_COMMENTS = "complaint_comments"
_ATTACHMENTS = "complaint_attachments"
_RECEIPTS = "complaint_read_receipts"

#: Embeds resolve through single foreign keys, so PostgREST handles them; the
#: unit does not, because complaints -> apartments is a composite key (see
#: admin_overview_repository.map_unit_codes_to_ids).
_COMPLAINT_SELECT = (
    "id, title, description, raised_by_membership_id, raised_by_label, unit_id,"
    "category_id, department_id, status, urgency, progress_percent, location,"
    "assignee_label, assigned_to_membership_id, due_at, reopen_count,"
    "resolution_rating, resolution_feedback, resolution_confirmed_at,"
    "created_at, updated_at,"
    "complaint_categories(name), departments(name)"
)


def list_complaints(
    client: Client,
    community_id: str,
    *,
    status: str | None,
    category_id: str | None,
    department_id: str | None,
    search: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """Page through complaints, newest first."""
    query = (
        client.table(_COMPLAINTS)
        .select(_COMPLAINT_SELECT, count="exact")
        .eq("community_id", community_id)
    )

    if status:
        query = query.eq("status", status)
    if category_id:
        query = query.eq("category_id", category_id)
    if department_id:
        query = query.eq("department_id", department_id)
    if search:
        safe = (
            search.replace("%", r"\%")
            .replace(",", " ")
            .replace("(", " ")
            .replace(")", " ")
        )
        pattern = f"%{safe}%"
        query = query.or_(
            f"title.ilike.{pattern},description.ilike.{pattern},"
            f"assignee_label.ilike.{pattern}"
        )

    response = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def get_complaint(client: Client, community_id: str, complaint_id: str) -> dict:
    """Fetch one complaint, or raise."""
    response = (
        client.table(_COMPLAINTS)
        .select(_COMPLAINT_SELECT)
        .eq("community_id", community_id)
        .eq("id", complaint_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Complaint not found.")
    return rows[0]


def list_events(client: Client, complaint_id: str) -> list[dict]:
    """The timeline, oldest first -- the order it is rendered in."""
    response = (
        client.table(_EVENTS)
        .select("id, event_type, label, message, actor_label, created_at")
        .eq("complaint_id", complaint_id)
        .order("created_at")
        .execute()
    )
    return response.data or []


def list_comments(client: Client, complaint_id: str) -> list[dict]:
    """Comments, oldest first.

    Internal comments are filtered out by RLS for non-admins, so this needs no
    visibility filter of its own -- and could not be trusted to apply one.
    """
    response = (
        client.table(_COMMENTS)
        .select("id, body, author_label, visibility, created_at")
        .eq("complaint_id", complaint_id)
        .is_("deleted_at", "null")
        .order("created_at")
        .execute()
    )
    return response.data or []


def list_attachments(client: Client, complaint_id: str) -> list[dict]:
    """Attachment metadata. The bytes live in Supabase Storage."""
    response = (
        client.table(_ATTACHMENTS)
        .select(
            "id, storage_path, attachment_type, content_type, size_bytes, created_at"
        )
        .eq("complaint_id", complaint_id)
        .order("created_at")
        .execute()
    )
    return response.data or []


def insert_attachment(
    client: Client,
    *,
    community_id: str,
    complaint_id: str,
    storage_path: str,
    attachment_type: str,
    content_type: str | None,
    size_bytes: int | None,
    uploaded_by_membership_id: str | None,
) -> dict:
    """Register a file that has already been uploaded to Storage."""
    try:
        response = (
            client.table(_ATTACHMENTS)
            .insert(
                {
                    "community_id": community_id,
                    "complaint_id": complaint_id,
                    "storage_path": storage_path,
                    "attachment_type": attachment_type,
                    "content_type": content_type,
                    "size_bytes": size_bytes,
                    "uploaded_by_membership_id": uploaded_by_membership_id,
                }
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not save the attachment.") from exc

    rows = response.data or []
    if not rows:
        raise NotFoundError("Complaint not found.")
    return rows[0]


def read_receipts_for(
    client: Client, membership_id: str, complaint_ids: list[str]
) -> dict[str, datetime]:
    """Return ``{complaint_id: last_read_at}`` for the caller.

    One query for the whole page rather than one per row. Absent means unread.
    """
    if not membership_id or not complaint_ids:
        return {}
    response = (
        client.table(_RECEIPTS)
        .select("complaint_id, last_read_at")
        .eq("membership_id", membership_id)
        .in_("complaint_id", complaint_ids)
        .execute()
    )
    return {row["complaint_id"]: row["last_read_at"] for row in (response.data or [])}


def mark_read(
    client: Client, *, community_id: str, complaint_id: str, membership_id: str
) -> None:
    """Upsert the caller's read receipt for one complaint."""
    try:
        (
            client.table(_RECEIPTS)
            .upsert(
                {
                    "community_id": community_id,
                    "complaint_id": complaint_id,
                    "membership_id": membership_id,
                    "last_read_at": "now()",
                },
                on_conflict="complaint_id,membership_id",
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not mark as read.") from exc


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
