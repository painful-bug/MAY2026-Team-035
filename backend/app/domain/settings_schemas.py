"""DTOs for community settings and the feature-module registry.

**The settings screen this serves currently persists nothing.**
``pages/AdminDashboard/Settings.jsx`` keeps four toggles in ``useState`` and its
save handler is a toast. So unlike every other surface in this API, there is no
existing data shape to reproduce -- the four field names below are ours, chosen
to say what the screen's own copy says.

Two shapes deserve a note before the classes:

* **Modules are not a page.** There are exactly ten of them, fixed by
  ``frontend/src/data/onboardingModules.js``, and a client that has to ask for
  page 2 of a ten-row fixed list is a client we made work for nothing.
  :class:`ModuleCollection` is therefore its own envelope, with the two counts
  worth putting on a screen, rather than ``Page[ModuleSummary]``.

* **Billing is read-only here.** :class:`BillingToggles` appears inside
  :class:`SettingsSnapshot` so one GET renders the whole settings card, but
  ``PUT /billing-settings`` is the only thing that writes it. Money having two
  writers is how two screens start disagreeing about a rate.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.domain.common_schemas import CamelModel

__all__ = [
    "CommunityProfile",
    "PreferenceSettings",
    "BillingToggles",
    "ModuleSummary",
    "ModuleCollection",
    "SettingsSnapshot",
    "UpdateSettingsRequest",
]


class CommunityProfile(CamelModel):
    """Who the community is. Read-only on this surface.

    There is no write for ``name`` or ``communityType``: ``communities`` (the
    baseline's rename of ``associations``) is the one table this build plan
    touches whose admin write policy has no community clause (build plan 1.2), so
    a rename endpoint would be the first of sixty-eight to depend on it.
    """

    id: str
    name: str
    community_type: str
    community_type_label: str
    status: str
    created_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    #: What the pin is called -- "Whitefield, Bengaluru". Suggested by the
    #: picker and then editable, so it is a label rather than a geocode. Unlike
    #: ``name`` above it *is* writable, through ``PUT /settings``: the admin who
    #: moved the pin is the one who knows what to call where it landed.
    location_label: str | None = None


class PreferenceSettings(CamelModel):
    """Community-wide preferences.

    ``unitLabelIsDerived`` says whether ``unitLabelSingular`` was chosen or
    inferred from the community type. A screen that cannot tell the difference
    shows an admin a value they never picked as though they had.

    ``requireVisitorPreapproval`` and ``noticeSmsBroadcastEnabled`` are stored and
    read by nothing -- there is no visitor backend and no SMS provider in this
    repository. They exist so the screen stops losing them, and API.md says so
    rather than leaving it to be discovered.
    """

    timezone: str
    unit_label_singular: str
    unit_label_is_derived: bool
    invite_ttl_hours: int
    visitor_code_ttl_minutes: int
    require_visitor_preapproval: bool
    notice_sms_broadcast_enabled: bool


class BillingToggles(CamelModel):
    """The two billing switches the settings screen shows. **Read-only here.**

    ``autoBillingEnabled`` cannot be true while ``defaultMaintenanceAmount`` is
    null -- the database refuses it. ``lateFeeEnabled`` cannot be true without a
    ``lateFeeAmount`` above zero, for the same reason.

    **Nothing charges a late fee and nothing runs billing on a schedule.**
    ``POST /maintenance-runs`` is manual and deliberately ignores
    ``autoBillingEnabled``: an admin pressing the button has said what they want
    more recently than a toggle did.
    """

    auto_billing_enabled: bool
    auto_billing_day: int
    late_fee_enabled: bool
    late_fee_amount: float | None = None
    late_fee_grace_days: int
    late_fee_period: str
    late_fee_period_label: str
    default_maintenance_amount: float | None = None


class ModuleSummary(CamelModel):
    """One feature module, as the community has it set.

    ``backendStatus`` is the field that makes this list worth reading: six of the
    ten modules have no backend at all, so an admin can otherwise switch on
    Parking Management and be given no hint that nothing will happen.

    ``isDefault`` is true when nobody has ever set this key for this community,
    which is how an eleventh module added to the catalogue reads before anyone
    touches it.
    """

    key: str
    name: str
    description: str
    enabled: bool
    is_default: bool
    default_enabled: bool
    backend_status: str
    backend_status_label: str
    backend_note: str
    sort_order: int
    updated_at: datetime | None = None
    updated_by: str | None = None


class ModuleCollection(CamelModel):
    """The ten modules and the two counts worth showing above them.

    ``enabledWithoutBackend`` is the honest number: modules switched on that
    nothing in the product implements.
    """

    items: list[ModuleSummary]
    total: int
    enabled_count: int
    enabled_without_backend: int


class SettingsSnapshot(CamelModel):
    """Everything the settings screen needs, in one response.

    ``hasSavedSettings`` is false for a community that has never saved: the
    values are then defaults rather than choices, and a screen that cannot tell
    the two apart will show "Asia/Kolkata" as though somebody picked it.
    """

    community: CommunityProfile
    preferences: PreferenceSettings
    billing: BillingToggles
    modules: ModuleCollection
    has_saved_settings: bool
    version: int
    updated_at: datetime | None = None
    updated_by: str | None = None


class UpdateSettingsRequest(CamelModel):
    """Patch the community preferences. Omitted fields are left unchanged.

    ``unitLabelSingular`` distinguishes omitted from null: sending null clears
    the override and goes back to deriving the label from the community type,
    which is not the same as leaving it alone. Key presence is what separates
    them, matching ``defaultMaintenanceAmount`` on the billing patch.
    """

    # Validated for real against `pg_timezone_names` in the database. The bounds
    # here only reject the shapes that are never a timezone; the catalogue is the
    # authority, and it lives where a restore can still see it.
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    unit_label_singular: str | None = Field(default=None, max_length=24)
    # 720 hours is 30 days. An invite that outlives a month is not a second
    # factor any more, it is a credential sitting in an inbox.
    invite_ttl_hours: int | None = Field(default=None, ge=1, le=720)
    visitor_code_ttl_minutes: int | None = Field(default=None, ge=5, le=1440)
    require_visitor_preapproval: bool | None = None
    notice_sms_broadcast_enabled: bool | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    #: Rides with the coordinate pair rather than travelling alone: the RPC that
    #: writes it is the one that moves the pin, and a label saved without a pin
    #: would be a name for a place the community is not. Optional even when the
    #: pair is sent -- a pin nobody named is still a valid pin.
    location_label: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _coordinate_pair(self) -> "UpdateSettingsRequest":
        coordinates_supplied = bool({"latitude", "longitude"} & self.model_fields_set)
        if coordinates_supplied and (self.latitude is None or self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self

    @field_validator("location_label")
    @classmethod
    def _trim_location_label(cls, value: str | None) -> str | None:
        """Whitespace-only is ``None``; the RPC then keeps the stored label."""
        if value is None:
            return None
        return value.strip() or None

    @field_validator("timezone")
    @classmethod
    def _no_whitespace(cls, value: str | None) -> str | None:
        """Reject a timezone containing whitespace before it reaches the database.

        An IANA name never has any, and the 409 the database would raise is a
        worse error than the 422 this produces.
        """
        if value is None:
            return None
        stripped = value.strip()
        if not stripped or any(character.isspace() for character in stripped):
            raise ValueError("A timezone must be an IANA name such as Asia/Kolkata.")
        return stripped
