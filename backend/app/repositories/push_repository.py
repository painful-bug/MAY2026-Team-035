"""Data access for Web Push subscriptions and the sender's claim.

Every function here goes through an RPC, and for once that is not the house
style being applied uniformly -- ``push_subscriptions`` has **RLS enabled with no
policy**, so there is no direct read or write of this table from any client the
API holds. ``service_role`` bypasses RLS and is what the sender uses; everything
a resident does reaches the table through a SECURITY DEFINER function that checks
``is_own_membership`` first.

The reason is what the table stores. ``p256dh_key`` and ``auth_key`` are the
browser's encryption material: a table any authenticated user could read is a
table from which an attacker collects the ability to push notifications to other
residents' phones as us. Compare ``0024``, which enabled RLS on ``sse_events``
for a milder version of the same problem.

Two clients appear in this module, and which one a function takes is part of its
meaning. ``register_subscription`` and ``remove_subscription`` take the caller's
request client, because the ownership check inside the function reads
``auth.uid()`` and there is no such thing on the service client. ``claim_batch``
and the outcome recorders take the service client, because the sender runs
without any request at all -- which is the whole point of out-of-app delivery.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_SUBSCRIPTIONS = "push_subscriptions"

#: Enough to encrypt and address one push, and nothing else. `failure_count` and
#: `last_success_at` are the sender's bookkeeping and never leave the database.
_SUBSCRIPTION_SELECT = "endpoint, p256dh_key, auth_key"


def register_subscription(
    client: Client,
    *,
    membership_id: str,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None,
) -> str:
    """Register or refresh this browser (RPC). Returns the subscription id.

    Idempotent on ``endpoint``: the browser re-subscribes after every
    service-worker update and after any VAPID key rotation, and each of those has
    to refresh the row rather than add one.
    """
    try:
        response = client.rpc(
            "register_push_subscription",
            {
                "p_membership_id": membership_id,
                "p_endpoint": endpoint,
                "p_p256dh": p256dh,
                "p_auth": auth,
                "p_user_agent": user_agent,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not register for push notifications."
        ) from exc
    return str(response.data or "")


def remove_subscription(
    client: Client, *, membership_id: str, endpoint: str
) -> int:
    """Unregister this browser (RPC). Returns how many rows went."""
    try:
        response = client.rpc(
            "delete_push_subscription",
            {"p_membership_id": membership_id, "p_endpoint": endpoint},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not remove the push subscription."
        ) from exc
    return int(response.data or 0)


def subscriptions_for(
    client: Client, *, membership_id: str
) -> list[dict[str, Any]]:
    """Every browser this member has registered. Service client only."""
    return (
        client.table(_SUBSCRIPTIONS)
        .select(_SUBSCRIPTION_SELECT)
        .eq("membership_id", membership_id)
        .execute()
        .data
        or []
    )


def claim_batch(client: Client, *, limit: int) -> list[dict[str, Any]]:
    """Atomically claim un-pushed notifications from the last hour (RPC).

    ``for update skip locked`` inside the function is what makes two sender
    processes safe: the second one's select walks past the rows the first has
    locked rather than waiting for them and then sending them again.
    """
    response = client.rpc("claim_push_batch", {"p_limit": limit}).execute()
    return response.data or []


def record_success(client: Client, *, endpoint: str) -> None:
    """The push was accepted: clear the failure streak."""
    client.rpc("record_push_success", {"p_endpoint": endpoint}).execute()


def record_failure(client: Client, *, endpoint: str, gone: bool) -> None:
    """The push was not accepted.

    ``gone`` is the ``404``/``410`` case, where the push service is telling us
    the subscription no longer exists; the function deletes the row. Anything
    else increments a counter and drops the row after five, because a
    subscription that has failed five times running is not coming back and
    retrying a dead endpoint forever is how you get rate-limited.
    """
    client.rpc(
        "record_push_failure", {"p_endpoint": endpoint, "p_gone": gone}
    ).execute()
