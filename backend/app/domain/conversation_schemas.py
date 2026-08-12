"""Wire models for the department-to-provider conversation.

One thread per (department, provider) pair, so a thread has no name of its own
and no title to render -- both counterparts are on every row and the client
labels the thread with whichever one is not the caller. The API deliberately
does not decide which that is: on a cross-community screen the caller is the
provider in every thread, and on a department screen they are the department in
every thread, and the caller already knows which screen they are.

``authorSide`` is what a message renderer switches on, not the author's id. The
two sides are stored in two different tables -- a membership and a provider row,
because an invited provider holds no membership in the community yet -- and
``0038`` 4 collapses that into one word so no client has to know it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel


class ConversationMessage(CamelModel):
    """One message, with its author resolved to a name and a side."""

    id: str
    conversation_id: str
    body: str
    #: ``provider`` or ``department``. Decided by the thread rather than by the
    #: sender, so a hired provider -- who holds both a membership and a provider
    #: row -- still reads as ``provider`` in their own thread.
    author_side: str
    author_name: str
    author_profile_id: str | None = None
    created_at: datetime | None = None


class Conversation(CamelModel):
    """One thread, with both counterparts named."""

    id: str
    community_id: str
    community_name: str | None = None
    department_id: str
    department_name: str | None = None
    department_kind: str | None = None
    service_provider_id: str
    provider_display_name: str | None = None
    provider_headline: str | None = None
    provider_profile_id: str | None = None
    #: The last line, for a thread list that does not fetch every thread's
    #: messages to render a preview.
    last_message_body: str | None = None
    message_count: int = 0
    last_message_at: datetime | None = None
    created_at: datetime | None = None


class ConversationThread(CamelModel):
    """A thread and its messages, oldest first.

    One response rather than two round trips, because a thread with no messages
    and a thread the caller cannot see are different answers -- 200 with an
    empty list and 404 -- and splitting the read would make them arrive
    separately.
    """

    conversation: Conversation
    messages: list[ConversationMessage] = Field(default_factory=list)


class OpenConversationRequest(CamelModel):
    """Start talking to a provider, or reopen the thread that already exists."""

    department_id: str
    service_provider_id: str


class PostMessageRequest(CamelModel):
    """One message.

    ``max_length`` matches the CHECK in ``0038`` 2 rather than being a rounder
    number, so an over-long message is a 422 naming the field instead of a 422
    from Postgres naming the constraint.
    """

    body: str = Field(min_length=1, max_length=4000)
