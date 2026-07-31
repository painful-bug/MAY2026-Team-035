"""Pydantic DTOs for the browser-safe HomeBandhu API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class MembershipContext(BaseModel):
    id: str
    community_id: str
    role: str
    department_id: str | None = None
    unit_id: str | None = None


class SessionContext(BaseModel):
    """Browser-safe session context; provider credentials remain HTTP-only."""

    identity: Profile
    membership: MembershipContext | None = None
    portal: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    onboarding_eligible: bool = False


class MessageResponse(BaseModel):
    message: str


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


class AmenityWrite(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="Utility", max_length=120)
    location: str = Field(default="", max_length=200)
    capacity: int | None = Field(default=None, ge=1, le=10000)
    booking_mode: str = Field(default="Exclusive", max_length=40)
    approval_required: bool = False
    hourly_rate: float = Field(default=0, ge=0)
    is_active: bool = True


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


class EmailTokenRequest(StrictModel):
    token_hash: str = Field(min_length=8, max_length=4096)
    verification_type: Literal["email", "signup", "recovery"] = "email"


class PasswordResetRequest(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    captcha_token: str | None = Field(default=None, max_length=4096)


class PasswordResetCompleteRequest(StrictModel):
    password: str = Field(min_length=15, max_length=256)


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


class WithdrawAccessRequest(StrictModel):
    pass


class AccessRequestCommunity(BaseModel):
    id: str
    name: str


class AccessRequestResponse(BaseModel):
    id: str
    community: AccessRequestCommunity
    status: str
    requested_relationship: str
    requested_unit_id: str | None = None
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


class RejectAccessRequest(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class BlacklistAccessRequest(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


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
