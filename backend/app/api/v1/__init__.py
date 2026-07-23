"""Version 1 of the HTTP API.

Aggregates all v1 routers into a single ``api_router`` that ``app.main`` mounts
under ``/api/v1``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import auth, invitations

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(invitations.router)
