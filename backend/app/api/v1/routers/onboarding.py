"""Google-authenticated founder onboarding."""

from fastapi import APIRouter, Depends

from app.api.deps import get_request_token, require_csrf
from app.domain.schemas import CommunityOnboardingRequest, CommunityOnboardingResponse
from app.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/community", response_model=CommunityOnboardingResponse, dependencies=[Depends(require_csrf)])
def create_community(
    body: CommunityOnboardingRequest,
    access_token: str = Depends(get_request_token),
) -> CommunityOnboardingResponse:
    from app.services import auth_service
    return onboarding_service.create_community(body, auth_service.verified_identity(access_token))
