"""Community settings and the feature-module registry.

Two rules, both of which this file exists to hold:

**Nothing here decides what a module means.** The service reports whether a
module is on and whether anything implements it. It does not gate any endpoint on
the answer, and no other service imports this one. Module enforcement is a
product decision (DECISIONS_NEEDED A24), and the failure mode of guessing is
severe: ``amenities-booking`` ships disabled, so enforcing it would 403 all
twenty-two step-8 endpoints on every community that exists.

**The defaults are labelled as defaults.** A community that has never saved
settings still gets a full snapshot -- the view fills in ``Asia/Kolkata``, 72
hours, and the rest -- with ``hasSavedSettings: false`` alongside. A screen that
renders a default as a choice is a screen that quietly attributes it to an admin.

Billing appears in the snapshot and is not written here. ``PUT /billing-settings``
(§9) is the only writer, because two writers is how a rate starts disagreeing
with itself.
"""

from __future__ import annotations

from app.core.formatting import parse_instant
from app.domain.settings_schemas import (
    BillingToggles,
    CommunityProfile,
    ModuleCollection,
    ModuleSummary,
    PreferenceSettings,
    SettingsSnapshot,
    UpdateSettingsRequest,
)
from app.domain.vocabularies import (
    backend_status_to_wire,
    community_type_label,
    late_fee_period_to_wire,
)
from app.repositories import settings_repository as repo
from app.repositories import tenancy_repository as tenancy_repo
from supabase import Client

__all__ = [
    "get_settings_snapshot",
    "update_settings",
]


def _community(client: Client, user_id: str) -> str:
    """The community the caller belongs to."""
    return tenancy_repo.get_caller_community_id(client, user_id)


def _amount(value: object) -> float | None:
    """Read a Postgres ``numeric`` off the wire, keeping null as null.

    Unlike the money service's helper this does **not** collapse null to zero: a
    late fine of zero is a fine somebody configured, and one of null is a fine
    nobody has. The database's CHECK distinguishes them, so this has to as well.
    """
    if value is None:
        return None
    return round(float(value), 2)


def _instant(value: object):
    """Parse an optional ``timestamptz``."""
    if value in (None, ""):
        return None
    return parse_instant(value)  # type: ignore[arg-type]


def _to_profile(row: dict) -> CommunityProfile:
    community_type = row.get("community_type") or "apartment"
    return CommunityProfile(
        id=row["community_id"],
        name=row.get("community_name") or "",
        community_type=community_type,
        community_type_label=community_type_label(community_type),
        status=row.get("community_status") or "Active",
        created_at=_instant(row.get("community_created_at")),
    )


def _to_preferences(row: dict) -> PreferenceSettings:
    return PreferenceSettings(
        timezone=row.get("timezone") or "Asia/Kolkata",
        # Derived in SQL when the override is null; the view has already done it.
        unit_label_singular=row.get("unit_label_singular") or "Flat",
        unit_label_is_derived=bool(row.get("unit_label_is_derived", True)),
        invite_ttl_hours=int(row.get("invite_ttl_hours") or 72),
        visitor_code_ttl_minutes=int(row.get("visitor_code_ttl_minutes") or 120),
        require_visitor_preapproval=bool(row.get("require_visitor_preapproval", True)),
        notice_sms_broadcast_enabled=bool(
            row.get("notice_sms_broadcast_enabled", False)
        ),
    )


def _to_billing(row: dict) -> BillingToggles:
    period = row.get("late_fee_period") or "weekly"
    return BillingToggles(
        auto_billing_enabled=bool(row.get("auto_billing_enabled", False)),
        auto_billing_day=int(row.get("auto_billing_day") or 1),
        late_fee_enabled=bool(row.get("late_fee_enabled", False)),
        late_fee_amount=_amount(row.get("late_fee_amount")),
        late_fee_grace_days=int(row.get("late_fee_grace_days") or 0),
        late_fee_period=period,
        late_fee_period_label=late_fee_period_to_wire(period),
        default_maintenance_amount=_amount(row.get("default_maintenance_amount")),
    )


def _to_module(row: dict) -> ModuleSummary:
    status = row.get("backend_status") or "none"
    return ModuleSummary(
        key=row["module_key"],
        name=row.get("display_name") or row["module_key"],
        description=row.get("description") or "",
        enabled=bool(row.get("enabled", False)),
        is_default=bool(row.get("is_default", False)),
        default_enabled=bool(row.get("default_enabled", False)),
        backend_status=status,
        backend_status_label=backend_status_to_wire(status),
        backend_note=row.get("backend_note") or "",
        sort_order=int(row.get("sort_order") or 0),
        updated_at=_instant(row.get("updated_at")),
        updated_by=row.get("updated_by_name"),
    )


def _to_collection(rows: list[dict]) -> ModuleCollection:
    """Build the module envelope, counting in Python because the set is ten rows.

    The one place this file counts anything. ``community_settings_overview``
    reports the same two numbers as SQL aggregates, and
    ``test_settings_mapping`` pins them against each other -- if the two ever
    disagree, the snapshot and the module list are showing different truths on
    the same screen.
    """
    items = [_to_module(row) for row in rows]
    return ModuleCollection(
        items=items,
        total=len(items),
        enabled_count=sum(1 for item in items if item.enabled),
        enabled_without_backend=sum(
            1 for item in items if item.enabled and item.backend_status == "none"
        ),
    )


def get_settings_snapshot(client: Client, user_id: str) -> SettingsSnapshot:
    """Everything the settings screen needs, in one response."""
    community_id = _community(client, user_id)
    row = repo.fetch_settings(client, community_id)
    modules = repo.list_modules(client, community_id)

    return SettingsSnapshot(
        community=_to_profile(row),
        preferences=_to_preferences(row),
        billing=_to_billing(row),
        modules=_to_collection(modules),
        has_saved_settings=bool(row.get("has_saved_settings", False)),
        version=int(row.get("version") or 0),
        updated_at=_instant(row.get("settings_updated_at")),
        updated_by=row.get("settings_updated_by_name"),
    )


def update_settings(
    client: Client, user_id: str, body: UpdateSettingsRequest
) -> SettingsSnapshot:
    """Patch the community preferences. Omitted fields are left unchanged."""
    community_id = _community(client, user_id)

    supplied = body.model_dump(exclude_unset=True)
    payload: dict = {}

    if "timezone" in supplied and body.timezone:
        payload["timezone"] = body.timezone
    # Key presence, not truthiness: null clears the override and returns to
    # deriving the label, which is a different instruction from omitting it. An
    # empty string means the same as null here rather than storing a blank -- the
    # form's "clear" gesture is deleting the text, not typing null.
    if "unit_label_singular" in supplied:
        label = (body.unit_label_singular or "").strip()
        payload["unit_label_singular"] = label or None
    if "invite_ttl_hours" in supplied and body.invite_ttl_hours:
        payload["invite_ttl_hours"] = body.invite_ttl_hours
    if "visitor_code_ttl_minutes" in supplied and body.visitor_code_ttl_minutes:
        payload["visitor_code_ttl_minutes"] = body.visitor_code_ttl_minutes
    if (
        "require_visitor_preapproval" in supplied
        and body.require_visitor_preapproval is not None
    ):
        payload["require_visitor_preapproval"] = body.require_visitor_preapproval
    if (
        "notice_sms_broadcast_enabled" in supplied
        and body.notice_sms_broadcast_enabled is not None
    ):
        payload["notice_sms_broadcast_enabled"] = body.notice_sms_broadcast_enabled

    if payload:
        repo.save_settings(client, community_id, payload)
    return get_settings_snapshot(client, user_id)


