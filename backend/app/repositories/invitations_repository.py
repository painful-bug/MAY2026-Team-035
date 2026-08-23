"""Data access for one-time ``resident_invites`` rows.

The service verifies the caller's tenant-scoped admin membership before using a
service client to create an invite. Public redemption is claimed through a
trusted SQL RPC because the resident has not authenticated yet.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.roles import Role
from supabase import Client

_TABLE = "resident_invites"


def insert_invitation(
    client: Client,
    *,
    token_hash: str,
    code_hash: str,
    phone: str | None,
    invitee_email: str,
    community_id: str,
    intended_unit_id: str,
    full_name: str | None,
    created_by_membership_id: str,
    expires_at: datetime,
) -> dict:
    """Insert a new invitation row and return it."""
    payload = {
        "token_hash": token_hash,
        "code_hash": code_hash,
        "invitee_phone_e164": phone,
        "invitee_email": invitee_email,
        "community_id": community_id,
        "intended_unit_id": intended_unit_id,
        "invitee_name": full_name,
        "intended_role": Role.RESIDENT.value.lower(),
        "created_by_membership_id": created_by_membership_id,
        "expires_at": expires_at.isoformat(),
        "legacy_unit_code": "UNKNOWN",
    }
    response = client.table(_TABLE).insert(payload).execute()
    return response.data[0]


def find_by_token_hash(service_client: Client, token_hash: str) -> dict | None:
    """Return the invitation matching ``token_hash`` (magic-link path)."""
    return _find_one(service_client, "token_hash", token_hash)


def find_by_code_hash(service_client: Client, code_hash: str) -> dict | None:
    """Return the invitation matching ``code_hash`` (typed-code path)."""
    return _find_one(service_client, "code_hash", code_hash)


def _find_one(client: Client, column: str, value: str) -> dict | None:
    response = client.table(_TABLE).select("*").eq(column, value).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None
