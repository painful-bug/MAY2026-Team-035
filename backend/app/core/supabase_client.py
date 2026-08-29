"""Single entry point for every Supabase interaction.

All Supabase access in the backend flows through this module — no other module
should call ``create_client`` directly. This keeps credentials, client options,
and the anon-vs-service-role safety boundary in one auditable place.

Three clients are exposed, each for a distinct trust level:

``get_anon_client()``
    Uses the public *anon* key. Subject to Row-Level Security with no user
    context, so it can only touch data exposed to anonymous visitors. Rarely
    used directly; prefer :func:`get_user_client` for request-scoped access.

``get_auth_client()``
    Creates a short-lived anonymous client for stateful GoTrue operations such
    as PKCE code exchange and refresh. Those operations update the client's
    in-memory auth session and must never share that state across browsers.

``get_service_client()``
    Uses the *service-role* key and **bypasses Row-Level Security**. Reserve it
    for narrowly audited privileged operations that RLS would otherwise block,
    such as atomic membership claims. Never build a service client from
    request-supplied data without an explicit authorization check.

``get_user_client(access_token)``
    An anon client with the caller's JWT attached, so PostgREST runs queries as
    that user and **RLS is enforced for their role**. This is the default path
    for reading and writing domain data on behalf of a signed-in user.

The anon and service clients are process-wide singletons (cheap, thread-safe for
our read-mostly usage). User clients are created per request because they carry
request-specific credentials.
"""

from __future__ import annotations

import time
from functools import lru_cache

import httpx
from app.config import get_settings
from postgrest.constants import DEFAULT_POSTGREST_CLIENT_TIMEOUT
from supabase import Client, ClientOptions, create_client

# Methods safe to replay after the request may already have reached the server.
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Transport-level failures worth one more attempt. On Windows a stale
# keep-alive connection to Supabase intermittently dies with
# ``httpx.ReadError: [WinError 10035]`` (WSAEWOULDBLOCK); an immediate retry on
# a fresh connection succeeds. Server disconnects on reused connections surface
# as ``RemoteProtocolError`` and are the same class of transient failure.
_RETRYABLE_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
)


class _TransientRetryTransport(httpx.HTTPTransport):
    """HTTPTransport that retries transient socket failures a bounded number of times.

    Connection-establishment failures are retried for every method because the
    request never reached the server. Read/write failures are retried only for
    idempotent methods: a POST (e.g. a PostgREST RPC) whose response read fails
    may already have executed server-side, so replaying it could double-apply.
    """

    def __init__(self, *args, transient_retries: int = 2, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._transient_retries = transient_retries

    def _should_retry(self, request: httpx.Request, exc: Exception) -> bool:
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            return True
        return request.method.upper() in _IDEMPOTENT_METHODS

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        for attempt in range(self._transient_retries + 1):
            try:
                return super().handle_request(request)
            except _RETRYABLE_ERRORS as exc:
                if attempt >= self._transient_retries or not self._should_retry(
                    request, exc
                ):
                    raise
                # The failed keep-alive connection is discarded by httpcore; a
                # short pause lets the pool settle before the fresh attempt.
                time.sleep(0.05 * (attempt + 1))
        raise AssertionError("unreachable")  # pragma: no cover


def _build_http_client() -> httpx.Client:
    """Create the httpx session shared by one Supabase client's sub-clients.

    Mirrors the defaults supabase-py would use when no client is injected
    (HTTP/2, redirects, the PostgREST timeout), plus the retry transport.
    """
    return httpx.Client(
        transport=_TransientRetryTransport(http2=True),
        timeout=httpx.Timeout(DEFAULT_POSTGREST_CLIENT_TIMEOUT),
        follow_redirects=True,
    )


def _build_client(key: str) -> Client:
    """Create a Supabase client for ``key`` with server-side options.

    Auto-refresh and session persistence are disabled: the backend is stateless
    and holds no long-lived browser-style session of its own. A custom httpx
    session is injected so transient Windows socket failures (WSAEWOULDBLOCK
    surfacing as ``httpx.ReadError``) are retried instead of becoming 500s.
    """
    settings = get_settings()
    options = ClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        httpx_client=_build_http_client(),
    )
    return create_client(settings.supabase_url, key, options)


@lru_cache
def get_anon_client() -> Client:
    """Return the shared anon-key client (RLS applies, no user context)."""
    return _build_client(get_settings().supabase_anon_key)


def get_auth_client() -> Client:
    """Return an isolated client for one stateful authentication transaction."""
    return _build_client(get_settings().supabase_anon_key)


@lru_cache
def get_service_client() -> Client:
    """Return the shared service-role client (bypasses RLS — privileged only)."""
    return _build_client(get_settings().supabase_service_role_key)


def get_user_client(access_token: str) -> Client:
    """Return a client scoped to ``access_token`` so RLS runs as that user.

    Args:
        access_token: A Supabase-issued JWT for the signed-in user.

    Returns:
        A fresh client whose PostgREST/Storage requests carry the user's bearer
        token, causing Row-Level Security to evaluate against their claims.
    """
    client = _build_client(get_settings().supabase_anon_key)
    # Attach the user's JWT so PostgREST authorizes as that user, not anon.
    client.postgrest.auth(access_token)
    return client
