"""Pydantic DTOs for API requests and responses.

These are the wire contracts between the React frontend and the backend. They
are deliberately separate from database row shapes so the storage layer can
evolve without breaking clients.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.roles import Role


class Principal(BaseModel):
    """The authenticated caller, derived from a verified access token."""

    user_id: str
    role: Role
    phone: str | None = None
    email: str | None = None


class Profile(BaseModel):
    """A user's community profile (the ``profiles`` table row)."""

    id: str
    role: Role
    full_name: str | None = None
    phone: str | None = None
    apartment_id: str | None = None
    association_id: str | None = None
    status: str = "Active"


class Session(BaseModel):
    """A Supabase auth session returned to the client after login/redeem."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: int | None = None
    user_id: str
    role: Role | None = None


# --- Auth: phone SMS OTP login -------------------------------------------------


class OtpRequest(BaseModel):
    """Body for requesting a login OTP."""

    phone: str = Field(..., examples=["+919876543210"])


class OtpVerifyRequest(BaseModel):
    """Body for verifying a login OTP."""

    phone: str = Field(..., examples=["+919876543210"])
    token: str = Field(..., examples=["123456"], description="The 6-digit SMS code.")


class RefreshRequest(BaseModel):
    """Body for refreshing a session (the 'remember me' path)."""

    refresh_token: str


class MessageResponse(BaseModel):
    """Generic acknowledgement response."""

    message: str


# --- Invitations: admin-initiated resident registration -----------------------


class CreateInvitationRequest(BaseModel):
    """Admin request to invite a new member to an apartment."""

    phone: str = Field(..., examples=["+919812345678"])
    apartment_id: str = Field(..., examples=["B-1204"])
    full_name: str | None = None
    role: Role = Role.RESIDENT


class InvitationCreated(BaseModel):
    """Invite delivery payload — shown to the admin exactly once.

    The plaintext ``link`` and ``code`` are never persisted or re-served; only
    their hashes are stored.
    """

    invitation_id: str
    link: str
    code: str
    phone: str
    apartment_id: str
    role: Role
    expires_at: datetime


class RedeemRequest(BaseModel):
    """Resident request to redeem an invite via link token or typed code.

    Exactly one of ``token`` (from the magic link) or ``code`` (typed manually)
    must be provided, along with the phone number being registered.
    """

    phone: str
    token: str | None = None
    code: str | None = None
