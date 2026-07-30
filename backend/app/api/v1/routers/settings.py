"""Community settings and feature-module routes.

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

from fastapi import APIRouter, Depends, Path

from app.api.deps import get_current_user, get_request_client, require_role
from app.domain.roles import Role
from app.domain.settings_schemas import (
    ModuleCollection,
    ModuleSummary,
    ModuleToggleRequest,
    ReplaceModulesRequest,
    SettingsSnapshot,
    UpdateSettingsRequest,
)
from app.services import settings_service
from supabase import Client

router = APIRouter(tags=["settings"])

_admin = Depends(require_role(Role.ADMIN))


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


@router.get(
    "/settings/modules",
    response_model=ModuleCollection,
    summary="List the feature modules",
)
async def list_modules(
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ModuleCollection:
    """The ten feature modules and this community's setting for each.

    **Any authenticated role**, unlike the rest of this file: if module state ever
    gates navigation then every shell needs it, and a resident learning the
    marketplace is off discloses nothing.

    ``backendStatus`` is the field worth rendering. Six of the ten modules have no
    backend at all, so without it an admin can switch on Parking Management and
    be given no hint that nothing will happen. ``enabledWithoutBackend`` is that
    count.
    """
    return settings_service.list_modules(client, principal.user_id)


@router.patch(
    "/settings/modules/{moduleKey}",
    response_model=ModuleSummary,
    summary="Toggle one feature module",
    dependencies=[_admin],
)
async def set_module(
    body: ModuleToggleRequest,
    module_key: str = Path(
        ...,
        alias="moduleKey",
        max_length=64,
        description="A catalogue key such as `amenities-booking`. Unknown keys 404.",
    ),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ModuleSummary:
    """Turn one module on or off.

    One key at a time so two admins toggling two different modules in the same
    minute do not undo each other -- which is what a whole-set write does.
    """
    return settings_service.set_module(
        client, principal.user_id, module_key, body.enabled
    )


@router.put(
    "/settings/modules",
    response_model=ModuleCollection,
    summary="Replace the whole module set",
    dependencies=[_admin],
)
async def replace_modules(
    body: ReplaceModulesRequest,
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ModuleCollection:
    """Set the whole module set from the list of keys that should be on.

    The shape the onboarding wizard already produces: ``enabledModules`` is the
    array of enabled keys, and every other key is off by omission. Every key is
    validated before anything is written, so one typo does not leave a community
    half-configured.

    An empty array is legitimate and turns everything off. A missing field is a
    `422` rather than the same thing, because a caller who forgot it would
    otherwise disable the whole product by accident.
    """
    return settings_service.replace_modules(client, principal.user_id, body)
