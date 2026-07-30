"""Version 1 of the HTTP API.

Aggregates all v1 routers into a single ``api_router`` that ``app.main`` mounts
under ``/api/v1``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    amenities,
    auth,
    complaints,
    dashboard,
    departments,
    invitations,
    money,
    people,
    settings,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(invitations.router)
api_router.include_router(dashboard.router)
api_router.include_router(people.router)
api_router.include_router(complaints.router)
api_router.include_router(departments.router)
api_router.include_router(money.router)
api_router.include_router(amenities.router)
api_router.include_router(settings.router)
