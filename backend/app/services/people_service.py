"""People service: promoting a member to administrator."""

from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError
from app.core.formatting import parse_instant
from app.core.logging import get_logger
from app.domain.people_schemas import AdminSummary, PromoteAdminRequest
from app.domain.roles import display_role
from app.repositories import people_repository as repo
from app.repositories import tenancy_repository as dash_repo
from supabase import Client

_logger = get_logger(__name__)


def _tower_of(unit_code: str | None) -> str | None:
    """Derive the tower from a unit code ('C-505' -> 'C').

    The frontend renders tower and flat as separate fields but only the full
    code is stored, because storing both invites them to disagree -- which is
    exactly the bug in ``createPendingRequestsSlice`` (see app/domain/units.py).
    """
    if not unit_code or "-" not in unit_code:
        return None
    return unit_code.split("-", 1)[0] or None


def promote_admin(
    client: Client, user_id: str, body: PromoteAdminRequest
) -> AdminSummary:
    """Give an existing member of the caller's community the ``admin`` role.

    Raises:
        NotFoundError: If no active membership in this community has that email.
        ConflictError: If that member is already an admin.
    """
    community_id = dash_repo.get_caller_community_id(client, user_id)

    membership = repo.find_active_membership_by_email(client, community_id, body.email)
    if membership is None:
        raise NotFoundError(
            "Nobody in this community uses that email address. "
            "Invite them first, then promote them once they have joined."
        )

    if str(membership.get("role", "")).lower() == "admin":
        raise ConflictError("That member is already an administrator.")

    repo.set_membership_role(client, membership["id"], "admin")
    _logger.info(
        "membership.promoted_to_admin",
        extra={"membership_id": membership["id"], "community_id": community_id},
    )

    return _to_admin_summary(client, community_id, membership)


def _to_admin_summary(
    client: Client, community_id: str, membership: dict
) -> AdminSummary:
    """Project a freshly promoted membership row into the admin DTO."""
    profile = membership.get("profiles") or {}
    unit_code = membership.get("unit_code")
    code_to_id = dash_repo.map_unit_codes_to_ids(
        client, community_id, [unit_code] if unit_code else []
    )

    return AdminSummary(
        id=membership["id"],
        profile_id=membership["profile_id"],
        name=profile.get("full_name"),
        email=profile.get("display_email"),
        phone=profile.get("phone_e164"),
        role="admin",
        display_role=display_role("ADMIN"),
        designation=None,
        flat=unit_code,
        unit_id=code_to_id.get(unit_code) if unit_code else None,
        status=membership.get("status", "active"),
        joined_at=parse_instant(membership["joined_at"]),
    )
