"""Community settings routes.

**Module management is not here any more.** The clean baseline ships
``feature_catalog`` + ``community_features``, whose ten keys and default-enabled
values are byte-identical to the ``module_catalogue`` step 9 built -- both were
derived from ``onboardingModules.js``. Their onboarding RPC already writes it, and
module selection exists only as an onboarding step, so our three endpoints and two
tables were duplicates with no caller. ``GET /settings`` still *reports*
``enabledModules``, read from ``community_features``. See
``docs/FRONTEND_WIRING_AUDIT.md`` and addendum C-11.

**There is no community rename here, and that is deliberate.**
``GET /settings`` reports the community's name, type and status; nothing writes
them. ``associations`` is the one table this build plan touches whose admin write
policy carries no community clause (build plan 1.2, owned by the auth workstream),
and a rename would be the first endpoint of sixty-eight to depend on it. It waits
for that fix rather than becoming the reason it was urgent.

**The billing toggles are readable here and writable only at
``PUT /billing-settings``.** They appear in the snapshot because the screen draws
all four switches on one card; money keeps one writer because two is how a rate
starts disagreeing with itself.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.admin_deps import require_admin, require_csrf_unsafe
from app.api.deps import get_current_user, get_request_client
from app.domain.settings_schemas import SettingsSnapshot, UpdateSettingsRequest
from app.services import settings_service
from supabase import Client

router = APIRouter(tags=["settings"], dependencies=[Depends(require_csrf_unsafe)])

_admin = Depends(require_admin)


@router.get(
    "/settings",
    response_model=SettingsSnapshot,
    summary="The community settings snapshot",
    dependencies=[_admin],
)
async def get_settings(
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> SettingsSnapshot:
    """Everything the settings screen needs, in one request.

    ``hasSavedSettings`` is ``false`` for a community that has never saved. The
    values are then defaults rather than choices, and rendering the two the same
    way tells an admin they picked a timezone they have never seen.
    """
    return settings_service.get_settings_snapshot(client, principal.user_id)


@router.put(
    "/settings",
    response_model=SettingsSnapshot,
    summary="Patch the community preferences",
    dependencies=[_admin],
)
async def update_settings(
    body: UpdateSettingsRequest,
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> SettingsSnapshot:
    """Patch the community preferences. Omitted fields are left unchanged.

    ``unitLabelSingular: null`` clears the override and goes back to deriving the
    word from the community type, which is not what omitting the field does.
    """
    return settings_service.update_settings(client, principal.user_id, body)


