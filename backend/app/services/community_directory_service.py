"""Authenticated, minimal community directory used by join onboarding."""

from __future__ import annotations

from app.config import get_settings
from app.core.exceptions import AuthorizationError, ValidationError
from app.core.supabase_client import get_service_client
from app.domain.schemas import (
    CommunitySearchItem,
    CommunitySearchResponse,
    CommunityUnitListResponse,
    CommunityUnitOption,
)
from app.repositories import communities_repository


def search(query: str, limit: int | None) -> CommunitySearchResponse:
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
    rows = communities_repository.search_joinable_communities(
        get_service_client(), query=normalized, limit=bounded_limit
    )
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
