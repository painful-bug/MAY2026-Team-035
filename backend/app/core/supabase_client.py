"""Single entry point for every Supabase interaction.

All Supabase access in the backend flows through this module — no other module
should call ``create_client`` directly. This keeps credentials, client options,
and the anon-vs-service-role safety boundary in one auditable place.

Three clients are exposed, each for a distinct trust level:

``get_anon_client()``
    Uses the public *anon* key. Subject to Row-Level Security with no user
    context, so it can only touch data exposed to anonymous visitors. Rarely
    used directly; prefer :func:`get_user_client` for request-scoped access.

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

from functools import lru_cache

from app.config import get_settings
from supabase import Client, ClientOptions, create_client


def _build_client(key: str) -> Client:
    """Create a Supabase client for ``key`` with server-side options.

    Auto-refresh and session persistence are disabled: the backend is stateless
    and holds no long-lived browser-style session of its own.
    """
    settings = get_settings()
    options = ClientOptions(
        auto_refresh_token=False,
        persist_session=False,
    )
    return create_client(settings.supabase_url, key, options)


@lru_cache
def get_anon_client() -> Client:
    """Return the shared anon-key client (RLS applies, no user context)."""
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
