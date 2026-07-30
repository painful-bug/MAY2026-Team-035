"""Unit tests for the settings and feature-module translation layer.

The database half -- the timezone lookup against ``pg_timezone_names``, the two
cross-field CHECKs behind the billing toggles, the RLS on ``community_settings``,
the catalogue-driven join -- cannot be tested here, because no migration has been
applied anywhere. DECISIONS_NEEDED E1 says so; these tests cover the half Python
owns.

Three of them pin decisions rather than mechanics, so that changing any of them
is a test failure and not a quiet behaviour change:

* ``unitLabelSingular`` is derived from the community type, and Python's fallback
  must produce the same word as the SQL one in ``community_settings_overview``.
  Two implementations of one rule is the reason to test it.
* ``lateFeeAmount`` keeps null as null instead of collapsing to ``0.0``. A fine
  of zero is one somebody configured; a fine of null is one nobody has.
* A module the catalogue lists but the community has no row for reads as its
  default rather than vanishing -- the property that makes an eleventh module
  toggleable the day it is added.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.settings_schemas import (
    ReplaceModulesRequest,
    UpdateSettingsRequest,
)
from app.domain.vocabularies import (
    backend_status_to_wire,
    community_type_label,
    late_fee_period_to_storage,
    late_fee_period_to_wire,
    unit_label_for,
)
from app.services.settings_service import (
    _to_billing,
    _to_collection,
    _to_module,
    _to_preferences,
    _to_profile,
)

_NOW = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)


def _settings_row(**overrides) -> dict:
    """A ``community_settings_overview`` row for a community that has saved."""
    row = {
        "community_id": "c-1",
        "community_name": "HomeBandhu Residency",
        "community_type": "apartment",
        "community_status": "Active",
        "community_created_at": _NOW.isoformat(),
        "timezone": "Asia/Kolkata",
        "unit_label_singular": "Flat",
        "unit_label_is_derived": True,
        "invite_ttl_hours": 72,
        "visitor_code_ttl_minutes": 120,
        "require_visitor_preapproval": True,
        "notice_sms_broadcast_enabled": False,
        "has_saved_settings": True,
        "version": 3,
        "settings_updated_at": _NOW.isoformat(),
        "settings_updated_by_name": "Priya Sharma",
        "auto_billing_enabled": False,
        "auto_billing_day": 1,
        "late_fee_enabled": False,
        "late_fee_amount": None,
        "late_fee_grace_days": 10,
        "late_fee_period": "weekly",
        "default_maintenance_amount": None,
        "modules_total": 10,
        "modules_enabled": 5,
        "modules_enabled_without_backend": 0,
    }
    row.update(overrides)
    return row


def _module_row(**overrides) -> dict:
    """A ``community_module_overview`` row."""
    row = {
        "community_id": "c-1",
        "module_key": "amenities-booking",
        "display_name": "Amenities Booking",
        "description": "Book clubhouse, gym, pool, etc.",
        "sort_order": 6,
        "backend_status": "implemented",
        "backend_note": "Build step 8.",
        "default_enabled": False,
        "enabled": True,
        "is_default": False,
        "updated_at": _NOW.isoformat(),
        "updated_by_membership_id": "m-1",
        "updated_by_name": "Priya Sharma",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stored", "label"),
    [
        ("apartment", "Apartment"),
        ("layout_villa", "Layout / Villa"),
        ("APARTMENT", "Apartment"),
    ],
)
def test_community_type_label_matches_the_onboarding_select(stored, label):
    """`communityTypeOptions` renders 'layout_villa' with spaces and a slash.

    No rule derives that from the stored value, which is why there is a table.
    """
    assert community_type_label(stored) == label


def test_community_type_label_falls_back_rather_than_raising():
    """An unknown type is a data problem, not a reason to 500 a settings screen."""
    assert community_type_label("townhouse") == "Apartment"
    assert community_type_label(None) == "Apartment"


@pytest.mark.parametrize(
    ("community_type", "word"),
    [("apartment", "Flat"), ("layout_villa", "Villa")],
)
def test_unit_label_is_derived_the_same_way_python_and_sql_derive_it(
    community_type, word
):
    """The SQL fallback in `community_settings_overview` is:

        case when community_type = 'apartment' then 'Flat' else 'Villa' end

    Python has to agree with it, because the API can be asked for the label by a
    caller whose community has no settings row for the view to left-join.
    """
    assert unit_label_for(community_type) == word


def test_unit_label_defaults_to_villa_for_anything_that_is_not_an_apartment():
    """Matching the SQL `else` branch exactly, including for null."""
    assert unit_label_for("townhouse") == "Villa"
    assert unit_label_for(None) == "Villa"


@pytest.mark.parametrize(
    ("wire", "stored"),
    [
        ("Weekly", "weekly"),
        ("weekly", "weekly"),
        ("Monthly", "monthly"),
        ("One-time", "once"),
        ("one time", "once"),
        ("once", "once"),
    ],
)
def test_late_fee_period_accepts_the_label_and_the_stored_value(wire, stored):
    assert late_fee_period_to_storage(wire) == stored


def test_unrecognised_late_fee_period_is_none_not_a_guess():
    """The service turns None into a 422 naming the three options.

    Defaulting to 'weekly' would mean a typo silently choosing how often a
    resident is fined.
    """
    assert late_fee_period_to_storage("fortnightly") is None
    assert late_fee_period_to_storage("") is None


def test_late_fee_period_round_trips_through_its_label():
    for stored in ("weekly", "monthly", "once"):
        assert late_fee_period_to_storage(late_fee_period_to_wire(stored)) == stored


@pytest.mark.parametrize(
    ("stored", "label"),
    [
        ("implemented", "Implemented"),
        ("partial", "Partial"),
        ("none", "Not implemented"),
    ],
)
def test_backend_status_labels(stored, label):
    assert backend_status_to_wire(stored) == label


def test_unknown_backend_status_reads_as_not_implemented():
    """The safe direction: claiming less than exists, never more."""
    assert backend_status_to_wire("planned") == "Not implemented"
    assert backend_status_to_wire(None) == "Not implemented"


# ---------------------------------------------------------------------------
# The snapshot
# ---------------------------------------------------------------------------


def test_profile_carries_both_the_machine_value_and_the_label():
    profile = _to_profile(_settings_row())
    assert profile.community_type == "apartment"
    assert profile.community_type_label == "Apartment"
    assert profile.name == "HomeBandhu Residency"


def test_preferences_report_whether_the_unit_label_was_chosen():
    """A screen that cannot tell a default from a choice shows an admin a value
    they never picked as though they had."""
    derived = _to_preferences(_settings_row(unit_label_is_derived=True))
    chosen = _to_preferences(
        _settings_row(unit_label_singular="Apartment", unit_label_is_derived=False)
    )
    assert derived.unit_label_is_derived is True
    assert chosen.unit_label_is_derived is False
    assert chosen.unit_label_singular == "Apartment"


def test_sms_broadcast_defaults_to_off():
    """The one toggle that spends money every time it fires. A missing value must
    not read as enabled."""
    row = _settings_row()
    del row["notice_sms_broadcast_enabled"]
    assert _to_preferences(row).notice_sms_broadcast_enabled is False


def test_late_fee_amount_keeps_null_distinct_from_zero():
    """`_amount` in the money service collapses null to 0.0, which would be wrong
    here: the CHECK behind `lateFeeEnabled` treats null as 'not configured' and
    zero as 'configured as nothing'."""
    assert _to_billing(_settings_row(late_fee_amount=None)).late_fee_amount is None
    assert _to_billing(_settings_row(late_fee_amount=0)).late_fee_amount == 0.0
    assert _to_billing(_settings_row(late_fee_amount="100.00")).late_fee_amount == 100.0


def test_billing_toggles_carry_the_period_label_alongside_the_value():
    billing = _to_billing(_settings_row(late_fee_period="once"))
    assert billing.late_fee_period == "once"
    assert billing.late_fee_period_label == "One-time"


def test_auto_billing_day_defaults_to_the_first():
    """Matching the frontend's copy: invoices "on the 1st of every month"."""
    assert _to_billing(_settings_row(auto_billing_day=None)).auto_billing_day == 1


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


