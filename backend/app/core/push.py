"""The Web Push sender: one background worker per process.

Mirrors ``RealtimeHub`` -- a single background task, not one per client -- and
obeys one extra constraint that the hub does not:

    **The hub may drop. The sender may not duplicate.**

The hub tolerates several processes: each polls the outbox on its own cursor and
fans out to its own connections, so two workers means two harmless copies of a
frame delivered to two different sets of browsers. The sender has no such
luxury. Two workers reading the same unsent notification send the same push
twice, and a resident's phone buzzes twice for one visitor.

Claiming is therefore atomic and happens in the database, not here:
``claim_push_batch`` marks the rows and returns them in one statement, and
``for update skip locked`` makes the second worker walk past what the first has
locked. This module never decides what to send -- it asks, and sends what it is
given.

Three consequences worth stating because they look like bugs otherwise:

* **A claimed row is marked sent before the HTTP call**, so a crash mid-send
  loses a buzz rather than repeating one. At-most-once is the correct bias for
  something that vibrates a phone at night, and the notification is in the feed
  either way.
* **Only the last hour is claimed.** If this worker is down for a day, those
  notifications are still in the feed; they simply never buzz. A phone that goes
  off at 3am about a visitor from yesterday is worse than silence.
* **Nothing here retries a send.** A transient failure increments the
  subscription's counter and the *next* notification is the retry. Retrying one
  notification against a struggling push service is how a backlog becomes a
  thundering herd against Google's endpoint.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from app.core.push_config import get_push_settings

logger = logging.getLogger(__name__)

# Slower than the SSE hub's 500ms, and for a different reason. Each tick here is
# an UPDATE, not an indexed read, and push is out-of-app delivery -- a second or
# two on a lock screen is imperceptible, while writing twice a second forever is
# not free.
POLL_INTERVAL_SECONDS = 2.0

# One claim. Large enough that a burst drains in a few ticks, small enough that a
# stalled batch cannot hold a lease over hundreds of notifications.
BATCH_SIZE = 50

# How long one push may take before it is abandoned. A push service that has not
# answered in this long is not going to.
SEND_TIMEOUT_SECONDS = 10.0

# The statuses that mean the subscription itself is gone, rather than that this
# attempt failed. Deleting on these is what keeps us from being rate-limited for
# hammering endpoints that will never answer again.
_GONE_STATUSES = frozenset({404, 410})


class PushSender:
    """Claim un-pushed notifications and deliver them to registered browsers."""

    def __init__(
        self,
        *,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._task: asyncio.Task[None] | None = None

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Start the worker, unless push is not configured.

        Started from the application lifespan rather than lazily on first use,
        which is the opposite of the SSE hub and follows from what push is for:
        the hub exists to serve connected clients, so no client means no work,
        while the sender exists precisely to reach a resident who has *nothing*
        open.
        """
        problem = get_push_settings().configuration_problem()
        if problem is not None:
            # One line, at startup, so an operator learns before a resident
            # does. Not an error: an environment without a keypair is an
            # environment where push is off, not one that is broken.
            logger.info("Web Push disabled: %s", problem)
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="web-push-sender")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    # -- the worker --------------------------------------------------------

    async def _run(self) -> None:
        """Claim and deliver forever.

        Never raises. A transient database failure must not kill the loop and
        silently stop every push in the process -- which would be invisible,
        because a push that is not sent looks exactly like a phone that is off.
        """
        while True:
            try:
                rows = await asyncio.to_thread(self._claim)
                for row in rows:
                    await self._deliver(row)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - loop must survive anything
                logger.exception("Push batch failed; retrying")
            await asyncio.sleep(self._poll_interval)

    def _claim(self) -> list[dict[str, Any]]:
        """Take the next batch. Runs in a worker thread: supabase-py is sync."""
        from app.core.supabase_client import get_service_client
        from app.repositories import push_repository

        return push_repository.claim_batch(
            get_service_client(), limit=self._batch_size
        )

    async def _deliver(self, row: dict[str, Any]) -> None:
        """Send one notification to every browser its recipient has registered.

        The recipient is a person (``0041``), so a resident who is also a worker
        in another society gets one push per browser rather than one per
        membership -- and a service provider who belongs to no society at all is
        reachable, which under the membership-keyed shape they were not.

        Concurrently, with each exception captured per subscription: one dead
        endpoint must not stall the rest of a resident's devices, let alone the
        batch.
        """
        from app.repositories import push_repository
        from app.services import push_service

        profile_id = str(row.get("profile_id") or "")
        if not profile_id:
            return

        def _read() -> list[dict[str, Any]]:
            from app.core.supabase_client import get_service_client

            return push_repository.subscriptions_for(
                get_service_client(), profile_id=profile_id
            )

        subscriptions = await asyncio.to_thread(_read)
        if not subscriptions:
            # Nothing registered. The notification is in the feed; there is
            # simply no phone to reach, which is the ordinary case for a
            # resident who has never granted permission.
            return

        body = json.dumps(push_service.push_payload(row), separators=(",", ":"))
        await asyncio.gather(
            *(
                asyncio.to_thread(self._send_one, subscription, body)
                for subscription in subscriptions
            ),
            return_exceptions=True,
        )

    # -- one send ----------------------------------------------------------

    def _send_one(self, subscription: dict[str, Any], body: str) -> None:
        """Encrypt and post one push, then record what happened.

        Synchronous on purpose: ``pywebpush`` is a blocking library and this runs
        in a thread, exactly as ``supabase-py`` does in the SSE hub. Wrapping a
        blocking call in something that merely looks async is how an event loop
        gets stalled by a slow push service.
        """
        from app.core.supabase_client import get_service_client
        from app.repositories import push_repository

        endpoint = str(subscription.get("endpoint") or "")
        if not endpoint:
            return

        status = self._post(subscription, body)
        client = get_service_client()
        if status is None:
            push_repository.record_success(client, endpoint=endpoint)
            return
        push_repository.record_failure(
            client, endpoint=endpoint, gone=status in _GONE_STATUSES
        )

    def _post(self, subscription: dict[str, Any], body: str) -> int | None:
        """Do the HTTP call. ``None`` on success, else the status to record.

        Split out from ``_send_one`` so a test can substitute the network
        without also substituting the bookkeeping that follows it -- the
        bookkeeping is where the ``410`` rule lives, and it is the part worth
        testing.
        """
        settings = get_push_settings()
        try:
            from pywebpush import WebPushException, webpush
        except ImportError:  # pragma: no cover - the dependency is declared
            logger.error("pywebpush is not installed; push cannot be sent")
            return 500

        try:
            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": {
                        "p256dh": subscription["p256dh_key"],
                        "auth": subscription["auth_key"],
                    },
                },
                data=body,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                timeout=SEND_TIMEOUT_SECONDS,
                # Zero means "deliver now or drop it". A push held by the
                # service and delivered an hour later is the 3am buzz the
                # one-hour claim window already refuses.
                ttl=0,
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 413:
                # Our payload is too big. A bug on this side, not a transport
                # failure, and logged as one so it is not lost in a retry count.
                logger.error("Push payload exceeded the endpoint's limit")
            return int(status) if status else 500
        except Exception:  # noqa: BLE001 - a bad subscription must not kill the batch
            logger.exception("Push send failed")
            return 500
        return None


#: The process-wide sender. Started and stopped by the application lifespan.
sender = PushSender()
