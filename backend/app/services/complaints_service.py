"""Complaints service: list, detail, edit, comments, read state, attachments."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import ValidationError
from app.core.formatting import long_date, parse_instant, time_ago
from app.core.logging import get_logger
from app.domain.common_schemas import Page
from app.domain.complaint_schemas import (
    AddCommentRequest,
    ComplaintAttachment,
    ComplaintComment,
    ComplaintDetail,
    ComplaintSummary,
    RegisterAttachmentRequest,
    TimelineEvent,
    UpdateComplaintRequest,
)
from app.domain.vocabularies import (
    is_open,
    status_to_storage,
    status_to_wire,
    urgency_to_wire,
)
from app.repositories import complaints_repository as repo
from app.repositories import dashboard_repository as dash_repo
from app.repositories import people_repository as people_repo
from supabase import Client

_logger = get_logger(__name__)

#: Supabase Storage bucket holding complaint photos. Must exist and be PRIVATE --
#: a public bucket would make every complaint photo world-readable by URL,
#: bypassing RLS entirely. Documented as a setup step in API.md.
ATTACHMENT_BUCKET = "complaint-attachments"

_SIGNED_URL_TTL_SECONDS = 60 * 10


def _embedded_name(row: dict, key: str) -> str | None:
    """Read a name out of a PostgREST embed, which may be a dict or a list."""
    value = row.get(key)
    if isinstance(value, dict):
        return value.get("name")
    if isinstance(value, list) and value:
        return value[0].get("name")
    return None


def _to_summary(
    row: dict,
    *,
    unit_code: str | None,
    last_read_at: datetime | None,
    now: datetime,
) -> ComplaintSummary:
    created = parse_instant(row["created_at"])
    updated = parse_instant(row["updated_at"])
    due = parse_instant(row["due_at"]) if row.get("due_at") else None

    return ComplaintSummary(
        id=row["id"],
        title=row["title"],
        description=row.get("description"),
        raised_by=row.get("raised_by_label"),
        raised_by_membership_id=row.get("raised_by_membership_id"),
        flat=unit_code,
        unit_id=row.get("unit_id"),
        location=row.get("location"),
        category=_embedded_name(row, "complaint_categories"),
        category_id=row.get("category_id"),
        department=_embedded_name(row, "departments"),
        department_id=row.get("department_id"),
        status=status_to_wire(row.get("status")),
        urgency=urgency_to_wire(row.get("urgency")),
        progress=row.get("progress_percent") or 0,
        assignee=row.get("assignee_label"),
        assigned_to_membership_id=row.get("assigned_to_membership_id"),
        date=long_date(created),
        time_ago=time_ago(created, now=now),
        submitted_at=created,
        updated_at=updated,
        expected_resolution_at=due,
        # Breaching means the deadline passed AND nobody has closed it. A
        # resolved complaint that took too long is late, not breaching -- the
        # tile counts work outstanding now.
        is_breaching=bool(due and due < now and is_open(row.get("status"))),
        # No receipt at all means never opened, so unread.
        has_unread_update=last_read_at is None or updated > last_read_at,
        reopened_count=row.get("reopen_count") or 0,
        rating=row.get("resolution_rating"),
        resident_feedback=row.get("resolution_feedback"),
        resolution_confirmed=row.get("resolution_confirmed_at") is not None,
    )


def _unit_codes(client: Client, community_id: str, rows: list[dict]) -> dict[str, str]:
    """Resolve ``unit_id -> code`` for a page of complaints.

    The reverse of the residents lookup, and separate for the same reason: the
    complaints -> apartments foreign key is composite, which PostgREST does not
    embed reliably.
    """
    unit_ids = sorted({row["unit_id"] for row in rows if row.get("unit_id")})
    if not unit_ids:
        return {}
    response = (
        client.table("apartments")
        .select("id, code")
        .eq("association_id", community_id)
        .in_("id", unit_ids)
        .execute()
    )
    return {row["id"]: row["code"] for row in (response.data or [])}


def _caller_membership(client: Client, community_id: str, user_id: str) -> str | None:
    return people_repo.get_membership_id_for_profile(client, community_id, user_id)


def list_complaints(
    client: Client,
    user_id: str,
    *,
    status: str | None = None,
    category_id: str | None = None,
    department_id: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[ComplaintSummary]:
    """Page through complaints, newest first."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    offset = (page - 1) * page_size

    stored_status = None
    if status:
        stored_status = status_to_storage(status)
        if stored_status is None:
            raise ValidationError(f"Unknown status '{status}'.", code="unknown_status")

    rows, total = repo.list_complaints(
        client,
        community_id,
        status=stored_status,
        category_id=category_id,
        department_id=department_id,
        search=search,
        offset=offset,
        limit=page_size,
    )

    unit_codes = _unit_codes(client, community_id, rows)
    membership_id = _caller_membership(client, community_id, user_id)
    receipts = repo.read_receipts_for(
        client, membership_id or "", [row["id"] for row in rows]
    )
    now = datetime.now(timezone.utc)

    items = [
        _to_summary(
            row,
            unit_code=unit_codes.get(row.get("unit_id") or ""),
            last_read_at=(
                parse_instant(receipts[row["id"]]) if row["id"] in receipts else None
            ),
            now=now,
        )
        for row in rows
    ]

    return Page[ComplaintSummary](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(items) < total,
    )


