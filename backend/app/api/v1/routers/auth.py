"""Authentication routes: phone SMS OTP login, refresh, and current profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_request_client
from app.domain.schemas import (
    MessageResponse,
    OtpRequest,
    OtpVerifyRequest,
    Principal,
    Profile,
    RefreshRequest,
    Session,
)
from app.services import auth_service
from supabase import Client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request", response_model=MessageResponse)
async def request_otp(body: OtpRequest) -> MessageResponse:
    """Send a login OTP to an existing member's phone."""
    auth_service.request_login_otp(body.phone)
    return MessageResponse(message="If the number is registered, a code has been sent.")


@router.post("/otp/verify", response_model=Session)
async def verify_otp(body: OtpVerifyRequest) -> Session:
    """Verify the SMS OTP and return a session."""
    return auth_service.verify_login_otp(body.phone, body.token)


@router.post("/refresh", response_model=Session)
async def refresh(body: RefreshRequest) -> Session:
    """Refresh an existing session (the 'remember me' path)."""
    return auth_service.refresh_session(body.refresh_token)


@router.get("/me", response_model=Profile)
async def me(
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Profile:
    """Return the authenticated caller's profile."""
    return auth_service.get_me(client, principal)
