"""Data access for the admin dashboard reads.

Every function takes a caller-scoped client, so Row-Level Security decides what
is visible and this layer never has to filter by community for *security*. It
still filters by community for *correctness* -- an admin who belongs to two
communities would otherwise see both blended into one dashboard.
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from supabase import Client

_ASSOCIATIONS = "associations"
_PROFILES = "profiles"
_MEMBERSHIPS = "community_memberships"
_COMPLAINTS = "complaints"
_NOTICES = "notices"
_APARTMENTS = "apartments"

# Complaint statuses that count as "active" on the dashboard tile. Mirrors the
# frontend's `complaints.filter(c => c.status !== 'Resolved')`, expanded to the
# real status vocabulary from migration 0011.
_ACTIVE_COMPLAINT_STATUSES = ("pending", "in_progress", "reopened")


def get_caller_community_id(client: Client, user_id: str) -> str:
    """Return the community the caller belongs to.

    Read from ``profiles.association_id`` rather than ``community_memberships``
    on purpose: it is the compatibility column that migration 0010 keeps in sync
    by trigger, it is a single indexed row, and it is the same value the JWT hook
    and the RLS helpers resolve. One source, no chance of disagreement.

    Raises:
        NotFoundError: If the caller has no profile or belongs to no community.
    """
    response = (
        client.table(_PROFILES)
        .select("association_id")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Profile not found.")

    community_id = rows[0].get("association_id")
    if not community_id:
        # Authenticated, but not placed in a community. A real state (a user
        # mid-onboarding), not an error in the caller's request -- but every
        # dashboard read is meaningless without it.
        raise NotFoundError("You do not belong to a community yet.")
    return community_id


def get_community(client: Client, community_id: str) -> dict:
    """Fetch the community row."""
    response = (
        client.table(_ASSOCIATIONS)
        .select("id, name, community_type, status, created_at")
        .eq("id", community_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Community not found.")
    return rows[0]


def count_residents(client: Client, community_id: str) -> int:
    """Count active resident memberships."""
    response = (
        client.table(_MEMBERSHIPS)
        .select("id", count="exact")
        .eq("community_id", community_id)
        .eq("role", "RESIDENT")
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    return response.count or 0


def count_active_complaints(client: Client, community_id: str) -> int:
    """Count complaints that are not resolved or closed."""
    response = (
        client.table(_COMPLAINTS)
        .select("id", count="exact")
        .eq("community_id", community_id)
        .in_("status", list(_ACTIVE_COMPLAINT_STATUSES))
        .limit(1)
        .execute()
    )
    return response.count or 0


def count_pending_registrations(client: Client, community_id: str) -> int:
    """Count registration requests awaiting review (real as of migration 0012)."""
    response = (
        client.table("registration_requests")
        .select("id", count="exact")
        .eq("community_id", community_id)
        .eq("status", "pending")
        .limit(1)
        .execute()
    )
    return response.count or 0


def list_residents(
    client: Client,
    community_id: str,
    *,
    search: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """Page through resident memberships with their profile fields.

    Returns ``(rows, total)``. ``profiles`` is embedded via the single foreign key
    ``community_memberships.profile_id -> profiles.id``; ``!inner`` makes it a
    join rather than a left join so that filtering on a profile column works.
    """
    query = (
        client.table(_MEMBERSHIPS)
        .select(
            "id, profile_id, role, status, joined_at,"
            "profiles!inner(full_name, email, phone, apartment_id, status)",
            count="exact",
        )
        .eq("community_id", community_id)
        .eq("role", "RESIDENT")
    )

    if search:
        # Escape PostgREST's filter delimiters. An unescaped comma would split
        # the `or` expression and silently widen the query.
        safe = search.replace("%", r"\%").replace(",", " ").replace("(", " ").replace(")", " ")
        pattern = f"%{safe}%"
        query = query.or_(
            f"full_name.ilike.{pattern},apartment_id.ilike.{pattern},"
            f"phone.ilike.{pattern},email.ilike.{pattern}",
            reference_table="profiles",
        )

    response = (
        query.order("joined_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def map_unit_codes_to_ids(
    client: Client, community_id: str, codes: list[str]
) -> dict[str, str]:
    """Resolve flat codes ('B-1204') to ``apartments.id`` for the R23 label+id pairing.

    Done as a separate lookup rather than a PostgREST embed because the path from
    a membership to a flat runs through ``unit_residencies``, whose foreign keys
    are *composite* ``(unit_id, community_id)``. PostgREST's embedding does not
    reliably resolve composite foreign keys, and a silently-empty embed is far
    worse than an explicit second query. One extra round trip per page.
    """
    if not codes:
        return {}
    response = (
        client.table(_APARTMENTS)
        .select("id, code")
        .eq("association_id", community_id)
        .in_("code", codes)
        .execute()
    )
    return {row["code"]: row["id"] for row in (response.data or [])}


def list_notices(
    client: Client, community_id: str, *, offset: int, limit: int
) -> tuple[list[dict], int]:
    """Page through published notices, newest first."""
    response = (
        client.table(_NOTICES)
        .select(
            "id, title, body, category, urgency, published_at",
            count="exact",
        )
        .eq("community_id", community_id)
        .eq("status", "published")
        .order("published_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)
