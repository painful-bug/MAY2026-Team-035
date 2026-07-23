"""Invitation routes: admin creates invites; residents redeem them (public)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_request_client, require_role
from app.domain.roles import Role
from app.domain.schemas import (
    CreateInvitationRequest,
    InvitationCreated,
    Principal,
    RedeemRequest,
    Session,
)
from app.services import invitation_service
from supabase import Client

router = APIRouter(tags=["invitations"])


@router.post(
    "/admin/invitations",
    response_model=InvitationCreated,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def create_invitation(
    body: CreateInvitationRequest,
    principal: Principal = Depends(get_current_user),
    admin_client: Client = Depends(get_request_client),
) -> InvitationCreated:
    """Admin: mint a resident invite; returns the one-time link + code."""
    return invitation_service.create_invitation(admin_client, principal, body)


@router.post("/auth/redeem", response_model=Session)
async def redeem_invitation(body: RedeemRequest) -> Session:
    """Public: redeem an invite via link token or typed code, returning a session."""
    return invitation_service.redeem(body)
