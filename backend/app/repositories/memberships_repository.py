"""Tenant-scoped membership lookups and trusted invitation claims."""

from __future__ import annotations

from app.core.exceptions import AuthorizationError, ConflictError
from app.domain.roles import Role
from supabase import Client


def require_active_role(
    caller_client: Client,
    *,
    profile_id: str,
    community_id: str,
    role: Role,
) -> dict:
    """Return the caller's active membership or reject a cross-tenant action.

    The caller-scoped client is intentional: PostgreSQL RLS makes this check a
    second boundary after the coarse JWT role guard.
    """
    response = (
        caller_client.table("community_memberships")
        .select("id, community_id, profile_id, role, status, ended_at")
        .eq("profile_id", profile_id)
        .eq("community_id", community_id)
        .eq("role", role.value.lower())
        .eq("status", "active")
        .is_("ended_at", None)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise AuthorizationError(
            "You do not have that role in this community.",
            code="community_role_required",
        )
    return rows[0]


def claim_resident_invite(
    service_client: Client,
    *,
    invite_id: str,
    profile_id: str,
) -> dict:
    """Atomically create membership/residency and consume an invite."""
    response = service_client.rpc(
        "claim_resident_invite",
        {"p_invite_id": invite_id, "p_profile_id": profile_id},
    ).execute()
    data = response.data
    if isinstance(data, list):
        result = data[0] if data else None
    else:
        result = data
    if not isinstance(result, dict):
        raise ConflictError(
            "This invite could not be claimed.", code="invite_claim_failed"
        )
    return result
