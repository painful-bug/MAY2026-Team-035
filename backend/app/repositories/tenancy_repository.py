"""Tenancy lookups shared by every admin-dashboard service.

What survives of the old ``dashboard_repository``. The dashboard reads it was
named for now come from the shared ``GET /dashboard/snapshot``, so the counting
and listing functions are gone (see ``docs/FRONTEND_WIRING_AUDIT.md``). These two
remain because every service needs them.

Both were rewritten for the clean baseline, which renamed the tables they used:

* ``profiles.association_id`` -> ``community_memberships.community_id``
* ``apartments (association_id, code)`` -> ``units (community_id, unit_code)``
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from supabase import Client

_MEMBERSHIPS = "community_memberships"
_UNITS = "units"


def get_caller_community_id(client: Client, user_id: str) -> str:
    """Return the community the caller belongs to.

    Resolved from ``community_memberships`` using the same table, filters and
    ordering as ``app.api.deps.get_active_membership``, so a handler holding an
    injected ``MembershipContext`` and a service calling this function can never
    disagree about which community is active.

    Prefer the injected ``MembershipContext.community_id`` in new handlers. This
    exists because thirty-odd service call sites take ``(client, user_id)``, and
    threading a FastAPI-shaped object through the service layer would couple
    services to the web framework for no behavioural gain.

    Raises:
        NotFoundError: If the caller has no active membership in any community.
    """
    response = (
        client.table(_MEMBERSHIPS)
        .select("community_id")
        .eq("profile_id", user_id)
        .eq("status", "active")
        .is_("ended_at", None)
        .order("is_default_community", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        # Authenticated, but not placed in a community. A real state (a user
        # mid-onboarding), not an error in the caller's request -- but every
        # dashboard read is meaningless without it.
        raise NotFoundError("You do not belong to a community yet.")

    community_id = rows[0].get("community_id")
    if not community_id:
        raise NotFoundError("You do not belong to a community yet.")
    return community_id


def map_unit_codes_to_ids(
    client: Client, community_id: str, codes: list[str]
) -> dict[str, str]:
    """Resolve unit codes ('B-1204') to ``units.id`` for the R23 label+id pairing.

    Done as a separate lookup rather than a PostgREST embed because the path from
    a membership to a unit runs through ``unit_residencies``, and a silently-empty
    embed is far worse than an explicit second query. One extra round trip per page.
    """
    if not codes:
        return {}
    response = (
        client.table(_UNITS)
        .select("id, unit_code")
        .eq("community_id", community_id)
        .in_("unit_code", codes)
        .execute()
    )
    return {row["unit_code"]: row["id"] for row in (response.data or [])}
