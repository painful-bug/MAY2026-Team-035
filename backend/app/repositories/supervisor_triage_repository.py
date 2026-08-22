"""Data access for the supervisor's triage dashboard.

Six RPCs and nothing else -- the snapshot and take-up from
``20260822120000_supervisor_triage.sql``, and resolve, priority, notes and chat
from ``20260822170000_supervisor_actions.sql``. Every one of them is
``SECURITY DEFINER`` and asks ``can_supervise_department`` for itself, which is
the reason there is no table or view read beside them: a read through RLS would
answer the same authorization question a second way, and the two would drift.

**The caller's request client, never the service client.** Both functions resolve
the caller from ``auth.uid()``; the service client has none, so passing it would
not fail loudly -- it would tell a signed-in supervisor they do not supervise
their own department.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client


def triage_snapshot(client: Client, *, department_id: str) -> dict[str, Any]:
    """The department's four dashboard sections, in one round trip.

    Returns the RPC's own object. ``{}`` when PostgREST hands back a scalar
    ``null``, which it does for a ``returns jsonb`` function that returned
    nothing -- a shape the RPC cannot actually produce, but one the service
    should not have to guess at.
    """
    try:
        response = client.rpc(
            "supervisor_triage_snapshot", {"p_department_id": department_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not load this department's dashboard."
        ) from exc
    data = response.data
    return data if isinstance(data, dict) else {}


def resolve_complaint(client: Client, *, complaint_id: str) -> None:
    """The department saying the work is done (RPC).

    Two `HB409`s are the substance of this call and both are written for a
    person: one job is running, so finish or cancel it first; or the complaint
    has already been settled. Everything else the RPC does -- calling off the
    other live jobs, telling their workers why, and letting
    ``complaints_on_resolved`` write the timeline entry and the resident's
    notification -- happens in the one transaction.
    """
    try:
        client.rpc(
            "supervisor_resolve_complaint", {"p_complaint_id": complaint_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not resolve that complaint."
        ) from exc


def raise_complaint_priority(client: Client, *, complaint_id: str) -> str:
    """Escalate one step (RPC). Returns the new stored priority.

    The storage word (``medium``, ``high``) comes back, not the wire word:
    ``app/domain/vocabularies.py`` is the one place this codebase translates a
    vocabulary, and a second translation in SQL would be free to disagree with
    it.
    """
    try:
        response = client.rpc(
            "raise_complaint_priority", {"p_complaint_id": complaint_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not raise the priority of that complaint."
        ) from exc
    return str(response.data or "")


def add_complaint_note(client: Client, *, complaint_id: str, note: str) -> str:
    """Append an internal note to a complaint's timeline (RPC).

    ``HB422`` for a note outside 1--2000 characters, which Pydantic has already
    refused -- the second check is the database's, and it is the one that holds
    for any caller the API does not own.
    """
    try:
        response = client.rpc(
            "add_complaint_note_internal",
            {"p_complaint_id": complaint_id, "p_note": note},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not add that note."
        ) from exc
    return str(response.data or "")


def open_complaint_thread(client: Client, *, complaint_id: str) -> str:
    """Open (or get) the complaint's chat thread (RPC). Returns the thread id.

    Idempotent by design: a second supervisor pressing the same button joins the
    thread that exists rather than forking a second one, so the client calls this
    every time rather than remembering.
    """
    try:
        response = client.rpc(
            "open_complaint_thread", {"p_complaint_id": complaint_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not open a chat about that complaint."
        ) from exc
    return str(response.data or "")


def take_up_complaint(client: Client, *, complaint_id: str) -> None:
    """A supervisor picking a new complaint up (RPC).

    Three refusals come out of here and every one is worth the caller reading:
    ``HB404`` for a complaint that does not exist, ``HB403`` for one in a
    department they do not supervise, and ``HB409`` naming whoever already holds
    it. ``pg_errors`` passes a custom code's message straight through, so the
    name in that sentence reaches the screen.
    """
    try:
        client.rpc(
            "take_up_complaint", {"p_complaint_id": complaint_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not take that complaint up."
        ) from exc
