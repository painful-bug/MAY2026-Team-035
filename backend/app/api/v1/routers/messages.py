"""Direct messages: five routes, and a guard that is deliberately thin.

Like ``conversations.py``, the router asks only that the caller is signed in.
Everything meaningful happens below: the RLS read policies scope the mailbox
to threads the caller is in, ``dm_pair_allowed`` decides who may open what,
and the work-order lock refuses a closed channel with a `409`. A role guard
here would be wrong twice over — every portal mounts the chat dock (admin,
worker, security, resident — the 2026-08-10 ruling), and the caller's role
per community is a fact the database already checks per row.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_current_user, get_request_client
from app.domain.message_schemas import (
    DmMessage,
    DmRecipient,
    DmThread,
    DmThreadDetail,
    OpenThreadRequest,
    PostDmMessageRequest,
)
from app.domain.schemas import Principal
from app.services import messages_service as service
from supabase import Client

router = APIRouter(tags=["messages"], dependencies=[Depends(require_csrf_unsafe)])


@router.get(
    "/messages/recipients",
    response_model=list[DmRecipient],
    summary="Who I can message in one community",
)
async def list_recipients(
    community_id: str = Query(..., alias="communityId"),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> list[DmRecipient]:
    """The chat dock's "to" field.

    Everyone the caller may open a direct thread with here: their department
    colleagues, the community's managers, and its admins — **"the committee"
    is the admin role** in this product (`USER_IDENTIFICATION.md`; committee
    offices are not separate roles). Residents see the office only: their
    channel to a worker is the job thread, which opens while the work order is
    live and locks when it ends.

    The list and the write share one rule (`dm_pair_allowed`), so nobody the
    directory offers can be refused, and nobody it omits can be reached by
    guessing a profile id.
    """
    return service.list_recipients(client, community_id=community_id)


@router.get(
    "/messages/threads",
    response_model=list[DmThread],
    summary="My message threads",
)
async def list_threads(
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> list[DmThread]:
    """One mailbox, every community.

    `counterpartName` is resolved for the caller — the same row answers "who
    is this with" differently for its two participants. `lockedAt` non-null
    means the thread reads fine and refuses writes: a finished job's channel
    is documented history, not a live line.
    """
    return service.list_threads(client, profile_id=principal.user_id)


@router.post(
    "/messages/threads",
    response_model=DmThreadDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Open (or return) a thread",
)
async def open_thread(
    body: OpenThreadRequest,
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> DmThreadDetail:
    """Idempotent on the pair.

    A direct thread (`recipientProfileId` + `communityId`) is one row per pair
    per community, upserted — opening a chat that exists returns it, so a
    client calls this whenever a name is picked rather than remembering. A job
    thread (`workOrderId`) joins the accepted worker to the complaint's
    resident, refuses once the job is terminal, and is the **only** channel a
    resident and a serviceman share.

    `403` when the pair is not allowed — a resident naming another resident,
    a worker naming someone from a department they do not share.
    """
    return service.open_thread(client, profile_id=principal.user_id, body=body)


@router.get(
    "/messages/threads/{thread_id}",
    response_model=DmThreadDetail,
    summary="One thread with its messages",
)
async def get_thread(
    thread_id: str = Path(...),
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> DmThreadDetail:
    """The thread, oldest message first.

    A message with a null `authorProfileId` is a system line — "the job ended,
    this conversation is closed" — written by the database when the lock
    landed, so the silence has an explanation in the transcript itself.

    `404` covers missing and not-yours alike; a stranger walking thread ids
    learns nothing from the difference.
    """
    return service.get_thread(
        client, profile_id=principal.user_id, thread_id=thread_id
    )


@router.post(
    "/messages/threads/{thread_id}/messages",
    response_model=DmMessage,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message",
)
async def post_message(
    body: PostDmMessageRequest,
    thread_id: str = Path(...),
    principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> DmMessage:
    """Append to a thread the caller is in.

    **`409` is the lock**: a work-order thread whose job completed refuses new
    messages — the protection the product owner asked for, so a serviceman
    cannot keep a private line to a resident after the work is done. The
    counterpart is notified (`dm.message`) inside the same transaction.
    """
    return service.post_message(
        client, profile_id=principal.user_id, thread_id=thread_id, body=body
    )
