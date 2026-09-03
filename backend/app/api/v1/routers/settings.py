"""Community settings routes.

**Module *management* is not here any more.** The clean baseline ships
``feature_catalog`` + ``community_features``, whose ten keys and default-enabled
values are byte-identical to the ``module_catalogue`` step 9 built -- both were
derived from ``onboardingModules.js``. Their onboarding RPC already writes it, and
module selection exists only as an onboarding step, so our three module endpoints
and two tables were duplicates with no caller. See
``docs/FRONTEND_WIRING_AUDIT.md`` and addendum C-11.

``GET /settings`` still *reports* the module collection, and that read was the
loose end for a while: it came from module tables of ours, so the duplication the
endpoint deletions were meant to remove survived one level down.
``0022_settings_views_on_baseline.sql`` closes it. ``community_module_overview``
is now a view over **their** ``feature_catalog`` and ``community_features``, so
there is exactly one place a module's enabled state lives and the onboarding
workstream owns the writer. ``0017_settings.sql``'s module tables are permanently
superseded and are not part of the rebuild.

The view adds three columns to ``feature_catalog`` rather than keeping a parallel
table: ``sort_order``, ``backend_status`` and ``backend_note``. They are
editorial metadata about *our* backend -- whether a module a community has
switched on actually does anything yet -- which is a fact about the code rather
than about the community, and the Settings screen is the place that should be
able to say so.

**There is no community rename here, and that is deliberate.**
``GET /settings`` reports the community's name, type and status; nothing writes
them. ``communities`` (the baseline's rename of ``associations``) is the one table
this build plan touches whose admin write policy carries no community clause
(build plan 1.2, owned by the auth workstream), and a rename would be the first
endpoint of sixty-eight to depend on it. It waits for that fix rather than
becoming the reason it was urgent.

**The billing toggles are readable here and writable only at
``PUT /billing-settings``.** They appear in the snapshot because the screen draws
all four switches on one card; money keeps one writer because two is how a rate
starts disagreeing with itself.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.admin_deps import require_admin, require_csrf_unsafe
from app.api.deps import get_active_membership, get_request_client
from app.domain.schemas import MembershipContext
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
def get_settings(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> SettingsSnapshot:
    """Everything the settings screen needs, in one request.

    ``hasSavedSettings`` is ``false`` for a community that has never saved. The
    values are then defaults rather than choices, and rendering the two the same
    way tells an admin they picked a timezone they have never seen.
    """
    return settings_service.get_settings_snapshot(client, membership.community_id)


@router.put(
    "/settings",
    response_model=SettingsSnapshot,
    summary="Patch the community preferences",
    dependencies=[_admin],
)
def update_settings(
    body: UpdateSettingsRequest,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> SettingsSnapshot:
    """Patch the community preferences. Omitted fields are left unchanged.

    ``unitLabelSingular: null`` clears the override and goes back to deriving the
    word from the community type, which is not what omitting the field does.
    """
    return settings_service.update_settings(client, membership.community_id, body)


