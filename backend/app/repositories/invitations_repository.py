"""Data access for the ``invitations`` table.

Writes during creation are performed with a caller-scoped (admin) client so RLS
applies; lookup + mark-redeemed during the public redeem flow run with the
service client (the resident is not yet authenticated).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.roles import Role
from supabase import Client

_TABLE = "invitations"


def insert_invitation(
    client: Client,
    *,
    token_hash: str,
    code_hash: str,
    phone: str,
    apartment_id: str,
    role: Role,
    full_name: str | None,
    created_by: str | None,
    expires_at: datetime,
) -> dict:
    """Insert a new invitation row and return it."""
    payload = {
        "token_hash": token_hash,
        "code_hash": code_hash,
        "phone": phone,
        "apartment_id": apartment_id,
        "role": role.value,
        "full_name": full_name,
        "created_by": created_by,
        "expires_at": expires_at.isoformat(),
    }
    response = client.table(_TABLE).insert(payload).execute()
    return response.data[0]


def find_by_token_hash(service_client: Client, token_hash: str) -> dict | None:
    """Return the invitation matching ``token_hash`` (magic-link path)."""
    return _find_one(service_client, "token_hash", token_hash)


def find_by_code_hash(service_client: Client, code_hash: str) -> dict | None:
    """Return the invitation matching ``code_hash`` (typed-code path)."""
    return _find_one(service_client, "code_hash", code_hash)


def mark_redeemed(service_client: Client, invitation_id: str) -> dict | None:
    """Atomically mark an invitation redeemed; return the row if we won the race.

    The ``is_("redeemed_at", None)`` filter makes this a compare-and-set: a
    second concurrent redeem updates zero rows and gets ``None`` back, enforcing
    single-use even under races.
    """
    response = (
        service_client.table(_TABLE)
        .update({"redeemed_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", invitation_id)
        .is_("redeemed_at", None)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def _find_one(client: Client, column: str, value: str) -> dict | None:
    response = client.table(_TABLE).select("*").eq(column, value).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None
