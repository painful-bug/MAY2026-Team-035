"""Skill authoring, and a community's categories with the trades behind them.

Thin, like every service over a definer RPC: the authorization questions are
asked in Postgres by ``can_manage_department`` and ``can_author_skills``, so
there is nothing for this layer to re-decide. What it does own is the shape of
the answer -- filling the two fields the wire declares non-null, and turning
``created`` into something the router can spend on a status code.
"""

from __future__ import annotations

from app.domain.service_provider_schemas import Skill
from app.domain.skill_schemas import (
    ComplaintCategory,
    CreateSkillRequest,
    SkillCreated,
    SkillSuggestion,
)
from app.repositories import skills_repository as repo
from supabase import Client


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


def list_categories(client: Client, *, membership_id: str) -> list[ComplaintCategory]:
    """The caller's community's categories, each with the trade it resolves to."""
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


def list_department_skills(client: Client, *, department_id: str) -> list[Skill]:
    """The skills one department claims.

    Returns ``Skill`` rather than a new model on purpose: this is the same
    object ``GET /skills`` returns, and a second shape for it would be two
    vocabularies for one thing.
    """
    return [
        Skill(
            id=row["id"],
            name=_text(row.get("name")),
            category=_text(row.get("category")),
            description=_text(row.get("description")),
        )
        for row in repo.list_department_skills(client, department_id=department_id)
    ]


def add_department_skill(
    client: Client, *, department_id: str, name: str
) -> SkillCreated:
    """The "Add skill" button: create if needed, attach, one call."""
    row = repo.add_department_skill(client, department_id=department_id, name=name)
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
    return list_department_skills(client, department_id=department_id)