def test_a_module_with_no_community_row_reads_as_its_default():
    """`community_module_overview` is driven by the catalogue, not by
    `community_modules`. This is the property that makes an eleventh module
    toggleable on the day it is added rather than invisible until somebody
    backfills a row for every community."""
    module = _to_module(
        _module_row(
            module_key="parking-management",
            enabled=True,
            is_default=True,
            default_enabled=True,
            updated_at=None,
            updated_by_name=None,
        )
    )
    assert module.is_default is True
    assert module.enabled is True
    assert module.updated_by is None


def test_collection_counts_enabled_modules_that_nothing_implements():
    """The number worth putting on the screen. Six of the ten modules have no
    backend, so an admin can otherwise switch three of them on and get no hint."""
    rows = [
        _module_row(module_key="complaint-management", backend_status="implemented"),
        _module_row(module_key="parking-management", backend_status="none"),
        _module_row(module_key="community-marketplace", backend_status="none"),
        _module_row(
            module_key="visitor-management", backend_status="none", enabled=False
        ),
        _module_row(module_key="notice-board", backend_status="partial"),
    ]
    collection = _to_collection(rows)
    assert collection.total == 5
    assert collection.enabled_count == 4
    # Only the two that are BOTH enabled and unimplemented.
    assert collection.enabled_without_backend == 2


