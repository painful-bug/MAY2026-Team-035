"""Skill authoring, and a community's categories with the trades behind them.

Thin, like every service over a definer RPC: the authorization questions are
asked in Postgres by ``can_manage_department`` and ``can_author_skills``, so
there is nothing for this layer to re-decide. What it does own is the shape of
the answer -- filling the two fields the wire declares non-null, and turning
``created`` into something the router can spend on a status code.
"""

from __future__ import annotations

from app.core.ttl_cache import TTLCache
from app.domain.service_provider_schemas import Skill
from app.domain.skill_schemas import (
    ComplaintCategory,
    CreateSkillRequest,
    SkillCreated,
    SkillSuggestion,
)
from app.repositories import skills_repository as repo
from supabase import Client

# Both reads below are community-scoped reference data -- a category list and a
# department's trade list barely change between one admin session and the
# next -- so both get the same 60-second, per-process TTL cache the
# departments list uses. See ``app.core.ttl_cache`` for the accepted
# process-local trade-off this relies on.
#
# Keyed by ``community_id``: every membership in the same community reads the
# same categories (``community_categories`` resolves the community from
# whichever membership calls it, but the answer does not depend on which one
# did), so caching per membership would fragment the cache across every
# person in a community for no benefit.
_CATEGORIES_CACHE: TTLCache[list[ComplaintCategory]] = TTLCache(
    ttl_seconds=60, max_entries=256
)

# Keyed by ``department_id`` rather than ``community_id``: this read answers a
# per-department question ("what does *this* department need"), not a
# per-community one, and the router that serves it does not carry a
# `MembershipContext` to derive a community id from without adding a lookup
# this cache exists to avoid. A department belongs to exactly one community,
# so invalidating by department id is exact rather than a broader proxy for it.
_DEPARTMENT_SKILLS_CACHE: TTLCache[list[Skill]] = TTLCache(
    ttl_seconds=60, max_entries=256
)


def reset_cache() -> None:
    """Empty both caches. For tests only."""
    _CATEGORIES_CACHE.clear()
    _DEPARTMENT_SKILLS_CACHE.clear()


def invalidate_categories_cache(community_id: str) -> None:
    """Drop the cached category list for one community.

    Categories are only ever created as a side effect of a department create
    or update (the RPC creates any name that does not already exist), so
    ``departments_service`` calls this after either write -- there is no
    dedicated category-mutation endpoint to hang it on instead.
    """
    _CATEGORIES_CACHE.invalidate(community_id)


def invalidate_department_skills_cache(department_id: str) -> None:
    """Drop the cached skill list for one department."""
    _DEPARTMENT_SKILLS_CACHE.invalidate(department_id)


def _text(value: object) -> str:
    """A non-null string for a nullable column.

    ``Skill.category`` and ``Skill.description`` are non-optional on the wire
    and the columns behind them are nullable. ``skills_and_categories``'s
    ``create_skill`` defaults both, so this only ever covers rows written before it.
    """
    return str(value) if value is not None else ""


def search(client: Client, *, query: str | None, limit: int) -> list[SkillSuggestion]:
    """Closest-match suggestions for the department form's skill box."""
    return [
        SkillSuggestion(
            id=row["id"],
            name=_text(row.get("name")),
            category=_text(row.get("category")),
            description=_text(row.get("description")),
            is_exact=bool(row.get("is_exact")),
            score=float(row.get("score") or 0.0),
        )
        for row in repo.search_skills(client, query=query, limit=limit)
    ]


def create(client: Client, *, body: CreateSkillRequest) -> SkillCreated:
    """Add a trade to the global catalogue, or return the existing match."""
    row = repo.create_skill(
        client,
        name=body.name,
        category=body.category,
        description=body.description,
    )
    return SkillCreated(
        id=row["id"],
        name=_text(row.get("name")),
        category=_text(row.get("category")),
        description=_text(row.get("description")),
        created=bool(row.get("created")),
    )


def list_categories(
    client: Client, *, membership_id: str, community_id: str
) -> list[ComplaintCategory]:
    """The caller's community's categories, each with the trade it resolves to.

    Cached 60 seconds per ``community_id``. ``membership_id`` still selects
    which row of ``community_memberships`` the RPC resolves the community
    from -- it is not part of the cache key, because the categories a
    membership sees are a fact about its community, not about it.
    """

    def _load() -> list[ComplaintCategory]:
        return [
            ComplaintCategory(
                id=row["id"],
                name=_text(row.get("name")),
                skill_id=row.get("skill_id"),
                skill_name=row.get("skill_name"),
                department_count=int(row.get("department_count") or 0),
            )
            for row in repo.community_categories(client, membership_id=membership_id)
        ]

    return _CATEGORIES_CACHE.get_or_load(community_id, _load)


def list_department_skills(client: Client, *, department_id: str) -> list[Skill]:
    """The skills one department claims.

    Returns ``Skill`` rather than a new model on purpose: this is the same
    object ``GET /skills`` returns, and a second shape for it would be two
    vocabularies for one thing.

    Cached 60 seconds per ``department_id``.
    """

    def _load() -> list[Skill]:
        return [
            Skill(
                id=row["id"],
                name=_text(row.get("name")),
                category=_text(row.get("category")),
                description=_text(row.get("description")),
            )
            for row in repo.list_department_skills(client, department_id=department_id)
        ]

    return _DEPARTMENT_SKILLS_CACHE.get_or_load(department_id, _load)


def add_department_skill(
    client: Client, *, department_id: str, name: str
) -> SkillCreated:
    """The "Add skill" button: create if needed, attach, one call."""
    row = repo.add_department_skill(client, department_id=department_id, name=name)
    invalidate_department_skills_cache(department_id)
    return SkillCreated(
        id=row["id"],
        name=_text(row.get("name")),
        category=_text(row.get("category")),
        description=_text(row.get("description")),
        created=bool(row.get("created")),
    )


def remove_department_skill(
    client: Client, *, department_id: str, skill_id: str
) -> None:
    """Detach one skill from one department."""
    repo.remove_department_skill(
        client, department_id=department_id, skill_id=skill_id
    )
    invalidate_department_skills_cache(department_id)


def set_department_skills(
    client: Client, *, department_id: str, skill_ids: list[str]
) -> list[Skill]:
    """Replace the set, then read it back.

    Read back rather than echoed, because the RPC is the authority on what
    landed -- and because a client that sent a retired id gets a 422 from the
    RPC rather than a cheerful echo of something that was not saved.
    """
    repo.set_department_skills(
        client, department_id=department_id, skill_ids=skill_ids
    )
    # Before the read-back below, or it would faithfully return the cached
    # set this call just replaced.
    invalidate_department_skills_cache(department_id)
    return list_department_skills(client, department_id=department_id)
