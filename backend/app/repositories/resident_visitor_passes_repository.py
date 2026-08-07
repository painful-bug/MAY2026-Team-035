"""Data access for the resident visitor-pass surface.

Reads go through ``visitor_pass_overview`` (``0032``); the two writes go through
SECURITY DEFINER functions, because each of them touches the pass row, its
append-only event log and -- for a decision -- a notification, and PostgREST has
no client-side transaction.

**Neither hash is ever read back.** The view does not select ``code_hash`` or
``pass_hash``, so no query in this module could return one. The hashes travel
only inwards, as parameters to ``create_visitor_pass``.

**The ownership filter is not the security boundary.** ``0032`` puts a policy on
``visitor_requests`` covering three audiences -- the resident who holds the pass,
the community's admins, and the community's ``security`` role, which has to see a
pass it neither raised nor owns. The predicate below is narrower than all of
that on purpose: this endpoint answers "mine".
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_OVERVIEW = "visitor_pass_overview"

_PASS_SELECT = (
    "id, visitor_name, purpose, purpose_details, guest_count, status,"
    "valid_from, valid_until, checked_in_at, checked_out_at, decided_at,"
    "cancelled_at, created_at, is_current, is_lapsed"
)


def list_mine(
    client: Client,
    *,
    membership_id: str,
    current: bool | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """One page of the caller's own passes, newest first, with the total.

    ``current`` filters on ``is_current`` -- computed in the view rather than
    from a status list here, so the two tabs cannot drift from the transitions
    the RPC allows.
    """
    query = (
        client.table(_OVERVIEW)
        .select(_PASS_SELECT, count="exact")
        .eq("requested_by_membership_id", membership_id)
    )
    if current is not None:
        query = query.eq("is_current", current)

    response = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def get_mine(
    client: Client, *, membership_id: str, pass_id: str
) -> dict[str, Any] | None:
    """One pass of the caller's, or ``None``.

    The membership predicate is part of the lookup rather than a check
    afterwards, so "not yours" and "not there" cannot be told apart.
    """
    rows = (
        client.table(_OVERVIEW)
        .select(_PASS_SELECT)
        .eq("id", pass_id)
        .eq("requested_by_membership_id", membership_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def create_pass(
    client: Client,
    *,
    membership_id: str,
    visitor_name: str,
    purpose: str,
    purpose_details: str,
    guest_count: int,
    expected_at: str | None,
    pass_hash: str,
    code_hash: str,
) -> str:
    """Create a pass (RPC) from two hashes. Returns its id.

    The plaintext code and token are **not** parameters. They are minted in the
    service, hashed there, and never sent -- so they cannot appear in a statement
    log, a slow-query log or a replication stream.
    """
    try:
        response = client.rpc(
            "create_visitor_pass",
            {
                "p_membership_id": membership_id,
                "p_visitor_name": visitor_name,
                "p_purpose": purpose,
                "p_purpose_details": purpose_details,
                "p_guest_count": guest_count,
                "p_expected_at": expected_at,
                "p_pass_hash": pass_hash,
                "p_code_hash": code_hash,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not create the visitor pass."
        ) from exc
    return str(response.data)


def decide(client: Client, *, pass_id: str, decision: str) -> None:
    """Approve, reject or cancel a pass (RPC).

    One call for all three. The states a pass may be settled from are one
    invariant, and it lives in the function rather than being restated per verb.
    """
    try:
        client.rpc(
            "decide_visitor_pass",
            {"p_pass_id": pass_id, "p_decision": decision},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not update the visitor pass."
        ) from exc
