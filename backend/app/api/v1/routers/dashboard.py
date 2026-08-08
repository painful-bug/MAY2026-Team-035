"""Database-backed projections and live updates for every authenticated portal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.api.deps import get_active_membership, require_csrf, require_membership_role
from app.api.v1.routers import events
from app.domain.schemas import AmenityWrite, DashboardSnapshot, MembershipContext
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/snapshot", response_model=DashboardSnapshot)
async def get_dashboard_snapshot(
    membership: MembershipContext = Depends(get_active_membership),
) -> DashboardSnapshot:
    """Return the caller's current, tenant-authorized dashboard records."""
    return await run_in_threadpool(dashboard_service.snapshot, membership)


@router.get(
    "/events",
    response_class=StreamingResponse,
    responses=events.SSE_RESPONSES,
    deprecated=True,
)
async def dashboard_events(
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    membership: MembershipContext = Depends(get_active_membership),
) -> StreamingResponse:
    """Deprecated alias for `GET /events`; identical behaviour.

    The stream was never dashboard-specific -- its guard has always been
    `get_active_membership` -- and since `0028` it is audience-scoped for every
    role, so it lives at `/events` now. This path stays because the admin
    frontend is wired to it and a working client is not worth breaking to tidy
    a URL. Both routes call the same handler body; there is no second
    implementation to keep in step.
    """
    return events.stream(membership, last_event_id)


@router.post("/amenities", dependencies=[Depends(require_csrf)])
async def create_amenity(
    body: AmenityWrite,
    membership: MembershipContext = Depends(
        require_membership_role("admin", "manager")
    ),
) -> dict:
    return await run_in_threadpool(
        dashboard_service.save_amenity,
        membership, amenity_id=None, payload=body.model_dump()
    )


@router.put("/amenities/{amenity_id}", dependencies=[Depends(require_csrf)])
async def update_amenity(
    amenity_id: str,
    body: AmenityWrite,
    membership: MembershipContext = Depends(
        require_membership_role("admin", "manager")
    ),
) -> dict:
    return await run_in_threadpool(
        dashboard_service.save_amenity,
        membership, amenity_id=amenity_id, payload=body.model_dump()
    )


@router.delete("/amenities/{amenity_id}", dependencies=[Depends(require_csrf)])
async def delete_amenity(
    amenity_id: str,
    membership: MembershipContext = Depends(
        require_membership_role("admin", "manager")
    ),
) -> dict:
    await run_in_threadpool(dashboard_service.remove_amenity, membership, amenity_id)
    return {"id": amenity_id}
