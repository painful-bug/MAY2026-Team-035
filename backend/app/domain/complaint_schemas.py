"""DTOs for the complaints surfaces."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel


class TimelineEvent(CamelModel):
    """One entry in the complaint's append-only timeline.

    Field names mirror the frontend's timeline objects exactly
    ({id, type, label, message, actor, createdAt}).
    """

    id: str
    type: str
    label: str
    message: str | None = None
    actor: str | None = None
    created_at: datetime


class ComplaintComment(CamelModel):
    """One message in the resident/management conversation."""

    id: str
    message: str
    author_name: str | None = None
    author_role: str | None = None
    visibility: str
    created_at: datetime


class ComplaintAttachment(CamelModel):
    """One uploaded file.

    ``url`` is a short-lived signed link. It is ``null`` when signing fails or the
    storage bucket is missing, rather than the endpoint erroring -- one bad
    attachment must not take down the complaint it belongs to.
    """

    id: str
    storage_path: str
    url: str | None = None
    attachment_type: str
    content_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime


class ComplaintSummary(CamelModel):
    """One complaint, in the shape the list screens render."""

    id: str
    title: str
    description: str | None = None

    raised_by: str | None = None
    raised_by_membership_id: str | None = None
    flat: str | None = None
    unit_id: str | None = None
    location: str | None = None

    category: str | None = None
    category_id: str | None = None
    department: str | None = None
    department_id: str | None = None

    status: str
    urgency: str
    progress: int
    assignee: str | None = None
    assigned_to_membership_id: str | None = None

    # Server-formatted for the frontend, with the machine-readable instant
    # alongside (see app.core.formatting).
    date: str
    time_ago: str
    submitted_at: datetime
    updated_at: datetime

    expected_resolution_at: datetime | None = None
    #: True when the deadline has passed and the complaint is still open. Computed
    #: server-side so every screen agrees on what "breaching" means.
    is_breaching: bool = False

    has_unread_update: bool = False
    reopened_count: int = 0
    rating: int | None = None
    resident_feedback: str | None = None
    resolution_confirmed: bool = False


class ComplaintDetail(ComplaintSummary):
    """A complaint plus everything hanging off it."""

    timeline: list[TimelineEvent] = Field(default_factory=list)
    comments: list[ComplaintComment] = Field(default_factory=list)
    attachments: list[ComplaintAttachment] = Field(default_factory=list)


class UpdateComplaintRequest(CamelModel):
    """Admin edit. Every field optional; omitted fields are left unchanged."""

    status: str | None = Field(None, description="Pending | In Progress | Resolved")
    assignee: str | None = Field(None, max_length=200)
    assigned_to_membership_id: str | None = None
    progress: int | None = Field(None, ge=0, le=100)
    expected_resolution_at: datetime | None = None
    #: Free text shown to the resident on the timeline. Writes an event even when
    #: nothing else changes -- it is the admin's "Resident-visible Update" box.
    update_note: str | None = Field(None, max_length=2000)


class AddCommentRequest(CamelModel):
    """A new comment on a complaint."""

    message: str = Field(..., min_length=1, max_length=2000)
    visibility: str = Field(
        "resident", description="'resident' (visible to them) or 'internal' (admins only)"
    )


class RegisterAttachmentRequest(CamelModel):
    """Register a file already uploaded to Supabase Storage."""

    storage_path: str = Field(..., max_length=500)
    attachment_type: str = Field("photo", description="photo | document | resolution_proof")
    content_type: str | None = Field(None, max_length=200)
    size_bytes: int | None = Field(None, ge=0)
