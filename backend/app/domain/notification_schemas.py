"""Wire models for the notification feed and the push registration it feeds.

Both live here because they are one feature seen from two sides: §10.1's three
layers share a single record, and a module split along transport lines would put
the feed row and the push it becomes in different files while they are rendered
from the same ``payload``.

**A notification is rendered strings, not a record.** ``title``, ``body`` and
``url`` are enough to draw a feed row and route a click. The record itself is
fetched through its own endpoint, where the ownership predicate lives -- so a
notification that goes stale (a complaint closed after the row was written) shows
a stale line and then the truth, rather than being the truth.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel, Page


class NotificationItem(CamelModel):
    """One row of the feed."""

    id: str
    #: The vocabulary in ``RESIDENT_BACKEND_DESIGN.md`` §10.3, e.g.
    #: ``visitor.approval_requested``. Deliberately not an enum: every later
    #: build step adds kinds, and a closed enum here would make the API model a
    #: file each of them has to edit before its own feature works.
    kind: str
    title: str
    body: str
    #: Where a click goes, as a frontend path. Empty when the notification is
    #: informational and has nowhere to route to.
    url: str
    is_unread: bool
    created_at: datetime


class NotificationFeed(Page[NotificationItem]):
    """The feed, with the one number a badge needs.

    A ``Page`` subclass rather than a new envelope: every collection on this API
    has one shape (§1.6 of ``API.md``) and a client that can render a page can
    render this. ``unread`` is not derivable from ``items`` -- it counts the
    whole feed, not the page -- which is exactly why it is a field rather than
    something the client adds up.
    """

    unread: int


class NotificationReadResult(CamelModel):
    """What changed, and what is left.

    ``unread`` is returned by both mark-read routes so a badge can be set from
    the response instead of re-fetching the feed to find out.
    """

    marked: int
    unread: int


class VapidPublicKey(CamelModel):
    """The public half of the keypair, for ``PushManager.subscribe``.

    Public by construction -- that is what the pair is for. The frontend must
    compare this against the ``applicationServerKey`` its stored subscription was
    created with and re-subscribe when they differ, because a key rotation
    otherwise stops push permanently and silently (§10.5).
    """

    public_key: str


class PushSubscriptionKeys(CamelModel):
    """The browser's encryption material.

    Field names are the browser's, not ours: ``PushSubscription.toJSON()``
    produces ``{"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}`` and this
    model accepts that document unchanged, so the frontend posts what the
    Push API handed it rather than transcribing it into our spelling. A
    transcription step is a place to put the ``auth`` value in the ``p256dh``
    field, and the failure would be a push that silently never decrypts.
    """

    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class RegisterPushSubscription(CamelModel):
    """Register this browser for push."""

    endpoint: str = Field(min_length=1)
    keys: PushSubscriptionKeys
    #: Only so an operator can tell a phone from a laptop when a resident says
    #: "one of my devices stopped buzzing". Never used to make a decision.
    user_agent: str | None = None


class UnregisterPushSubscription(CamelModel):
    """Stop pushing to this browser."""

    endpoint: str = Field(min_length=1)


class PushSubscriptionResult(CamelModel):
    """Acknowledgement for a registration or its removal."""

    #: True after a register, false after a delete. The endpoint is not echoed
    #: back: it is a device identifier and it was already in the request.
    subscribed: bool
