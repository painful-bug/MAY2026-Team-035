"""Data access for the ``profiles`` table.

Reads use a caller-scoped client so Row-Level Security applies; privileged
writes performed during provisioning use the service-role client passed in by
the service layer.
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.domain.roles import Role
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


def upsert_profile_role(
    service_client: Client,
    *,
    user_id: str,
    role: Role,
    full_name: str | None,
    phone: str | None,
    apartment_id: str | None,
    association_id: str | None = None,
) -> Profile:
    """Create or update a profile's role/placement (service-role only).

    Used by the invite-redeem flow after the auth user is provisioned. Runs with
    the service client because it may write rows the new user cannot yet see.
    """
    payload = {
        "id": user_id,
        "role": role.value,
        "full_name": full_name,
        "phone": phone,
        "apartment_id": apartment_id,
        "association_id": association_id,
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
        role=Role(row["role"]),
        full_name=row.get("full_name"),
        phone=row.get("phone"),
        apartment_id=row.get("apartment_id"),
        association_id=row.get("association_id"),
        status=row.get("status", "Active"),
    )
