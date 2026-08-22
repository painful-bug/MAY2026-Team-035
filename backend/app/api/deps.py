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
from app.core.supabase_client import get_service_client, get_user_client
from app.core.web_session import (
    CSRF_HEADER,
    PREAUTH_CSRF_COOKIE,
    RECOVERY_ACCESS_COOKIE,
    RECOVERY_CSRF_COOKIE,
    cookie_name,
    csrf_token,
)
from app.domain.schemas import MembershipContext, MembershipSet, Principal
from supabase import Client

# auto_error=False so we can raise our own AppError (consistent JSON shape).
_bearer = HTTPBearer(auto_error=False)


def _extract_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str:
    from app.core.exceptions import AuthenticationError

    if credentials is not None and credentials.credentials:
        return credentials.credentials
    access = (
        request.cookies.get(cookie_name("access"))
        or request.cookies.get("__Host-hb_access")
        or request.cookies.get("hb_access")
    )
    if access:
        return access
    # The access and CSRF cookies expire before the refresh cookie. Tell the
    # browser this specific 401 is refreshable without exposing the HttpOnly
    # refresh token itself. A genuinely signed-out request keeps the ordinary
    # authentication_error code and must not trigger a pointless refresh.
    if request.cookies.get(cookie_name("refresh")):
        raise AuthenticationError("Session has expired.", code="token_expired")
    raise AuthenticationError("Missing bearer token.")


def _verified_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[str, Principal]:
    """Decode one request token once across all authentication dependencies."""
    cached = getattr(request.state, "homebandhu_auth", None)
    if cached is not None:
        return cached
    token = _extract_token(request, credentials)
    resolved = (token, decode_token(token))
    request.state.homebandhu_auth = resolved
    return resolved


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Resolve and verify the caller from the ``Authorization`` header."""
    return _verified_request(request, credentials)[1]


def get_request_client(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Client:
    """Return a Supabase client scoped to the caller's token (RLS enforced).

    Use this for reading/writing domain data on behalf of the signed-in user so
    Postgres Row-Level Security authorizes each query against their role.
    """
    token, _ = _verified_request(request, credentials)
    cached = getattr(request.state, "homebandhu_user_client", None)
    if cached is None:
        cached = get_user_client(token)
        request.state.homebandhu_user_client = cached
    return cached


def get_request_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Return a verified caller token without exposing it to handlers' clients."""
    return _verified_request(request, credentials)[0]


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


def _has_active_residency(membership_id: str) -> bool:
    """Does this membership currently live in a unit?

    One row is the whole question, so the read stops at one. ``ended_at is
    null`` rather than a date comparison because that is the predicate the
    partial unique index ``residencies_active_member_unit`` is built on
    (``0001_baseline.sql:53``) and the one the session layer already uses
    (``app/services/auth_service.py:463-471``) -- two places asking "is this
    person resident here" must not be able to disagree.

    Service-role, deliberately. The caller is asking a question *about
    themselves* and the answer decides whether their own request proceeds; an
    RLS-scoped read that returned nothing because a policy hid the row would
    read here as "you do not live anywhere", which is the wrong 403 for the
    wrong reason.
    """
    rows = (
        get_service_client().table("unit_residencies")
        .select("id")
        .eq("membership_id", membership_id)
        .is_("ended_at", None)
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def require_resident_capability() -> Callable[[MembershipContext], MembershipContext]:
    """Admit anyone who actually lives here, whatever their role says.

    **Resident-ness is a ``unit_residencies`` lookup, never a role implication.**
    One ``community_memberships`` row exists per person per community
    (``memberships_active_person_community``, ``0001_baseline.sql:45``), so the
    admin who owns flat B-402 has exactly one membership and its role is
    ``admin``. ``require_membership_role("resident")`` refused them the resident
    verbs on their own home -- cancelling work in their own flat, confirming a
    resolution they are the only witness to, answering a visit proposed to
    them -- which is not a policy anybody chose; it is the role column standing
    in for a fact it never recorded.

    The session layer has agreed with this since Google sign-in landed: it grants
    an admin the ``resident`` capability outright
    (``app/services/auth_service.py:474-476``), so the portal has been offering
    these buttons to a caller the per-request layer then refused. This guard is
    that agreement moved down one layer -- and made stricter, because it asks
    about the residency rather than assuming it from the role.

    Cost is one indexed read, and only for callers who are not already
    ``resident`` -- the overwhelmingly common case does no query at all.

    The refusal is byte-identical to ``require_membership_role``'s: same message,
    same ``community_role_required`` code. Widening who passes is not a wire
    change, and a client that special-cases the resident 403 must keep working.

    Build the closure once at import time; FastAPI caches dependencies by
    identity, and a fresh closure per route would resolve the same guard twice on
    a router that declares it in both places.
    """

    def _guard(
        membership: MembershipContext = Depends(get_active_membership),
    ) -> MembershipContext:
        if membership.role == "resident" or _has_active_residency(membership.id):
            return membership
        raise AuthorizationError(
            "You do not have permission for this community action.",
            code="community_role_required",
        )

    return _guard
