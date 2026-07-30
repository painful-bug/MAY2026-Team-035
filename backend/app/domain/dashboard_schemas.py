"""DTOs for the admin dashboard surfaces.

Separate from :mod:`app.domain.schemas` (auth and invitations) for one reason
that is worth stating, because it is an inconsistency and not an accident:

**These serialize to camelCase; the auth DTOs serialize to snake_case.**

``schemas.py`` emits ``access_token`` / ``full_name``. The React app, which we
cannot change, reads ``timeAgo``, ``raisedBy``, ``slaHours``, ``apartmentId`` --
camelCase throughout its seeded data. Two options existed: convert the whole
codebase to camelCase now (touching working auth code that another developer is
actively changing), or scope camelCase to the new surfaces. The second is chosen.

The seam is real and should not be left implicit: ``/api/v1/auth/*`` speaks
snake_case, everything else speaks camelCase. The fix is to give the auth DTOs the
same base class when that code is next touched deliberately -- not as a drive-by
edit during a schema migration.
"""

from __future__ import annotations

from datetime import datetime

# Re-exported so existing imports of CamelModel/Page from this module keep working.
from app.domain.common_schemas import CamelModel, Page

__all__ = [
    "CamelModel",
    "Page",
    "CommunitySummary",
    "ResidentSummary",
    "NoticeSummary",
    "CollectionSummary",
    "AdminDashboard",
]


class CommunitySummary(CamelModel):
    """The caller's community -- the header and settings screens read this."""

    id: str
    name: str
    community_type: str
    status: str
    created_at: datetime


class ResidentSummary(CamelModel):
    """One resident row.

    Carries both the display label and the id for every reference (R23):
    ``flat`` + ``unitId``, ``role`` + ``displayRole``. The frontend ignores keys
    it does not know, so the ids are free to send and let screens adopt them
    one at a time.
    """

    id: str
    profile_id: str
    name: str | None = None
    # Always null today. `profiles` has no email column -- the address lives in
    # `auth.users`, which needs the service-role key to read. Resolved in step 4
    # by adding `profiles.email`; documented rather than quietly omitted, because
    # the Residents screen renders it.
    email: str | None = None
    phone: str | None = None
    role: str
    display_role: str
    flat: str | None = None
    unit_id: str | None = None
    status: str
    joined_at: datetime


class NoticeSummary(CamelModel):
    """One notice. ``date``/``timeAgo`` are server-formatted; ``publishedAt`` is
    the machine-readable instant beside them (see app.core.formatting)."""

    id: str
    title: str
    description: str | None = None
    category: str | None = None
    urgency: str
    date: str
    time_ago: str
    published_at: datetime


class CollectionSummary(CamelModel):
    """Maintenance collection totals, in whole rupees.

    ``percent`` is 0 when ``target`` is 0. The frontend computes this itself and
    guards the divide-by-zero; a real founding community has no invoices at all,
    so the server must guard it too rather than emitting NaN.
    """

    current: int
    target: int
    percent: int


class AdminDashboard(CamelModel):
    """The admin home aggregate.

    One request instead of five, because the counts are a server concern: the
    frontend currently derives them by filtering whole collections in the
    browser, which stops working the moment those collections are paginated.
    """

    total_residents: int
    pending_requests: int
    active_complaints: int
    collection: CollectionSummary
    generated_at: datetime
