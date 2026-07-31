"""Complaints service: admin edits and comments.

Two operations, because those are the two the frontend performs. The complaints
read path is their ``GET /dashboard/snapshot``, which already projects each
complaint with its comments and history embedded, so the list, detail,
read-receipt and attachment paths were removed rather than duplicated -- see
``docs/FRONTEND_WIRING_AUDIT.md`` §3.
"""

from __future__ import annotations

from app.core.exceptions import ValidationError
from app.domain.complaint_schemas import AddCommentRequest, UpdateComplaintRequest
from app.domain.vocabularies import status_to_storage
from app.repositories import complaints_repository as repo
from app.repositories import people_repository as people_repo
from app.repositories import tenancy_repository as tenancy_repo
from supabase import Client


def _caller_membership(client: Client, community_id: str, user_id: str) -> str | None:
    return people_repo.get_membership_id_for_profile(client, community_id, user_id)


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
    client: Client, user_id: str, complaint_id: str, body: UpdateComplaintRequest
) -> None:
    """Apply an admin edit, with its timeline entries, atomically."""
    community_id = tenancy_repo.get_caller_community_id(client, user_id)
    membership_id = _caller_membership(client, community_id, user_id)

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
    client: Client, user_id: str, complaint_id: str, body: AddCommentRequest
) -> None:
    """Add a comment to a complaint."""
    community_id = tenancy_repo.get_caller_community_id(client, user_id)
    membership_id = _caller_membership(client, community_id, user_id)

    repo.add_comment(
        client,
        complaint_id=complaint_id,
        body=body.message,
        visibility=body.visibility,
        author_membership=membership_id,
        author_label=_actor_label(client, user_id),
    )
