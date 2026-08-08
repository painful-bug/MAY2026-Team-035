"""Backend-owned, provider-neutral authentication endpoints.

Tokens only ever travel between this BFF and Supabase or through HTTP-only
cookies.  Browser JSON responses contain status and membership context only.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from functools import partial
from typing import TypeVar, cast

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from supabase import Client

from app.api.deps import get_current_user, get_request_client, get_request_token, require_csrf
from app.config import get_settings
from app.core.exceptions import AuthenticationError, ServiceUnavailableError, ValidationError
from app.core.web_session import (
    OAUTH_COOKIE,
    RECOVERY_ACCESS_COOKIE,
    RECOVERY_REFRESH_COOKIE,
    clear_cookie,
    clear_session,
    cookie_name,
    establish_preauth_csrf,
    establish_recovery_session,
    establish_session,
    set_transaction_cookie,
    sign_payload,
    verify_payload,
)
from app.domain.schemas import (
    AuthMethod,
    AuthMethodsResponse,
    EmailTokenRequest,
    MessageResponse,
    PasswordResetCompleteRequest,
    PasswordResetRequest,
    PasswordSignInRequest,
    PasswordSignUpRequest,
    Principal,
    SessionContext,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
_T = TypeVar("_T")


async def _run_provider_operation(operation: Callable[..., _T], *args: object, **kwargs: object) -> _T:
    try:
        return cast(
            _T,
            await asyncio.wait_for(
                run_in_threadpool(partial(operation, *args, **kwargs)),
                timeout=get_settings().auth_provider_timeout_seconds,
            ),
        )
    except TimeoutError as exc:
        raise ServiceUnavailableError(
            "The authentication provider did not respond in time. Please try again.",
            code="auth_provider_timeout",
        ) from exc


def _methods() -> AuthMethodsResponse:
    settings = get_settings()
    settings.validate_auth_configuration()
    descriptors = {
        "google": ("redirect", "Continue with Google"),
        "email_password": ("credentials", "Continue with email"),
    }
    return AuthMethodsResponse(
        primary=settings.auth_primary_method.lower(),
        methods=[
            AuthMethod(id=method, kind=descriptors[method][0], label=descriptors[method][1])
            for method in settings.enabled_auth_methods
        ],
    )


def _require_enabled(method: str) -> None:
    if method not in get_settings().enabled_auth_methods:
        raise ValidationError("This authentication method is not enabled.", code="provider_disabled")


@router.get("/methods")
async def auth_methods(request: Request) -> Response:
    payload = _methods().model_dump(mode="json")
    etag = '"' + hashlib.sha256(repr(payload).encode()).hexdigest() + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=300"})
    return JSONResponse(payload, headers={"ETag": etag, "Cache-Control": "public, max-age=300"})


@router.get("/csrf", response_model=MessageResponse)
async def csrf(response: Response) -> MessageResponse:
    establish_preauth_csrf(response)
    return MessageResponse(message="CSRF protection ready.")


@router.get("/oauth/{provider}/start", status_code=307)
async def oauth_start(provider: str, next: str | None = Query(None)) -> RedirectResponse:
    _require_enabled(provider)
    return_path = auth_service.safe_return_path(next)
    url, transaction = auth_service.start_oauth(provider)
    response = RedirectResponse(url=url, status_code=307)
    set_transaction_cookie(response, OAUTH_COOKIE, sign_payload({**transaction, "next": return_path}, ttl_seconds=300))
    return response


@router.get("/oauth/{provider}/callback", status_code=307)
async def oauth_callback(request: Request, provider: str, code: str | None = None) -> RedirectResponse:
    _require_enabled(provider)
    transaction = verify_payload(request.cookies.get(OAUTH_COOKIE))
    if not code:
        raise AuthenticationError("Sign-in code is missing.", code="oauth_code_missing")
    session = await _run_provider_operation(auth_service.exchange_google_code, code, str(transaction["verifier"]))
    destination = f"{get_settings().frontend_base_url.rstrip('/')}{transaction['next']}"
    response = RedirectResponse(destination, status_code=307)
    establish_session(response, access_token=session.access_token, refresh_token=session.refresh_token, expires_in=session.expires_in)
    clear_cookie(response, OAUTH_COOKIE)
    return response


# Compatibility routes keep existing bookmarks and Google callbacks working.
@router.get("/google/start", status_code=307)
async def google_start(next: str | None = Query(None)) -> RedirectResponse:
    return await oauth_start("google", next)


@router.get("/google/callback", status_code=307)
async def google_callback(request: Request, code: str | None = None) -> RedirectResponse:
    return await oauth_callback(request, "google", code)


@router.post("/password/sign-up", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def password_sign_up(body: PasswordSignUpRequest) -> MessageResponse:
    _require_enabled("email_password")
    if get_settings().auth_captcha_enabled and not body.captcha_token:
        raise ValidationError("Complete the CAPTCHA challenge.", code="captcha_required")
    await _run_provider_operation(auth_service.sign_up_with_password, email=body.email, password=body.password, full_name=body.full_name.strip(), captcha_token=body.captcha_token)
    return MessageResponse(message="If the account can be created, check your email to confirm it.")


@router.post("/password/sign-in", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def password_sign_in(body: PasswordSignInRequest, response: Response) -> MessageResponse:
    _require_enabled("email_password")
    if get_settings().auth_captcha_enabled and not body.captcha_token:
        raise ValidationError("Complete the CAPTCHA challenge.", code="captcha_required")
    session = await _run_provider_operation(auth_service.sign_in_with_password, email=body.email.strip().casefold(), password=body.password, captcha_token=body.captcha_token)
    establish_session(response, access_token=session.access_token, refresh_token=session.refresh_token, expires_in=session.expires_in)
    return MessageResponse(message="Signed in.")


@router.post("/email/verify", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def verify_email(body: EmailTokenRequest, response: Response) -> MessageResponse:
    if body.verification_type not in {"email", "signup"}:
        raise ValidationError("Invalid email verification request.", code="verification_invalid")
    session = await _run_provider_operation(auth_service.verify_email_token, body.token_hash, body.verification_type)
    establish_session(response, access_token=session.access_token, refresh_token=session.refresh_token, expires_in=session.expires_in)
    return MessageResponse(message="Email verified.")


@router.post("/email/resend", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def resend_email(body: PasswordResetRequest) -> MessageResponse:
    """Send the sign-up confirmation link again.

    The recovery path when the first link expired, never arrived, or was spent by
    a mail-security scanner -- without it, a user whose confirmation failed has
    nowhere to go, since signing in is now correctly refused until they confirm.
    The response is identical whether or not the address has an unconfirmed
    account, so it cannot be used to discover who has registered.
    """
    _require_enabled("email_password")
    if get_settings().auth_captcha_enabled and not body.captcha_token:
        raise ValidationError("Complete the CAPTCHA challenge.", code="captcha_required")
    await _run_provider_operation(
        auth_service.resend_confirmation_email,
        email=body.email.strip().casefold(),
        captcha_token=body.captcha_token,
    )
    return MessageResponse(message="If an unconfirmed account exists, a confirmation email will be sent.")


@router.post("/password/reset/request", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def password_reset_request(body: PasswordResetRequest) -> MessageResponse:
    _require_enabled("email_password")
    if get_settings().auth_captcha_enabled and not body.captcha_token:
        raise ValidationError("Complete the CAPTCHA challenge.", code="captcha_required")
    await _run_provider_operation(auth_service.send_password_recovery, email=body.email.strip().casefold(), captcha_token=body.captcha_token)
    return MessageResponse(message="If an account matches that email, check your inbox for recovery instructions.")


@router.post("/password/reset/verify", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def password_reset_verify(body: EmailTokenRequest, response: Response) -> MessageResponse:
    session = await _run_provider_operation(auth_service.verify_recovery_token, body.token_hash)
    establish_recovery_session(response, access_token=session.access_token, refresh_token=session.refresh_token, expires_in=session.expires_in)
    return MessageResponse(message="Password recovery verified.")


@router.post("/password/reset/complete", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def password_reset_complete(request: Request, body: PasswordResetCompleteRequest, response: Response) -> MessageResponse:
    access = request.cookies.get(RECOVERY_ACCESS_COOKIE)
    refresh_token = request.cookies.get(RECOVERY_REFRESH_COOKIE)
    if not access or not refresh_token:
        raise AuthenticationError("Request a new password recovery link.", code="recovery_required")
    await _run_provider_operation(auth_service.complete_password_recovery, access_token=access, refresh_token=refresh_token, password=body.password)
    clear_session(response)
    return MessageResponse(message="Password updated. Sign in with your new password.")


@router.get("/session", response_model=SessionContext)
async def session(principal: Principal = Depends(get_current_user), client: Client = Depends(get_request_client), access_token: str = Depends(get_request_token)) -> SessionContext:
    return await run_in_threadpool(auth_service.get_session_context, client, principal, access_token)


@router.post("/refresh", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def refresh(request: Request, response: Response) -> MessageResponse:
    refresh_token = request.cookies.get(cookie_name("refresh"))
    if not refresh_token:
        raise AuthenticationError("No refresh session is available.")
    session = await _run_provider_operation(auth_service.refresh_session, refresh_token)
    establish_session(response, access_token=session.access_token, refresh_token=session.refresh_token, expires_in=session.expires_in)
    return MessageResponse(message="Session refreshed.")


@router.post("/logout", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def logout(request: Request, response: Response) -> MessageResponse:
    access = request.cookies.get(cookie_name("access"))
    refresh_token = request.cookies.get(cookie_name("refresh"))
    if access and refresh_token:
        try:
            await _run_provider_operation(auth_service.revoke_session, access_token=access, refresh_token=refresh_token)
        except (AuthenticationError, ServiceUnavailableError):
            pass
    clear_session(response)
    return MessageResponse(message="Logged out.")
