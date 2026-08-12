"""The job dispatcher.

What is covered, stated plainly because it is easy to overclaim: **this
exercises the loop, not the engine.** Every decision the dispatcher causes --
who is free, who gets the offer, what the resident is told -- happens inside
``0037``, which this suite has no database to run, so none of it can run here.
What is tested is the part written in Python:
claiming, per-task isolation, the failure path, and the lifecycle.

The rule these tests exist to protect is the inverse of the push sender's, and
the inversion is the reason the file is worth reading:

    The sender may not duplicate. The dispatcher may not drop.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core import supabase_client
from app.core.dispatcher import Dispatcher
from app.repositories import dispatch_repository


def claimed(**overrides: Any) -> dict[str, Any]:
    """One row as `claim_dispatch_batch` returns it."""
    base: dict[str, Any] = {
        "task_id": "task-id",
        "work_order_id": "work-order-id",
        "kind": "ping",
        "due_at": "2026-08-10T09:30:00Z",
        "attempts": 1,
    }
    base.update(overrides)
    return base


@pytest.fixture
def service_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Supabase client as a bare sentinel that must never be called.

    Every repository function is replaced in these tests, so any attempt to use
    this object is a test reaching the network, which is the failure worth
    making loud rather than mocking politely.
    """
    monkeypatch.setattr(supabase_client, "get_service_client", lambda: object())


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """Capture what the dispatcher asked the database to do."""
    calls: dict[str, list] = {"fired": [], "failed": [], "completed": []}

    monkeypatch.setattr(
        dispatch_repository,
        "fire",
        lambda client, *, task_id: calls["fired"].append(task_id) or "skipped",
    )
    monkeypatch.setattr(
        dispatch_repository,
        "fail",
        lambda client, *, task_id, error: calls["failed"].append((task_id, error)),
    )
    monkeypatch.setattr(
        dispatch_repository,
        "complete",
        lambda client, *, task_id: calls["completed"].append(task_id),
    )
    return calls


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_the_dispatcher_starts_unconditionally(service_client: None) -> None:
    """No configuration gate, unlike `PushSender`.

    An environment with no VAPID keypair is one where push is legitimately off.
    There is no equivalent for dispatch: a process that silently did not
    dispatch would be indistinguishable from a department where nobody was
    free, which is the failure with no alarm attached.
    """

    async def run() -> bool:
        dispatcher = Dispatcher(poll_interval=0.01)
        await dispatcher.start()
        started = dispatcher.running
        await dispatcher.stop()
        return started

    assert asyncio.run(run()) is True


def test_stopping_is_clean_and_repeatable(service_client: None) -> None:
    """Cancellation is not an error, and stopping twice is not either.

    The lifespan calls `stop` on the way out of a process that may already be
    tearing down; a second call raising would turn an orderly shutdown into a
    traceback in the logs.
    """

    async def run() -> bool:
        dispatcher = Dispatcher(poll_interval=0.01)
        await dispatcher.start()
        await dispatcher.stop()
        await dispatcher.stop()
        return dispatcher.running

    assert asyncio.run(run()) is False


# ---------------------------------------------------------------------------
# Claiming and firing
# ---------------------------------------------------------------------------


