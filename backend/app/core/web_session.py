"""Cookie and transaction helpers for the backend-owned browser session.

No provider credential is returned to JavaScript.  Values are deliberately
small, signed with HMAC, and have explicit expiry so they are safe to keep in
short-lived HTTP-only transaction cookies.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Response

from app.config import get_settings
from app.core.exceptions import AuthenticationError

ACCESS_COOKIE = "__Host-hb_access"
REFRESH_COOKIE = "__Host-hb_refresh"
CSRF_COOKIE = "__Host-hb_csrf"
PREAUTH_CSRF_COOKIE = "hb_preauth_csrf"
RECOVERY_ACCESS_COOKIE = "hb_recovery_access"
RECOVERY_REFRESH_COOKIE = "hb_recovery_refresh"
RECOVERY_CSRF_COOKIE = "hb_recovery_csrf"
OAUTH_COOKIE = "hb_oauth_transaction"
INVITATION_COOKIE = "hb_pending_invitation"
CSRF_HEADER = "X-CSRF-Token"


def random_urlsafe(size: int = 32) -> str:
    return secrets.token_urlsafe(size)


def cookie_name(suffix: str) -> str:
    """Use the required host-only names in HTTPS deployments.

    Browsers reject ``__Host-`` cookies without ``Secure``. Local HTTP uses an
    intentionally distinct development name while preserving production's
    cookie contract exactly.
    """
    return f"__Host-hb_{suffix}" if get_settings().use_secure_cookies else f"hb_{suffix}"


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def sign_payload(payload: dict[str, Any], *, ttl_seconds: int) -> str:
    body = {**payload, "exp": int(time.time()) + ttl_seconds}
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=")
    signature = hmac.new(
        get_settings().cookie_signing_secret.encode(), encoded, hashlib.sha256
    ).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def verify_payload(value: str | None) -> dict[str, Any]:
    if not value or "." not in value:
        raise AuthenticationError("Authentication transaction is missing.")
    encoded, supplied_signature = value.split(".", 1)
    expected = hmac.new(
        get_settings().cookie_signing_secret.encode(), encoded.encode(), hashlib.sha256
    ).digest()
    try:
        signature = base64.urlsafe_b64decode(supplied_signature + "==")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=="))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthenticationError("Authentication transaction is invalid.") from exc
    if not hmac.compare_digest(expected, signature) or payload.get("exp", 0) < time.time():
        raise AuthenticationError("Authentication transaction has expired.")
    return payload


def set_transaction_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=300,
        httponly=True,
        secure=get_settings().use_secure_cookies,
        samesite="lax",
        path="/",
    )


def clear_cookie(response: Response, name: str, *, httponly: bool = True) -> None:
    response.delete_cookie(name, path="/", httponly=httponly, secure=get_settings().use_secure_cookies, samesite="lax")


def csrf_token(access_token: str) -> str:
    return hmac.new(
        get_settings().cookie_signing_secret.encode(), access_token.encode(), hashlib.sha256
    ).hexdigest()


def establish_session(response: Response, *, access_token: str, refresh_token: str, expires_in: int | None, persist: bool) -> None:
    """Write the session cookies, honouring the sign-in page's "Remember me".

    ``persist`` False is the default answer: the refresh cookie is written with
    no ``Max-Age`` so the browser drops it when the window closes, and the login
    page is there again next time. ``persist`` True keeps today's multi-day
    refresh window, which is what silently signs a returning visitor back in.

    The companion ``remember`` cookie exists because ``/auth/refresh`` rotates
    the refresh token and has to re-issue these cookies without the original
    request's answer in hand. It carries no secret -- the worst a user can do by
    editing it is change how long their own session survives -- so it is not
    signed.
    """
    settings = get_settings()
    max_age = expires_in or 3600
    remember_max_age = 60 * 60 * 24 * settings.auth_session_idle_days
    common = {"secure": settings.use_secure_cookies, "httponly": True, "samesite": "lax", "path": "/"}
    response.set_cookie(cookie_name("access"), access_token, max_age=max_age, **common)
    response.set_cookie(cookie_name("refresh"), refresh_token, max_age=remember_max_age if persist else None, **common)
    response.set_cookie(cookie_name("csrf"), csrf_token(access_token), max_age=max_age, httponly=False, secure=settings.use_secure_cookies, samesite="strict", path="/")
    if persist:
        response.set_cookie(cookie_name("remember"), "1", max_age=remember_max_age, **common)
    else:
        clear_cookie(response, cookie_name("remember"))
    clear_cookie(response, PREAUTH_CSRF_COOKIE, httponly=False)


def establish_recovery_session(response: Response, *, access_token: str, refresh_token: str, expires_in: int | None) -> None:
    """Store a short-lived recovery session that cannot satisfy normal auth deps."""
    settings = get_settings()
    max_age = min(expires_in or 600, 600)
    common = {"secure": settings.use_secure_cookies, "httponly": True, "samesite": "lax", "path": "/"}
    response.set_cookie(RECOVERY_ACCESS_COOKIE, access_token, max_age=max_age, **common)
    response.set_cookie(RECOVERY_REFRESH_COOKIE, refresh_token, max_age=max_age, **common)
    response.set_cookie(RECOVERY_CSRF_COOKIE, csrf_token(access_token), max_age=max_age, httponly=False, secure=settings.use_secure_cookies, samesite="strict", path="/")
    clear_cookie(response, PREAUTH_CSRF_COOKIE, httponly=False)


def establish_preauth_csrf(response: Response) -> str:
    token = random_urlsafe()
    response.set_cookie(PREAUTH_CSRF_COOKIE, token, max_age=600, httponly=False, secure=get_settings().use_secure_cookies, samesite="strict", path="/")
    return token


def clear_session(response: Response) -> None:
    for name, http_only in ((cookie_name("access"), True), (cookie_name("refresh"), True), (cookie_name("csrf"), False), (cookie_name("remember"), True), (PREAUTH_CSRF_COOKIE, False), (RECOVERY_ACCESS_COOKIE, True), (RECOVERY_REFRESH_COOKIE, True), (RECOVERY_CSRF_COOKIE, False), (OAUTH_COOKIE, True), (INVITATION_COOKIE, True)):
        clear_cookie(response, name, httponly=http_only)
