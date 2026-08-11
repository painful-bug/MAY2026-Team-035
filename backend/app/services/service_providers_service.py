"""Registering as a service person, and keeping that registration current.

Step 1 of ``docs/plans/SERVICE_OPERATIONS_PLAN.md``. Six operations, all of them
about one person's own record, none of them scoped to a community -- which is
the point: a plumber exists before any society has heard of them, and the
"which communities need me" search in ``0034`` 9 has to run for someone who
holds no membership anywhere.

**Everything here is a read-back.** Each write calls its RPC and then re-reads
``service_provider_overview``, so the response is the row the database settled
on rather than the request echoed with an id attached. That matters more than
usual here because three fields are not the caller's to choose: ``skillNames``
comes from the catalogue, ``communityCount`` is counted from live memberships,
and ``serviceRadiusKm`` defaults in SQL when omitted.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.domain.service_provider_schemas import (
    AvailabilityResult,
    ServiceProviderProfile,
    SetSkillsRequest,
    Skill,
    SkillsSavedResult,
    SaveServiceProviderRequest,
    UpdateServiceProviderRequest,
)
from app.repositories import service_providers_repository as repo
from supabase import Client


def _text(value: object) -> str:
    """``None`` and whitespace both become the empty string.

    The wire model uses ``str`` rather than ``str | None`` for the optional
    prose fields, because a client rendering a headline should not have to
    distinguish "never filled in" from "cleared" -- both draw nothing.
    """
    return str(value).strip() if value not in (None, "") else ""


def _to_profile(row: dict[str, Any]) -> ServiceProviderProfile:
    return ServiceProviderProfile(
        id=row["id"],
        display_name=_text(row.get("display_name")),
        headline=_text(row.get("headline")),
        bio=_text(row.get("bio")),
        phone=_text(row.get("phone_e164")),
        latitude=row.get("latitude"),
        longitude=row.get("longitude"),
        service_radius_km=float(row.get("service_radius_km") or 0),
        status=_text(row.get("status")) or "active",
        is_available=bool(row.get("is_available")),
        skill_ids=[str(value) for value in (row.get("skill_ids") or [])],
        skill_names=[str(value) for value in (row.get("skill_names") or [])],
        community_count=int(row.get("community_count") or 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_mine(client: Client, *, profile_id: str) -> ServiceProviderProfile:
    """The caller's own profile, or 404 if they have not registered.

    A 404 rather than an empty profile: "you are not a service provider" is a
    different answer from "you are one with nothing filled in", and the worker
    dashboard routes on it -- an unregistered caller is sent to the registration
    form rather than shown a blank one they might mistake for saved.
    """
    row = repo.get_by_profile(client, profile_id=profile_id)
    if row is None:
        raise NotFoundError(
            "You have not registered as a service provider.",
            code="service_provider_not_found",
        )
    return _to_profile(row)


def save_mine(
    client: Client, *, profile_id: str, body: UpdateServiceProviderRequest
) -> ServiceProviderProfile:
    """Register, or edit an existing registration.

    One function behind both ``POST`` and ``PATCH`` because
    ``upsert_service_provider`` is one RPC. The two routes differ in what they
    may say about the *name*: registration (``SaveServiceProviderRequest``, a
    subclass) carries it, settings (``UpdateServiceProviderRequest``) cannot —
    the PO's rule that name and email are identity, not settings. The RPC
    coalesces a null name onto the stored value since ``0045``.
    """
    repo.save_profile(
        client,
        display_name=getattr(body, "display_name", None),
        headline=body.headline,
        bio=body.bio,
        phone=body.phone,
        latitude=body.latitude,
        longitude=body.longitude,
        service_radius_km=body.service_radius_km,
    )
    return get_mine(client, profile_id=profile_id)


def register_mine(
    client: Client, *, profile_id: str, body: SaveServiceProviderRequest
) -> ServiceProviderProfile:
    """Atomically create or repair the caller's complete professional profile."""
    repo.register_profile(
        client,
        display_name=body.display_name,
        headline=body.headline,
        phone=body.phone,
        latitude=body.latitude,
        longitude=body.longitude,
        service_radius_km=body.service_radius_km,
        skill_ids=body.skill_ids,
    )
    return get_mine(client, profile_id=profile_id)


def list_skills(client: Client) -> list[Skill]:
    """The global catalogue of trades, for the registration form's checkboxes."""
    return [
        Skill(
            id=row["id"],
            name=_text(row.get("name")),
            category=_text(row.get("category")),
            description=_text(row.get("description")),
        )
        for row in repo.list_skills(client)
    ]


def set_skills(client: Client, *, body: SetSkillsRequest) -> SkillsSavedResult:
    """Replace the caller's trades with the given set.

    The count comes back from the database rather than from ``len(skillIds)``,
    and the difference is the point: ids that name a retired or unknown skill are
    dropped by the RPC, so a client sending eight and being told six has learned
    something true.
    """
    return SkillsSavedResult(
        skill_count=repo.set_skills(client, skill_ids=body.skill_ids)
    )


def set_availability(client: Client, *, is_available: bool) -> AvailabilityResult:
    """Go online or offline for new work.

    Offline stops the dispatch sweep in ``0037`` offering new jobs. It does
    **not** cancel jobs already accepted -- a worker who has agreed to be
    somewhere at four o'clock has made a commitment that a toggle does not
    retract, and the resident waiting for them has been told a name.
    """
    return AvailabilityResult(
        is_available=repo.set_availability(client, is_available=is_available)
    )
