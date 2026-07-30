"""Complaint routes.

Reads and comments are open to any member of the community -- a resident must be
able to follow and discuss their own complaint. Editing is admin-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.deps import get_current_user, get_request_client, require_role
from app.domain.common_schemas import MessageResult, Page
from app.domain.complaint_schemas import (
    AddCommentRequest,
    ComplaintAttachment,
    ComplaintDetail,
    ComplaintSummary,
    RegisterAttachmentRequest,
    UpdateComplaintRequest,
)
from app.domain.roles import Role
from app.services import complaints_service
from supabase import Client

router = APIRouter(prefix="/complaints", tags=["complaints"])

_NO_STORE = "no-store"


@router.get("", response_model=Page[ComplaintSummary], summary="List complaints")
async def list_complaints(
    response: Response,
    status_filter: str | None = Query(
        None, alias="status", description="Pending | In Progress | Resolved"
    ),
    category_id: str | None = Query(None, alias="categoryId"),
    department_id: str | None = Query(None, alias="departmentId"),
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[ComplaintSummary]:
    """Complaints in the caller's community, newest first.

    `hasUnreadUpdate` and `isBreaching` are computed per caller and per request,
    so this response is never cacheable.
    """
    response.headers["Cache-Control"] = _NO_STORE
    return complaints_service.list_complaints(
        client,
        principal.user_id,
        status=status_filter,
        category_id=category_id,
        department_id=department_id,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{complaint_id}", response_model=ComplaintDetail, summary="Get one complaint"
)
async def get_complaint(
    response: Response,
    complaint_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ComplaintDetail:
    """One complaint with its timeline, comments and attachments.

    Internal comments are omitted for non-admin callers -- enforced by RLS, not
    by this layer.
    """
    response.headers["Cache-Control"] = _NO_STORE
    return complaints_service.get_complaint(client, principal.user_id, complaint_id)


@router.patch(
    "/{complaint_id}",
    response_model=MessageResult,
    dependencies=[Depends(require_role(Role.ADMIN))],
    summary="Update a complaint",
)
async def update_complaint(
    body: UpdateComplaintRequest,
    complaint_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Change status, assignee, progress or the expected resolution date.

    The edit and its timeline entries are written in **one transaction**, so a
    status can never change without leaving a trace. `updateNote` writes a
    resident-visible timeline entry even when nothing else changes.
    """
    complaints_service.update_complaint(
        client, principal.user_id, complaint_id, body
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
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Add a comment. Any member may comment; only admins may write `internal`."""
    complaints_service.add_comment(client, principal.user_id, complaint_id, body)
    return MessageResult(message="Comment added.")


@router.post(
    "/{complaint_id}/read",
    response_model=MessageResult,
    summary="Mark a complaint as read",
)
async def mark_read(
    complaint_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Clear the caller's unread badge for this complaint.

    Read state is **per person**, not a flag on the complaint -- the frontend's
    single `hasUnreadUpdate` boolean cannot represent an admin and a resident
    having seen different versions.
    """
    complaints_service.mark_read(client, principal.user_id, complaint_id)
    return MessageResult(message="Marked as read.")


@router.post(
    "/{complaint_id}/attachments",
    response_model=ComplaintAttachment,
    status_code=status.HTTP_201_CREATED,
    summary="Register an uploaded attachment",
)
async def register_attachment(
    body: RegisterAttachmentRequest,
    complaint_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ComplaintAttachment:
    """Record a file already uploaded to Supabase Storage.

    The bytes never pass through this API: the client uploads straight to
    Storage and then registers the path here. Keeps large uploads off the
    application server.
    """
    return complaints_service.register_attachment(
        client, principal.user_id, complaint_id, body
    )
