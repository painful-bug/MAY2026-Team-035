"""Provider-neutral Supabase authentication and membership session context."""

from __future__ import annotations

from contextlib import suppress
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


def confirmation_redirect_url() -> str:
    """Where a confirmation link must land: the page that spends the token hash.

    The Supabase email template has to point here *carrying* ``token_hash``; see
    ``docs/SUPABASE_AUTH_SETUP.md``.  A template left on GoTrue's default
    ``{{ .ConfirmationURL }}`` redirects to this page with no hash to spend,
    which is what leaves the confirm button with nothing to do.
    """
    from app.config import get_settings

    return f"{get_settings().frontend_base_url.rstrip('/')}/auth/confirm-email"


def _unconfirmed_email() -> AuthenticationError:
    """The one refusal for an address nobody has proven they own.

    Naming the reason does not enumerate accounts.  This branch is only reachable
    by someone who already supplied the correct password, so it tells them
    nothing about the account that they did not already know -- and staying vague
    here would strand a real user with no idea what to do next.
    """
    return AuthenticationError(
        "Confirm your email address before signing in. "
        "Check your inbox for the confirmation link.",
        code="email_not_confirmed",
    )


def _discard_session(client: Client) -> None:
    """Revoke whatever session ``client`` is holding, best effort.

    Used when a sign-in is refused *after* GoTrue has already minted tokens.
    A failure to clean up must never mask the refusal that prompted it.
    """
    with suppress(Exception):
        client.auth.sign_out({"scope": "local"})


def sign_up_with_password(*, email: str, password: str, full_name: str, captcha_token: str | None) -> None:
    """Create an email identity. The caller intentionally gets no existence signal."""
    options: dict[str, object] = {
        "data": {"full_name": full_name},
        "email_redirect_to": confirmation_redirect_url(),
    }
    if captcha_token:
        options["captcha_token"] = captcha_token
    try:
        get_auth_client().auth.sign_up({"email": email, "password": password, "options": options})
    except Exception as exc:  # GoTrue deliberately obscures duplicate sign-ups.
        raise AuthenticationError("Account creation could not be started.", code="password_signup_failed") from exc


def resend_confirmation_email(*, email: str, captcha_token: str | None) -> None:
    """Send the sign-up confirmation link again, revealing nothing about the address.

    The recovery path for a confirmation link that expired, never arrived, or was
    spent by a mail scanner.  Errors are swallowed for the same reason
    :func:`send_password_recovery` swallows them: the caller gets one fixed
    answer either way, so this cannot be used to discover who has registered.
    """
    options: dict[str, object] = {"email_redirect_to": confirmation_redirect_url()}
    if captcha_token:
        options["captcha_token"] = captcha_token
    with suppress(Exception):
        get_auth_client().auth.resend(
            {"type": "signup", "email": email, "options": options}
        )


def sign_in_with_password(*, email: str, password: str, captcha_token: str | None) -> SupabaseSession:
    """Exchange credentials for a session, but only for a confirmed email address.

    Two different things stand between a password and a session, and both end up
    as ``email_not_confirmed`` here.  With Supabase's **Confirm email** setting
    on, GoTrue refuses the grant itself.  With it off, GoTrue returns a perfectly
    valid session for an address nobody has ever proven they own, and this
    function is the last thing that can say no -- which is the state that
    produced the reported bypass.  Checking both means the answer stops depending
    on a dashboard toggle nobody in the codebase can see.
    """
    options: dict[str, object] = {}
    if captcha_token:
        options["captcha_token"] = captcha_token
    client = get_auth_client()
    try:
        result = client.auth.sign_in_with_password(
            {"email": email, "password": password, "options": options}
        )
    except Exception as exc:
        if getattr(exc, "code", None) == "email_not_confirmed":
            raise _unconfirmed_email() from exc
        raise AuthenticationError("Invalid email or password.", code="invalid_credentials") from exc
    if result.session is None:
        raise AuthenticationError("Invalid email or password.", code="invalid_credentials")
    if not getattr(result.user, "email_confirmed_at", None):
        # Tokens exist by the time we get to object to them, so spend them here:
        # refusing a sign-in must not leave a live refresh token behind for an
        # account that was never verified. A missing user object fails closed --
        # unproven is unproven.
        _discard_session(client)
        raise _unconfirmed_email()
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


def _portal_for(membership: dict, role: str) -> str:
    """Which portal this membership lands in.

    Two of the five portals are the membership role spelled straight through.
    `security-manager` is the one that is not, and it has two spellings because
    **rank and role are separate axes** (D3):

    * a `manager` membership whose department is a security department. Nothing
      writes a `manager` membership today -- `hire_service_applicant`
      (`0035:918`) mints `security` or `worker` and there is no other minter --
      so this branch is currently unreachable. It stays because `manager` is a
      real `membership_role` value and an admin surface may yet write one, and
      because a *plumbing* manager must keep landing in their own portal: the
      `departments.kind` question is the whole point of the branch.
    * a `security` membership whose active roster row ranks `manager` or
      `supervisor`. This is the spelling real people have, and it is not a new
      policy -- it is `gate_admin_community_for` (`0040:589`), the live guard on
      posts CRUD and shift scheduling, asked from the other side. A portal that
      disagreed with that predicate could only be wrong in one of two ways:
      unreachable, which is what it was, or full of screens whose writes 403.

    `supervisor` is included for the same reason: `gate_admin_community_for`
    grants supervisors the manager's writes, so routing them to the guard portal
    would hand somebody permissions with no screen to spend them on.

    One extra read, and only on the path that needs it.
    """
    if role == "manager" and membership.get("department_id"):
        kind = (
            get_service_client().table("departments")
            .select("kind")
            .eq("id", membership["department_id"])
            .limit(1)
            .execute().data
            or []
        )
        if kind and str(kind[0].get("kind") or "") == "security":
            return "security-manager"
        return role
    if role == "security":
        senior = (
            get_service_client().table("staff_assignments")
            .select("id")
            .eq("membership_id", membership["id"])
            .eq("status", "active")
            .in_("rank", ["manager", "supervisor"])
            .limit(1)
            .execute().data
            or []
        )
        if senior:
            return "security-manager"
    return role


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
        # A member of nothing is usually somebody about to register a society --
        # but it is also a service person who has registered and not yet been
        # hired anywhere, and they have a portal of their own. Without this the
        # second sign-in lands them on the account page with no route back to
        # /worker, which is the screen holding their applications.
        #
        # One extra read, and only on the path that already has no membership to
        # read anything else from.
        provider = (
            get_service_client().table("service_providers")
            .select("id")
            .eq("profile_id", principal.user_id)
            .limit(1)
            .execute().data
            or []
        )
        if provider:
            return SessionContext(
                identity=profile, portal="worker", capabilities=["worker"]
            )
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
    portal = _portal_for(membership, role)
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
