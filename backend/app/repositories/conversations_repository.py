"""Data access for hiring conversations.

Reads go through ``conversation_overview`` and
``conversation_message_overview``; both writes go through the two SECURITY
DEFINER functions in ``0038`` 5. Neither table carries an insert, update or
delete policy, so there is no path from this process to a row those functions
did not write.

**Every function here takes the caller's request client**, for the reason
``hiring_repository`` states: both RPCs and both views resolve the caller from
``auth.uid()``, which does not exist on the service client.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_CONVERSATIONS = "conversation_overview"
_MESSAGES = "conversation_message_overview"

#: Listed rather than ``*`` so a column added to the view later does not
#: silently widen the response.
_CONVERSATION_SELECT = (
    "id, community_id, community_name, department_id, department_name, "
    "department_kind, service_provider_id, provider_display_name, "
    "provider_headline, provider_profile_id, last_message_body, "
    "message_count, last_message_at, created_at"
)

_MESSAGE_SELECT = (
    "id, conversation_id, body, author_side, author_name, author_profile_id, "
    "created_at"
)


def list_conversations(
    client: Client, *, department_id: str | None = None
) -> list[dict[str, Any]]:
    """Every thread the caller is in, most recent first.

    Unfiltered by default, and that is the point: a provider working for four
    societies has one inbox, and the RLS policy on ``conversations`` is what
    makes it their four rather than everyone's. ``department_id`` narrows it for
    the manager's side, where a department screen wants only its own.
    """
    query = client.table(_CONVERSATIONS).select(_CONVERSATION_SELECT)
    if department_id:
        query = query.eq("department_id", department_id)
    return (
        query.order("last_message_at", desc=True, nullsfirst=False)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


def get_conversation(
    client: Client, *, conversation_id: str
) -> dict[str, Any] | None:
    """One thread, or ``None`` when the policy hides it from this caller."""
    rows = (
        client.table(_CONVERSATIONS)
        .select(_CONVERSATION_SELECT)
        .eq("id", conversation_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_messages(
    client: Client, *, conversation_id: str, limit: int
) -> list[dict[str, Any]]:
    """The thread's messages, oldest first."""
    return (
        client.table(_MESSAGES)
        .select(_MESSAGE_SELECT)
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(limit)
        .execute()
        .data
        or []
    )


def get_message(client: Client, *, message_id: str) -> dict[str, Any] | None:
    """One message, or ``None`` when the policy hides its thread."""
    rows = (
        client.table(_MESSAGES)
        .select(_MESSAGE_SELECT)
        .eq("id", message_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def open_conversation(
    client: Client, *, department_id: str, service_provider_id: str
) -> str:
    """Return the thread for this pair, creating it if it is new (RPC).

    Idempotent. Two managers opening the same chat get the same id, so a client
    may call this every time it renders the button rather than remembering
    whether it has been called.
    """
    try:
        response = client.rpc(
            "open_conversation",
            {
                "p_department_id": department_id,
                "p_service_provider_id": service_provider_id,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not open that conversation."
        ) from exc
    return str(response.data or "")


def post_message(client: Client, *, conversation_id: str, body: str) -> str:
    """Append one message (RPC). Returns its id."""
    try:
        response = client.rpc(
            "post_conversation_message",
            {"p_conversation_id": conversation_id, "p_body": body},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not send that message.") from exc
    return str(response.data or "")
