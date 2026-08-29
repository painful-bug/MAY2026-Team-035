"""Pydantic DTOs for the browser-safe HomeBandhu API contracts."""

from __future__ import annotations

import re
from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Reject fields the browser is not authorised to control."""

    model_config = ConfigDict(extra="forbid")


class Principal(BaseModel):
    """The authenticated identity derived from a verified Supabase token."""

    user_id: str
    phone: str | None = None
    email: str | None = None
    email_verified: bool = False
    full_name: str | None = None


class Profile(BaseModel):
    """Identity/contact data; community authorisation never lives here."""

    id: str
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool = True


class MembershipUnit(BaseModel):
    """Human-readable labels for a resolved residency.

    ``building_name``/``building_type`` are null for standalone homes, whose
    ``units.building_id`` is null -- a community is apartments XOR standalone
    homes, never both.
    """

    unit_code: str
    unit_type: str | None = None
    building_name: str | None = None
    building_type: str | None = None


class MembershipContext(BaseModel):
    id: str
    community_id: str
    role: str
    department_id: str | None = None
    unit_id: str | None = None
    # Only the session read populates this; every other resolver leaves it None
    # because nothing else renders a flat label.
    unit: MembershipUnit | None = None


class MembershipSet(BaseModel):
    """Every active membership the caller holds, in default-first order.

    A resident belongs to one community and a staff member to none, so until
    now ``get_active_membership`` could resolve tenancy with ``limit 1`` and
    nothing noticed. A service person belongs to as many communities as have
    hired them, and their calendar is the union of all of them -- so the scalar
    stopped being an implementation detail and became a wrong answer.

    Only Postgres was ever right about this. ``is_community_member(uuid)`` has
    always been an ``exists`` over every membership the caller holds, so no RLS
    policy assumed a single community; the assumption lived entirely in the one
    query this replaces.

    ``memberships`` is never empty -- the resolver raises rather than hand back
    a set with no default.
    """

    memberships: list[MembershipContext]

    @property
    def default(self) -> MembershipContext:
        """The membership every single-community handler already meant."""
        return self.memberships[0]

    @property
    def community_ids(self) -> list[str]:
        return [membership.community_id for membership in self.memberships]

    def for_community(self, community_id: str) -> MembershipContext | None:
        """The caller's membership in one community, or ``None``.

        Returns rather than raises so a service can decide whether absence is a
        403 or a 404 -- which differ by whether the caller is allowed to learn
        that the community exists.
        """
        for membership in self.memberships:
            if membership.community_id == community_id:
                return membership
        return None


class SessionContext(BaseModel):
    """Browser-safe session context; provider credentials remain HTTP-only."""

    identity: Profile
    membership: MembershipContext | None = None
    portal: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    onboarding_eligible: bool = False


class MessageResponse(BaseModel):
    message: str


class WeeklyNewCounts(BaseModel):
    """Rows created in the trailing 7 days -- the dashboard's trend chips.

    Integer counts, always present, `0` when nothing was created. Computed by
    `dashboard_repository.weekly_new_counts` as head-only count queries, so the
    values are whole-community truth rather than a tally of the capped lists.
    """

    residents: int = 0
    complaints: int = 0
    visitorRequests: int = 0  # noqa: N815
    bookings: int = 0


class DashboardSnapshot(BaseModel):
    """One tenant-scoped projection used by all authenticated portals."""

    users: list[dict] = Field(default_factory=list)
    complaints: list[dict] = Field(default_factory=list)
    visitors: list[dict] = Field(default_factory=list)
    amenities: list[dict] = Field(default_factory=list)
    bookings: list[dict] = Field(default_factory=list)
    payments: list[dict] = Field(default_factory=list)
    notices: list[dict] = Field(default_factory=list)
    departments: list[dict] = Field(default_factory=list)
    activities: list[dict] = Field(default_factory=list)
    # Admin-only. `AdminLayout.jsx` renders the sidebar badge from the length of
    # this list and `appStore.js` has always read `snapshot.pendingRequests`;
    # until it was added here the badge could never appear, because the key was
    # never sent. Residents get an empty list -- see `dashboard_service.snapshot`.
    pendingRequests: list[dict] = Field(default_factory=list)  # noqa: N815
    # Trailing-7-day creation counts for the dashboard trend chips, replacing
    # the frontend's hardcoded "+2 this week" placeholders.
    weeklyNew: WeeklyNewCounts = Field(default_factory=WeeklyNewCounts)  # noqa: N815


# An amenity photo travels as a base64 `data:` URL in `amenities.image_url`,
# capped at roughly 100KB of binary (a base64 payload is 4/3 of its bytes). The
# browser downscales before it submits; this ceiling is the backstop that turns
# an oversized upload into a 422 instead of a Postgres row nobody can read back
# in a page budget. The alternative -- a storage bucket -- is a deployment
# HomeBandhu does not have.
_MAX_IMAGE_DATA_URL_CHARS = 140_000
_MAX_IMAGE_HTTPS_URL_CHARS = 2_000
_IMAGE_DATA_URL = re.compile(
    r"^data:image/(?:png|jpeg|webp|gif);base64,[A-Za-z0-9+/\s]+={0,2}$"
)
# 'HH:MM' or 'HH:MM:SS' -- the two spellings Postgres `time` accepts and the
# two an <input type="time"> emits (it drops the seconds unless asked for them).
_CLOCK_TIME = re.compile(r"^(?P<h>[01]\d|2[0-3]):(?P<m>[0-5]\d)(?::(?P<s>[0-5]\d))?$")


def _clock_or_none(value: str | None) -> str | None:
    """Validate an 'HH:MM'/'HH:MM:SS' string; empty becomes None (= no hours set)."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not _CLOCK_TIME.match(value):
        raise ValueError("Time must be in HH:MM or HH:MM:SS form.")
    return value


