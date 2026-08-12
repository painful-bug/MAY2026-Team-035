"""Complaint routes: the two writes the admin screens perform.

Commenting is open to any member of the community -- a resident must be able to
discuss their own complaint. Editing is admin-only.

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
from app.domain.complaint_schemas import AddCommentRequest, StaffComplaintDetail, UpdateComplaintRequest
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
