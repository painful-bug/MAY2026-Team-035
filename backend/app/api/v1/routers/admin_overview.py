"""Admin dashboard read-only routes.

These four endpoints establish the conventions every later dashboard surface
copies: the ``Page`` envelope, the ``timeAgo`` + ISO pairing, the label + id
pairing, and ``Cache-Control`` chosen per endpoint rather than globally.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_current_user, get_request_client, require_role
from app.domain.dashboard_schemas import (
    AdminDashboard,
    CommunitySummary,
    NoticeSummary,
    Page,
    ResidentSummary,
)
from app.domain.roles import Role
from app.services import admin_overview_service
from supabase import Client

router = APIRouter(tags=["dashboard"])

# Responses carrying a relative time ("2h ago") are only correct at the instant
# they are generated, so they must never be cached. Applied per endpoint, not as
# middleware, so that endpoints without a relative time stay cacheable.
_NO_STORE = "no-store"


@router.get(
    "/dashboard/admin",
    response_model=AdminDashboard,
    dependencies=[Depends(require_role(Role.ADMIN))],
    summary="Admin home aggregate",
)
async def get_admin_dashboard(
    response: Response,
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> AdminDashboard:
    """Counts for the admin home tiles, in one request instead of five."""
    response.headers["Cache-Control"] = _NO_STORE
    return admin_overview_service.get_admin_dashboard(client, principal.user_id)


@router.get(
    "/communities/current",
    response_model=CommunitySummary,
    summary="The caller's community",
)
async def get_current_community(
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> CommunitySummary:
    """Return the community the caller belongs to.

    Open to any authenticated member, not admins only: the resident shell needs
    the community name in its header too.
    """
    return admin_overview_service.get_community(client, principal.user_id)


@router.get(
    "/residents",
    response_model=Page[ResidentSummary],
    dependencies=[Depends(require_role(Role.ADMIN))],
    summary="List residents",
)
async def list_residents(
    search: str | None = Query(
        None, max_length=100, description="Matches name, flat code or phone."
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[ResidentSummary]:
    """Page through the community's residents.

    Returns ``{"items": [], "total": 0}`` with HTTP 200 when there are none --
    never a 404, so the frontend has one shape to render either way.
    """
    return admin_overview_service.list_residents(
        client, principal.user_id, search=search, page=page, page_size=page_size
    )


@router.get(
    "/notices",
    response_model=Page[NoticeSummary],
    summary="List published notices",
)
async def list_notices(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[NoticeSummary]:
    """Published notices, newest first. Readable by any member of the community."""
    response.headers["Cache-Control"] = _NO_STORE
    return admin_overview_service.list_notices(
        client, principal.user_id, page=page, page_size=page_size
    )
