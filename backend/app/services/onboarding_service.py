"""Founder community creation through one audited database transaction."""

from __future__ import annotations

from postgrest.exceptions import APIError

from app.core.exceptions import AppError, ConflictError, ServiceUnavailableError
from app.core.logging import get_logger
from app.core.pg_errors import translate
from app.core.supabase_client import get_service_client
from app.domain.schemas import (
    CommunityOnboardingRequest,
    CommunityOnboardingResponse,
    Principal,
)

_logger = get_logger(__name__)


def create_community(
    request: CommunityOnboardingRequest,
    principal: Principal,
) -> CommunityOnboardingResponse:
    """Call the baseline SQL function; Google identity alone grants no tenancy."""
    payload = request.model_dump(mode="json")
    payload["founder_profile_id"] = principal.user_id
    payload["founder_email"] = principal.email
    try:
        result = (
            get_service_client()
            .rpc("create_founder_community", {"p_payload": payload})
            .execute()
            .data
        )
    except APIError as exc:
        _logger.exception("create_founder_community RPC failed")
        if exc.code == "PGRST202" and "create_founder_community" in exc.message:
            raise ServiceUnavailableError(
                "Community registration is being set up. Please try again shortly.",
                code="founder_onboarding_not_deployed",
            ) from exc
        error = translate(exc, default_message="Community could not be created.")
        if type(error) is not AppError:
            raise error from exc
        raise ServiceUnavailableError(
            "Community registration is temporarily unavailable. Please try again.",
            code="founder_onboarding_unavailable",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        _logger.exception("create_founder_community RPC unavailable")
        raise ServiceUnavailableError(
            "Community registration is temporarily unavailable. Please try again.",
            code="founder_onboarding_unavailable",
        ) from exc
    row = result[0] if isinstance(result, list) and result else result
    if not isinstance(row, dict):
        raise ConflictError("Community could not be created.", code="onboarding_failed")
    return CommunityOnboardingResponse(community=row["community"], admin=row["admin"])