def test_collection_counts_agree_with_the_views_own_aggregates():
    """`community_settings_overview` reports the same two numbers in SQL. If the
    Python count and the SQL count disagree, one screen shows two truths."""
    rows = [
        _module_row(module_key="resident-management", enabled=True,
                    backend_status="implemented"),
        _module_row(module_key="parking-management", enabled=True,
                    backend_status="none"),
        _module_row(module_key="staff-management", enabled=False,
                    backend_status="implemented"),
    ]
    collection = _to_collection(rows)
    row = _settings_row(
        modules_total=len(rows),
        modules_enabled=2,
        modules_enabled_without_backend=1,
    )
    assert collection.total == row["modules_total"]
    assert collection.enabled_count == row["modules_enabled"]
    assert collection.enabled_without_backend == row["modules_enabled_without_backend"]


def test_an_empty_module_list_is_zeros_not_an_error():
    collection = _to_collection([])
    assert (collection.total, collection.enabled_count) == (0, 0)


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def test_a_timezone_with_whitespace_is_rejected_before_the_database_sees_it():
    """An IANA name never contains whitespace, and a 422 naming the field is a
    better error than the 409 the RPC would raise."""
    with pytest.raises(PydanticValidationError):
        UpdateSettingsRequest(timezone="Asia / Kolkata")
    with pytest.raises(PydanticValidationError):
        UpdateSettingsRequest(timezone="   ")


def test_a_timezone_is_trimmed_but_not_otherwise_touched():
    """Case is left alone: the RPC looks the name up case-insensitively and stores
    the catalogue's own spelling, so normalising here would be a second opinion."""
    assert UpdateSettingsRequest(timezone="  asia/kolkata ").timezone == "asia/kolkata"


def test_omitting_a_field_is_distinct_from_sending_null():
    """The whole basis of the patch: null clears the unit-label override and
    returns to deriving it; an absent key leaves it as it was."""
    omitted = UpdateSettingsRequest().model_dump(exclude_unset=True)
    cleared = UpdateSettingsRequest(unitLabelSingular=None).model_dump(
        exclude_unset=True
    )
    assert "unit_label_singular" not in omitted
    assert cleared == {"unit_label_singular": None}


def test_an_invite_ttl_beyond_thirty_days_is_rejected():
    """An invite that outlives a month is not a second factor, it is a credential
    sitting in an inbox. The database CHECK agrees; this is the earlier of the
    two."""
    assert UpdateSettingsRequest(inviteTtlHours=720).invite_ttl_hours == 720
    with pytest.raises(PydanticValidationError):
        UpdateSettingsRequest(inviteTtlHours=721)
    with pytest.raises(PydanticValidationError):
        UpdateSettingsRequest(inviteTtlHours=0)


def test_visitor_code_ttl_bounds():
    with pytest.raises(PydanticValidationError):
        UpdateSettingsRequest(visitorCodeTtlMinutes=4)
    with pytest.raises(PydanticValidationError):
        UpdateSettingsRequest(visitorCodeTtlMinutes=1441)


def test_replacing_the_module_set_requires_the_field():
    """An empty array means every module off, which is legitimate. A missing field
    means the caller forgot, and treating the two the same would let a client
    disable the whole product by omission."""
    assert ReplaceModulesRequest(moduleKeys=[]).module_keys == []
    with pytest.raises(PydanticValidationError):
        ReplaceModulesRequest()


def test_the_switch_body_carries_a_boolean_not_an_absence():
    """`PATCH .../modules/{key}` with `{}` is a 422 rather than a guess about
    which direction the admin meant to move the switch."""
    from app.domain.settings_schemas import ModuleToggleRequest

    assert ModuleToggleRequest(enabled=False).enabled is False
    with pytest.raises(PydanticValidationError):
        ModuleToggleRequest()
