"""The canonical live-update stream, for every portal.

`GET /dashboard/events` came first and is admin-shaped only in its path: the
guard has always been `get_active_membership`, so any active member could open
it. With `0028_event_audience.sql` the rows themselves carry an audience and
the hub filters on it, which makes one stream correct for every role -- so the
stream gets a name that does not claim to be about the dashboard.

The old path stays, unchanged in shape and now audience-scoped, as a deprecated
alias. The admin frontend is already wired to it and this workstream does not
break a working client to tidy a URL.

Both routes are the same three lines around `dashboard_service.event_stream`,
and the response declaration is shared rather than copied, because the reason
it is written out by hand is easy to lose -- see `SSE_RESPONSES`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from app.api.deps import get_active_membership
from app.domain.schemas import MembershipContext
from app.services import dashboard_service

router = APIRouter(tags=["realtime"])

# FastAPI would otherwise advertise `application/json` here, because that is its
# default for any route whose return type it cannot infer a media type from --
# and a client generated from that spec would try to JSON-decode a live stream.
SSE_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {"text/event-stream": {}},
        "description": "Event stream. Frame format and topics: docs/API.md 5.1.",
    },
    401: {"description": "No session."},
    403: {"description": "No active membership."},
}


def parse_last_event_id(raw: str | None) -> int:
    """Cursor from the `Last-Event-ID` header a reconnecting browser resends.

    A malformed value is a zero, not a 422. The header is set by the browser's
    own `EventSource` implementation, not by application code, and refusing the
    reconnect would leave the client with no way to recover other than to stop
    sending the header it is required to send.

    The value only ever moves the cursor forward within a stream the caller is
    already authorized for; it cannot widen the audience. See
    `app.core.realtime._Subscriber.accepts`.
    """
    try:
        return max(int(raw or 0), 0)
    except ValueError:
        return 0


def stream(
    membership: MembershipContext, last_event_id: str | None
) -> StreamingResponse:
    """Shared body for both routes."""
    return StreamingResponse(
        dashboard_service.event_stream(membership, parse_last_event_id(last_event_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # nginx buffers proxied responses by default, which for a stream
            # means the browser sees nothing until the buffer fills.
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/events", response_class=StreamingResponse, responses=SSE_RESPONSES)
async def events(
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    membership: MembershipContext = Depends(get_active_membership),
) -> StreamingResponse:
    """Same-origin SSE stream, scoped to the caller's audience.

    Delivers the outbox rows addressed to the caller's community, to their
    role, or to them personally -- and nothing else. No provider token is
    exposed to the browser.
    """
    return stream(membership, last_event_id)
