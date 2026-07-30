"""Data access for administrator promotion.

Reads and simple writes go through the caller-scoped client so RLS applies.

Rewritten for the clean baseline, which renamed every column this module used:
``profiles.email`` -> ``display_email``, ``profiles.phone`` -> ``phone_e164``,
``profiles.apartment_id`` -> a join through ``unit_residencies`` to
``units.unit_code``, and the ``role`` vocabulary from uppercase to the lowercase
``public.membership_role`` enum.
"""

from __future__ import annotations

from app.core.pg_errors import translate
from supabase import Client

_MEMBERSHIPS = "community_memberships"

_MEMBER_SELECT = (
    "id, profile_id, role, status, joined_at,"
    "profiles!inner(full_name, display_email, phone_e164, is_active),"
    "unit_residencies(units(unit_code))"
)


def find_active_membership_by_email(
    client: Client, community_id: str, email: str
) -> dict | None:
    """Find one active membership in this community whose profile has ``email``.

    ``profiles.display_email`` is ``citext`` with a unique index, so the match is
    case-insensitive and cannot return two people. Returns ``None`` rather than
    raising, because "not a member" is the expected answer the caller turns into a
    404 with actionable wording.

    The unit code is flattened onto the row here so the service does not have to
    know the shape of the ``unit_residencies -> units`` embed.
    """
    response = (
        client.table(_MEMBERSHIPS)
        .select(_MEMBER_SELECT)
        .eq("community_id", community_id)
        .eq("status", "active")
        .is_("ended_at", None)
        .eq("profiles.display_email", email)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return None

    row = rows[0]
    residencies = row.get("unit_residencies") or []
    unit = (residencies[0] or {}).get("units") if residencies else None
    row["unit_code"] = (unit or {}).get("unit_code")
    return row


def set_membership_role(client: Client, membership_id: str, role: str) -> None:
    """Set a membership's role.

    Deliberately does not touch ``community_admin_terms``. That table records who
    holds the community's single *designated* admin office, guarded by the
    ``community_admin_one_active`` partial unique index; writing it here would
    either violate that index or silently depose the sitting admin. Promotion
    grants the role, not the office.
    """
    try:
        (
            client.table(_MEMBERSHIPS)
            .update({"role": role})
            .eq("id", membership_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error
        raise translate(exc) from exc
