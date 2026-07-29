"""Supabase identity-token verification using the project's JWKS.

Tokens establish identity only.  Community permissions are resolved from
memberships in each protected operation rather than copied into a JWT claim.
"""

from __future__ import annotations

from functools import lru_cache

import jwt

from app.config import get_settings
from app.core.exceptions import AuthenticationError
from app.domain.schemas import Principal

# Supabase issues user tokens with this audience.
_AUDIENCE = "authenticated"


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{get_settings().supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def decode_token(token: str) -> Principal:
    """Verify ``token`` and return the authenticated :class:`Principal`.

    Args:
        token: A raw Supabase-issued JWT (no ``Bearer`` prefix).

    Returns:
        The verified principal, with role resolved from the ``user_role`` claim.

    Raises:
        AuthenticationError: If the token is missing, malformed, expired, or the
            role claim is absent/invalid.
    """
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256":
            if not settings.supabase_jwt_secret:
                raise AuthenticationError("Legacy token signing is disabled.")
            key = settings.supabase_jwt_secret
        else:
            key = _jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=[algorithm], audience=_AUDIENCE)
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session has expired.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise AuthenticationError("Token is missing a subject claim.")

    return Principal(
        user_id=user_id,
        phone=claims.get("phone") or None,
        email=claims.get("email") or None,
        email_verified=bool(claims.get("email_confirmed_at") or claims.get("email_verified")),
    )
