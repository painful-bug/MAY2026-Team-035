"""DTOs for the People surface: administrators.

The resident, registration-request and resident-update DTOs were removed with
their endpoints -- see ``docs/FRONTEND_WIRING_AUDIT.md``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.domain.common_schemas import CamelModel


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


class PromoteAdminRequest(CamelModel):
    """Body for ``POST /admins``.

    ``email`` identifies an existing member. The other four fields are accepted
    and ignored: the Admins screen sends them, but a promotion must not rewrite
    the member's profile or move them to a different flat. See the endpoint
    docstring.
    """

    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=32)
    tower: str | None = Field(None, max_length=50)
    flat: str | None = Field(None, max_length=50)

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("A valid email address is required.")
        return value
