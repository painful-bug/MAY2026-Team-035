"""Invitation service: admin-initiated resident registration.

Two entry points:

``create_invitation``
    An admin mints an invite for one phone number and community unit. We
    generate a magic-link token and a short typable code, store only their
    hashes, and return the plaintext link + code exactly once.

``redeem``
    A resident activates their account via **either** the link token **or** the
    typed code. The validity decision (:func:`evaluate_invitation`) is a pure
    function mirroring ``frontend/src/lib/invites.js#applyRedeem`` so it is
    trivially unit-testable. On success we provision the Supabase auth user,
    atomically claim the invite into membership and residency, and mint a
    session so the resident lands logged in. They use SMS OTP thereafter.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings
from app.core import tokens
from app.core.exceptions import ConflictError, ValidationError
from app.core.logging import get_logger
from app.core.supabase_client import get_anon_client, get_service_client
from app.domain.roles import Role
from app.domain.schemas import (
    CreateInvitationRequest,
    InvitationCreated,
    Principal,
    RedeemRequest,
    Session,
)
from app.repositories import (
    invitations_repository,
    memberships_repository,
    profiles_repository,
)
from supabase import Client

_logger = get_logger(__name__)


def create_invitation(
    admin_client: Client,
    principal: Principal,
    request: CreateInvitationRequest,
) -> InvitationCreated:
    """Create an invite and return its one-time link + code (admin only)."""
    admin_membership = memberships_repository.require_active_role(
        admin_client,
        profile_id=principal.user_id,
        community_id=request.community_id,
        role=Role.ADMIN,
    )
    token = tokens.generate_token()
    code = tokens.generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=get_settings().invite_ttl_hours
    )

    row = invitations_repository.insert_invitation(
        get_service_client(),
        token_hash=tokens.hash_secret(token),
        code_hash=tokens.hash_secret(code),
        phone=request.phone,
        community_id=request.community_id,
        intended_unit_id=request.intended_unit_id,
        full_name=request.full_name,
        email=request.email,
        created_by_membership_id=admin_membership["id"],
        expires_at=expires_at,
    )

    link = f"{get_settings().frontend_base_url.rstrip('/')}/join/{token}"
    return InvitationCreated(
        invitation_id=row["id"],
        link=link,
        code=code,
        phone=request.phone,
        community_id=request.community_id,
        intended_unit_id=request.intended_unit_id,
        expires_at=datetime.fromisoformat(row["expires_at"]),
    )


def evaluate_invitation(
    invite: dict | None, *, now: datetime | None = None
) -> str | None:
    """Return a rejection reason for ``invite``, or None if it is redeemable.

    Reasons: ``"invalid"`` (no such invite), ``"used"`` (already redeemed),
    ``"expired"`` (past its TTL). Pure and side-effect free.
    """
    now = now or datetime.now(timezone.utc)
    if invite is None:
        return "invalid"
    if invite.get("status") and invite.get("status") != "issued":
        return "used"
    if invite.get("redeemed_at") is not None:
        return "used"
    expires_at = _parse_dt(invite.get("expires_at"))
    if expires_at is not None and now > expires_at:
        return "expired"
    return None


_REASON_ERRORS = {
    "invalid": ValidationError("This invite is not valid.", code="invite_invalid"),
    "used": ConflictError("This invite has already been used.", code="invite_used"),
    "expired": ValidationError("This invite has expired.", code="invite_expired"),
}


def redeem(request: RedeemRequest) -> Session:
    """Redeem an invite via link token or typed code and return a session."""
    if not request.token and not request.code:
        raise ValidationError("Provide an invite link token or code.")

    service = get_service_client()

    # Resolve the invite from whichever artifact the resident supplied.
    if request.token:
        invite = invitations_repository.find_by_token_hash(
            service, tokens.hash_secret(request.token)
        )
    else:
        code_hash = tokens.hash_secret(tokens.normalize_code(request.code or ""))
        invite = invitations_repository.find_by_code_hash(service, code_hash)

    reason = evaluate_invitation(invite)
    if reason is not None:
        raise _REASON_ERRORS[reason]
    assert invite is not None  # narrowed by evaluate_invitation
    if invite.get("invitee_phone_e164") != request.phone:
        # Do not disclose that a real invitation exists for another number.
        raise _REASON_ERRORS["invalid"]

    # Auth provisioning happens first; the SQL RPC below then consumes the
    # invite and creates membership + residency in one database transaction.
    # A failed claim therefore never creates partial domain access.
    session = _provision_and_login(
        phone=request.phone,
        full_name=invite.get("invitee_name"),
        community_id=invite.get("community_id"),
        intended_unit_id=invite.get("intended_unit_id"),
    )
    memberships_repository.claim_resident_invite(
        service,
        invite_id=invite["id"],
        profile_id=session.user_id,
    )
    _logger.info(
        "Invitation %s redeemed for unit %s",
        invite["id"],
        invite.get("intended_unit_id"),
    )
    return session


def _provision_and_login(
    *,
    phone: str,
    full_name: str | None,
    community_id: str | None,
    intended_unit_id: str | None,
) -> Session:
    """Create the auth user + profile and mint an initial session.

    Immediate login uses a one-time random password (the resident never sees it
    and authenticates via SMS OTP thereafter). The account is created with its
    phone pre-confirmed since the admin vouches for the number.
    """
    service = get_service_client()
    one_time_password = secrets.token_urlsafe(24)

    try:
        created = service.auth.admin.create_user(
            {
                "phone": phone,
                "phone_confirm": True,
                "password": one_time_password,
                "user_metadata": {
                    "full_name": full_name,
                    "community_id": community_id,
                    "intended_unit_id": intended_unit_id,
                },
            }
        )
    except Exception as exc:  # noqa: BLE001 - map SDK/duplicate errors
        raise ConflictError(
            "An account for this phone number already exists. Log in instead.",
            code="user_exists",
        ) from exc

    user = created.user
    if user is None:
        raise ConflictError("Could not create the account.")

    # Ensure identity fields are set even if the Auth trigger raced or lacked
    # metadata.  Membership/residency is claimed by the transactional RPC.
    profiles_repository.upsert_profile(
        service,
        user_id=user.id,
        full_name=full_name,
        phone=phone,
    )

    result = get_anon_client().auth.sign_in_with_password(
        {"phone": phone, "password": one_time_password}
    )
    if result.session is None:
        raise ConflictError("Account created but sign-in failed. Use OTP login.")
    return _session_from_result(result.session, user.id, Role.RESIDENT)


def _session_from_result(session: Any, user_id: str, role: Role) -> Session:
    return Session(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_at=getattr(session, "expires_at", None),
        user_id=user_id,
        role=role,
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
