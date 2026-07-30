"""Data-access layer.

Every module here reads/writes through ``app.core.supabase_client``.
"""

from . import (
    access_requests_repository,
    communities_repository,
    invitations_repository,
    memberships_repository,
    profiles_repository,
)

__all__ = [
    "access_requests_repository",
    "communities_repository",
    "invitations_repository",
    "memberships_repository",
    "profiles_repository",
]
