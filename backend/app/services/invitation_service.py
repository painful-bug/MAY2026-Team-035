"""Email-bound invitations redeemed only by the matching Google identity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.core import tokens
from app.core.exceptions import ConflictError, ValidationError
from app.core.logging import get_logger
from app.core.supabase_client import get_service_client
from app.domain.schemas import CreateInvitationRequest, InvitationCreated, Principal
from app.repositories import invitations_repository, memberships_repository, profiles_repository
from supabase import Client

_logger = get_logger(__name__)


def normalized_email(email: str) -> str:
    value = email.strip().casefold()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValidationError("A valid invitation email is required.")
    return value


def create_invitation(admin_client: Client, principal: Principal, request: CreateInvitationRequest) -> InvitationCreated:
    memberships = (
        admin_client.table("community_memberships")
        .select("id, community_id")
        .eq("profile_id", principal.user_id)
        .eq("role", "admin")
        .eq("status", "active")
        .is_("ended_at", None)
        .order("is_default_community", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not memberships:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError(
            "An active administrator membership is required.",
            code="community_role_required",
        )
    admin_membership = memberships[0]
    token = tokens.generate_token()
    code = tokens.generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=get_settings().invite_ttl_hours)
    email = normalized_email(request.invitee_email)
    row = invitations_repository.insert_invitation(
        get_service_client(), token_hash=tokens.hash_secret(token), code_hash=tokens.hash_secret(code),
        phone=request.phone, invitee_email=email, community_id=admin_membership["community_id"],
        intended_unit_id=request.intended_unit_id, full_name=request.full_name,
        created_by_membership_id=admin_membership["id"], expires_at=expires_at,
    )
    return InvitationCreated(
        invitation_id=row["id"], link=f"{get_settings().frontend_base_url.rstrip('/')}/join/{token}",
        code=code, invitee_email=email, community_id=admin_membership["community_id"],
        intended_unit_id=request.intended_unit_id, expires_at=datetime.fromisoformat(row["expires_at"]),
    )


def resolve_invitation(*, token: str | None, code: str | None) -> dict:
    if bool(token) == bool(code):
        raise ValidationError("Provide one invitation link or code.")
    service = get_service_client()
    invite = (
        invitations_repository.find_by_token_hash(service, tokens.hash_secret(token))
        if token else invitations_repository.find_by_code_hash(service, tokens.hash_secret(tokens.normalize_code(code or "")))
    )
    if evaluate_invitation(invite) is not None:
        # A generic response avoids letting an unauthenticated caller enumerate
        # invitation validity or invitee addresses.
        raise ValidationError("This invitation cannot be used.", code="invite_unavailable")
    assert invite is not None
    return invite


def evaluate_invitation(invite: dict | None, *, now: datetime | None = None) -> str | None:
    now = now or datetime.now(timezone.utc)
    if invite is None:
        return "invalid"
    if invite.get("status") and invite.get("status") != "issued" or invite.get("redeemed_at") is not None:
        return "used"
    raw_expiry = invite.get("expires_at")
    if raw_expiry:
        expiry = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if now > expiry:
            return "expired"
    return None


def redeem_pending_invitation(invite: dict, identity: Principal) -> dict:
    if not identity.email_verified or not identity.email:
        raise ValidationError("A verified Google email is required.", code="email_not_verified")
    if normalized_email(identity.email) != normalized_email(str(invite.get("invitee_email") or "")):
        raise ValidationError("This invitation cannot be used.", code="invite_unavailable")
    service = get_service_client()
    profiles_repository.upsert_profile(
        service, user_id=identity.user_id, full_name=invite.get("invitee_name"),
        phone=invite.get("invitee_phone_e164"), email=identity.email,
    )
    try:
        result = memberships_repository.claim_resident_invite(service, invite_id=invite["id"], profile_id=identity.user_id)
    except ConflictError:
        raise
    _logger.info("Email-bound invitation %s redeemed", invite["id"])
    return result
