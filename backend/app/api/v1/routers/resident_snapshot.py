"""The resident home aggregate — `GET /resident/snapshot`.

Separate from `/dashboard/snapshot` by design (§5.1), not by accident. The two
screens want genuinely different things: an admin wants counts across the
community, a resident wants their own dues, their own visitors, their own
complaints. Branching one payload on a runtime role produces a response whose
shape cannot be typed and is one `if` away from putting a community-wide figure
in front of a resident.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_active_membership, get_request_client
from app.domain.resident_snapshot_schemas import ResidentSnapshot
from app.domain.schemas import MembershipContext
from app.services import resident_snapshot_service as service
from supabase import Client

router = APIRouter(tags=["resident-home"])


@router.get(
    "/resident/snapshot",
    response_model=ResidentSnapshot,
    summary="The resident home aggregate",
)
async def resident_snapshot(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> ResidentSnapshot:
    """Everything the resident home screen renders, in one call.

    **Takes no parameters.** Tenancy is the resolved membership and the community
    it belongs to, so there is nothing a caller could send that would widen what
    comes back.

    Every part is the same projection the screen it links to would return —
    `ResidentInvoice`, `VisitorPass`, `ComplaintSummary`, `Notice`,
    `NotificationItem` — so a bill on the home screen and the same bill on the
    Payments page can never show different amounts.

    Two things worth reading before wiring it up:

    * **The visitor counts are guests, not passes.** One pass for a party of
      twelve counts as twelve, which is what the shipped screen does and what a
      resident means by *how many people are coming*.
    * **`dues.isPartialTotal`** says `outstandingTotal` was summed over as many
      unpaid bills as one read carries. It is false for any resident with a
      normal number of them; when it is true, the total is a lower bound and the
      Payments page has the rest.

    `activity` is the caller's notification feed. There is no second event log,
    and `unreadNotifications` counts the whole feed rather than the five events
    returned here — a badge drawn from the page would be wrong the moment anybody
    scrolled.

    **Requires an active membership.** Not resident-only: a member of staff who
    lives in the community has dues and visitors like anyone else, and the
    aggregate is theirs, not their department's.
    """
    return service.snapshot(
        client,
        membership_id=membership.id,
        community_id=membership.community_id,
    )
