"""Shared FastAPI dependencies for authentication and authorization.

These wrap the framework-agnostic security helpers so routers can declare their
identity and active-membership requirements declaratively::

    async def handler(principal: Principal = Depends(get_current_user)): ...
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthorizationError
from app.core.security import decode_token
from app.core.web_session import (
    CSRF_HEADER,
    PREAUTH_CSRF_COOKIE,
    RECOVERY_ACCESS_COOKIE,
    RECOVERY_CSRF_COOKIE,
    cookie_name,
    csrf_token,
)
from app.core.supabase_client import get_service_client, get_user_client
from app.domain.schemas import MembershipContext, MembershipSet, Principal
from supabase import Client

# auto_error=False so we can raise our own AppError (consistent JSON shape).
_bearer = HTTPBearer(auto_error=False)


def _extract_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str:
    from app.core.exceptions import AuthenticationError

    if credentials is not None and credentials.credentials:
        return credentials.credentials
    if request.cookies.get(cookie_name("access")) or request.cookies.get("__Host-hb_access") or request.cookies.get("hb_access"):
        return request.cookies.get(cookie_name("access")) or request.cookies.get("__Host-hb_access") or request.cookies.get("hb_access")
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token.")
    return credentials.credentials


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Resolve and verify the caller from the ``Authorization`` header."""
    return decode_token(_extract_token(request, credentials))


def get_request_client(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Client:
    """Return a Supabase client scoped to the caller's token (RLS enforced).

    Use this for reading/writing domain data on behalf of the signed-in user so
    Postgres Row-Level Security authorizes each query against their role.
    """
    token = _extract_token(request, credentials)
    # Verify before trusting the token to scope a client.
    decode_token(token)
    return get_user_client(token)


def get_request_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Return a verified caller token without exposing it to handlers' clients."""
    token = _extract_token(request, credentials)
    decode_token(token)
    return token


def require_csrf(request: Request) -> None:
    """Enforce same-origin, session-bound CSRF protection on unsafe browser calls."""
    from app.config import get_settings
    from app.core.exceptions import AuthorizationError

    origin = request.headers.get("origin") or request.headers.get("referer", "").rstrip("/")
    expected_origin = get_settings().frontend_base_url.rstrip("/")
    if origin != expected_origin:
        raise AuthorizationError("Invalid request origin.", code="csrf_origin_invalid")
    access = request.cookies.get(cookie_name("access"))
    recovery_access = request.cookies.get(RECOVERY_ACCESS_COOKIE)
    csrf_cookie = (
        request.cookies.get(cookie_name("csrf")) if access
        else request.cookies.get(RECOVERY_CSRF_COOKIE) if recovery_access
        else request.cookies.get(PREAUTH_CSRF_COOKIE)
    )
    if not csrf_cookie or request.headers.get(CSRF_HEADER) != csrf_cookie:
        raise AuthorizationError("CSRF token is required.", code="csrf_invalid")
    if access and csrf_cookie != csrf_token(access):
        raise AuthorizationError("CSRF token is invalid.", code="csrf_invalid")
    if recovery_access and csrf_cookie != csrf_token(recovery_access):
        raise AuthorizationError("CSRF token is invalid.", code="csrf_invalid")


def get_membership_set(
    principal: Principal = Depends(get_current_user),
) -> MembershipSet:
    """Resolve every active membership from Postgres, default first.

    This is the query ``get_active_membership`` used to run with ``limit 1``.
    Dropping the limit costs nothing -- the caller has one row in almost every
    case -- and it means a service person's cross-community dashboard needs one
    request-scoped read rather than a second resolver of its own.
    """
    rows = (
        get_service_client().table("community_memberships")
        .select("id, community_id, role, department_id")
        .eq("profile_id", principal.user_id)
        .eq("status", "active")
        .is_("ended_at", None)
        .order("is_default_community", desc=True)
        .order("created_at")
        .execute()
        .data
        or []
    )
    if not rows:
        raise AuthorizationError(
            "An active community membership is required.",
            code="active_membership_required",
        )
    return MembershipSet(
        memberships=[
            MembershipContext(
                id=row["id"],
                community_id=row["community_id"],
                role=str(row["role"]).lower(),
                department_id=row.get("department_id"),
            )
            for row in rows
        ]
    )


def get_active_membership(
    principal: Principal = Depends(get_current_user),
) -> MembershipContext:
    """Resolve tenancy from Postgres, never from an identity JWT claim.

    The default membership, which is what every handler written before service
    personnel existed already meant by "the caller's community".

    **It keeps taking a ``Principal``, and that is not incidental.** Declaring
    ``Depends(get_membership_set)`` here would read identically to FastAPI and
    break every direct call -- ``tests/api/test_session_flow.py`` calls this
    function positionally to prove the role comes from ``community_memberships``
    rather than from a token claim, and a handful of services do the same. The
    seam this feature needed was additive; a changed parameter type is not
    additive, it just looks like it from inside the framework.

    The cost is that a handler depending on *both* this and
    ``get_membership_set`` would read twice. None does: a handler wants either
    one community or all of them.
    """
    return get_membership_set(principal).default


def require_community_role(
    community_id: str, memberships: MembershipSet, *roles: str
) -> MembershipContext:
    """The caller's membership in one named community, or 403.

    For handlers whose community comes from the *resource* -- a job, an
    application, a department -- rather than from whichever membership happens
    to be the caller's default. Never reads a community id from a request body:
    see ``docs/design/ADMIN_DASHBOARD_DESIGN.md`` 10.
    """
    membership = memberships.for_community(community_id)
    allowed = {role.lower() for role in roles}
    if membership is None or (allowed and membership.role not in allowed):
        raise AuthorizationError(
            "You do not have permission for this community action.",
            code="community_role_required",
        )
    return membership


def require_membership_role(*roles: str) -> Callable[[MembershipContext], MembershipContext]:
    """Check a role on the resolved active membership, not a JWT."""
    allowed = {role.lower() for role in roles}

    def _guard(
        membership: MembershipContext = Depends(get_active_membership),
    ) -> MembershipContext:
        if membership.role not in allowed:
            raise AuthorizationError(
                "You do not have permission for this community action.",
                code="community_role_required",
            )
        return membership

    return _guard

