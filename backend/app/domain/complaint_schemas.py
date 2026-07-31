"""DTOs for the complaints surfaces.

Request bodies only. The complaints read path is their ``GET /dashboard/snapshot``,
which projects each complaint with its comments and history embedded, so the
response DTOs this module used to carry (summary, detail, timeline, comments,
attachments) went with the reads that were removed -- see
``docs/FRONTEND_WIRING_AUDIT.md`` §3.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel


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
        "resident",
        description="'resident' (visible to them) or 'internal' (admins only)",
    )
