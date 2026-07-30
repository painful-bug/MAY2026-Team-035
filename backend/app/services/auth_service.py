"""Backend-owned Google OAuth, cookie refresh, and browser session context."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.supabase_client import (
    get_anon_client,
    get_service_client,
    get_user_client,
)
from app.core.web_session import pkce_challenge, random_urlsafe
from app.domain.schemas import MembershipContext, Principal, SessionContext
from app.repositories import profiles_repository
from supabase import Client


@dataclass(frozen=True)
class SupabaseSession:
    access_token: str
    refresh_token: str
    expires_in: int | None


def safe_return_path(value: str | None) -> str:
    path = value or "/auth/callback"
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise ValidationError("Invalid return path.", code="invalid_return_path")
    return path


def start_google_oauth() -> tuple[str, dict[str, str]]:
    """Build the Google/Supabase authorize redirect and its PKCE transaction.

    GoTrue generates the provider ``state`` value for this endpoint. Supplying
    our own opaque state causes GoTrue to reject the provider callback as
    ``bad_oauth_state``. The signed, HTTP-only transaction cookie binds this
    browser to its PKCE verifier instead.
    """
    from app.config import get_settings

    settings = get_settings()
    verifier = random_urlsafe(64)
    callback = f"{settings.backend_base_url.rstrip('/')}/api/v1/auth/google/callback"
    query = urlencode(
        {
            "provider": "google",
            "redirect_to": callback,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "s256",
        }
    )
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/authorize?{query}"
    return url, {"verifier": verifier}


def exchange_google_code(code: str, verifier: str) -> SupabaseSession:
    try:
        result = get_anon_client().auth.exchange_code_for_session(
            {"auth_code": code, "code_verifier": verifier}
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Google sign-in could not be completed.") from exc
    if result.session is None:
        raise AuthenticationError("Google sign-in could not be completed.")
    return _session_from_result(result.session)


def refresh_session(refresh_token: str) -> SupabaseSession:
    try:
        result = get_anon_client().auth.refresh_session(refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Session refresh failed.") from exc
    if result.session is None:
        raise AuthenticationError("Session refresh failed.")
    return _session_from_result(result.session)


def revoke_session(access_token: str) -> None:
    try:
        get_user_client(access_token).auth.sign_out()
    except Exception:
        # Cookie clearing remains important even if the provider already
        # invalidated the session or is temporarily unavailable.
        return


def get_session_context(
    client: Client,
    principal: Principal,
    access_token: str,
) -> SessionContext:
    """Resolve context and materialize a harmless identity profile on first login."""
    try:
        profile = profiles_repository.get_profile(client, principal.user_id)
    except NotFoundError:
        identity = google_identity(access_token)
        profile = profiles_repository.upsert_profile(
            get_service_client(), user_id=identity.user_id, full_name=None,
            phone=None, email=identity.email,
        )
    rows = (
        get_service_client().table("community_memberships")
        .select("id, community_id, role, department_id, is_default_community")
        .eq("profile_id", principal.user_id)
        .eq("status", "active")
        .is_("ended_at", None)
        .order("is_default_community", desc=True)
        .limit(1)
        .execute().data
        or []
    )
    if not rows:
        return SessionContext(identity=profile, onboarding_eligible=True)
    membership = rows[0]
    residency = (
        get_service_client().table("unit_residencies")
        .select("unit_id")
        .eq("membership_id", membership["id"])
        .is_("ended_at", None)
        .limit(1)
        .execute().data
        or []
    )
    role = str(membership["role"]).lower()
    portal = (
        "security-manager"
        if role == "manager" and membership.get("department_id")
        else role
    )
    capabilities = [role]
    if role == "admin":
        capabilities.append("resident")
    return SessionContext(
        identity=profile,
        membership=MembershipContext(
            id=membership["id"], community_id=membership["community_id"], role=role,
            department_id=membership.get("department_id"),
            unit_id=residency[0].get("unit_id") if residency else None,
        ),
        portal=portal,
        capabilities=capabilities,
    )


def google_identity(access_token: str) -> Principal:
    """Ask GoTrue for current identity before an email-bound sensitive claim."""
    try:
        result = get_anon_client().auth.get_user(access_token)
        user = result.user
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Could not verify the Google identity.") from exc
    if user is None or not user.email or not getattr(user, "email_confirmed_at", None):
        raise AuthenticationError(
            "A verified Google email is required.", code="email_not_verified"
        )
    return Principal(
        user_id=user.id,
        email=user.email,
        phone=user.phone,
        email_verified=True,
    )


def _session_from_result(session: object) -> SupabaseSession:
    access = getattr(session, "access_token", None)
    refresh = getattr(session, "refresh_token", None)
    if not access or not refresh:
        raise AuthenticationError("Google sign-in did not create a session.")
    return SupabaseSession(access, refresh, getattr(session, "expires_in", None))
