"""Complaint routes: the writes the admin screens perform.

Commenting is open to any member of the community -- a resident must be able to
discuss their own complaint. Editing and raising are admin-only.

The complaint *reads* were removed after the frontend wiring audit
(``docs/FRONTEND_WIRING_AUDIT.md``): ``GET /dashboard/snapshot`` projects
``complaints[]`` with comments and history already embedded, and both writes here
fire the shared SSE trigger, so the UI refreshes without a matching read.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status

from app.api.admin_deps import require_admin, require_csrf_unsafe
from app.api.deps import get_active_membership, get_current_user, get_request_client
from app.domain.common_schemas import MessageResult
from app.domain.complaint_schemas import (
    AddCommentRequest,
    AdminComplaintRaised,
    AdminRaiseComplaintRequest,
    StaffComplaintDetail,
    UpdateComplaintRequest,
)
from app.domain.schemas import MembershipContext
from app.services import complaints_service
from supabase import Client

router = APIRouter(
    prefix="/complaints",
    tags=["complaints"],
    dependencies=[Depends(require_csrf_unsafe)],
)


@router.get(
    "/staff/complaints/{complaint_id}",
    response_model=StaffComplaintDetail,
    dependencies=[Depends(require_admin)],
    summary="Staff complaint detail with full timeline",
)
async def staff_complaint_detail(
    complaint_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> StaffComplaintDetail:
    return complaints_service.staff_detail(client, complaint_id=complaint_id)


@router.post(
    "/admin-raise",
    response_model=AdminComplaintRaised,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Raise a complaint from the admin portal",
)
async def admin_raise_complaint(
    body: AdminRaiseComplaintRequest,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> AdminComplaintRaised:
    """File a complaint from the admin portal, in one of two modes.

    Related user stories: Resident 2.6 - complaint status tracking with history;
    Resident 2.8 - complaint accountability.

    **On behalf of a resident** (`forMembershipId` present). The complaint is
    owned by that resident's membership: it appears on their portal with the
    chat, the status and the timeline, and they keep the resident verbs --
    confirm the resolution, reopen it, cancel scheduled work. The admin is
    recorded as the *actor* of the `raised` event, which is where the fact that
    somebody else filed it belongs. It is history, not a property of the
    complaint, and it must not be able to move the complaint off the list of the
    person whose home the problem is in.

    **Not attached to a unit** (`forMembershipId` absent). A burnt-out lobby
    light, a broken gym treadmill, a gate that will not close. It is owned by the
    admin's own membership -- somebody has to own it, and the person who noticed
    is the honest answer -- and it is marked admin-portal-only, so it does not
    appear in that admin's own resident-portal "My Complaints". That list is what
    happened to them at home; a complaint about the lobby is not that.

    **This route exists because an admin is also a resident.** There is one
    membership row per person per community, and admins already hold the
    `resident` capability, so `POST /complaints` would have accepted both of
    these calls -- and filed both onto the admin's resident list, where the
    second one does not belong and the first one is filed against the wrong
    person entirely.

    Everything downstream is unchanged: the same category-then-skill department
    routing, the same priority-derived SLA, the same notification to the
    community's admins and the complaint's department manager, and the same
    supervisor -> work order pipeline. An admin-raised complaint is a complaint.

    `403` when the caller is not an active admin of their community, and when
    `forMembershipId` names a membership in a different community -- refused
    rather than ignored, since filing it into the caller's own community would
    hand a complaint to a management team that has never heard of the person it
    names. `404` for a `skillId` that names no active trade; `422` for an
    unrecognised `priority` or a complaint with neither a category nor a skill.
    """
    complaint_id = complaints_service.admin_raise_complaint(
        client, membership_id=membership.id, body=body
    )
    return AdminComplaintRaised(id=complaint_id, message="Complaint raised.")


@router.patch(
    "/{complaint_id}",
    response_model=MessageResult,
    dependencies=[Depends(require_admin)],
    summary="Update a complaint",
)
async def update_complaint(
    body: UpdateComplaintRequest,
    complaint_id: str = Path(...),
    principal=Depends(get_current_user),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Change status, assignee, progress or the expected resolution date.

    Related user stories: Resident 2.6 - complaint status tracking with history; Resident 2.8 - complaint accountability.

    The edit and its timeline entries are written in **one transaction**, so a
    status can never change without leaving a trace. `updateNote` writes a
    resident-visible timeline entry even when nothing else changes.
    """
    complaints_service.update_complaint(
        client, principal.user_id, membership.id, complaint_id, body
    )
    return MessageResult(message="Complaint updated.")


@router.post(
    "/{complaint_id}/comments",
    response_model=MessageResult,
    status_code=status.HTTP_201_CREATED,
    summary="Comment on a complaint",
)
async def add_comment(
    body: AddCommentRequest,
    complaint_id: str = Path(...),
    principal=Depends(get_current_user),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Add a comment. Any member may comment; only admins may write `internal`.

    The membership dependency is what makes "any member" a real check. It also
    replaced a `404` with the documented `403` for a signed-in caller who belongs
    to no community: the service used to discover that by failing to find their
    community, which answered "no such complaint" to a question that was really
    about the caller.
    """
    complaints_service.add_comment(
        client, principal.user_id, membership.id, complaint_id, body
    )
    return MessageResult(message="Comment added.")
