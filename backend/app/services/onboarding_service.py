"""Founder community creation through one audited database transaction."""

from __future__ import annotations

from app.core.exceptions import ConflictError, ServiceUnavailableError
from app.core.supabase_client import get_service_client
from app.domain.schemas import (
    CommunityOnboardingRequest,
    CommunityOnboardingResponse,
    Principal,
)


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
    except Exception as exc:  # noqa: BLE001
        if "PGRST202" in str(exc) or "create_founder_community" in str(exc):
            raise ServiceUnavailableError(
                "Community registration is being set up. Please try again shortly.",
                code="founder_onboarding_not_deployed",
            ) from exc
        raise ConflictError(
            "Community could not be created. Please try again.",
            code="onboarding_failed",
        ) from exc
    row = result[0] if isinstance(result, list) and result else result
    if not isinstance(row, dict):
        raise ConflictError("Community could not be created.", code="onboarding_failed")
    return CommunityOnboardingResponse(community=row["community"], admin=row["admin"])
