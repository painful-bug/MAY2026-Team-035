"""Community directory endpoints available before tenancy is established."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.domain.schemas import (
    CommunitySearchResponse,
    CommunityUnitListResponse,
    Principal,
)
from app.services import community_directory_service

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("/search", response_model=CommunitySearchResponse)
async def search_communities(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int | None = Query(default=None, ge=1, le=20),
    _: Principal = Depends(get_current_user),
) -> CommunitySearchResponse:
    return community_directory_service.search(q, limit)


@router.get("/admin/units", response_model=CommunityUnitListResponse)
async def list_admin_units(
    principal: Principal = Depends(get_current_user),
) -> CommunityUnitListResponse:
    return community_directory_service.admin_units(principal.user_id)
