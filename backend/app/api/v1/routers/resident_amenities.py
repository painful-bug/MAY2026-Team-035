"""The resident half of the amenity surface.

Separate from `routers/amenities.py`, which is the admin-dashboard workstream's
file and already carries thirteen admin routes plus the two deliberately
unguarded resident writes. Adding to it would put two workstreams in one router
list for no gain -- the same reason `resident_api.py` exists at all. Nothing
here is a duplicate of anything there: `amenities.py` has no catalogue read,
which is the whole of finding 3.1.

The guard is `get_active_membership`: any active member, not `resident` only. A
security guard or a worker asking what facilities the community has is a
reasonable thing to answer, and this response carries no per-resident data to
scope. The *write* path stays as it is.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_active_membership, get_request_client
from app.domain.common_schemas import Page
from app.domain.resident_amenity_schemas import BookableAmenity
from app.domain.schemas import MembershipContext
from app.services import resident_amenities_service
from supabase import Client

router = APIRouter(tags=["amenities"])


@router.get(
    "/amenities/available",
    response_model=Page[BookableAmenity],
    summary="List bookable amenities",
)
async def list_available_amenities(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> Page[BookableAmenity]:
    """The amenities the caller may request a booking against.

    **"Available" means bookable in principle, not free right now.** Every
    amenity here exists, is active, and has no temporary closure recorded
    against it. Whether a particular slot is open is decided on write, under an
    advisory lock, by the booking guard -- a read endpoint that answered it
    would be describing a moment that had already passed by the time the
    resident submitted the form.

    The community is read from the caller's active membership, resolved from
    Postgres. There is no community parameter, so there is nothing to tamper
    with.

    Returns the full catalogue in one response: `page` is always 1 and, for any
    community this product will plausibly see, `hasMore` is false. It is
    computed rather than asserted — a `true` means the catalogue has outgrown
    being unpaged and rows are being withheld, which no client could work out
    from the response otherwise. The `Page` envelope is kept so every collection
    on this API has one shape.
    """
    return resident_amenities_service.list_available(
        client,
        # The community, not the whole context. A projection with no per-role
        # branch in it should not be handed the caller's role to grow one from.
        community_id=membership.community_id,
    )
