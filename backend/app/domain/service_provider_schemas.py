"""Wire models for a service person's own profile and the skill catalogue.

A **service provider** is a person who fixes things, registered once, globally.
They are not scoped to a community and they hold no membership until a
department manager hires them -- which is the whole reason this surface exists
separately from ``people_schemas``, where every model is a member of somewhere.

**The catalogue is global; a community's categories are not.** ``skills`` is one
list of trades seeded by ``0034``; ``complaint_categories`` is per-community and
carries a nullable ``skill_id`` pointing into it. That asymmetry is what makes
"which communities need my skills" answerable before anyone has hired anyone,
and it is recorded in ``docs/plans/SERVICE_OPERATIONS_PROGRESS.md`` 4.1.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel


class Skill(CamelModel):
    """One trade from the global catalogue."""

    id: str
    name: str
    #: ``maintenance``, ``facilities`` or ``security`` for the seeded twelve.
    #: Free text rather than an enum: the catalogue is data, and a closed enum
    #: here would mean a code change before an operator could add a trade.
    category: str
    description: str


class ServiceProviderProfile(CamelModel):
    """A service person as they see themselves.

    ``communityCount`` is how many communities currently employ them, counted
    from live memberships rather than stored. It is here because the dashboard's
    empty state turns on it: a provider in no community is shown the "find
    work" prompt rather than an empty calendar.
    """

    id: str
    display_name: str
    headline: str
    bio: str
    phone: str
    latitude: float | None
    longitude: float | None
    service_radius_km: float
    #: ``active`` or ``suspended``. A suspended provider keeps their profile and
    #: their history; they simply stop being offered work.
    status: str
    #: The dashboard's offline toggle. False means "do not offer me new jobs" --
    #: it does not cancel work already accepted.
    is_available: bool
    skill_ids: list[str]
    skill_names: list[str]
    community_count: int
    created_at: datetime
    updated_at: datetime


class CandidateProfile(CamelModel):
    """A service person as a *hiring manager* sees them.

    Deliberately not ``ServiceProviderProfile``. That model is what somebody
    sees of themselves; this one is what a stranger with a vacancy sees, and the
    difference is two fields:

    **No ``latitude``/``longitude``.** The hiring surface already answers the
    only question a manager has about where somebody is -- ``distanceKm``, which
    the candidate list computes from the community's own point. Handing out a
    home coordinate instead would be answering a question nobody asked with a
    fact the person did not offer for that purpose. ``serviceRadiusKm`` is here
    because it is a statement they published about how far they travel.

    **No ``profileId``.** Nothing on this screen addresses them by profile, and
    an id that unlocks other surfaces is not something a candidate read should
    hand out.

    ``phone`` *is* here, and is not a widening: the candidate list and every
    application card have carried ``phoneE164`` since ``0035``. Somebody being
    considered for a job in your building is somebody you may ring.
    """

    id: str
    display_name: str
    headline: str
    bio: str
    phone: str
    service_radius_km: float
    #: ``active`` or ``suspended``. A suspended provider is not offered by the
    #: candidate search at all, so this is only ever ``active`` when reached
    #: from there -- but an application from before a suspension can still be
    #: opened, and the screen should be able to say so.
    status: str
    #: Their own "not taking work" toggle. It does not stop a manager hiring
    #: them; it stops the dispatcher offering them jobs afterwards.
    is_available: bool
    skill_ids: list[str]
    skill_names: list[str]
    #: How many communities currently employ them. The one number on this page
    #: that is about workload rather than identity.
    community_count: int
    registered_at: datetime


class UpdateServiceProviderRequest(CamelModel):
    """Edit what is already registered — everything except the name.

    **The name is not here on purpose** (PO rule, 2026-08-10): a service
    person's name and email are identity, edited nowhere in settings. The RPC
    coalesces a null name onto the stored value, so this model simply never
    sends one.

    **Every field is optional, and omitting one leaves it alone.** A `null` is
    not an erasure -- the RPC coalesces onto the stored value -- so a client
    may PATCH one field without first reading the other six and echoing them
    back.
    """

    headline: str | None = Field(default=None, max_length=160)
    bio: str | None = Field(default=None, max_length=2000)
    phone: str | None = Field(default=None, max_length=20)
    #: Where they are based. Together with ``serviceRadiusKm`` this decides
    #: which communities they are shown, so it is worth the client asking for
    #: browser geolocation rather than leaving both null -- a provider with no
    #: coordinates still appears in every search, but sorts last.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    service_radius_km: float | None = Field(default=None, gt=0, le=500)


class SaveServiceProviderRequest(UpdateServiceProviderRequest):
    """Register: the update shape plus the one field registration must have.

    One RPC serves both (``upsert_service_provider``); the two models exist
    because the *name* requirement differs. Registration names you;
    settings never rename you.
    """

    display_name: str = Field(min_length=2, max_length=120)


class SetSkillsRequest(CamelModel):
    """The complete set of trades this person offers.

    A ``PUT`` of the whole list rather than add/remove operations: the screen is
    a set of checkboxes, and two clients toggling different boxes against a
    delta API is a lost update that nobody notices until a plumber stops being
    offered plumbing.

    An unknown or retired skill id is **ignored, not rejected.** The RPC selects
    against the catalogue rather than trusting the argument, so a client holding
    a stale list saves the trades that still exist instead of failing whole.
    """

    skill_ids: list[str] = Field(default_factory=list, max_length=40)


class SetAvailabilityRequest(CamelModel):
    """The offline toggle."""

    is_available: bool


class AvailabilityResult(CamelModel):
    """What the toggle settled on, read back from the database."""

    is_available: bool


class SkillsSavedResult(CamelModel):
    """How many trades this person now offers."""

    skill_count: int
