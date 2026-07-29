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
from app.core.web_session import CSRF_HEADER, cookie_name, csrf_token
from app.core.supabase_client import get_service_client, get_user_client
from app.domain.schemas import MembershipContext, Principal
from supabase import Client

# auto_error=False so we can raise our own AppError (consistent JSON shape).
_bearer = HTTPBearer(auto_error=False)


def _extract_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str:
    from app.core.exceptions import AuthenticationError

    if credentials is not None and credentials.credentials:
        return credentials.credentials
    if request.cookies.get(cookie_name("access")):
        return request.cookies[cookie_name("access")]
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
    if access and request.headers.get(CSRF_HEADER) != request.cookies.get(cookie_name("csrf")):
        raise AuthorizationError("CSRF token is required.", code="csrf_invalid")
    if access and request.cookies.get(cookie_name("csrf")) != csrf_token(access):
        raise AuthorizationError("CSRF token is invalid.", code="csrf_invalid")


def get_active_membership(
    principal: Principal = Depends(get_current_user),
) -> MembershipContext:
    """Resolve tenancy from Postgres, never from an identity JWT claim."""
    rows = (
        get_service_client().table("community_memberships")
        .select("id, community_id, role, department_id")
        .eq("profile_id", principal.user_id)
        .eq("status", "active")
        .is_("ended_at", None)
        .order("is_default_community", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise AuthorizationError(
            "An active community membership is required.",
            code="active_membership_required",
        )
    row = rows[0]
    return MembershipContext(
        id=row["id"],
        community_id=row["community_id"],
        role=str(row["role"]).lower(),
        department_id=row.get("department_id"),
    )


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
