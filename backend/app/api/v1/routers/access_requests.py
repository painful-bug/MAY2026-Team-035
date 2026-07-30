"""Resident join requests and the administrator decision queue."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, require_csrf
from app.domain.schemas import (
    AccessRequestListResponse,
    AccessRequestResponse,
    ApproveAccessRequest,
    BlacklistAccessRequest,
    CreateAccessRequest,
    Principal,
    RejectAccessRequest,
)
from app.services import access_request_service

router = APIRouter(tags=["access requests"])


@router.post(
    "/access-requests",
    response_model=AccessRequestResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_access_request(
    body: CreateAccessRequest,
    principal: Principal = Depends(get_current_user),
) -> AccessRequestResponse:
    return access_request_service.create(body, principal)


@router.get("/access-requests/mine", response_model=AccessRequestListResponse)
def my_access_requests(
    principal: Principal = Depends(get_current_user),
) -> AccessRequestListResponse:
    return access_request_service.mine(principal)


@router.post(
    "/access-requests/{request_id}/withdraw",
    response_model=AccessRequestResponse,
    dependencies=[Depends(require_csrf)],
)
def withdraw_access_request(
    request_id: str,
    principal: Principal = Depends(get_current_user),
) -> AccessRequestResponse:
    return access_request_service.withdraw(request_id, principal)


@router.get("/admin/access-requests", response_model=AccessRequestListResponse)
def admin_access_requests(
    status: str = Query("pending", pattern="^(pending|approved|rejected|withdrawn)$"),
    limit: int = Query(25, ge=1, le=100),
    principal: Principal = Depends(get_current_user),
) -> AccessRequestListResponse:
    return access_request_service.list_for_admin(principal, status=status, limit=limit)


@router.post(
    "/admin/access-requests/{request_id}/approve",
    dependencies=[Depends(require_csrf)],
)
def approve_access_request(
    request_id: str,
    body: ApproveAccessRequest,
    principal: Principal = Depends(get_current_user),
) -> dict:
    return access_request_service.approve(request_id, body, principal)


@router.post(
    "/admin/access-requests/{request_id}/reject",
    dependencies=[Depends(require_csrf)],
)
def reject_access_request(
    request_id: str,
    body: RejectAccessRequest,
    principal: Principal = Depends(get_current_user),
) -> dict:
    return access_request_service.reject(request_id, body, principal)


@router.post(
    "/admin/access-requests/{request_id}/blacklist",
    dependencies=[Depends(require_csrf)],
)
def blacklist_access_request(
    request_id: str,
    body: BlacklistAccessRequest,
    principal: Principal = Depends(get_current_user),
) -> dict:
    return access_request_service.blacklist(request_id, body, principal)
