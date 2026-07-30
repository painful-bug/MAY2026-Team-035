"""People routes: residents, admins, and registration review.

Note what is *not* here: submitting a registration request. That is part of
registration, which is out of scope for this workstream -- these endpoints are
the admin-facing review half only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.deps import get_current_user, get_request_client, require_role
from app.domain.common_schemas import MessageResult, Page
from app.domain.people_schemas import (
    AdminSummary,
    ApprovedRegistration,
    RegistrationRequestSummary,
    RejectRegistrationRequest,
    UpdateResidentRequest,
)
from app.domain.roles import Role
from app.services import people_service
from supabase import Client

router = APIRouter(tags=["people"], dependencies=[Depends(require_role(Role.ADMIN))])


@router.get("/admins", response_model=Page[AdminSummary], summary="List admins")
async def list_admins(
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[AdminSummary]:
    """Every admin of the caller's community.

    Returned in the standard page envelope for consistency, but not paginated --
    an association has a committee, not a directory.
    """
    return people_service.list_admins(client, principal.user_id)


@router.patch(
    "/residents/{membership_id}",
    response_model=MessageResult,
    summary="Update a resident",
)
async def update_resident(
    body: UpdateResidentRequest,
    membership_id: str = Path(
        ..., description="The membership id, not the profile id."
    ),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Patch a resident's editable fields. Omitted fields are left unchanged."""
    people_service.update_resident(client, principal.user_id, membership_id, body)
    return MessageResult(message="Resident updated.")


@router.delete(
    "/residents/{membership_id}",
    response_model=MessageResult,
    summary="Remove a resident",
)
async def remove_resident(
    membership_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Deactivate a resident and end their residency.

    **This is not a delete.** Complaints, invoices and payments reference the
    membership; removing the row would either cascade them away or fail outright.
    The member stops appearing in active lists and the flat reads as vacant.

    Returns 409 if an admin tries to remove their own membership -- there is no
    recovery path from locking a community out of its own dashboard.
    """
    people_service.remove_resident(client, principal.user_id, membership_id)
    return MessageResult(message="Resident removed.")


@router.get(
    "/registrations",
    response_model=Page[RegistrationRequestSummary],
    summary="List registration requests",
)
async def list_registrations(
    response: Response,
    status_filter: str = Query(
        "pending",
        alias="status",
        pattern="^(pending|approved|rejected)$",
        description="Which requests to return.",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[RegistrationRequestSummary]:
    """Self-signup requests awaiting review, newest first."""
    # Carries a server-formatted `date`, so it must not be cached.
    response.headers["Cache-Control"] = "no-store"
    return people_service.list_registration_requests(
        client,
        principal.user_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/registrations/{request_id}/approve",
    response_model=ApprovedRegistration,
    status_code=status.HTTP_201_CREATED,
    summary="Approve a registration request",
)
async def approve_registration(
    request_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ApprovedRegistration:
    """Approve a request and mint the applicant's invitation, atomically.

    **Approval does not create an active account.** It issues an invite the
    applicant redeems, because the invite token is a mandatory second factor.
    The returned ``link`` and ``code`` are shown once and are not recoverable.

    201 rather than 200: this creates an invitation.
    """
    return people_service.approve_registration(client, principal.user_id, request_id)


@router.post(
    "/registrations/{request_id}/reject",
    response_model=MessageResult,
    summary="Reject a registration request",
)
async def reject_registration(
    body: RejectRegistrationRequest | None = None,
    request_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Reject a pending request. The applicant may apply again."""
    people_service.reject_registration(
        client, principal.user_id, request_id, body.reason if body else None
    )
    return MessageResult(message="Registration request rejected.")
