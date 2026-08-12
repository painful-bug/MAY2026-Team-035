"""Direct messages: the chat dock's service.

The one piece of shaping that happens here is **counterpart resolution** — a
thread stores its pair in canonical order, and "who is this thread with"
depends on who is asking. The database cannot answer that per caller in a
view without recomputing it on every row for every reader; one comparison in
Python can.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.message_schemas import (
    DmMessage,
    DmRecipient,
    DmThread,
    DmThreadDetail,
    OpenThreadRequest,
    PostDmMessageRequest,
)
from app.repositories import messages_repository as repo
from supabase import Client


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_thread(row: dict[str, Any], *, profile_id: str) -> DmThread:
    a_id = str(row["participant_a_profile_id"])
    b_id = str(row["participant_b_profile_id"])
    a_name = str(row.get("participant_a_name") or "Someone")
    b_name = str(row.get("participant_b_name") or "Someone")
    mine_is_a = profile_id == a_id
    return DmThread(
        id=row["id"],
        community_id=row["community_id"],
        community_name=_text(row.get("community_name")),
        kind=str(row.get("kind") or "direct"),
        work_order_id=_text(row.get("work_order_id")),
        counterpart_profile_id=b_id if mine_is_a else a_id,
        counterpart_name=b_name if mine_is_a else a_name,
        participant_a_profile_id=a_id,
        participant_b_profile_id=b_id,
        participant_a_name=a_name,
        participant_b_name=b_name,
        locked_at=row.get("locked_at"),
        last_message_at=row.get("last_message_at"),
        last_message_body=_text(row.get("last_message_body")),
        created_at=row.get("created_at"),
    )


def _to_message(row: dict[str, Any]) -> DmMessage:
    return DmMessage(
        id=row["id"],
        thread_id=row["thread_id"],
        author_profile_id=_text(row.get("author_profile_id")),
        body=str(row.get("body") or ""),
        created_at=row.get("created_at"),
    )


def list_recipients(
    client: Client, *, community_id: str
) -> list[DmRecipient]:
    """The dock's "to" field: everyone the caller may open a thread with."""
    return [
        DmRecipient(
            profile_id=row["profile_id"],
            display_name=str(row.get("display_name") or "Someone"),
            label=str(row.get("label") or ""),
        )
        for row in repo.recipients(client, community_id=community_id)
    ]


def list_threads(client: Client, *, profile_id: str) -> list[DmThread]:
    """One mailbox across every community — RLS makes the list the caller's."""
    return [
        _to_thread(row, profile_id=profile_id) for row in repo.list_threads(client)
    ]


def get_thread(
    client: Client, *, profile_id: str, thread_id: str
) -> DmThreadDetail:
    """One thread with its messages, oldest first."""
    row = repo.get_thread(client, thread_id=thread_id)
    if row is None:
        raise NotFoundError("No such conversation.", code="thread_not_found")
    thread = _to_thread(row, profile_id=profile_id)
    messages = [
        _to_message(item)
        for item in repo.list_messages(client, thread_id=thread_id)
    ]
    return DmThreadDetail(**thread.model_dump(), messages=messages)


def open_thread(
    client: Client, *, profile_id: str, body: OpenThreadRequest
) -> DmThreadDetail:
    """Open (or return) a thread — a person, or a live job's channel.

    Exactly one subject, checked here so a request that cannot mean anything
    never reaches the database: a person needs the community that scopes the
    pair rule; a work order carries its own community.
    """
    wants_person = bool(body.recipient_profile_id)
    wants_job = bool(body.work_order_id)
    if wants_person == wants_job:
        raise ValidationError(
            "Name a recipient or a work order — exactly one.",
            code="thread_subject_required",
        )
    if wants_person and not body.community_id:
        raise ValidationError(
            "A direct thread needs the community you share.",
            code="community_id_required",
        )

    if wants_person:
        thread_id = repo.open_direct_thread(
            client,
            community_id=str(body.community_id),
            recipient_profile_id=str(body.recipient_profile_id),
        )
    else:
        thread_id = repo.open_work_order_thread(
            client, work_order_id=str(body.work_order_id)
        )
    return get_thread(client, profile_id=profile_id, thread_id=thread_id)


def post_message(
    client: Client, *, profile_id: str, thread_id: str, body: PostDmMessageRequest
) -> DmMessage:
    """Append one message.

    A locked thread comes back `409` from the RPC — the work-order lock is the
    feature, not an error to smooth over. The message is re-read through the
    view so the response is what the database stored.
    """
    message_id = repo.post_message(client, thread_id=thread_id, body=body.body)
    for row in repo.list_messages(client, thread_id=thread_id):
        if str(row.get("id")) == message_id:
            return _to_message(row)
    # The write succeeded and the read-back missed — surface it rather than
    # inventing a message the database may not have stored this way.
    raise NotFoundError(
        "Message sent but could not be read back.", code="message_not_found"
    )
