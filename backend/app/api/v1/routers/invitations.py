"""Membership invitations, with a Google-email-bound public activation flow."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from supabase import Client

from app.api.deps import get_current_user, get_request_client, get_request_token, require_csrf
from app.core.web_session import INVITATION_COOKIE, clear_cookie, set_transaction_cookie, sign_payload, verify_payload
from app.core.supabase_client import get_service_client
from app.domain.schemas import (
    CreateInvitationRequest, InvitationCreated, MessageResponse, PrepareInvitationRequest,
    Principal, RedeemInvitationRequest,
)
from app.services import auth_service, invitation_service

router = APIRouter(tags=["invitations"])


@router.post("/admin/invitations", response_model=InvitationCreated, dependencies=[Depends(require_csrf)])
async def create_invitation(
    body: CreateInvitationRequest,
    principal: Principal = Depends(get_current_user),
    admin_client: Client = Depends(get_request_client),
) -> InvitationCreated:
    return invitation_service.create_invitation(admin_client, principal, body)


@router.post("/invitations/prepare", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def prepare_invitation(body: PrepareInvitationRequest, response: Response) -> MessageResponse:
    invite = invitation_service.resolve_invitation(token=body.token, code=body.code)
    set_transaction_cookie(response, INVITATION_COOKIE, sign_payload({"invite_id": invite["id"]}, ttl_seconds=300))
    return MessageResponse(message="Invitation ready.")


@router.post("/invitations/redeem", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def redeem_invitation(
    _: RedeemInvitationRequest,
    request: Request,
    response: Response,
    access_token: str = Depends(get_request_token),
) -> MessageResponse:
    pending = verify_payload(request.cookies.get(INVITATION_COOKIE))
    invite_id = pending.get("invite_id")
    invite = get_service_client().table("resident_invites").select("*").eq("id", invite_id).limit(1).execute().data
    if not invite:
        from app.core.exceptions import ValidationError
        raise ValidationError("This invitation cannot be used.", code="invite_unavailable")
    identity = auth_service.google_identity(access_token)
    invitation_service.redeem_pending_invitation(invite[0], identity)
    clear_cookie(response, INVITATION_COOKIE)
    return MessageResponse(message="Invitation redeemed.")
