"""The resident portal's routers, aggregated into one mountable router.

Same arrangement as ``admin_api.py`` and for the same reason: ``app.api.v1``
mounts this with one import and one ``include_router``, so two workstreams
never edit the same router list and the merge stays clean.

Not everything behind this router is resident-only. ``events`` is the canonical
live-update stream for every role, and the notification and push routers that
follow it are member-wide too. They are here because this workstream builds and
owns them, not because a resident is the only caller -- see
``docs/design/RESIDENT_BACKEND_DESIGN.md`` 6.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    events,
    notifications,
    push,
    resident_amenities,
    resident_complaints,
    resident_home,
    resident_money,
    resident_snapshot,
    resident_visitor_passes,
)

resident_router = APIRouter()
resident_router.include_router(events.router)
resident_router.include_router(resident_snapshot.router)
resident_router.include_router(resident_amenities.router)
resident_router.include_router(resident_complaints.router)
resident_router.include_router(resident_visitor_passes.router)
resident_router.include_router(resident_money.router)
resident_router.include_router(resident_home.router)
resident_router.include_router(notifications.router)
resident_router.include_router(push.router)
