"""Admin-dashboard routers, aggregated into one mountable router.

Everything the admin dashboard workstream adds lives behind this single
``admin_router``. ``app.api.v1`` mounts it with two lines — one import and one
``include_router`` — so the two workstreams do not both edit the same router
list and the merge stays clean.

The routers here serve the admin screens that the shared dashboard snapshot
cannot: anything needing pagination, filtering, or a write. Reads that the
snapshot already satisfies are deliberately absent — see
``docs/RECONCILIATION_ADDENDUM.md`` C-8.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    admin_overview,
    amenities,
    complaints,
    departments,
    money,
    people,
    settings,
)

admin_router = APIRouter()
admin_router.include_router(admin_overview.router)
admin_router.include_router(people.router)
admin_router.include_router(complaints.router)
admin_router.include_router(departments.router)
admin_router.include_router(money.router)
admin_router.include_router(amenities.router)
admin_router.include_router(settings.router)
