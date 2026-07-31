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
from collections.abc import AsyncIterator
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


# The frame a lagging client gets instead of the events it missed. `topic`
# matches what the generic outbox trigger emits, so the browser's existing
# `dashboard.refresh` listener re-snapshots and converges without needing to
# know it ever fell behind.
def _resync_event(event_id: int) -> Event:
    return Event(id=event_id, topic="dashboard.refresh", payload={"resync": True})


# `eq=False` keeps the default identity hash. Subscribers are held in a set and
# two connections are never "the same" even with identical field values, so
# the dataclass-generated __eq__ (which would set __hash__ to None and make
# them unhashable) is exactly wrong here.
@dataclass(eq=False)
class _Subscriber:
    community_id: str
    queue: asyncio.Queue[Event] = field(
        default_factory=lambda: asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    )
    dropped: bool = False

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
            payload = row.get("payload")
            event = Event(
                id=event_id,
                topic=str(row.get("topic") or "dashboard.refresh"),
                payload=payload if isinstance(payload, dict) else {"raw": payload},
            )
            for subscriber in group:
                subscriber.push(event)

    # -- subscription ------------------------------------------------------

    async def subscribe(
        self, community_id: str, *, last_event_id: int = 0
    ) -> AsyncIterator[str]:
        """Yield SSE frames for one community until the client disconnects.

        Honours `Last-Event-ID`: a browser that reconnects mid-stream is caught
        up from the database first, then attached to the live feed, so a
        reconnect across a network blip does not lose the events that happened
        during it.
        """
        await self.start()
        subscriber = _Subscriber(community_id=community_id)
        async with self._lock:
            self._subscribers.setdefault(community_id, set()).add(subscriber)

        try:
            for frame in await self._backfill(community_id, last_event_id):
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
                    yield _resync_event(event.id).frame()
        finally:
            async with self._lock:
                group = self._subscribers.get(community_id)
                if group is not None:
                    group.discard(subscriber)
                    if not group:
                        del self._subscribers[community_id]

    async def _backfill(self, community_id: str, last_event_id: int) -> list[str]:
        """Frames the client missed while it was disconnected."""
        if last_event_id <= 0:
            return []
        from app.core.supabase_client import get_service_client
        from app.repositories import dashboard_repository

        def _read() -> list[dict[str, Any]]:
            return dashboard_repository.read_events(
                get_service_client(), community_id=community_id, after_id=last_event_id
            )

        try:
            rows = await asyncio.to_thread(_read)
        except Exception:  # noqa: BLE001 - a failed backfill must not kill the stream
            logger.exception("SSE backfill failed for community %s", community_id)
            return []

        frames = []
        for row in rows:
            payload = row.get("payload")
            frames.append(
                Event(
                    id=int(row["id"]),
                    topic=str(row.get("topic") or "dashboard.refresh"),
                    payload=payload if isinstance(payload, dict) else {"raw": payload},
                ).frame()
            )
        return frames


hub = RealtimeHub()
