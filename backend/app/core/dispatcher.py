"""The job dispatcher: one background worker per process.

Mirrors ``PushSender`` almost line for line -- claim, act, sleep, started from
the application lifespan, never raising -- and reverses its central rule.

    **The sender may not duplicate. The dispatcher may not drop.**

``push.py`` claims by marking a notification sent *before* the send, so a crash
loses a buzz rather than repeating one. At-most-once is correct for something
that vibrates a phone at 3am. It is wrong here: a dropped ``resident_timeout``
is a complaint left waiting forever with nobody coming, which is the exact
silence this feature exists to end.

So ``claim_dispatch_batch`` takes a **lease**. A task claimed and not finished
within five minutes is claimable again by whichever process is still alive, and
the cost of that -- a task can fire twice -- is paid inside Postgres, where every
firing function re-reads the work order and returns without writing if the world
has already moved on. That idempotency is load-bearing, and it is why this module
is allowed to be as simple as it looks.

Three things worth stating because they look like omissions otherwise:

* **This file contains no dispatch logic at all.** It does not know what a
  ``ping`` is. It claims rows, calls ``fire_dispatch_task`` on each, and records
  the outcome; the mapping from a kind to an action lives in ``0037`` beside the
  actions. Adding a fifth task kind does not touch Python. That is not tidiness
  -- there is still no notification API in Python, and every notification in this
  product must be written inside the transaction that caused it.
* **Every process polls.** Two app processes are safe, because the claim is
  atomic, but each of them runs its own loop. At this scale that is free and it
  matches ``PushSender`` exactly. The ceiling is real and is worth a rewrite when
  it arrives, not before.
* **Nothing here retries.** A failed task is released with its reason recorded
  and picked up on a later tick by whoever claims it next, five times, and then
  it retires itself. Retry logic in this loop would be a second scheduler
  arguing with the one in the database.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Slower than push's 2s and far slower than the SSE hub's 500ms, because the
# tightest deadline anything here answers to is a thirty-minute escalation.
# Fifteen seconds of latency is invisible against that, and the claim query is
# one indexed read against a partial index over the open set.
POLL_INTERVAL_SECONDS = 15.0

# One claim. Small, because each task in a batch is a round trip that does real
# work -- a batch of fifty would hold its lease while the fiftieth waited.
BATCH_SIZE = 20


class Dispatcher:
    """Claim due dispatch tasks and ask Postgres to fire them."""

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
        """Start the worker.

        Unconditional, unlike ``PushSender.start``, which returns early without
        a VAPID keypair. There is no configuration to be missing here: an
        environment with a database is an environment where the engine runs, and
        a deployment that quietly did not dispatch would be indistinguishable
        from one where nobody happened to be free.
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="job-dispatcher")

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
        """Claim and fire forever.

        Never raises. A transient database failure must not kill the loop and
        silently stop every dispatch in the process -- a failure mode with no
        alarm attached, because a job that was never offered looks exactly like
        a department where nobody was free.
        """
        while True:
            try:
                for row in await asyncio.to_thread(self._claim):
                    await asyncio.to_thread(self._fire, row)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - loop must survive anything
                logger.exception("Dispatch batch failed; retrying")
            await asyncio.sleep(self._poll_interval)

    def _claim(self) -> list[dict[str, Any]]:
        """Take the next batch. Runs in a worker thread: supabase-py is sync."""
        from app.core.supabase_client import get_service_client
        from app.repositories import dispatch_repository

        return dispatch_repository.claim_batch(
            get_service_client(), limit=self._batch_size
        )

    def _fire(self, row: dict[str, Any]) -> None:
        """Run one task, and record the outcome either way.

        The failure branch is the reason this is a method rather than two lines
        in the loop above: one task that raises must not abandon the rest of the
        batch, and it must not stay leased -- an unreleased lease is five minutes
        of nothing happening to a job somebody is waiting on.
        """
        from app.core.supabase_client import get_service_client
        from app.repositories import dispatch_repository

        task_id = str(row.get("task_id") or "")
        if not task_id:
            return

        client = get_service_client()
        try:
            outcome = dispatch_repository.fire(client, task_id=task_id)
        except Exception as exc:  # noqa: BLE001 - one bad task, not the batch
            logger.exception("Dispatch task %s failed", task_id)
            with contextlib.suppress(Exception):
                dispatch_repository.fail(client, task_id=task_id, error=str(exc))
            return

        logger.info(
            "Dispatched %s for work order %s: %s",
            row.get("kind"),
            row.get("work_order_id"),
            outcome,
        )


#: The process-wide dispatcher. Started and stopped by the application lifespan.
dispatcher = Dispatcher()
