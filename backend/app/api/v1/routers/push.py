"""Web Push registration.

Three routes, all of them plumbing: hand the browser the public key it needs to
subscribe, store what it gets back, and remove it when the resident turns
notifications off. Removal is a ``POST`` to ``/push/subscriptions/unregister``
rather than a ``DELETE``, for the reason recorded on that route. The interesting
decisions are in ``push_service`` and §10.5 of the design.

**Everything here returns 503 ``push_not_configured`` in an environment with no
VAPID keypair, and nothing else in the product notices.** Push is an
enhancement; an unconfigured environment must not be a broken environment.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_current_user, get_request_client
from app.domain.notification_schemas import (
    PushSubscriptionResult,
    RegisterPushSubscription,
    UnregisterPushSubscription,
    VapidPublicKey,
)
from app.domain.schemas import Principal
from app.services import push_service
from supabase import Client

router = APIRouter(tags=["push"], dependencies=[Depends(require_csrf_unsafe)])


@router.get(
    "/push/vapid-key",
    response_model=VapidPublicKey,
    summary="Public key for PushManager.subscribe",
)
def vapid_key(
    _principal: Principal = Depends(get_current_user),
) -> VapidPublicKey:
    """The public half of this server's VAPID keypair.

    Public by construction -- that is what the pair is for -- but still behind a
    sign-in guard, because an unauthenticated endpoint that names your push key
    is free reconnaissance for no benefit. Identity rather than membership,
    matching the two routes below: a caller who may subscribe must be able to
    read the key they subscribe with.

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
def subscribe(
    body: RegisterPushSubscription,
    _principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> PushSubscriptionResult:
    """Register the calling browser against the signed-in person.

    **Identity is the whole guard, and no membership is required.** Since
    ``0041`` a push subscription is keyed on the profile, so this works for a
    service provider who has registered and not yet been hired -- the caller for
    whom out-of-app delivery matters most, because what they are waiting for
    arrives while the app is closed.

    The body is `PushSubscription.toJSON()` unchanged, so the frontend posts what
    the Push API handed it rather than transcribing it -- a transcription step is
    somewhere to put `auth` into the `p256dh` field, and that failure looks like
    a push that silently never decrypts.

    **Idempotent on `endpoint`.** The browser re-subscribes after every
    service-worker update and after any key rotation, and each of those refreshes
    the row rather than adding one. A repeat is a 200, not a 409: the client is
    describing a state, not creating a resource.
    """
    return push_service.register(client, body=body)


@router.post(
    "/push/subscriptions/unregister",
    response_model=PushSubscriptionResult,
    summary="Unregister a browser",
)
def unsubscribe(
    body: UnregisterPushSubscription,
    _principal: Principal = Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> PushSubscriptionResult:
    """Stop pushing to one browser.

    **The endpoint arrives in a body**, because a push endpoint URL is a device
    identifier: in a query string or a path segment it lands in every access log
    and proxy trace between here and the browser, for a request whose whole
    purpose is to stop tracking that device.

    **A removal that carries a body is a `POST` to a sub-path, not a `DELETE`.**
    RFC 9110 leaves content on a `DELETE` with no defined semantics -- clients
    may refuse to send it, intermediaries may strip it, and OpenAPI tooling
    warns on it -- so the one method whose body is guaranteed to arrive carries
    it instead. That is the second path this endpoint's design always named as
    the remedy, chosen over a query parameter, which would have put the device
    identifier back in the logs.

    Always a 200, even when the row had already gone, and it works whether or not
    the server has a VAPID keypair. This is a resident turning notifications off:
    an error because the state was already reached, or because an operator lost a
    key, would leave them unable to do the one thing they asked for.
    """
    return push_service.unregister(client, body=body)