def _as_time(value: str | None) -> time | None:
    match = _CLOCK_TIME.match(value) if value else None
    if match is None:
        return None
    return time(
        int(match.group("h")), int(match.group("m")), int(match.group("s") or 0)
    )


class AmenityWrite(StrictModel):
    """The body of POST/PUT `/dashboard/amenities` -- the only amenity write
    endpoints the app has, so anything the catalogue form collects has to fit
    here or it is dropped on the floor (issue #48 D2).

    `image`, `openingTime` and `closingTime` are columns on `amenities` since
    `0023` (`image_url`, `opening_time`, `closing_time`); the model carries them
    so the form can reach them. The hours are checked against each other here
    for the same reason `amenities_hours_check` exists in `0023` -- with the
    check only in Postgres a reversed pair is a 500, and it is a 422.
    """

    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="Utility", max_length=120)
    location: str = Field(default="", max_length=200)
    capacity: int | None = Field(default=None, ge=1, le=10000)
    booking_mode: str = Field(default="Exclusive", max_length=40)
    approval_required: bool = False
    hourly_rate: float = Field(default=0, ge=0)
    is_active: bool = True
    image: str | None = None
    opening_time: str | None = None
    closing_time: str | None = None

    @field_validator("image")
    @classmethod
    def _image_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if value.startswith("data:"):
            if len(value) > _MAX_IMAGE_DATA_URL_CHARS:
                raise ValueError(
                    "The image is too large. Use one under 100KB "
                    "(the form downscales before it uploads)."
                )
            if not _IMAGE_DATA_URL.match(value):
                raise ValueError(
                    "An inline image must be a base64 data URL of a PNG, JPEG, "
                    "WebP or GIF."
                )
            return value
        if value.startswith("https://"):
            if len(value) > _MAX_IMAGE_HTTPS_URL_CHARS:
                raise ValueError("The image URL is too long.")
            return value
        raise ValueError(
            "An image must be an https:// URL or a base64 image data URL."
        )

    @field_validator("opening_time", "closing_time")
    @classmethod
    def _hours_shape(cls, value: str | None) -> str | None:
        return _clock_or_none(value)

    @model_validator(mode="after")
    def _hours_are_ordered(self) -> "AmenityWrite":
        opens, closes = _as_time(self.opening_time), _as_time(self.closing_time)
        if opens is not None and closes is not None and opens >= closes:
            raise ValueError("The opening time must be before the closing time.")
        return self


