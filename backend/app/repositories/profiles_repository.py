"""Data access for identity-only ``profiles`` rows.

Community membership and residency intentionally live in their own tables;
this repository must never use ``profiles`` as an authorization source.
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.domain.schemas import Profile
from supabase import Client

_TABLE = "profiles"


def get_profile(client: Client, user_id: str) -> Profile:
    """Fetch a single profile by user id.

    Args:
        client: A Supabase client (typically caller-scoped, so RLS applies).
        user_id: The auth user's UUID.

    Raises:
        NotFoundError: If no visible profile exists for ``user_id``.
    """
    response = (
        client.table(_TABLE).select("*").eq("id", user_id).limit(1).execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Profile not found.")
    return _to_profile(rows[0])


def upsert_profile(
    service_client: Client,
    *,
    user_id: str,
    full_name: str | None,
    phone: str | None,
    email: str | None = None,
) -> Profile:
    """Create or update a user's identity profile (service-role only).

    Used after Supabase Auth provisioning.  It may write a row the newly
    created user cannot yet read, so it deliberately receives a service client.
    """
    payload = {
        "id": user_id,
        "full_name": full_name,
        "phone_e164": phone,
        "display_email": email,
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    response = (
        service_client.table(_TABLE).upsert(payload, on_conflict="id").execute()
    )
    return _to_profile(response.data[0])


def _to_profile(row: dict) -> Profile:
    """Map a raw table row to a :class:`Profile`."""
    return Profile(
        id=row["id"],
        full_name=row.get("full_name"),
        phone=row.get("phone_e164"),
        email=row.get("display_email"),
        is_active=row.get("is_active", True),
    )
