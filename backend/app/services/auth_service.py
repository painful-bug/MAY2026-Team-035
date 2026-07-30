"""Provider-neutral Supabase authentication and membership session context."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.supabase_client import (
    get_auth_client,
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


def start_oauth(provider: str) -> tuple[str, dict[str, str]]:
    """Start a configured redirect provider without leaking provider details upstream."""
    if provider != "google":
        raise ValidationError("Unsupported authentication provider.", code="provider_unsupported")
    return start_google_oauth()


def exchange_google_code(code: str, verifier: str) -> SupabaseSession:
    try:
        result = get_auth_client().auth.exchange_code_for_session(
            {"auth_code": code, "code_verifier": verifier}
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Google sign-in could not be completed.") from exc
    if result.session is None:
        raise AuthenticationError("Google sign-in could not be completed.")
    return _session_from_result(result.session)


def refresh_session(refresh_token: str) -> SupabaseSession:
    try:
        result = get_auth_client().auth.refresh_session(refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Session refresh failed.") from exc
    if result.session is None:
        raise AuthenticationError("Session refresh failed.")
    return _session_from_result(result.session)


def sign_up_with_password(*, email: str, password: str, full_name: str, captcha_token: str | None) -> None:
    """Create an email identity. The caller intentionally gets no existence signal."""
    from app.config import get_settings

    options: dict[str, object] = {
        "data": {"full_name": full_name},
        "email_redirect_to": f"{get_settings().frontend_base_url.rstrip('/')}/auth/confirm-email",
    }
    if captcha_token:
        options["captcha_token"] = captcha_token
    try:
        get_auth_client().auth.sign_up({"email": email, "password": password, "options": options})
    except Exception as exc:  # GoTrue deliberately obscures duplicate sign-ups.
        raise AuthenticationError("Account creation could not be started.", code="password_signup_failed") from exc


def sign_in_with_password(*, email: str, password: str, captcha_token: str | None) -> SupabaseSession:
    options: dict[str, object] = {}
    if captcha_token:
        options["captcha_token"] = captcha_token
    try:
        result = get_auth_client().auth.sign_in_with_password(
            {"email": email, "password": password, "options": options}
        )
    except Exception as exc:
        raise AuthenticationError("Invalid email or password.", code="invalid_credentials") from exc
    if result.session is None:
        raise AuthenticationError("Invalid email or password.", code="invalid_credentials")
    return _session_from_result(result.session)


def verify_email_token(token_hash: str, verification_type: str = "email") -> SupabaseSession:
    try:
        result = get_auth_client().auth.verify_otp({"token_hash": token_hash, "type": verification_type})
    except Exception as exc:
        raise AuthenticationError("This verification link is invalid or has expired.", code="verification_invalid") from exc
    if result.session is None:
        raise AuthenticationError("This verification link is invalid or has expired.", code="verification_invalid")
    return _session_from_result(result.session)


def send_password_recovery(*, email: str, captcha_token: str | None) -> None:
    from app.config import get_settings

    options: dict[str, object] = {"redirect_to": f"{get_settings().frontend_base_url.rstrip('/')}/auth/reset-password"}
    if captcha_token:
        options["captcha_token"] = captcha_token
    try:
        get_auth_client().auth.reset_password_for_email(email, options)
    except Exception:
        # Keep a generic response: reset flows must not enumerate accounts.
        return


def verify_recovery_token(token_hash: str) -> SupabaseSession:
    try:
        result = get_auth_client().auth.verify_otp({"token_hash": token_hash, "type": "recovery"})
    except Exception as exc:
        raise AuthenticationError("This recovery link is invalid or has expired.", code="recovery_invalid") from exc
    if result.session is None:
        raise AuthenticationError("This recovery link is invalid or has expired.", code="recovery_invalid")
    return _session_from_result(result.session)


def complete_password_recovery(*, access_token: str, refresh_token: str, password: str) -> None:
    client = get_auth_client()
    try:
        client.auth.set_session(access_token, refresh_token)
        client.auth.update_user({"password": password})
        client.auth.sign_out({"scope": "local"})
    except Exception as exc:
        raise AuthenticationError("Password could not be updated. Request a new recovery link.", code="recovery_update_failed") from exc


def revoke_session(*, access_token: str, refresh_token: str) -> None:
    """Best-effort local revocation; cookie clearing remains authoritative at the BFF."""
    client = get_auth_client()
    client.auth.set_session(access_token, refresh_token)
    client.auth.sign_out({"scope": "local"})


def get_session_context(
    client: Client,
    principal: Principal,
    access_token: str,
) -> SessionContext:
    """Resolve context and materialize a harmless identity profile on first login."""
    try:
        profile = profiles_repository.get_profile(client, principal.user_id)
    except NotFoundError:
        identity = verified_identity(access_token)
        profile = profiles_repository.upsert_profile(
            get_service_client(), user_id=identity.user_id, full_name=identity.full_name,
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


def verified_identity(access_token: str) -> Principal:
    """Ask GoTrue for the authenticated identity; provider never determines authorization."""
    try:
        result = get_anon_client().auth.get_user(access_token)
        user = result.user
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError("Could not verify the authenticated identity.") from exc
    if user is None or not user.email:
        raise AuthenticationError(
            "Your sign-in account must provide an email address.",
            code="identity_email_missing",
        )
    metadata = getattr(user, "user_metadata", None) or {}
    full_name = metadata.get("full_name") if isinstance(metadata, dict) else None
    return Principal(
        user_id=user.id,
        email=user.email,
        phone=user.phone,
        email_verified=bool(getattr(user, "email_confirmed_at", None)),
        full_name=full_name if isinstance(full_name, str) else None,
    )


def _session_from_result(session: object) -> SupabaseSession:
    access = getattr(session, "access_token", None)
    refresh = getattr(session, "refresh_token", None)
    if not access or not refresh:
        raise AuthenticationError("Authentication did not create a session.")
    return SupabaseSession(access, refresh, getattr(session, "expires_in", None))