class AuthMethod(BaseModel):
    id: str
    kind: Literal["redirect", "credentials"]
    label: str
    enabled: bool = True


class AuthMethodsResponse(BaseModel):
    primary: str
    methods: list[AuthMethod]


class PasswordSignUpRequest(StrictModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=15, max_length=256)
    captcha_token: str | None = Field(default=None, max_length=4096)
    intent: Literal["service-provider"] | None = None

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        value = value.strip().casefold()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("A valid email address is required.")
        return value


class PasswordSignInRequest(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    captcha_token: str | None = Field(default=None, max_length=4096)
    # "Remember me" on the sign-in card. Off unless asked for, so a shared or
    # public browser gets the login page back once the window closes.
    remember_me: bool = False


class EmailTokenRequest(StrictModel):
    token_hash: str = Field(min_length=8, max_length=4096)
    verification_type: Literal["email", "signup", "recovery"] = "email"


class PasswordResetRequest(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    captcha_token: str | None = Field(default=None, max_length=4096)


class EmailConfirmationResendRequest(PasswordResetRequest):
    intent: Literal["service-provider"] | None = None


class PasswordResetCompleteRequest(StrictModel):
    password: str = Field(min_length=15, max_length=256)


class ServiceSignupTelemetryRequest(StrictModel):
    event_name: Literal[
        "cta_impression",
        "cta_clicked",
        "auth_completed",
        "provider_profile_completed",
        "first_application_submitted",
    ] = Field(alias="eventName")


# --- Invitations --------------------------------------------------------------


class CreateInvitationRequest(StrictModel):
    """An active administrator invites a resident into their own community."""

    intended_unit_id: str
    invitee_email: str = Field(min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=20)
    full_name: str | None = Field(default=None, max_length=160)

    @field_validator("invitee_email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("A valid invitation email is required.")
        return value


class InvitationCreated(BaseModel):
    invitation_id: str
    link: str
    code: str
    invitee_email: str
    community_id: str
    intended_unit_id: str
    expires_at: datetime


class PrepareInvitationRequest(StrictModel):
    token: str | None = Field(default=None, min_length=1, max_length=512)
    code: str | None = Field(default=None, min_length=1, max_length=64)


class RedeemInvitationRequest(StrictModel):
    pass


# --- Community directory and access requests --------------------------------


class CommunitySearchItem(BaseModel):
    id: str
    name: str
    community_type: str
    city: str | None = None
    state: str | None = None


class CommunitySearchResponse(BaseModel):
    items: list[CommunitySearchItem] = Field(default_factory=list)


class CommunityUnitOption(BaseModel):
    id: str
    unit_code: str
    building_name: str | None = None


class CommunityUnitListResponse(BaseModel):
    items: list[CommunityUnitOption] = Field(default_factory=list)


Relationship = Literal["owner", "tenant", "family_member", "caregiver", "other"]


class CreateAccessRequest(StrictModel):
    community_id: str
    requested_unit_id: str | None = None
    requested_relationship: Relationship = "tenant"
    phone: str | None = Field(default=None, max_length=20)
    # The applicant's residence claim, as free text: Tower/Block + Flat for an
    # apartment community, the villa number for a villa layout. Free text by
    # product ruling (2026-08-27) -- non-members must never see the community's
    # unit inventory, so there is nothing to validate against here.
    requested_building_text: str | None = Field(default=None, max_length=120)
    requested_unit_text: str | None = Field(default=None, max_length=120)

    @field_validator("requested_building_text", "requested_unit_text")
    @classmethod
    def _strip_residence_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class WithdrawAccessRequest(StrictModel):
    pass


class AccessRequestCommunity(BaseModel):
    id: str
    name: str
    # Drives the admin/applicant UI's residence labelling: "Tower + Flat" for
    # `apartment`, "Villa number" for `layout_villa`. Optional because a row
    # can reach `_summary` without the communities embed.
    community_type: str | None = None


class AccessRequestResponse(BaseModel):
    id: str
    community: AccessRequestCommunity
    status: str
    requested_relationship: str
    requested_unit_id: str | None = None
    requested_building_text: str | None = None
    requested_unit_text: str | None = None
    applicant_name: str | None = None
    applicant_email: str | None = None
    applicant_phone_e164: str | None = None
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


class AccessRequestListResponse(BaseModel):
    items: list[AccessRequestResponse] = Field(default_factory=list)


class ApproveAccessRequest(StrictModel):
    unit_id: str | None = None
    relationship: Relationship | None = None
    # The admin-confirmed residence, as text. The service canonicalises the
    # pair with `normalize_unit_code(building_code, unit_code)` and the RPC
    # finds-or-creates the unit. `unit_id` stays the highest-precedence input.
    unit_code: str | None = Field(default=None, max_length=120)
    building_code: str | None = Field(default=None, max_length=120)


class RejectAccessRequest(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class BlacklistAccessRequest(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class AccessRequestDecisionResponse(BaseModel):
    """The typed answer of an admin decision (approve, reject, blacklist).

    `membership_id` and `unit_id` are populated only by an approval -- and
    `unit_id` only once the residence-claim migration teaches the RPC to
    return it, so absence is tolerated.
    """

    request_id: str
    status: str
    membership_id: str | None = None
    unit_id: str | None = None


# --- Founder onboarding -------------------------------------------------------


class MapPoint(StrictModel):
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class CommunityStructure(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)


class FounderProfileInput(StrictModel):
    fullName: str = Field(min_length=2, max_length=160)
    designation: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=20)
    unitNumber: str = Field(min_length=1, max_length=80)
    founderStructureId: str | None = Field(default=None, max_length=80)
    profileImage: str | None = None

    @field_validator("profileImage")
    @classmethod
    def _reject_inline_image(cls, value: str | None) -> str | None:
        if value and value.startswith("data:"):
            raise ValueError("Profile images must be uploaded separately.")
        return value


class CommunityOnboardingRequest(StrictModel):
    name: str = Field(min_length=3, max_length=100)
    community_type: Literal["apartment", "layout_villa"]
    address_line1: str = Field(min_length=3, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(min_length=3, max_length=20)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    # Optional, unlike the pair above. A community must have a pin -- every
    # proximity search in 0034 is written against it -- but nothing breaks when
    # nobody names the pin, and the founder wizard already asks for a postal
    # address two fields up. 120 characters matches the database check.
    location_label: str | None = Field(default=None, max_length=120)
    blocks: list[CommunityStructure] = Field(default_factory=list, max_length=10)
    villas: list[CommunityStructure] = Field(default_factory=list, max_length=50)
    block_locations: dict[str, MapPoint] = Field(default_factory=dict)
    villa_locations: dict[str, MapPoint] = Field(default_factory=dict)
    enabled_features: list[str] = Field(default_factory=list, max_length=10)
    admin_profile: FounderProfileInput

    @field_validator("country_code")
    @classmethod
    def _country_code(cls, value: str) -> str:
        value = value.upper()
        if not value.isalpha():
            raise ValueError("Country code must contain two letters.")
        return value


class CommunityOnboardingResponse(BaseModel):
    community: dict
    admin: dict
