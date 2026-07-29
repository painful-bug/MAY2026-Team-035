"""Role definitions and the RBAC hierarchy.

The five roles mirror the ``user_role`` Postgres enum (see
``supabase/migrations/0001_init.sql``) and the ``user_role`` claim injected into
every access token by the custom access-token hook.

Capability model:

* ``ADMIN`` is a superset of ``RESIDENT`` — an administrator is also a resident
  of the community, so any resident-gated resource is reachable by an admin.
* ``MANAGER``, ``WORKER`` and ``SECURITY`` are distinct staff capabilities
  that do not imply one another or resident access.

:func:`role_satisfies` is the single source of truth for "does this role meet
this requirement" and is used by both the API guards and the tests.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """A user's role within a community."""

    RESIDENT = "RESIDENT"
    MANAGER = "MANAGER"
    WORKER = "WORKER"
    SECURITY = "SECURITY"
    ADMIN = "ADMIN"


# Roles each role implicitly satisfies, in addition to itself.
_IMPLIED_ROLES: dict[Role, frozenset[Role]] = {
    Role.ADMIN: frozenset({Role.RESIDENT}),
}


def effective_roles(role: Role) -> frozenset[Role]:
    """Return every role ``role`` satisfies, including itself."""
    return frozenset({role}) | _IMPLIED_ROLES.get(role, frozenset())


def role_satisfies(user_role: Role, required: Role) -> bool:
    """Return True if ``user_role`` meets the ``required`` role.

    An admin satisfies a resident requirement; staff roles satisfy only
    themselves.
    """
    return required in effective_roles(user_role)


def satisfies_any(user_role: Role, required: tuple[Role, ...]) -> bool:
    """Return True if ``user_role`` satisfies at least one of ``required``."""
    return any(role_satisfies(user_role, role) for role in required)


def parse_role(value: str | None) -> Role | None:
    """Parse a raw claim/string into a :class:`Role`, or None if invalid."""
    if not value:
        return None
    normalized = value.upper()
    # The browser prototype used Technician and Serviceman as global roles.
    # They are worker specialisations in the membership-based model.
    normalized = {"TECHNICIAN": "WORKER", "SERVICEMAN": "WORKER"}.get(
        normalized, normalized
    )
    try:
        return Role(normalized)
    except ValueError:
        return None
