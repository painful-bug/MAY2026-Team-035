"""People routes: promoting a member to administrator.

Everything else this router used to carry was removed after the frontend wiring
audit (``docs/FRONTEND_WIRING_AUDIT.md``): the resident and admin *reads* are
served by ``GET /dashboard/snapshot``, and the registration-review trio duplicated
their ``/admin/access-requests`` endpoints, which the frontend already calls.

What is left is the one people action no endpoint anywhere could serve.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.admin_deps import require_admin, require_csrf_unsafe
from app.api.deps import get_active_membership, get_request_client
from app.domain.schemas import MembershipContext
from app.domain.people_schemas import AdminSummary, PromoteAdminRequest
from app.services import people_service
from supabase import Client

router = APIRouter(
    tags=["people"],
    dependencies=[Depends(require_admin), Depends(require_csrf_unsafe)],
)


@router.post(
    "/admins",
    response_model=AdminSummary,
    summary="Promote a member to administrator",
)
def promote_admin(
    body: PromoteAdminRequest,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> AdminSummary:
    """Give an existing community member the ``admin`` role.

    **This promotes, it does not invite.** The person must already be an active
    member of the caller's community, matched by email. That is the flow
    ``roles.md`` describes -- *"Resident -> Committee members -> Admin"* -- and it
    is the only one available: the shared invitation contract hardcodes
    ``intended_role = 'resident'`` and exposes no role field, so an admin-bound
    invite cannot be minted without duplicating the token machinery this
    workstream does not own.

    Returns **404** when the email belongs to nobody in the community. The caller
    should invite them first (``POST /admin/invitations``), let them redeem, then
    promote. Returns **409** if they are already an admin.

    Only ``email`` is used. ``name``, ``phone``, ``tower`` and ``flat`` are
    accepted because the Admins screen sends them, but the member already has all
    four on their profile and residency, and letting a promotion silently rewrite
    someone's flat would be a worse bug than ignoring the fields.
    """
    return people_service.promote_admin(client, membership.community_id, body)
