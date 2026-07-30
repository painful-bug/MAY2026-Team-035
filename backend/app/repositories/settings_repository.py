"""Data access for community settings and the feature-module registry.

Reads go through the two ``security_invoker`` views from migration 0017; writes
go through its three RPCs. The module writes are RPCs for a reason that is not
transactionality: a bulk set has to validate all ten keys *before* writing any of
them, so one typo in an array does not leave a community half-configured, and a
PostgREST upsert cannot express "check everything first".
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.core.pg_errors import translate
from supabase import Client

_SETTINGS = "community_settings_overview"
_MODULES = "community_module_overview"

_SETTINGS_SELECT = (
    "community_id, community_name, community_type, community_status,"
    "community_created_at, timezone, unit_label_singular, unit_label_is_derived,"
    "invite_ttl_hours, visitor_code_ttl_minutes, require_visitor_preapproval,"
    "notice_sms_broadcast_enabled, has_saved_settings, version,"
    "settings_updated_at, settings_updated_by_name, auto_billing_enabled,"
    "auto_billing_day, late_fee_enabled, late_fee_amount, late_fee_grace_days,"
    "late_fee_period, default_maintenance_amount, modules_total, modules_enabled,"
    "modules_enabled_without_backend"
)

_MODULE_SELECT = (
    "community_id, module_key, display_name, description, sort_order,"
    "backend_status, backend_note, default_enabled, enabled, is_default,"
    "updated_at, updated_by_membership_id, updated_by_name"
)


def fetch_settings(client: Client, community_id: str) -> dict:
    """The settings snapshot for one community.

    Never returns ``None`` for a community that exists: the view left-joins the
    settings row and fills in the defaults, so a community that has never saved
    still has a snapshot. ``has_saved_settings`` is how the caller tells them
    apart. A missing row here means the community itself is gone.
    """
    response = (
        client.table(_SETTINGS)
        .select(_SETTINGS_SELECT)
        .eq("community_id", community_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Community not found.")
    return rows[0]


def list_modules(client: Client, community_id: str) -> list[dict]:
    """Every catalogue module with this community's setting for it.

    Ordered by the catalogue's own ``sort_order`` so the list matches the order
    the onboarding wizard shows the same ten cards in. Unpaged on purpose -- the
    set is fixed at ten by ``onboardingModules.js``.
    """
    response = (
        client.table(_MODULES)
        .select(_MODULE_SELECT)
        .eq("community_id", community_id)
        .order("sort_order")
        .execute()
    )
    return response.data or []


def fetch_module(client: Client, community_id: str, module_key: str) -> dict:
    """One module row, or raise."""
    response = (
        client.table(_MODULES)
        .select(_MODULE_SELECT)
        .eq("community_id", community_id)
        .eq("module_key", module_key)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Module not found.")
    return rows[0]


def save_settings(client: Client, community_id: str, payload: dict) -> None:
    """Patch the community preferences (RPC), creating the row on first use."""
    try:
        client.rpc(
            "save_community_settings",
            {"p_community_id": community_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not save the settings.") from exc


def set_module(
    client: Client, community_id: str, module_key: str, enabled: bool
) -> None:
    """Turn one module on or off (RPC)."""
    try:
        client.rpc(
            "set_community_module",
            {
                "p_community_id": community_id,
                "p_module_key": module_key,
                "p_enabled": enabled,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update the module.") from exc


def set_modules(client: Client, community_id: str, module_keys: list[str]) -> None:
    """Set the whole module set from the list of enabled keys (RPC)."""
    try:
        client.rpc(
            "set_community_modules",
            {"p_community_id": community_id, "p_module_keys": module_keys},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not update the modules.") from exc
