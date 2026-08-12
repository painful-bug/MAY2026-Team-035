"""Wire models for direct messages: the chat dock's mailbox.

A thread is two people in one community — or two people around one live work
order, which is the same shape with a lock on the end of it. The counterpart
fields are resolved per caller in the service, because "who is this thread
with" depends on who is asking; the two snapshot names ride along so a client
can also label the *author* of each message without a second read.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel


class DmRecipient(CamelModel):
    """One person the caller may open a thread with."""

    profile_id: str
    display_name: str
    #: ``Admin``, ``Manager``, or the department's name — enough for the
    #: dock's "to" field to say who somebody is, not an authorization fact.
    label: str


class DmThread(CamelModel):
    """One thread, as the mailbox lists it."""

    id: str
    community_id: str
    community_name: str | None = None
    #: ``direct`` or ``work_order``.
    kind: str
    work_order_id: str | None = None
    #: The other person, resolved for the caller.
    counterpart_profile_id: str
    counterpart_name: str
    participant_a_profile_id: str
    participant_b_profile_id: str
    participant_a_name: str
    participant_b_name: str
    #: Set when the thread closed (a work-order thread whose job ended). A
    #: locked thread reads fine and refuses writes with a `409` — documented
    #: history, closed channel.
    locked_at: datetime | None = None
    last_message_at: datetime | None = None
    last_message_body: str | None = None
    created_at: datetime | None = None


class DmMessage(CamelModel):
    """One line of a thread."""

    id: str
    thread_id: str
    #: Null is a system line — "this conversation is closed" — written by the
    #: database, not by a person.
    author_profile_id: str | None = None
    body: str
    created_at: datetime | None = None


class DmThreadDetail(DmThread):
    """A thread with its messages, oldest first."""

    messages: list[DmMessage] = Field(default_factory=list)


class OpenThreadRequest(CamelModel):
    """Open (or return) a thread.

    Exactly one subject: a person (``recipientProfileId`` + ``communityId``)
    for a direct thread, or a ``workOrderId`` for the job channel. Sending
    both, or neither, is a `422` before anything is written.
    """

    community_id: str | None = None
    recipient_profile_id: str | None = None
    work_order_id: str | None = None


class PostDmMessageRequest(CamelModel):
    """Append one message."""

    body: str = Field(min_length=1, max_length=4000)
