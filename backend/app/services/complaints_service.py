"""Complaints service: admin edits and comments.

Two operations, because those are the two the frontend performs. The complaints
read path is their ``GET /dashboard/snapshot``, which already projects each
complaint with its comments and history embedded, so the list, detail,
read-receipt and attachment paths were removed rather than duplicated -- see
``docs/FRONTEND_WIRING_AUDIT.md`` §3.

**Both functions take the caller's ``membership_id`` rather than resolving it.**
They used to call a ``people_repository.get_membership_id_for_profile`` that has
never existed in this repository -- so both writes raised ``AttributeError`` on
their second line, and the suite never noticed because
``tests/api/test_complaints.py`` monkeypatches this module wholesale. The fix is
not to write the missing function: the request has already resolved the caller's
membership by the time either route's body runs (``require_admin`` is
``require_membership_role("admin")``, which depends on ``get_active_membership``),
so re-deriving it here would cost two round trips to learn something the
dependency graph computed a moment earlier.
"""

from __future__ import annotations

from app.core.exceptions import ValidationError
from app.domain.complaint_schemas import AddCommentRequest, UpdateComplaintRequest
from app.domain.vocabularies import comment_visibility_to_storage, status_to_storage
from app.repositories import complaints_repository as repo
from supabase import Client


def _actor_label(
    client: Client, user_id: str, fallback: str | None = None
) -> str | None:
    """The display name written onto the timeline entry this write produces."""
    profile = (
        client.table("profiles")
        .select("full_name")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return (profile.data or [{}])[0].get("full_name") or fallback


def update_complaint(
    client: Client,
    user_id: str,
    membership_id: str,
    complaint_id: str,
    body: UpdateComplaintRequest,
) -> None:
    """Apply an admin edit, with its timeline entries, atomically."""
    stored_status = None
    if body.status is not None:
        stored_status = status_to_storage(body.status)
        if stored_status is None:
            raise ValidationError(
                f"Unknown status '{body.status}'.", code="unknown_status"
            )

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
        actor_label=_actor_label(client, user_id, "Management"),
    )


def add_comment(
    client: Client,
    user_id: str,
    membership_id: str,
    complaint_id: str,
    body: AddCommentRequest,
) -> None:
    """Add a comment to a complaint.

    ``visibility`` is translated rather than forwarded. The wire word is
    ``resident``; the column, both RPCs and every read filter say ``public``, and
    ``complaint_comments_visibility_check`` rejects anything else -- so passing
    the request through made every comment a 422, including the frontend's, which
    hardcodes ``resident``. Same shape as ``status_to_storage`` above.
    """
    stored_visibility = comment_visibility_to_storage(body.visibility)
    if stored_visibility is None:
        raise ValidationError(
            f"Unknown visibility '{body.visibility}'.", code="unknown_visibility"
        )

    repo.add_comment(
        client,
        complaint_id=complaint_id,
        body=body.message,
        visibility=stored_visibility,
        author_membership=membership_id,
        author_label=_actor_label(client, user_id),
    )
