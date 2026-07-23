"""Shared FastAPI dependencies for authentication and authorization.

These wrap the framework-agnostic security helpers so routers can declare their
access requirements declaratively::

    @router.post(..., dependencies=[Depends(require_role(Role.ADMIN))])

or receive the caller and an RLS-scoped Supabase client directly::

    async def handler(principal: Principal = Depends(get_current_user)): ...
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthorizationError
from app.core.security import decode_token
from app.core.supabase_client import get_user_client
from app.domain.roles import Role, satisfies_any
from app.domain.schemas import Principal
from supabase import Client

# auto_error=False so we can raise our own AppError (consistent JSON shape).
_bearer = HTTPBearer(auto_error=False)


def _extract_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    from app.core.exceptions import AuthenticationError

    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token.")
    return credentials.credentials


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Resolve and verify the caller from the ``Authorization`` header."""
    return decode_token(_extract_token(credentials))


def get_request_client(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Client:
    """Return a Supabase client scoped to the caller's token (RLS enforced).

    Use this for reading/writing domain data on behalf of the signed-in user so
    Postgres Row-Level Security authorizes each query against their role.
    """
    token = _extract_token(credentials)
    # Verify before trusting the token to scope a client.
    decode_token(token)
    return get_user_client(token)


def require_role(*roles: Role) -> Callable[[Principal], Principal]:
    """Build a dependency that admits only callers satisfying one of ``roles``.

    Role implication applies (see :func:`app.domain.roles.role_satisfies`), so
    ``require_role(Role.RESIDENT)`` also admits an ``ADMIN``.
    """

    def _guard(principal: Principal = Depends(get_current_user)) -> Principal:
        if not satisfies_any(principal.role, roles):
            allowed = ", ".join(role.value for role in roles)
            raise AuthorizationError(
                f"Requires one of: {allowed}.", code="insufficient_role"
            )
        return principal

    return _guard
