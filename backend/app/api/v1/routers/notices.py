"""Notice board routes.

Only a write. The notice *list* comes from ``GET /dashboard/snapshot``, which
already projects ``notices[]`` — see ``docs/FRONTEND_WIRING_AUDIT.md``. Posting a
notice had no endpoint anywhere: build step 3 created the table, and the Notices
screen's ``addNotice`` has been writing to browser memory ever since.

This router uses the injected ``MembershipContext`` rather than looking tenancy up
from a user id, which is the pattern new handlers should follow.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.admin_deps import require_admin, require_csrf_unsafe
from app.api.deps import get_request_client
from app.domain.notice_schemas import CreateNoticeRequest, NoticeCreated
from app.domain.schemas import MembershipContext
from app.services import notices_service
from supabase import Client

router = APIRouter(tags=["notices"], dependencies=[Depends(require_csrf_unsafe)])


@router.post(
    "/notices",
    response_model=NoticeCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Post a notice",
)
async def create_notice(
    body: CreateNoticeRequest,
    membership: MembershipContext = Depends(require_admin),
    client: Client = Depends(get_request_client),
) -> NoticeCreated:
    """Publish a notice to the caller's community.

    Published immediately: ``published_at`` is set to now. The screen has no draft
    state and no schedule control, so a nullable ``published_at`` left unset would
    create notices that no reader could ever see.

    The insert fires the shared SSE trigger on ``notices``, so every connected
    client re-snapshots and the notice appears without this endpoint needing a
    matching read.

    **``category`` and ``urgency`` are stored but not yet rendered.** The shared
    snapshot projects notices as ``{id, title, description, date, createdAt}``
    (``dashboard_service.py:202``) and drops both fields. Adding them there is a
    one-line change owned by the dashboard workstream; until it lands the two
    values round-trip through this endpoint's response but not through the
    snapshot.
    """
    return notices_service.create_notice(
        client,
        community_id=membership.community_id,
        membership_id=membership.id,
        body=body,
    )
