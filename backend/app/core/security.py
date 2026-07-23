"""Access-token verification.

Supabase signs access tokens with the project JWT secret (HS256). We verify the
signature and expiry locally — no network round-trip — and project the token
into a :class:`Principal`. The ``role`` is read from the ``user_role`` custom
claim added by the access-token hook (see
``supabase/migrations/0003_access_token_hook.sql``).
"""

from __future__ import annotations

import jwt

from app.config import get_settings
from app.core.exceptions import AuthenticationError
from app.domain.roles import Role, parse_role
from app.domain.schemas import Principal

# Supabase issues user tokens with this audience.
_AUDIENCE = "authenticated"


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
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=_AUDIENCE,
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session has expired.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    user_id = claims.get("sub")
    if not user_id:
        raise AuthenticationError("Token is missing a subject claim.")

    role = parse_role(claims.get("user_role"))
    if role is None:
        # The access-token hook must be registered; a token without a role claim
        # cannot be authorized for anything.
        raise AuthenticationError(
            "Token is missing a valid role claim.", code="missing_role_claim"
        )

    return Principal(
        user_id=user_id,
        role=role,
        phone=claims.get("phone") or None,
        email=claims.get("email") or None,
    )


def role_from_claims(claims: dict) -> Role | None:
    """Helper to extract a role from an already-decoded claim set."""
    return parse_role(claims.get("user_role"))
