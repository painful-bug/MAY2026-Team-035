"""Version 1 of the HTTP API.

Aggregates all v1 routers into a single ``api_router`` that ``app.main`` mounts
under ``/api/v1``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.admin_api import admin_router
from app.api.v1.routers import access_requests, auth, communities, dashboard, invitations, onboarding

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(communities.router)
api_router.include_router(access_requests.router)
api_router.include_router(dashboard.router)
api_router.include_router(invitations.router)
api_router.include_router(onboarding.router)
api_router.include_router(admin_router)
