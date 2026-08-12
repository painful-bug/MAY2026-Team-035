"""The conversation a department has with a service person.

Step 3 of ``docs/plans/SERVICE_OPERATIONS_PLAN.md``, and the plan's verification
for it is one sentence: **RLS denies a non-participant.** That is the reason
this module is thin. There is no authorization decision here to get wrong,
because there is none to make here at all -- participation is a property of the
thread rather than of the caller's role, so it is computed by
``is_conversation_participant`` (``0038`` 3) and enforced by the two read
policies and the two RPCs.

What that buys: a caller who is not in a thread gets an empty list from the list
endpoint, a 404 from the read, and a 403 from the post, without this file
containing a single ``if``. A check written here would be a fourth copy of a
rule already stated three times in SQL, and the copy that drifts is always the
one furthest from the data.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.domain.conversation_schemas import (
    Conversation,
    ConversationMessage,
    ConversationThread,
    OpenConversationRequest,
    PostMessageRequest,
)
from app.repositories import conversations_repository as repo
from supabase import Client

#: One page of a thread. High enough that no hiring conversation reaches it, and
#: present so a thread that somehow does cannot return an unbounded response.
_MESSAGE_LIMIT = 500


def _text(value: object) -> str | None:
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _to_conversation(row: dict[str, Any]) -> Conversation:
    return Conversation(
        id=row["id"],
        community_id=row["community_id"],
        community_name=_text(row.get("community_name")),
        department_id=row["department_id"],
        department_name=_text(row.get("department_name")),
        department_kind=_text(row.get("department_kind")),
        service_provider_id=row["service_provider_id"],
        provider_display_name=_text(row.get("provider_display_name")),
        provider_headline=_text(row.get("provider_headline")),
        provider_profile_id=_text(row.get("provider_profile_id")),
        last_message_body=_text(row.get("last_message_body")),
        message_count=int(row.get("message_count") or 0),
        last_message_at=row.get("last_message_at"),
        created_at=row.get("created_at"),
    )


def _to_message(row: dict[str, Any]) -> ConversationMessage:
    return ConversationMessage(
        id=row["id"],
        conversation_id=row["conversation_id"],
        body=str(row.get("body") or ""),
        author_side=str(row.get("author_side") or "department"),
        author_name=str(row.get("author_name") or "Unknown"),
        author_profile_id=_text(row.get("author_profile_id")),
        created_at=row.get("created_at"),
    )


def list_conversations(
    client: Client, *, department_id: str | None
) -> list[Conversation]:
    """Every thread the caller is in, most recent first.

    The same call serves both sides. A provider omits ``department_id`` and gets
    their inbox across every community; a manager passes one and gets that
    department's. Neither of them can widen it by passing an id they have no
    business with -- the policy is what decides, and an id outside it simply
    returns nothing.
    """
    return [
        _to_conversation(row)
        for row in repo.list_conversations(client, department_id=department_id)
    ]


def get_thread(client: Client, *, conversation_id: str) -> ConversationThread:
    """One thread with its messages, oldest first.

    **A thread the caller is not in is a 404, not a 403.** The policy hides the
    row rather than refusing it, and that is the right answer here: a
    department's threads with other providers should not be enumerable by
    walking ids and reading which refusals come back.
    """
    row = repo.get_conversation(client, conversation_id=conversation_id)
    if row is None:
        raise NotFoundError("No such conversation.", code="conversation_not_found")
    return ConversationThread(
        conversation=_to_conversation(row),
        messages=[
            _to_message(message)
            for message in repo.list_messages(
                client, conversation_id=conversation_id, limit=_MESSAGE_LIMIT
            )
        ],
    )


def open_conversation(
    client: Client, *, body: OpenConversationRequest
) -> ConversationThread:
    """Open the thread for a (department, provider) pair, or return it.

    Idempotent, so this is what a "Message" button calls every time it is
    pressed rather than something a client has to call once and remember. The
    response is the full thread because the caller pressing that button is about
    to render it, and a thread that already existed already has messages in it.
    """
    conversation_id = repo.open_conversation(
        client,
        department_id=body.department_id,
        service_provider_id=body.service_provider_id,
    )
    return get_thread(client, conversation_id=conversation_id)


def post_message(
    client: Client, *, conversation_id: str, body: PostMessageRequest
) -> ConversationMessage:
    """Append one message and return it as stored.

    As stored, not as sent: the body is trimmed by the RPC and the author's name
    and side are resolved from the thread, none of which the caller supplied. A
    client appending the request to its own list would show a message that
    differs from what everyone else sees.
    """
    message_id = repo.post_message(
        client, conversation_id=conversation_id, body=body.body
    )
    row = repo.get_message(client, message_id=message_id)
    if row is None:
        raise NotFoundError("No such conversation.", code="conversation_not_found")
    return _to_message(row)
