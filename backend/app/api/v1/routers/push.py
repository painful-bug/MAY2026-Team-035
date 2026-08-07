"""Web Push registration.

Three routes, all of them plumbing: hand the browser the public key it needs to
subscribe, store what it gets back, and remove it when the resident turns
notifications off. The interesting decisions are in ``push_service`` and §10.5 of
the design.

**Everything here returns 503 ``push_not_configured`` in an environment with no
VAPID keypair, and nothing else in the product notices.** Push is an
enhancement; an unconfigured environment must not be a broken environment.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_active_membership, get_request_client
from app.domain.notification_schemas import (
    PushSubscriptionResult,
    RegisterPushSubscription,
    UnregisterPushSubscription,
    VapidPublicKey,
)
from app.domain.schemas import MembershipContext
from app.services import push_service
from supabase import Client

router = APIRouter(tags=["push"], dependencies=[Depends(require_csrf_unsafe)])


@router.get(
    "/push/vapid-key",
    response_model=VapidPublicKey,
    summary="Public key for PushManager.subscribe",
)
async def vapid_key(
    _: MembershipContext = Depends(get_active_membership),
) -> VapidPublicKey:
    """The public half of this server's VAPID keypair.

    Public by construction -- that is what the pair is for -- but still behind a
    membership guard, because an unauthenticated endpoint that names your push
    key is free reconnaissance for no benefit.

    **A client must re-read this on load and compare it against the
    `applicationServerKey` its stored subscription was created with.** A
    subscription is bound to the key that created it, the protocol offers no
    dual-key period, and a rotation therefore stops push permanently and
    silently -- no error anywhere, pushes simply stop arriving.
    """
    return push_service.public_key()


@router.post(
    "/push/subscriptions",
    response_model=PushSubscriptionResult,
    summary="Register a browser for push",
)
async def subscribe(
    body: RegisterPushSubscription,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> PushSubscriptionResult:
    """Register the calling browser against the caller's membership.

    The body is `PushSubscription.toJSON()` unchanged, so the frontend posts what
    the Push API handed it rather than transcribing it -- a transcription step is
    somewhere to put `auth` into the `p256dh` field, and that failure looks like
    a push that silently never decrypts.

    **Idempotent on `endpoint`.** The browser re-subscribes after every
    service-worker update and after any key rotation, and each of those refreshes
    the row rather than adding one. A repeat is a 200, not a 409: the client is
    describing a state, not creating a resource.
    """
    return push_service.register(
        client, membership_id=membership.id, body=body
    )


@router.delete(
    "/push/subscriptions",
    response_model=PushSubscriptionResult,
    summary="Unregister a browser",
)
async def unsubscribe(
    body: UnregisterPushSubscription,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> PushSubscriptionResult:
    """Stop pushing to one browser.

    **The endpoint arrives in a body, not a query string**, which is unusual for
    a `DELETE` and deliberate. A push endpoint URL is a device identifier; in a
    query string it lands in every access log and proxy trace between here and
    the browser, for a request whose whole purpose is to stop tracking that
    device. A `DELETE` body is legal but not universally respected by HTTP
    clients, so this was checked rather than assumed: `frontend/src/lib/api/
    client.js` spreads its options straight into `fetch`, which sends it. If a
    future client drops it, the fix is a second path, not a query parameter.

    Always a 200, even when the row had already gone, and it works whether or not
    the server has a VAPID keypair. This is a resident turning notifications off:
    an error because the state was already reached, or because an operator lost a
    key, would leave them unable to do the one thing they asked for.
    """
    return push_service.unregister(
        client, membership_id=membership.id, body=body
    )