def get_complaint(client: Client, user_id: str, complaint_id: str) -> ComplaintDetail:
    """One complaint with its timeline, comments and attachments."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    row = repo.get_complaint(client, community_id, complaint_id)

    unit_codes = _unit_codes(client, community_id, [row])
    membership_id = _caller_membership(client, community_id, user_id)
    receipts = repo.read_receipts_for(client, membership_id or "", [complaint_id])
    now = datetime.now(timezone.utc)

    summary = _to_summary(
        row,
        unit_code=unit_codes.get(row.get("unit_id") or ""),
        last_read_at=(
            parse_instant(receipts[complaint_id]) if complaint_id in receipts else None
        ),
        now=now,
    )

    return ComplaintDetail(
        **summary.model_dump(),
        timeline=[
            TimelineEvent(
                id=event["id"],
                type=event["event_type"],
                label=event["label"],
                message=event.get("message"),
                actor=event.get("actor_label"),
                created_at=parse_instant(event["created_at"]),
            )
            for event in repo.list_events(client, complaint_id)
        ],
        comments=[
            ComplaintComment(
                id=comment["id"],
                message=comment["body"],
                author_name=comment.get("author_label"),
                author_role=None,
                visibility=comment.get("visibility", "resident"),
                created_at=parse_instant(comment["created_at"]),
            )
            for comment in repo.list_comments(client, complaint_id)
        ],
        attachments=_attachments(client, complaint_id),
    )


def _attachments(client: Client, complaint_id: str) -> list[ComplaintAttachment]:
    """Attachment metadata with short-lived signed download links."""
    rows = repo.list_attachments(client, complaint_id)
    if not rows:
        return []

    signed: dict[str, str] = {}
    try:
        paths = [row["storage_path"] for row in rows]
        result = client.storage.from_(ATTACHMENT_BUCKET).create_signed_urls(
            paths, _SIGNED_URL_TTL_SECONDS
        )
        for entry in result or []:
            path = entry.get("path")
            url = entry.get("signedURL") or entry.get("signedUrl")
            if path and url:
                signed[path] = url
    except Exception as exc:  # noqa: BLE001
        # A missing bucket or a storage outage must not take down the complaint
        # the files belong to. The metadata is still useful; the links are not.
        _logger.warning("Could not sign attachment URLs: %s", exc)

    return [
        ComplaintAttachment(
            id=row["id"],
            storage_path=row["storage_path"],
            url=signed.get(row["storage_path"]),
            attachment_type=row.get("attachment_type", "photo"),
            content_type=row.get("content_type"),
            size_bytes=row.get("size_bytes"),
            created_at=parse_instant(row["created_at"]),
        )
        for row in rows
    ]


def update_complaint(
    client: Client, user_id: str, complaint_id: str, body: UpdateComplaintRequest
) -> None:
    """Apply an admin edit, with its timeline entries, atomically."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    membership_id = _caller_membership(client, community_id, user_id)

    stored_status = None
    if body.status is not None:
        stored_status = status_to_storage(body.status)
        if stored_status is None:
            raise ValidationError(
                f"Unknown status '{body.status}'.", code="unknown_status"
            )

    profile = client.table("profiles").select("full_name").eq("id", user_id).limit(1).execute()
    actor_label = (profile.data or [{}])[0].get("full_name") or "Management"

    repo.update_complaint(
        client,
        complaint_id=complaint_id,
        status=stored_status,
        assignee_label=body.assignee,
        assigned_to=body.assigned_to_membership_id,
        progress_percent=body.progress,
        due_at=body.expected_resolution_at,
        update_note=body.update_note,
        actor_membership=membership_id,
        actor_label=actor_label,
    )


def add_comment(
    client: Client, user_id: str, complaint_id: str, body: AddCommentRequest
) -> None:
    """Add a comment to a complaint."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    membership_id = _caller_membership(client, community_id, user_id)

    profile = client.table("profiles").select("full_name").eq("id", user_id).limit(1).execute()
    author_label = (profile.data or [{}])[0].get("full_name")

    repo.add_comment(
        client,
        complaint_id=complaint_id,
        body=body.message,
        visibility=body.visibility,
        author_membership=membership_id,
        author_label=author_label,
    )


def mark_read(client: Client, user_id: str, complaint_id: str) -> None:
    """Record that the caller has seen this complaint's current state."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    membership_id = _caller_membership(client, community_id, user_id)
    if not membership_id:
        raise ValidationError("You have no membership in this community.")
    repo.mark_read(
        client,
        community_id=community_id,
        complaint_id=complaint_id,
        membership_id=membership_id,
    )


def register_attachment(
    client: Client, user_id: str, complaint_id: str, body: RegisterAttachmentRequest
) -> ComplaintAttachment:
    """Record a file already uploaded to Storage against a complaint."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    # Confirms the complaint exists in the caller's community before writing a
    # row that points at it.
    repo.get_complaint(client, community_id, complaint_id)
    membership_id = _caller_membership(client, community_id, user_id)

    row = repo.insert_attachment(
        client,
        community_id=community_id,
        complaint_id=complaint_id,
        storage_path=body.storage_path,
        attachment_type=body.attachment_type,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        uploaded_by_membership_id=membership_id,
    )

    return ComplaintAttachment(
        id=row["id"],
        storage_path=row["storage_path"],
        url=None,
        attachment_type=row.get("attachment_type", "photo"),
        content_type=row.get("content_type"),
        size_bytes=row.get("size_bytes"),
        created_at=parse_instant(row["created_at"]),
    )
