"""Tenancy lookups shared by every admin-dashboard service.

What survives of the old ``dashboard_repository``. The dashboard reads it was
named for now come from the shared ``GET /dashboard/snapshot``, so the counting
and listing functions are gone (see ``docs/FRONTEND_WIRING_AUDIT.md``).

``get_caller_community_id`` is gone too: it re-ran the membership query that
``app.api.deps.get_active_membership`` had already resolved for the same
request, so the routers now thread ``MembershipContext.community_id`` into the
services instead.

Rewritten for the clean baseline, which renamed the tables it uses:

* ``apartments (association_id, code)`` -> ``units (community_id, unit_code)``
"""

from __future__ import annotations

from supabase import Client

_UNITS = "units"


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
