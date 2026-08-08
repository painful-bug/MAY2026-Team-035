"""One shared poller behind every dashboard SSE connection.

The outbox pattern was already here: writes land in `public.sse_events` via
triggers, and `GET /dashboard/events` streams them to the browser. What was not
here was a sane way to *read* it.

The previous reader polled once per connected client, from a synchronous
generator that called `time.sleep(5)`. Two consequences, both load-bearing:

  * Starlette iterates a sync generator in the anyio worker threadpool, so each
    connected admin pinned one OS thread for the entire life of the stream.
    That pool defaults to 40 threads. The 41st dashboard would not merely lag --
    it would starve every other request in the process, because the pool is
    shared with all other sync work.
  * N admins watching one community issued N identical queries per tick.

This module inverts it. A single background task polls the whole outbox on one
global cursor and fans rows out to in-memory queues, so cost is one indexed
query per tick for the entire process regardless of how many people are
watching, and no connection holds a thread at all.

Latency is the poll interval, defaulting to 500ms. That is a deliberate choice
over the alternatives:

  * `LISTEN`/`NOTIFY` would be push, but needs a direct Postgres connection.
    The service only holds Supabase's PostgREST client -- no `DATABASE_URL`, no
    driver -- so it would mean a new dependency, a new secret, and a connection
    outside the pooler.
  * Supabase Realtime is the native answer and is where this should end up, but
    it is a browser-side WebSocket subscription. Adopting it means handing the
    frontend a Supabase key and moving tenant filtering into RLS, which reverses
    the deliberate "no provider token is exposed to the browser" decision that
    the same-origin SSE endpoint exists to enforce.

See docs/ARCHITECTURE.md for the comparison in full.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Poll cadence. One query per tick for the whole process, so this can be short
# without being expensive: 500ms is ~2 queries/second total, on a primary-key
# range scan that returns nothing almost every time.
POLL_INTERVAL_SECONDS = 0.5

# A client that falls this far behind is not going to catch up event by event.
# It gets a synthetic refresh instead -- see `_Subscriber.push`.
QUEUE_MAXSIZE = 64

# Ceiling on one poll. Bounded so a backlog cannot produce an unbounded response.
BATCH_SIZE = 500

# How often to remind an idle connection that it is still alive. Proxies and
# load balancers commonly close a silent stream at 60s.
HEARTBEAT_SECONDS = 20.0

# The audiences `0028_event_audience.sql` puts on every outbox row. The column
# is `not null default 'community'`, so a row from before that migration reads
# as community-wide -- which is what it was.
AUDIENCE_COMMUNITY = "community"
AUDIENCE_ROLE = "role"
AUDIENCE_MEMBER = "member"


@dataclass
class Event:
    """One outbox row, on its way to one browser."""

    id: int
    topic: str
    payload: dict[str, Any]

    def frame(self) -> str:
        """Render as an SSE frame.

        `payload` is serialised with `json.dumps`, not interpolated. The
        previous implementation wrote the dict straight into the data field,
        which produced Python repr -- `{'table': 'complaints'}`, with single
        quotes -- so anything calling `JSON.parse` on it threw. It also meant a
        payload containing a newline would split the frame and desynchronise
        the stream.
        """
        body = json.dumps(self.payload, separators=(",", ":"), default=str)
        return f"id: {self.id}\nevent: {self.topic}\ndata: {body}\n\n"


_ADMIN_ROLES = frozenset({"admin", "manager"})


# The frame a lagging client gets instead of the events it missed: re-read
# everything, you have a gap.
#
# The topic depends on the role because one of the two listeners already ships.
# `dashboard.refresh` is what the admin frontend is wired to, and this
# workstream does not get to change frontend code -- so admins keep it and
# converge exactly as before. Every other role gets `stream.resync`, which is
# the same instruction under a name that does not claim to be about the admin
# dashboard. `0028` retargets the `dashboard.refresh` *topic* to
# {admin,manager}; this frame is synthesised per subscriber and never goes
# through the audience filter, so the two have to agree by construction.
def _resync_event(event_id: int, role: str = "") -> Event:
    topic = "dashboard.refresh" if role in _ADMIN_ROLES else "stream.resync"
    return Event(id=event_id, topic=topic, payload={"resync": True})


# `eq=False` keeps the default identity hash. Subscribers are held in a set and
# two connections are never "the same" even with identical field values, so
# the dataclass-generated __eq__ (which would set __hash__ to None and make
# them unhashable) is exactly wrong here.
@dataclass(eq=False)
class _Subscriber:
    community_id: str
    # No defaults on these two, deliberately. A subscriber that could be built
    # without an identity is a subscriber that can be built by accident, and
    # the audience filter below is only as good as the identity it filters on.
    membership_id: str
    role: str
    queue: asyncio.Queue[Event] = field(
        default_factory=lambda: asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    )
    dropped: bool = False

    def accepts(self, row: Mapping[str, Any]) -> bool:
        """Whether this connection is in the row's audience.

        The single filter, applied identically to live dispatch and to the
        reconnect backfill. Both `membership_id` and `role` come from the
        membership the endpoint resolved out of Postgres, so a client cannot
        widen its own stream -- the same guarantee that already covered
        `community_id`, one field further.

        Anything it cannot classify is delivered to nobody.
        `sse_events_audience_shape_check` means such a row cannot be written,
        so this branch is a second lock on a door that is already bolted; it
        exists because the failure mode of guessing would be a disclosure.
        """
        audience = row.get("audience") or AUDIENCE_COMMUNITY
        if audience == AUDIENCE_COMMUNITY:
            return True
        if audience == AUDIENCE_ROLE:
            roles = row.get("audience_roles") or ()
            return self.role in {str(role).lower() for role in roles}
        if audience == AUDIENCE_MEMBER:
            recipient = row.get("recipient_membership_id")
            return recipient is not None and str(recipient) == self.membership_id
        return False

    def push(self, event: Event) -> None:
        """Enqueue without ever blocking the poller.

        A slow consumer must not be able to stall delivery for everyone else,
        so this degrades instead of waiting: once the queue is full we stop
        queueing detail and remember that a resync is owed.
        """
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped = True


class RealtimeHub:
    """Fan-out from one outbox poller to many connections."""

    def __init__(
        self,
        *,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._subscribers: dict[str, set[_Subscriber]] = {}
        self._task: asyncio.Task[None] | None = None
        self._cursor: int | None = None
        self._lock = asyncio.Lock()

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="sse-outbox-poller")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    @property
    def subscriber_count(self) -> int:
        return sum(len(group) for group in self._subscribers.values())

    # -- the poller --------------------------------------------------------

    async def _run(self) -> None:
        """Poll the outbox forever, dispatching to whoever is listening.

        Never raises: a transient database failure must not kill the loop and
        silently freeze every dashboard in the process.
        """
        while True:
            try:
                if self._subscribers:
                    rows = await asyncio.to_thread(self._fetch, self._cursor)
                    if rows:
                        self._dispatch(rows)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - loop must survive anything
                logger.exception("SSE outbox poll failed; retrying")
            await asyncio.sleep(self._poll_interval)

    def _fetch(self, cursor: int | None) -> list[dict[str, Any]]:
        """Read the next batch. Runs in a worker thread: supabase-py is sync.

        A `None` cursor means this process has not read the outbox yet. Rather
        than replay history to the first client that connects, seed the cursor
        at the current high-water mark and start from there.
        """
        from app.core.supabase_client import get_service_client
        from app.repositories import dashboard_repository

        client = get_service_client()
        if cursor is None:
            self._cursor = dashboard_repository.latest_event_id(client)
            return []
        return dashboard_repository.read_events_since(
            client, after_id=cursor, limit=self._batch_size
        )

    def _dispatch(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            event_id = int(row["id"])
            self._cursor = max(self._cursor or 0, event_id)
            group = self._subscribers.get(str(row["community_id"]))
            if not group:
                continue
            event = _event_from(row)
            # One `Event` shared by every recipient -- it is immutable in
            # practice and building one per subscriber would undo the point of
            # fanning out from a single query.
            for subscriber in group:
                if subscriber.accepts(row):
                    subscriber.push(event)

    # -- subscription ------------------------------------------------------

    async def subscribe(
        self,
        community_id: str,
        *,
        membership_id: str,
        role: str,
        last_event_id: int = 0,
    ) -> AsyncIterator[str]:
        """Yield SSE frames for one membership until the client disconnects.

        `community_id`, `membership_id` and `role` must all come from a
        membership the caller has already resolved out of Postgres. The hub
        takes no identity from a header, a query parameter or a
        `Last-Event-ID`; those it does read are used to seek, never to widen.

        Honours `Last-Event-ID`: a browser that reconnects mid-stream is caught
        up from the database first, then attached to the live feed, so a
        reconnect across a network blip does not lose the events that happened
        during it.
        """
        await self.start()
        subscriber = _Subscriber(
            community_id=community_id, membership_id=membership_id, role=role
        )
        async with self._lock:
            self._subscribers.setdefault(community_id, set()).add(subscriber)

        try:
            for frame in await self._backfill(subscriber, last_event_id):
                yield frame

            while True:
                try:
                    event = await asyncio.wait_for(
                        subscriber.queue.get(), timeout=HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    # A comment line. Keeps proxies from reaping an idle stream
                    # and lets the server notice a vanished client.
                    yield ": keepalive\n\n"
                    continue

                yield event.frame()

                if subscriber.dropped and subscriber.queue.empty():
                    subscriber.dropped = False
                    yield _resync_event(event.id, subscriber.role).frame()
        finally:
            async with self._lock:
                group = self._subscribers.get(community_id)
                if group is not None:
                    group.discard(subscriber)
                    if not group:
                        del self._subscribers[community_id]

    async def _backfill(self, subscriber: _Subscriber, last_event_id: int) -> list[str]:
        """Frames this subscriber missed while it was disconnected.

        The audience filter is applied twice on purpose. The query narrows in
        Postgres, because the read is capped and filtering only in Python would
        let a burst of admin traffic fill the cap and hide a resident's own
        events behind it. `accepts` then decides, because a mistake in a
        hand-written PostgREST expression should be able to lose an event and
        never to leak one.
        """
        if last_event_id <= 0:
            return []
        from app.core.supabase_client import get_service_client
        from app.repositories import dashboard_repository

        def _read() -> list[dict[str, Any]]:
            return dashboard_repository.read_events(
                get_service_client(),
                community_id=subscriber.community_id,
                after_id=last_event_id,
                membership_id=subscriber.membership_id,
                role=subscriber.role,
            )

        try:
            rows = await asyncio.to_thread(_read)
        except Exception:  # noqa: BLE001 - a failed backfill must not kill the stream
            logger.exception(
                "SSE backfill failed for community %s", subscriber.community_id
            )
            return []

        return [_event_from(row).frame() for row in rows if subscriber.accepts(row)]


def _event_from(row: Mapping[str, Any]) -> Event:
    payload = row.get("payload")
    return Event(
        id=int(row["id"]),
        topic=str(row.get("topic") or "dashboard.refresh"),
        payload=payload if isinstance(payload, dict) else {"raw": payload},
    )


hub = RealtimeHub()
