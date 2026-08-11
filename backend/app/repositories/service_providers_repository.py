"""Data access for service-provider profiles and the skill catalogue.

Reads go through ``service_provider_overview``; writes go through the three
SECURITY DEFINER functions in ``0034`` 10. That is the house split, and here it
is also the security boundary: ``service_providers`` carries a read policy and
**no insert, update or delete policy at all**, matching ``0031``. There is no
path from this process to a row it does not own.

Every function takes the caller's request client rather than the service client.
All three RPCs resolve the provider from ``auth.uid()`` themselves, and
``auth.uid()`` does not exist on the service client -- passing the wrong one
would not fail loudly, it would raise "sign in required" for a caller who is
signed in.
"""

from __future__ import annotations

from typing import Any

from postgrest.exceptions import APIError

from app.core.exceptions import ServiceUnavailableError
from app.core.pg_errors import translate
from supabase import Client

_OVERVIEW = "service_provider_overview"
_SKILLS = "skills"

#: Everything ``ServiceProviderProfile`` renders. Listed rather than ``*`` so a
#: column added to the view later does not silently widen this response.
_PROFILE_SELECT = (
    "id, profile_id, display_name, headline, bio, phone_e164, latitude, "
    "longitude, service_radius_km, status, is_available, skill_ids, "
    "skill_names, community_count, created_at, updated_at"
)


def get_by_profile(client: Client, *, profile_id: str) -> dict[str, Any] | None:
    """The caller's own provider row, or ``None`` if they never registered."""
    rows = (
        client.table(_OVERVIEW)
        .select(_PROFILE_SELECT)
        .eq("profile_id", profile_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_skills(client: Client) -> list[dict[str, Any]]:
    """The active skill catalogue, alphabetically.

    Retired trades are filtered here rather than deleted in the database: a
    provider who has held a skill for two years keeps the row that says so, and
    a deleted skill would take their history with it (``on delete restrict``
    would refuse, which is the same problem wearing a different hat).
    """
    return (
        client.table(_SKILLS)
        .select("id, name, category, description")
        .eq("is_active", True)
        .order("name")
        .execute()
        .data
        or []
    )


def save_profile(
    client: Client,
    *,
    display_name: str,
    headline: str | None,
    bio: str | None,
    phone: str | None,
    latitude: float | None,
    longitude: float | None,
    service_radius_km: float | None,
) -> str:
    """Register or edit the caller's profile (RPC). Returns the provider id.

    Idempotent on ``profile_id``: a second registration edits the first rather
    than colliding with it. A ``null`` argument leaves the stored value alone --
    the RPC coalesces -- so this is safe to call with a partial body.
    """
    try:
        response = client.rpc(
            "upsert_service_provider",
            {
                "p_display_name": display_name,
                "p_headline": headline,
                "p_bio": bio,
                "p_phone_e164": phone,
                "p_latitude": latitude,
                "p_longitude": longitude,
                "p_service_radius_km": service_radius_km,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not save the service provider profile."
        ) from exc
    return str(response.data or "")


def register_profile(
    client: Client,
    *,
    display_name: str,
    headline: str | None,
    phone: str | None,
    latitude: float,
    longitude: float,
    service_radius_km: float,
    skill_ids: list[str],
) -> str:
    """Atomically create/repair the caller's profile and complete skill set."""
    try:
        response = client.rpc(
            "register_service_provider",
            {
                "p_display_name": display_name,
                "p_headline": headline,
                "p_phone_e164": phone,
                "p_latitude": latitude,
                "p_longitude": longitude,
                "p_service_radius_km": service_radius_km,
                "p_skill_ids": skill_ids,
            },
        ).execute()
    except APIError as exc:
        # The atomic registration RPC is introduced by the forward-only
        # service-professional migration. Retrying with the old two-write path
        # would permit a partial profile, so report the rollout mismatch.
        if exc.code == "PGRST202" and "register_service_provider" in exc.message:
            raise ServiceUnavailableError(
                "Service-professional registration is being set up. Please try again shortly.",
                code="service_provider_registration_not_deployed",
            ) from exc
        raise translate(
            exc, default_message="Could not register the service provider."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not register the service provider."
        ) from exc
    return str(response.data or "")


def set_skills(client: Client, *, skill_ids: list[str]) -> int:
    """Replace the caller's trades (RPC). Returns how many they now hold."""
    try:
        response = client.rpc(
            "set_service_provider_skills", {"p_skill_ids": skill_ids}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not save your skills.") from exc
    return int(response.data or 0)


def set_availability(client: Client, *, is_available: bool) -> bool:
    """Flip the offline toggle (RPC). Returns what the database settled on."""
    try:
        response = client.rpc(
            "set_service_provider_availability", {"p_is_available": is_available}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not change your availability."
        ) from exc
    return bool(response.data)
