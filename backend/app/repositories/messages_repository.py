"""Data access for direct messages.

Reads go through ``dm_thread_overview`` and ``dm_message_overview``; every
write goes through the four SECURITY DEFINER functions in ``0046``. Neither
table carries an insert, update or delete policy.

**Every function here takes the caller's request client** — the RPCs and both
views resolve the caller from ``auth.uid()``, which does not exist on the
service client, and the RLS read policies are the mailbox's scoping.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_THREADS = "dm_thread_overview"
_MESSAGES = "dm_message_overview"

_THREAD_SELECT = (
    "id, community_id, community_name, kind, work_order_id, "
    "participant_a_profile_id, participant_b_profile_id, participant_a_name, "
    "participant_b_name, locked_at, last_message_at, last_message_body, "
    "created_at"
)

_MESSAGE_SELECT = "id, thread_id, author_profile_id, body, created_at"


def list_threads(client: Client) -> list[dict[str, Any]]:
    """Every thread the caller is in, most recent first.

    Unfiltered on purpose: the dock is one mailbox across every community the
    caller belongs to, and the RLS policy is what makes the list theirs.
    """
    return (
        client.table(_THREADS)
        .select(_THREAD_SELECT)
        .order("last_message_at", desc=True, nullsfirst=False)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


def get_thread(client: Client, *, thread_id: str) -> dict[str, Any] | None:
    """One thread, or ``None`` when the policy hides it from this caller."""
    rows = (
        client.table(_THREADS)
        .select(_THREAD_SELECT)
        .eq("id", thread_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_messages(
    client: Client, *, thread_id: str, limit: int = 200
) -> list[dict[str, Any]]:
    """The thread's messages, oldest first."""
    return (
        client.table(_MESSAGES)
        .select(_MESSAGE_SELECT)
        .eq("thread_id", thread_id)
        .order("created_at")
        .limit(limit)
        .execute()
        .data
        or []
    )


def recipients(client: Client, *, community_id: str) -> list[dict[str, Any]]:
    """Who the caller may open a thread with in one community (RPC)."""
    try:
        response = client.rpc(
            "dm_recipients", {"p_community_id": community_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not list who you can message."
        ) from exc
    return response.data or []


def open_direct_thread(
    client: Client, *, community_id: str, recipient_profile_id: str
) -> str:
    """One thread per pair per community, upserted (RPC)."""
    try:
        response = client.rpc(
            "open_direct_thread",
            {
                "p_community_id": community_id,
                "p_recipient_profile_id": recipient_profile_id,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not open that thread.") from exc
    return str(response.data or "")


def open_work_order_thread(client: Client, *, work_order_id: str) -> str:
    """The worker<->resident channel for one live job (RPC)."""
    try:
        response = client.rpc(
            "open_work_order_thread", {"p_work_order_id": work_order_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not open that thread.") from exc
    return str(response.data or "")


def post_message(client: Client, *, thread_id: str, body: str) -> str:
    """Append one message (RPC). ``HB409`` -> 409 when the thread is locked."""
    try:
        response = client.rpc(
            "post_dm_message", {"p_thread_id": thread_id, "p_body": body}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not send that message.") from exc
    return str(response.data or "")
