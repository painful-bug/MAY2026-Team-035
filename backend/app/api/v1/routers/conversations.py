"""The hiring conversation, from both ends.

Four routes and **no role guard**, which is the whole design rather than an
omission. The other two routers in this feature bracket the choice: a provider
route is guarded by identity alone because the caller may belong to no community
yet, and a department route is guarded by ``require_admin_or_manager`` because
every path under it names a department. This one is neither. Participation is a
property of the *thread* -- one department and one provider -- so there is no
role a router could check that would answer it.

So the authorization lives where the thread does. ``is_conversation_participant``
(``0038`` 3) is called by both read policies and both write RPCs, and the
consequence is visible from outside: a non-participant sees an empty list, a
404 on a thread they do not belong to, and a 403 if they post to one. None of
those three answers is produced by code in this file.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_current_user, get_request_client
from app.domain.conversation_schemas import (
    Conversation,
    ConversationMessage,
    ConversationThread,
    OpenConversationRequest,
    PostMessageRequest,
)
from app.domain.schemas import Principal
from app.services import conversations_service as service
from supabase import Client

router = APIRouter(
    tags=["conversations"],
    dependencies=[Depends(require_csrf_unsafe)],
)


@router.get(
    "/conversations",
    response_model=list[Conversation],
    summary="My conversations",
)
def list_conversations(
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
    department_id: str | None = Query(None, alias="departmentId"),
) -> list[Conversation]:
    """Every thread the caller is part of, most recent first.

    **One inbox, not one per community.** A service person hired by three
    societies talks to three departments and has one screen; omitting
    `departmentId` is what that screen calls. A manager passes one and gets that
    department's threads.

    Passing a `departmentId` the caller has no part in is not an error -- it
    returns nothing. The filter narrows what the policy already allows and can
    never widen it, which is why it is safe to take from the query string.

    Both counterparts are named on every row. Which of them is "the other side"
    depends on who is asking, and the caller knows that better than this
    endpoint does.
    """
    return service.list_conversations(client, department_id=department_id)


@router.post(
    "/conversations",
    response_model=ConversationThread,
    status_code=status.HTTP_201_CREATED,
    summary="Open a conversation",
)
def open_conversation(
    body: OpenConversationRequest,
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ConversationThread:
    """Start talking to a provider, or return the thread that already exists.

    **Idempotent, and `201` either way.** There is exactly one thread per
    (department, provider) pair -- a unique constraint, not a convention -- so
    this is what a "Message" button calls every time it is pressed rather than
    something a client must call once and remember. Two managers pressing it at
    the same moment get the same thread; without the constraint they would get
    two, each holding half the conversation.

    Either side may open it: a manager sizing up a candidate, or a provider
    asking a question before applying. Anyone else gets a `403` -- creating the
    thread would otherwise be how a stranger joined it.

    The response is the full thread, because a thread that already existed
    already has messages and the caller is about to render them.
    """
    return service.open_conversation(client, body=body)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationThread,
    summary="Read a conversation",
)
def get_conversation(
    conversation_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ConversationThread:
    """One thread and its messages, oldest first.

    **A thread the caller is not in is a `404`, not a `403`.** The policy hides
    the row rather than refusing it, which means a department's conversations
    with other providers cannot be enumerated by walking ids and reading which
    refusals come back.

    `authorSide` is what a renderer switches on. The two sides live in two
    different tables -- a membership and a provider row, because an invited
    provider holds no membership in the community yet -- and the view collapses
    that into one word so no client has to know it.
    """
    return service.get_thread(client, conversation_id=conversation_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessage,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message",
)
def post_message(
    body: PostMessageRequest,
    conversation_id: str = Path(...),
    _: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> ConversationMessage:
    """Append one message to a thread the caller is part of.

    **Which side the message is from is decided by the thread, not by the
    sender.** A provider who has since been hired holds both a membership and a
    provider row, and either would be a true answer to "who wrote this"; the
    thread makes it one answer, so `authorSide` reads the same for their first
    message and their hundredth.

    The stored message is returned rather than the request. The body is trimmed
    and the author's name is resolved server-side, so a client that appended its
    own request to the list would be showing something nobody else sees.

    There is no notification. `notifications.recipient_membership_id` is not
    nullable and the provider a manager most needs to reach -- an invited one,
    not yet hired -- holds no membership in that community, so a notification
    path here would work for some threads and silently not for others. The
    conversation list is the delivery mechanism until the worker portal
    subscribes to events.
    """
    return service.post_message(
        client, conversation_id=conversation_id, body=body
    )
