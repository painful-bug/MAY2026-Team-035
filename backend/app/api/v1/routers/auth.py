"""Google-only authentication routes.  Tokens are never returned as JSON."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import (
    get_current_user,
    get_request_client,
    get_request_token,
    require_csrf,
)
from app.core.exceptions import AuthenticationError
from app.core.web_session import (
    OAUTH_COOKIE,
    clear_cookie,
    clear_session,
    cookie_name,
    establish_session,
    set_transaction_cookie,
    sign_payload,
    verify_payload,
)
from app.domain.schemas import (
    AuthMethod,
    AuthMethodsResponse,
    MessageResponse,
    Principal,
    SessionContext,
)
from app.services import auth_service
from supabase import Client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/methods", response_model=AuthMethodsResponse)
async def auth_methods() -> AuthMethodsResponse:
    """Expose only server-enabled, browser-safe authentication methods."""
    from app.config import get_settings

    settings = get_settings()
    settings.validate_auth_configuration()
    labels = {"google": "Continue with Google"}
    return AuthMethodsResponse(
        primary=settings.auth_primary_method.lower(),
        methods=[
            AuthMethod(id=method, kind="redirect", label=labels[method])
            for method in settings.enabled_auth_methods
        ],
    )


@router.get("/google/start", status_code=307)
async def google_start(next: str | None = Query(None)) -> RedirectResponse:
    return_path = auth_service.safe_return_path(next)
    url, transaction = auth_service.start_google_oauth()
    response = RedirectResponse(url=url, status_code=307)
    transaction_cookie = sign_payload(
        {**transaction, "next": return_path}, ttl_seconds=300
    )
    set_transaction_cookie(response, OAUTH_COOKIE, transaction_cookie)
    return response


@router.get("/google/callback", status_code=307)
async def google_callback(
    request: Request,
    code: str | None = None,
) -> RedirectResponse:
    transaction = verify_payload(request.cookies.get(OAUTH_COOKIE))
    if not code:
        raise AuthenticationError(
            "Google sign-in code is missing.", code="oauth_code_missing"
        )
    session = auth_service.exchange_google_code(code, str(transaction["verifier"]))
    from app.config import get_settings

    destination = f"{get_settings().frontend_base_url.rstrip('/')}{transaction['next']}"
    redirect = RedirectResponse(destination, status_code=307)
    establish_session(
        redirect,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
    )
    clear_cookie(redirect, OAUTH_COOKIE)
    return redirect


@router.get("/session", response_model=SessionContext)
async def session(
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
    access_token: str = Depends(get_request_token),
) -> SessionContext:
    return auth_service.get_session_context(client, principal, access_token)


@router.post(
    "/refresh",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def refresh(request: Request, response: Response) -> MessageResponse:
    refresh_token = request.cookies.get(cookie_name("refresh"))
    if not refresh_token:
        raise AuthenticationError("No refresh session is available.")
    session = auth_service.refresh_session(refresh_token)
    establish_session(
        response,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
    )
    return MessageResponse(message="Session refreshed.")


@router.post(
    "/logout",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def logout(request: Request, response: Response) -> MessageResponse:
    if token := request.cookies.get(cookie_name("access")):
        auth_service.revoke_session(token)
    clear_session(response)
    return MessageResponse(message="Logged out.")
