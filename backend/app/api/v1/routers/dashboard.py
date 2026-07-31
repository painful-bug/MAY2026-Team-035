"""Database-backed projections and live updates for every authenticated portal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.api.deps import get_active_membership, require_csrf, require_membership_role
from app.domain.schemas import AmenityWrite, DashboardSnapshot, MembershipContext
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/snapshot", response_model=DashboardSnapshot)
async def get_dashboard_snapshot(
    membership: MembershipContext = Depends(get_active_membership),
) -> DashboardSnapshot:
    """Return the caller's current, tenant-authorized dashboard records."""
    return await run_in_threadpool(dashboard_service.snapshot, membership)


# The generated spec would otherwise advertise `application/json` here, because
# that is FastAPI's default for any route it cannot infer a media type from --
# and a client generated from that would try to JSON-decode a live stream.
@router.get(
    "/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Event stream. Frame format and topics: docs/API.md 5.1.",
        },
        401: {"description": "No session."},
        403: {"description": "No active membership."},
    },
)
async def dashboard_events(
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    membership: MembershipContext = Depends(get_active_membership),
) -> StreamingResponse:
    """Same-origin SSE stream. No provider token is exposed to the browser."""
    try:
        cursor = int(last_event_id or 0)
    except ValueError:
        cursor = 0
    return StreamingResponse(
        dashboard_service.event_stream(membership, cursor),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
