"""Authenticated, minimal community directory used by join onboarding."""

from __future__ import annotations

from postgrest.exceptions import APIError

from app.config import get_settings
from app.core.exceptions import AuthorizationError, ServiceUnavailableError, ValidationError
from app.core.supabase_client import get_service_client
from app.domain.schemas import (
    CommunitySearchItem,
    CommunitySearchResponse,
    CommunityUnitListResponse,
    CommunityUnitOption,
)
from app.repositories import communities_repository


def search(query: str, limit: int | None, profile_id: str) -> CommunitySearchResponse:
    normalized = " ".join(query.split())
    if len(normalized) < 2:
        raise ValidationError(
            "Enter at least two characters to search communities.",
            code="community_search_query_too_short",
        )
    if len(normalized) > 100:
        raise ValidationError("Community search is too long.", code="validation_failed")
    settings = get_settings()
    bounded_limit = min(
        max(limit or settings.community_search_default_limit, 1),
        settings.community_search_max_limit,
    )
    try:
        rows = communities_repository.search_joinable_communities(
            get_service_client(),
            query=normalized,
            limit=bounded_limit,
            profile_id=profile_id,
        )
    except APIError as exc:
        # This is a deployment/schema mismatch, not a malformed user search.
        # Do not fall back to the former two-argument RPC: it lacks the active
        # blacklist exclusion and would expose communities that must stay hidden.
        if exc.code == "PGRST202" and "search_joinable_communities" in exc.message:
            raise ServiceUnavailableError(
                "Community search is being updated. Please try again shortly.",
                code="community_search_schema_unavailable",
            ) from exc
        raise ServiceUnavailableError(
            "Community search is temporarily unavailable. Please try again.",
            code="community_search_unavailable",
        ) from exc
    return CommunitySearchResponse(items=[CommunitySearchItem(**row) for row in rows])


def admin_units(profile_id: str) -> CommunityUnitListResponse:
    service = get_service_client()
    memberships = (
        service.table("community_memberships")
        .select("community_id")
        .eq("profile_id", profile_id)
        .eq("role", "admin")
        .eq("status", "active")
        .is_("ended_at", None)
        .order("is_default_community", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not memberships:
        raise AuthorizationError(
            "Administrator access is required.", code="community_role_required"
        )
    rows = (
        service.table("units")
        .select("id, unit_code, buildings(name)")
        .eq("community_id", memberships[0]["community_id"])
        .eq("status", "active")
        .order("unit_code")
        .execute()
        .data
        or []
    )
    return CommunityUnitListResponse(
        items=[
            CommunityUnitOption(
                id=row["id"],
                unit_code=row["unit_code"],
                building_name=(row.get("buildings") or {}).get("name")
                if not isinstance(row.get("buildings"), list)
                else (row.get("buildings") or [{}])[0].get("name"),
            )
            for row in rows
        ]
    )
