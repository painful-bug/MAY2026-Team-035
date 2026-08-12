"""A service person's own registration.

Six routes, and the notable thing about all of them is the guard: **authenticated
only, with no membership requirement.**

That is deliberate and it is load-bearing. Every other write surface in this API
resolves an active community membership first, because every other caller is a
member of somewhere. A service person is not: they register, and only later does
a department manager hire them. Putting ``get_active_membership`` on these routes
would 403 an unregistered provider out of exactly the screens that let them apply
for work -- a system in which nobody can ever be hired. See
``docs/plans/SERVICE_OPERATIONS_PROGRESS.md`` 4.4.

Authorization is not thereby absent, it has moved: the three RPCs behind these
routes resolve the provider from ``auth.uid()`` themselves, and
``service_providers`` carries a read policy and no write policy at all.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_current_user, get_request_client
from app.domain.schemas import Principal
from app.domain.service_provider_schemas import (
    AvailabilityResult,
    SaveServiceProviderRequest,
    ServiceProviderProfile,
    SetAvailabilityRequest,
    SetSkillsRequest,
    Skill,
    SkillsSavedResult,
    UpdateServiceProviderRequest,
)
from app.services import service_providers_service as service
from supabase import Client

router = APIRouter(
    tags=["service-providers"], dependencies=[Depends(require_csrf_unsafe)]
)


@router.get(
    "/skills",
    response_model=list[Skill],
    summary="The global catalogue of trades",
)
async def list_skills(
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> list[Skill]:
    """Every active skill, alphabetically.

    **Global, not per-community**, which is the asymmetry the whole feature rests
    on: `complaint_categories` is a community's own vocabulary and carries a
    nullable `skillId` pointing into this list. Without that link the community
    search returns nothing for everybody, so a category a community invents that
    matches no trade here is not an error -- it only means no service person is
    matched to it.

    A retired trade is filtered out here rather than deleted, so a provider who
    has held it for two years keeps the row that says so.
    """
    return service.list_skills(client)


@router.post(
    "/service-providers",
    response_model=ServiceProviderProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Register as a service person",
)
async def register(
    body: SaveServiceProviderRequest,
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ServiceProviderProfile:
    """Create the caller's service-provider profile.

    **Idempotent on the caller.** A second registration edits the first rather
    than colliding with it -- `upsert_service_provider` is an upsert on
    `profile_id` -- so a half-finished form resumed on another device is not a
    409 the person cannot act on. The status is still `201`, because from the
    client's side the resource now exists either way.

    Coordinates are optional and worth sending. A provider with none still
    appears in every community search; they simply sort last, since there is no
    distance to order them by.
    """
    return service.save_mine(client, profile_id=principal.user_id, body=body)


@router.get(
    "/service-providers/me",
    response_model=ServiceProviderProfile,
    summary="My service-provider profile",
)
async def get_mine(
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ServiceProviderProfile:
    """The caller's own profile, with their trades and community count.

    **404 when the caller has never registered**, rather than an empty profile.
    The two are different answers and the dashboard routes on the difference: an
    unregistered caller is sent to the registration form, not shown a blank one
    they might take for saved.

    `communityCount` is counted from live memberships, not stored. It is what
    drives the empty state -- a provider employed nowhere sees the "find work"
    prompt instead of an empty calendar.
    """
    return service.get_mine(client, profile_id=principal.user_id)


@router.patch(
    "/service-providers/me",
    response_model=ServiceProviderProfile,
    summary="Edit my service-provider profile",
)
async def update_mine(
    body: UpdateServiceProviderRequest,
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ServiceProviderProfile:
    """Change the caller's details — **everything except the name.**

    `displayName` is not accepted here (and an extra field is a `422`, per the
    strict models): a service person's name and email are identity, edited
    nowhere in settings — a product-owner rule from 2026-08-10. Registration
    still names you; this route never renames you.

    **An omitted field is left alone, not cleared.** The RPC coalesces onto the
    stored value, so a client may send one changed field without first reading
    the other six and echoing them back.

    The response is re-read from the database rather than composed from the
    request, because `serviceRadiusKm` defaults in SQL and `skillNames` and
    `communityCount` are not the caller's to set.
    """
    return service.save_mine(client, profile_id=principal.user_id, body=body)


@router.put(
    "/service-providers/me/skills",
    response_model=SkillsSavedResult,
    summary="Set which trades I offer",
)
async def set_skills(
    body: SetSkillsRequest,
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> SkillsSavedResult:
    """Replace the caller's trades with the given set.

    **A `PUT` of the whole set, not add and remove.** The screen is a list of
    checkboxes, and two tabs toggling different boxes against a delta API is a
    lost update nobody notices until a plumber stops being offered plumbing.

    **An unknown or retired skill id is ignored, not rejected.** The RPC selects
    against the catalogue rather than trusting the argument, so a client holding
    a stale list saves the trades that still exist instead of failing whole. That
    is why `skillCount` comes back: sending eight and being told six is the
    client learning something true.
    """
    return service.set_skills(client, body=body)


@router.patch(
    "/service-providers/me/availability",
    response_model=AvailabilityResult,
    summary="Go online or offline for new work",
)
async def set_availability(
    body: SetAvailabilityRequest,
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> AvailabilityResult:
    """The dashboard's offline toggle.

    Offline stops the dispatch sweep offering new jobs. **It does not cancel work
    already accepted** -- a worker who agreed to be somewhere at four o'clock has
    made a commitment a toggle does not retract, and a resident has been told
    their name. Cancelling a scheduled visit is a separate act with its own
    notification.
    """
    return service.set_availability(client, is_available=body.is_available)
