"""Data access for the dispatch queue. Service client only, every one of them.

There is no request behind any of this. The dispatcher runs on a timer with no
caller, no cookie and no ``auth.uid()``, which is why every function here takes
the service client and why ``dispatch_tasks`` has **RLS enabled with no policy**:
no client the API hands out has any reason to read it, and ``service_role``
bypasses RLS anyway. Compare ``push_repository``, which draws the same line for
the same reason.

Four verbs, and the shape of them is the whole design. ``claim_batch`` leases
work; ``fire`` asks Postgres to do it; ``complete`` and ``fail`` record which
happened. **Nothing here decides anything** -- the mapping from a task kind to an
action lives in ``fire_dispatch_task`` (``0037`` section 6), beside the actions
it dispatches to, so adding a fifth kind never touches Python.

None of these translate errors through ``app.core.pg_errors``. That module exists
to turn a SQLSTATE into an HTTP status for a caller who is waiting, and there is
nobody waiting. A failure here becomes a row in ``last_error`` and a line in the
log.
"""

from __future__ import annotations

from typing import Any

from supabase import Client


def claim_batch(client: Client, *, limit: int) -> list[dict[str, Any]]:
    """Lease the next due tasks (RPC).

    ``for update skip locked`` inside the function is what makes two dispatcher
    processes safe: the second one's select walks past the rows the first has
    locked rather than waiting for them and then firing them again.
    """
    response = client.rpc("claim_dispatch_batch", {"p_limit": limit}).execute()
    return response.data or []


def fire(client: Client, *, task_id: str) -> str:
    """Run one claimed task and mark it done (RPC). Returns what it did.

    The return value is for the log, not for a decision: ``offered:3``,
    ``assigned:<uuid>``, ``no_candidate``, ``skipped``, ``already_done``. A task
    that fires twice under the lease answers ``already_done`` rather than acting
    twice, which is the contract every function behind this one keeps.
    """
    response = client.rpc("fire_dispatch_task", {"p_task_id": task_id}).execute()
    return str(response.data or "")


def complete(client: Client, *, task_id: str) -> None:
    """Mark a task finished.

    Belt and braces: ``fire_dispatch_task`` already completes what it ran, in
    the same transaction as the work. This exists for the paths that end without
    firing anything, and it is idempotent so calling it after a successful fire
    costs a no-op rather than an error.
    """
    client.rpc("complete_dispatch_task", {"p_task_id": task_id}).execute()


def fail(client: Client, *, task_id: str, error: str) -> None:
    """Record why a task did not fire and release its lease.

    A separate call rather than part of ``fire`` because it has to survive the
    failure: whatever went wrong inside ``fire_dispatch_task`` took its whole
    transaction with it, including any note it might have written about itself.
    """
    client.rpc(
        "fail_dispatch_task", {"p_task_id": task_id, "p_error": error}
    ).execute()
