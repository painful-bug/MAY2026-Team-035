"""Wire models for authoring skills and reading a community's categories.

**Reading the catalogue lives elsewhere.** ``Skill`` and ``GET /skills`` are in
``service_provider_schemas.py`` and ``routers/service_providers.py``, because
that endpoint exists for the service person's registration screen and has since
``0034``. This module is the *authoring* half: adding a trade to the catalogue,
and attaching trades to a department. Splitting them that way keeps the
registration surface -- which any signed-in person may read -- separate from the
surface only admins and managers may write.

**The catalogue is global and stays global.** ``skills`` has never carried a
``community_id``. A per-community catalogue would mean one trade spelled several
ways, so a plumber registering in two societies claims "Plumbing" twice and the
hiring search matches neither. The argument is set out in ``0034`` 39-48 and the
instruction that produced this module repeats it.
"""

from __future__ import annotations

from pydantic import Field

from app.domain.common_schemas import CamelModel


class SkillSuggestion(CamelModel):
    """One closest-match result for the department form's skill box.

    ``isExact`` is computed by Postgres rather than by the client, so the rule
    for when to offer "add this as a new skill" lives in one place. It is case-
    and whitespace-insensitive: typing ``"  plumbing "`` is exact against
    ``Plumbing`` and must not offer to create a second one.

    ``score`` is the raw pg_trgm similarity, 0 to 1. It is exposed because a
    suggestion list that cannot say *how* close a match is cannot explain itself
    -- and because the frontend uses it for nothing else, deliberately: the
    ordering is already done here.
    """

    id: str
    name: str
    category: str
    description: str
    is_exact: bool
    score: float


class CreateSkillRequest(CamelModel):
    """Add a trade to the global catalogue."""

    name: str = Field(min_length=1, max_length=80)
    #: Free text, not an enum -- the catalogue is data. Omitted becomes
    #: ``other``, which earns a visible group in the worker's chip grid rather
    #: than a null nobody classified.
    category: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=500)


class SkillCreated(CamelModel):
    """A skill, and whether this call is what brought it into being.

    ``created`` is false when a case-insensitive match already existed, which is
    the normal outcome of somebody typing a trade that is already there. The
    router turns it into 201 or 200 so the status code is not a polite fiction.
    """

    id: str
    name: str
    category: str
    description: str
    created: bool


class ComplaintCategory(CamelModel):
    """One of a community's complaint categories, and the trade it resolves to.

    ``skillName`` being null is the case this model exists to surface. A
    category whose name matches no trade is not an error -- ``0034`` 204-206
    settled that -- but until now it has been *invisible*, and an invisible one
    is a category whose complaints no hiring search will ever match, with
    nothing anywhere saying so. The category form shows it as a warning.
    """

    id: str
    name: str
    skill_id: str | None = None
    skill_name: str | None = None
    #: How many departments claim this category. Zero means nobody handles it.
    department_count: int = 0