def test_every_claimed_task_is_fired(
    service_client: None, recorder: dict[str, list], monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = [
        claimed(task_id="task-1", kind="ping"),
        claimed(task_id="task-2", kind="auto_assign"),
        claimed(task_id="task-3", kind="resident_timeout"),
    ]
    monkeypatch.setattr(
        dispatch_repository, "claim_batch", lambda client, *, limit: batch
    )

    dispatcher = Dispatcher(poll_interval=0.01)
    for row in dispatcher._claim():
        dispatcher._fire(row)

    assert recorder["fired"] == ["task-1", "task-2", "task-3"]
    assert recorder["failed"] == []


def test_a_row_without_a_task_id_is_skipped_rather_than_fired(
    service_client: None, recorder: dict[str, list]
) -> None:
    """Defensive, and cheap. A malformed row reaching `fire` would send a null
    task id to Postgres, which answers `missing` -- correct, but a round trip
    to learn something the row already said."""
    Dispatcher()._fire(claimed(task_id=None))

    assert recorder["fired"] == []


def test_the_batch_size_reaches_the_claim(
    service_client: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []
    monkeypatch.setattr(
        dispatch_repository,
        "claim_batch",
        lambda client, *, limit: seen.append(limit) or [],
    )

    Dispatcher(batch_size=7)._claim()

    assert seen == [7]


# ---------------------------------------------------------------------------
# Failure. The half that matters.
# ---------------------------------------------------------------------------


def test_a_failing_task_is_recorded_and_its_lease_released(
    service_client: None, recorder: dict[str, list], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lease is the whole reason this branch exists.

    A task that raised and was left claimed is five minutes of nothing
    happening to a job somebody is waiting on -- `fail_dispatch_task` clears
    `claimed_at` so the next tick can pick it up.
    """

    def boom(client, *, task_id):
        raise RuntimeError("no candidate view")

    monkeypatch.setattr(dispatch_repository, "fire", boom)

    Dispatcher()._fire(claimed(task_id="task-9"))

    assert recorder["failed"] == [("task-9", "no candidate view")]


def test_one_failing_task_does_not_abandon_the_rest_of_the_batch(
    service_client: None, recorder: dict[str, list], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fire(client, *, task_id):
        if task_id == "task-2":
            raise RuntimeError("transient")
        recorder["fired"].append(task_id)
        return "skipped"

    monkeypatch.setattr(dispatch_repository, "fire", fire)
    monkeypatch.setattr(
        dispatch_repository,
        "claim_batch",
        lambda client, *, limit: [
            claimed(task_id="task-1"),
            claimed(task_id="task-2"),
            claimed(task_id="task-3"),
        ],
    )

    dispatcher = Dispatcher()
    for row in dispatcher._claim():
        dispatcher._fire(row)

    assert recorder["fired"] == ["task-1", "task-3"]
    assert [task_id for task_id, _ in recorder["failed"]] == ["task-2"]


def test_a_failure_to_record_the_failure_is_swallowed(
    service_client: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both calls fail and the batch survives anyway.

    The database being unreachable is exactly when `fire` raises *and* `fail`
    cannot be written. Letting the second exception out would take down the
    loop for the whole process at the moment it is least able to recover.
    """

    def boom(*args, **kwargs):
        raise RuntimeError("database is gone")

    monkeypatch.setattr(dispatch_repository, "fire", boom)
    monkeypatch.setattr(dispatch_repository, "fail", boom)

    Dispatcher()._fire(claimed())  # must not raise


def test_the_loop_survives_a_failing_claim(
    service_client: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transient database failure must not silently stop every dispatch in
    the process. The loop logs and comes back on the next tick."""
    attempts: list[int] = []

    def claim(client, *, limit):
        attempts.append(1)
        raise RuntimeError("connection reset")

    monkeypatch.setattr(dispatch_repository, "claim_batch", claim)

    async def run() -> None:
        dispatcher = Dispatcher(poll_interval=0.01)
        await dispatcher.start()
        await asyncio.sleep(0.08)
        still_running = dispatcher.running
        await dispatcher.stop()
        assert still_running is True

    asyncio.run(run())
    assert len(attempts) > 1


# ---------------------------------------------------------------------------
# The contract with `0037`
# ---------------------------------------------------------------------------


def test_the_dispatcher_knows_nothing_about_task_kinds() -> None:
    """The kinds appear in `0037`, not here.

    `fire_dispatch_task` maps a kind to an action beside the actions it
    dispatches to, so adding a fifth kind is a migration and nothing else. If
    this assertion ever fails, a branch on `kind` has appeared in Python and the
    engine has started living in two places.
    """
    import inspect

    from app.core import dispatcher as module

    body = "".join(
        line
        for line in inspect.getsource(module.Dispatcher).splitlines(keepends=True)
        if not line.lstrip().startswith("#")
    )

    for kind in ("ping", "auto_assign", "resident_timeout"):
        assert kind not in body
