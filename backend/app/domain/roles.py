"""Role names and their display labels.

The five values mirror the ``membership_role`` Postgres enum. This file once
carried an RBAC hierarchy (``role_satisfies`` and friends) claiming to be "the
single source of truth" for authorization — it never was: the live guards are
``require_membership_role`` in ``app/api/deps.py`` and the ``can_*`` predicates
in SQL, both of which read the membership row, not a token claim. The hierarchy
was deleted in the Phase 2 dead-code sweep (docs/potential issues/ item 2);
what remains is what the codebase actually uses — the :class:`Role` names and
the display-label mapping.
"""

from __future__ import annotations

from enum import Enum

# The stored vocabulary is uppercase (public.user_role); the React app renders
# 'Admin' / 'Resident' / 'Security'. Mapping lives here rather than in the
# database so that open decision 2 (reconciling the enum with the ERD's lowercase
# vocabulary) stays free to be settled either way.
_DISPLAY_ROLE = {
    "RESIDENT": "Resident",
    "ADMIN": "Admin",
    "MANAGER": "Manager",
    "TECHNICIAN": "Technician",
    "SECURITY": "Security",
}


def display_role(role: str) -> str:
    """Return the label the frontend renders for a stored role value."""
    return _DISPLAY_ROLE.get(role, role.title())


class Role(str, Enum):
    """A user's role within a community.

    Still imported by ``memberships_repository`` and ``invitations_repository``
    as a typed name for the enum values — which is why the sweep kept it.
    """

    RESIDENT = "RESIDENT"
    MANAGER = "MANAGER"
    WORKER = "WORKER"
    SECURITY = "SECURITY"
    ADMIN = "ADMIN"
