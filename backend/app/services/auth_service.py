"""Provider-neutral Supabase authentication and membership session context."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from time import perf_counter
from urllib.parse import urlencode

from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.supabase_client import (
    get_anon_client,
    get_auth_client,
    get_service_client,
)
from app.core.web_session import pkce_challenge, random_urlsafe
from app.domain.schemas import (
    MembershipContext,
    MembershipUnit,
    Principal,
    Profile,
    SessionContext,
)
from app.repositories import profiles_repository
from supabase import Client

_logger = get_logger(__name__)


@contextmanager
def _session_step(name: str) -> Iterator[None]:
    """Log one privacy-safe session substep without identity or tenant data."""
    started = perf_counter()
    try:
        yield
    finally:
        _logger.info(
            "auth_session_step step=%s duration_ms=%.2f",
            name,
            (perf_counter() - started) * 1000,
        )


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


def confirmation_redirect_url(intent: str | None = None) -> str:
    """Where a confirmation link must land: the page that spends the token hash.

    The Supabase email template has to point here *carrying* ``token_hash``; see
    ``docs/SUPABASE_AUTH_SETUP.md``.  A template left on GoTrue's default
    ``{{ .ConfirmationURL }}`` redirects to this page with no hash to spend,
    which is what leaves the confirm button with nothing to do.

    **The intent is appended as a query parameter, not concatenated with a
    literal ``?``.** A base URL that already carries a query -- which is what a
    ``frontend_base_url`` with one, or any future caller passing a richer
    landing page, would produce -- would otherwise yield ``…?a=b?intent=…``.
    That is not a URL with two parameters: ``URLSearchParams`` reads the whole
    tail as one value, so the *other* parameter silently disappears. The page
    this lands on parses ``token_hash`` out of exactly that query string, so
    the failure mode is a confirmation link that cannot be confirmed.
    """
    from app.config import get_settings

    base = f"{get_settings().frontend_base_url.rstrip('/')}/auth/confirm-email"
    if intent != "service-provider":
        return base
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urlencode({'intent': intent})}"


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


def sign_up_with_password(*, email: str, password: str, full_name: str, captcha_token: str | None, intent: str | None = None) -> None:
    """Create an email identity. The caller intentionally gets no existence signal."""
    from app.config import get_settings

    options: dict[str, object] = {"data": {"full_name": full_name}}
    if get_settings().auth_email_confirmation_required:
        options["email_redirect_to"] = confirmation_redirect_url(intent)
    if captcha_token:
        options["captcha_token"] = captcha_token
    try:
        get_auth_client().auth.sign_up({"email": email, "password": password, "options": options})
    except Exception as exc:  # GoTrue deliberately obscures duplicate sign-ups.
        raise AuthenticationError("Account creation could not be started.", code="password_signup_failed") from exc


def resend_confirmation_email(*, email: str, captcha_token: str | None, intent: str | None = None) -> None:
    """Send the sign-up confirmation link again, revealing nothing about the address.

    The recovery path for a confirmation link that expired, never arrived, or was
    spent by a mail scanner.  Errors are swallowed for the same reason
    :func:`send_password_recovery` swallows them: the caller gets one fixed
    answer either way, so this cannot be used to discover who has registered.
    """
    options: dict[str, object] = {"email_redirect_to": confirmation_redirect_url(intent)}
    if captcha_token:
        options["captcha_token"] = captcha_token
    with suppress(Exception):
        get_auth_client().auth.resend(
            {"type": "signup", "email": email, "options": options}
        )


def sign_in_with_password(*, email: str, password: str, captcha_token: str | None) -> SupabaseSession:
    """Exchange credentials, enforcing the application confirmation setting."""
    from app.config import get_settings
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
    if get_settings().auth_email_confirmation_required and not getattr(
        result.user, "email_confirmed_at", None
    ):
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
        if "departments" in membership:
            department = membership.get("departments")
            if isinstance(department, list):
                department = department[0] if department else None
            if isinstance(department, dict) and department.get("kind") == "security":
                return "security-manager"
            return role
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
        if "staff_assignments" in membership:
            assignments = membership.get("staff_assignments") or []
            if isinstance(assignments, dict):
                assignments = [assignments]
            senior = any(
                row.get("status") == "active"
                and row.get("rank") in {"manager", "supervisor"}
                for row in assignments
                if isinstance(row, dict)
            )
            return "security-manager" if senior else role
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


def get_session_memberships(profile_id: str) -> list[dict]:
    """The caller's default membership, or nothing.

    Extracted so the claim below can re-read after writing one, without the two
    reads drifting into asking slightly different questions.
    """
    with _session_step("membership"):
        return (
            get_service_client().table("community_memberships")
            .select(
                "id,community_id,role,department_id,is_default_community,"
                "unit_residencies!unit_residencies_membership_id_fkey("
                "unit_id,ended_at,units(unit_code,unit_type,"
                "buildings(name,building_type))),"
                "departments!community_memberships_department_id_fkey(kind),"
                "staff_assignments!staff_assignments_membership_id_fkey("
                "id,rank,status)"
            )
            .eq("profile_id", profile_id)
            .eq("status", "active")
            .is_("ended_at", None)
            .order("is_default_community", desc=True)
            .limit(1)
            .execute().data
            or []
        )


def get_session_profile(
    client: Client,
    principal: Principal,
    access_token: str,
) -> Profile:
    """Read or materialize the identity profile used by the session response."""
    with _session_step("profile"):
        try:
            return profiles_repository.get_profile(client, principal.user_id)
        except NotFoundError:
            identity = verified_identity(access_token)
            return profiles_repository.upsert_profile(
                get_service_client(),
                user_id=identity.user_id,
                full_name=identity.full_name,
                phone=None,
                email=identity.email,
            )


def _claim_staff_invitations(
    profile: Profile, principal: Principal, access_token: str
) -> bool:
    """Admit a manager or supervisor whose invitation names this email.

    Returns whether anything was claimed, so the caller knows to re-read.

    **`profile` is the :class:`~app.domain.schemas.Profile` model, not a table
    row.** The only caller is `get_session_context`, and both branches it can
    arrive from -- `profiles_repository.get_profile` and
    `profiles_repository.upsert_profile` -- return the model; the repository's
    `_to_profile` is what maps the `profiles.display_email` column onto
    `Profile.email`, so there is no second spelling to fall back to here. This
    parameter was annotated `dict` and read with `.get()` while every caller
    passed the model, which raised `AttributeError` before the `try` below and
    so failed the whole session read rather than the claim.

    **The email is taken from the verified identity, never from the profile row
    alone.** `profiles.display_email` is written by `upsert_profile` from the
    same GoTrue identity, so on the sign-in path the two agree -- but the
    profile is an ordinary table, and treating a table as the authority on who
    somebody is would make a row a credential. `verified_identity` asks GoTrue.

    A failure here is swallowed. Claiming is an *enhancement* to a session that
    is otherwise valid: somebody who has been provisioned and hits a database
    error should land on the account page and be admitted on their next
    sign-in, not be refused a session they are entitled to.
    """
    email = profile.email
    try:
        email = verified_identity(access_token).email or email
    except Exception:  # noqa: BLE001 - see the docstring: never fail the session
        pass
    if not email:
        return False
    try:
        claimed = get_service_client().rpc(
            "claim_staff_invitations",
            {"p_profile_id": principal.user_id, "p_email": email},
        ).execute().data
    except Exception:  # noqa: BLE001
        return False
    if isinstance(claimed, dict):
        return True
    return bool(claimed)


def _unit_from_residency(residency: dict | None) -> MembershipUnit | None:
    """Map the unit embedded in the existing residency read.

    The residency is already authoritative for both ``unit_id`` and the admin's
    resident capability. Embedding its unit avoids a second serial PostgREST
    request just to render the header. Standalone homes have no building row.
    """
    unit = (residency or {}).get("units")
    if isinstance(unit, list):
        unit = unit[0] if unit else None
    if not isinstance(unit, dict) or not unit.get("unit_code"):
        return None
    building = unit.get("buildings")
    if isinstance(building, list):
        building = building[0] if building else None
    building = building if isinstance(building, dict) else {}
    return MembershipUnit(
        unit_code=unit["unit_code"],
        unit_type=unit.get("unit_type"),
        building_name=building.get("name"),
        building_type=building.get("building_type"),
    )


def _active_residency(membership: dict) -> dict | None:
    """Return the active residency embedded in the membership projection."""
    rows = membership.get("unit_residencies") or []
    if isinstance(rows, dict):
        rows = [rows]
    return next(
        (
            row
            for row in rows
            if isinstance(row, dict) and row.get("ended_at") is None
        ),
        None,
    )


def get_session_context(
    client: Client,
    principal: Principal,
    access_token: str,
    prefetched: tuple[Profile, list[dict]] | None = None,
) -> SessionContext:
    """Resolve context and materialize a harmless identity profile on first login."""
    if prefetched is None:
        profile = get_session_profile(client, principal, access_token)
        rows = get_session_memberships(principal.user_id)
    else:
        profile, rows = prefetched
    # Leadership does not register (0049). An admin creating a manager has no
    # profile to attach a membership to -- that person has never signed in -- so
    # the provisioning waits on their email and is claimed here.
    #
    # **The claim runs on every session read, not only on the membership-less
    # one.** It sat inside `if not rows:` until 2026-08-21, and that guard was a
    # gap rather than an optimization: a person who already belongs to a
    # community -- a resident, a worker, a supervisor of one department invited
    # to be manager of another -- never reached the claim at all. Their pending
    # invitation was neither applied nor refused; it simply waited, invisibly,
    # while the department that sent it saw `pending` forever. Since
    # `20260821140000`/`20260821170000` the refusal half matters just as much:
    # an invitation that *cannot* be applied is marked `blocked` and both sides
    # are told, and that announcement was reachable only by people with no
    # membership. Neither half is a thing to make conditional on the reader.
    # (The 2026-08-23 merge with main's bounded session restoration kept this
    # unconditional; main still had the `if not rows:` guard.)
    #
    # The email comes from `verified_identity`, never from anything a client
    # sent: the email IS the authorization, so a caller who could choose it
    # could admit themselves to any department. `claim_staff_invitations` is
    # revoked from `authenticated` for the same reason and runs on the service
    # client.
    #
    # **Cost.** One GoTrue `get_user` and one RPC per call. This is
    # `GET /auth/session`, which the browser calls on load and after a refresh
    # -- not a per-request path -- and the RPC is a single indexed read on
    # `staff_invitations` when there is nothing pending, which is the ordinary
    # case. Nothing is cached: a cached answer to "is there an invitation for
    # this address" is an invitation that lands late for the length of the cache.
    #
    # The re-read stays conditional. `_claim_staff_invitations` returns whether
    # anything was claimed, and a claim writes both a membership and a roster
    # row, so `_portal_for` below needs the membership row itself rather than an
    # assumption -- but a call that claimed nothing has changed nothing, and
    # re-reading after it would run the membership query twice on every sign-in,
    # forever.
    if _claim_staff_invitations(profile, principal, access_token):
        rows = get_session_memberships(principal.user_id)
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
    residency_row = _active_residency(membership)
    role = str(membership["role"]).lower()
    portal = _portal_for(membership, role)
    capabilities = [role]
    # An admin is also a resident -- **when they actually live here.** One
    # membership row per person per community, and resident-ness is the active
    # `unit_residencies` row above, never a role implication (product ruling,
    # 2026-08-20). Granting the capability unconditionally made the session
    # disagree with `require_resident_capability`, which asks the same question
    # per request and answers it from the same table: a flat-less admin was shown
    # the resident affordances and then 403'd by the guard when they used one.
    # The residency read is already done, so agreeing with the guard costs
    # nothing but the predicate.
    if role == "admin" and residency_row:
        capabilities.append("resident")
    unit_id = residency_row.get("unit_id") if residency_row else None
    return SessionContext(
        identity=profile,
        membership=MembershipContext(
            id=membership["id"], community_id=membership["community_id"], role=role,
            department_id=membership.get("department_id"),
            unit_id=unit_id,
            unit=_unit_from_residency(residency_row),
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
