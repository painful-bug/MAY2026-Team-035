"""Privacy-minimal, non-blocking service-signup funnel events."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import require_csrf
from app.config import get_settings
from app.core.web_session import cookie_name
from app.domain.schemas import MessageResponse, ServiceSignupTelemetryRequest
from app.repositories import service_signup_telemetry_repository as repo

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post(
    "/service-signup",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def record_service_signup_event(
    body: ServiceSignupTelemetryRequest, request: Request, response: Response
) -> MessageResponse:
    """Record one allowlisted event; storage failure never blocks the funnel."""
    name = cookie_name("service_funnel")
    try:
        visitor_id = UUID(request.cookies.get(name, ""))
    except ValueError:
        visitor_id = uuid4()
        response.set_cookie(
            name,
            str(visitor_id),
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            secure=get_settings().use_secure_cookies,
            samesite="lax",
            path="/",
        )
    repo.record(visitor_id, body.event_name)
    return MessageResponse(message="Recorded.")
