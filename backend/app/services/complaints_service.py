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
from app.domain.complaint_schemas import (
    AddCommentRequest,
    AdminRaiseComplaintRequest,
    StaffComplaintDetail,
    UpdateComplaintRequest,
)
from app.services.resident_complaints_service import _event_message
from app.domain.vocabularies import (
    comment_visibility_to_storage,
    complaint_priority_to_storage,
    status_to_storage,
)
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


def admin_raise_complaint(
    client: Client,
    *,
    membership_id: str,
    body: AdminRaiseComplaintRequest,
) -> str:
    """File a complaint from the admin portal. Returns its id.

    Everything that decides anything is in ``admin_raise_complaint`` -- that the
    caller is an active admin, that a ``forMembershipId`` names somebody in the
    same community, which membership ends up owning the row, which portal shows
    it, the department routing, the SLA and the notification, all in one
    transaction. What is left here is the same job this layer does for the
    resident's raise: translate a vocabulary before the database has to reject
    it.

    ``priority`` is that translation. It is the frontend's word (``High``) and
    the column's values are ``low``/``medium``/``high``; an unrecognised one is a
    422 naming the field rather than a ``22P02`` surfacing as an opaque failure
    from three layers down. ``complaint_priority_to_storage`` returns ``None``
    for a word it has not heard rather than defaulting, so "they sent nothing"
    and "they sent something we do not understand" stay distinguishable -- the
    schema's ``Low`` default already covers the first.

    **The membership is the caller's, resolved by the dependency graph.** It is
    not read from the body, and ``forMembershipId`` is a separate field for that
    reason: an endpoint that let a caller name the membership they are acting
    *as* is one where ``require_admin`` proves something about a person other
    than the one the write is attributed to.
    """
    priority = complaint_priority_to_storage(body.priority)
    if priority is None:
        raise ValidationError(
            f"Unknown priority: {body.priority}", code="unknown_priority"
        )

    return repo.admin_raise_complaint(
        client,
        actor_membership_id=membership_id,
        title=body.title.strip(),
        description=body.description.strip(),
        category=body.category.strip(),
        priority=priority,
        location=body.location.strip(),
        department_id=body.department_id,
        skill_id=body.skill_id,
        for_membership_id=body.for_membership_id,
    )


def staff_detail(client: Client, *, complaint_id: str) -> StaffComplaintDetail:
    result = repo.staff_detail(client, complaint_id=complaint_id)
    events = result.get("events") if isinstance(result.get("events"), list) else []
    rendered = []
    for event in events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        rendered.append({**event, "message": _event_message(str(event.get("event_type") or ""), payload)})
    complaint = result.get("complaint") if isinstance(result.get("complaint"), dict) else {}
    return StaffComplaintDetail(complaint=complaint, events=rendered)
