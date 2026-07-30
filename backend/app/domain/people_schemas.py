"""DTOs for the People surfaces: residents, admins, registration requests."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel


class RegistrationRequestSummary(CamelModel):
    """One pending self-signup awaiting admin review."""

    id: str
    name: str
    email: str | None = None
    phone: str
    # `flat` is the canonical code ('C-505'); `tower` is derived from it for the
    # frontend, which renders the two separately.
    flat: str
    tower: str | None = None
    status: str
    date: str
    submitted_at: datetime


class AdminSummary(CamelModel):
    """One admin of the community."""

    id: str
    profile_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str
    display_role: str
    # The office held in the residents' association (President, Secretary, ...),
    # which is a different axis from `role`.
    designation: str | None = None
    flat: str | None = None
    unit_id: str | None = None
    status: str
    joined_at: datetime


class UpdateResidentRequest(CamelModel):
    """Editable fields on a resident.

    Every field is optional: this is a PATCH, and omitting a field leaves it
    unchanged. Explicitly sending ``null`` clears it.
    """

    name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=32)
    designation: str | None = Field(None, max_length=100)


class RejectRegistrationRequest(CamelModel):
    """Body for rejecting a registration request."""

    reason: str | None = Field(None, max_length=500)


class ApprovedRegistration(CamelModel):
    """Result of approving a registration request.

    Approval mints an **invitation**, it does not create an active account: the
    invite token is a mandatory second factor. ``link`` and ``code`` are shown to
    the admin exactly once and are never recoverable -- only their digests are
    stored.
    """

    request_id: str
    invitation_id: str
    link: str
    code: str
    phone: str
    flat: str
    name: str | None = None
    expires_at: datetime
