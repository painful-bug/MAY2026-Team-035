"""Web Push registration, and the payload a push carries.

``docs/design/RESIDENT_BACKEND_DESIGN.md`` §5.11, §10.5 and §10.8. Standards Web
Push over our own VAPID keypair -- no vendor account, no SDK in the frontend
bundle, and no third party ever learns who visited which flat and when.

**The push body carries the detail** (`PO`, 2026-08-04). ``US-2.1``'s recorded
pain point is a notification that produces *"only a notification sound without
displaying the actual notification"*, so a generic "open the app" push would be a
milder version of the exact failure the story exists to fix -- and a resident
being asked to approve or reject someone needs the name to decide.

The privacy objection does not survive contact with the protocol: RFC 8291
encrypts the payload end to end between this server and the browser, keyed to the
subscription's own material, so Google, Mozilla and Apple relay ciphertext they
cannot read. That property is precisely what §5.11 paid for by rejecting
OneSignal; having paid for it, we use it.

**One thing may never appear in a push body: the visitor security code.** §5.4
makes it a hashed credential returned exactly once, and a credential on a lock
screen is a credential readable by anyone holding the phone. That rule is
enforced by construction rather than by review -- see
``notifications_service.render``, which reads three keys and copies nothing else.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ServiceUnavailableError
from app.core.push_config import get_push_settings
from app.domain.notification_schemas import (
    PushSubscriptionResult,
    RegisterPushSubscription,
    UnregisterPushSubscription,
    VapidPublicKey,
)
from app.repositories import push_repository as repo
from app.services import notifications_service
from supabase import Client

#: The stable code a client branches on when push is not configured. Prose in
#: `message` may be reworded; this may not.
PUSH_NOT_CONFIGURED = "push_not_configured"


def _require_configured() -> None:
    """503 unless a usable keypair is present.

    Fails closed but not loudly: this is the only thing that breaks in an
    environment with no VAPID keys. Push is an enhancement, so an unconfigured
    environment must not be a broken environment -- the same shape as ``0024``
    scheduling under ``pg_cron`` when the extension exists and no-opping when it
    does not.

    The message says nothing about *which* value is missing. That is an
    operator's business, discoverable from the startup log, and a caller cannot
    act on it.
    """
    if not get_push_settings().enabled:
        raise ServiceUnavailableError(
            "Push notifications are not configured on this server.",
            code=PUSH_NOT_CONFIGURED,
        )


def public_key() -> VapidPublicKey:
    """The public half of the keypair, for ``PushManager.subscribe``.

    A client must compare this against the ``applicationServerKey`` its stored
    subscription was created with and re-subscribe when they differ. Without that
    check a key rotation stops push permanently and *silently*: subscriptions are
    bound to the key that created them, the protocol offers no dual-key period,
    and nothing anywhere reports an error (§10.5).
    """
    _require_configured()
    return VapidPublicKey(public_key=get_push_settings().vapid_public_key)


def register(
    client: Client, *, membership_id: str, body: RegisterPushSubscription
) -> PushSubscriptionResult:
    """Register this browser against the caller's membership.

    Requires push to be configured, even though the row could be stored without
    it. A subscription created while the server has no keypair is a subscription
    bound to nothing, and the resident would have granted notification permission
    for a channel that can never deliver -- a permission prompt is expensive
    enough that spending one on nothing is worse than a 503.
    """
    _require_configured()
    repo.register_subscription(
        client,
        membership_id=membership_id,
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        user_agent=body.user_agent,
    )
    return PushSubscriptionResult(subscribed=True)


def unregister(
    client: Client, *, membership_id: str, body: UnregisterPushSubscription
) -> PushSubscriptionResult:
    """Stop pushing to this browser.

    Deliberately **not** gated on push being configured, and deliberately a 200
    even when nothing was deleted. Both follow from what this endpoint is for: a
    resident turning notifications off. Refusing because the server lost its
    keypair, or erroring because the row had already gone, would leave them
    unable to complete the one action they asked for.
    """
    repo.remove_subscription(
        client, membership_id=membership_id, endpoint=body.endpoint
    )
    return PushSubscriptionResult(subscribed=False)


def push_payload(row: dict[str, Any]) -> dict[str, Any]:
    """What the service worker receives, built from the stored notification.

    Rendered through ``notifications_service.render`` -- the same call the feed
    row uses -- so the line on the lock screen and the line in the list can never
    tell different stories about one event (§10.8).

    ``tag`` lets the browser coalesce: three gate attempts for one visitor should
    collapse into one notification rather than stack into three. A writer opts in
    by putting the entity id in ``payload.tag``; without one the notification id
    is used, which is unique and therefore never coalesces. That is the right
    default -- wrongly merging two different complaints into one line loses a
    notification, while wrongly showing two lines only costs a scroll.

    Still an id and rendered strings, never a record: push payloads are capped at
    about 4 KB after encryption, and the authoritative read is
    ``GET /notifications``, where the ownership predicate lives.
    """
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    kind = str(row.get("kind") or "")
    notification_id = str(row.get("notification_id") or row.get("id") or "")
    title, body, url = notifications_service.render(kind, payload)
    return {
        "title": title,
        "body": body,
        "tag": str(payload.get("tag") or notification_id),
        "data": {
            "notificationId": notification_id,
            "kind": kind,
            "url": url,
        },
    }
