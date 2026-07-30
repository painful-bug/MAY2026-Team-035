"""Data access for the notice board.

One insert, through the caller-scoped client so RLS applies. No RPC: publishing a
notice is a single-table, single-statement write, so the transaction PostgREST
gives it for free is the whole transaction it needs.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.pg_errors import translate
from supabase import Client

_NOTICES = "notices"


def insert_notice(
    client: Client,
    *,
    community_id: str,
    membership_id: str,
    title: str,
    body_text: str,
    category: str,
    urgency: str,
) -> dict:
    """Insert a published notice and return the stored row.

    ``published_at`` is sent as an explicit timestamp rather than defaulted in the
    table: the column is nullable so a future draft state stays possible, and a
    table default of ``now()`` would make an unpublished draft unrepresentable.
    It is a client-side ISO string because PostgREST sends JSON -- a literal
    ``"now()"`` would be stored as that seven-character string, not evaluated.

    ``category`` and ``urgency`` are added by our additive migration 0018 -- the
    clean baseline's ``notices`` table has neither.
    """
    payload = {
        "community_id": community_id,
        "author_membership_id": membership_id,
        "title": title,
        "body": body_text,
        "category": category,
        "urgency": urgency,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = client.table(_NOTICES).insert(payload).execute()
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error
        raise translate(exc, default_message="Could not post the notice.") from exc

    rows = response.data or []
    if not rows:
        # PostgREST returns the inserted row unless the insert was silently
        # filtered by RLS. Treat that as a failure, not an empty success --
        # returning a 201 with no id would be a lie.
        raise translate(
            RuntimeError("Notice insert returned no row; check RLS on notices."),
            default_message="Could not post the notice.",
        )
    return rows[0]
