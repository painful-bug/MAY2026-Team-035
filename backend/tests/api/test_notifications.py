"""The notification feed and Web Push registration.

Three things are tested and they are worth keeping apart.

The **HTTP surface** -- who may call, which membership the query is scoped to,
what the response may not contain. The repository is replaced, and the
substitute records its arguments, which is how the recipient assertions are made.

The **projection** -- what a stored `payload` becomes. Those go through the
service directly: the interesting cases are payload shapes, and routing one
through a request would only add noise between the input and the assertion.

The **push configuration gate** -- that an environment with no VAPID keypair
returns 503 on the two endpoints that need one, and nothing else changes. That
is the whole of §10.5's "fail closed, but do not fail loudly", and it is the part
most likely to be broken by someone tidying the settings class later.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.push_config import get_push_settings
from app.repositories import notifications_repository, push_repository
from app.services import notifications_service

FEED = "/api/v1/notifications"
VAPID_KEY = "/api/v1/push/vapid-key"
SUBSCRIPTIONS = "/api/v1/push/subscriptions"

# Shaped like real ones -- unpadded base64url, 87 and 43 characters, which is a
# 65-byte P-256 point and a 32-byte scalar. Not a keypair: nothing in these tests
# signs anything, and a real private key has no business in a repository.
FAKE_PUBLIC_KEY = "B" + "x" * 86
FAKE_PRIVATE_KEY = "p" * 43


def row(**overrides: Any) -> dict[str, Any]:
    """One `notification_overview` row, as PostgREST would return it."""
    base: dict[str, Any] = {
        "id": "notification-id",
        "kind": "visitor.approval_requested",
        "payload": {
            "title": "Ravi is at the gate",
            "body": "Delivery for flat A-402",
            "url": "/resident/visitors/visit-id",
        },
        "read_at": None,
        "is_unread": True,
        "created_at": "2026-08-04T09:30:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def feed(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace the feed queries. Records arguments, returns what is staged."""
    captured: dict = {"rows": [row()], "total": 1, "unread": 1, "marked": True}

    def fake_list_feed(
        client: Any, *, membership_id: str, unread_only: bool, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        captured["membership_id"] = membership_id
        captured["unread_only"] = unread_only
        captured["offset"] = offset
        captured["limit"] = limit
        return captured["rows"], captured["total"]

    def fake_unread_count(client: Any, *, membership_id: str) -> int:
        captured["unread_for"] = membership_id
        return captured["unread"]

    def fake_mark_read(client: Any, *, notification_id: str) -> bool:
        captured["marked_id"] = notification_id
        return bool(captured["marked"])

    def fake_mark_all_read(client: Any, *, membership_id: str) -> int:
        captured["marked_all_for"] = membership_id
        return 4

    monkeypatch.setattr(notifications_repository, "list_feed", fake_list_feed)
    monkeypatch.setattr(notifications_repository, "unread_count", fake_unread_count)
    monkeypatch.setattr(notifications_repository, "mark_read", fake_mark_read)
    monkeypatch.setattr(notifications_repository, "mark_all_read", fake_mark_all_read)
    return captured


@pytest.fixture
def push_configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict]:
    """An environment with a usable VAPID keypair, and a stubbed subscription table."""
    monkeypatch.setenv("VAPID_PUBLIC_KEY", FAKE_PUBLIC_KEY)
    monkeypatch.setenv("VAPID_PRIVATE_KEY", FAKE_PRIVATE_KEY)
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:ops@example.test")
    get_push_settings.cache_clear()

    captured: dict = {}

    def fake_register(client: Any, **kwargs: Any) -> str:
        captured.update(kwargs)
        return "subscription-id"

    def fake_remove(client: Any, **kwargs: Any) -> int:
        captured.update(kwargs)
        captured["removed"] = True
        return 1

    monkeypatch.setattr(push_repository, "register_subscription", fake_register)
    monkeypatch.setattr(push_repository, "remove_subscription", fake_remove)
    yield captured
    get_push_settings.cache_clear()


@pytest.fixture
def push_unconfigured(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """An environment where nobody has generated a keypair."""
    for name in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(name, raising=False)
    get_push_settings.cache_clear()
    yield
    get_push_settings.cache_clear()


# ---------------------------------------------------------------------------
# The feed
# ---------------------------------------------------------------------------


def test_the_feed_requires_a_session(api_client: TestClient) -> None:
    assert api_client.get(FEED).status_code == 401


def test_a_resident_reads_their_own_feed(
    resident_api_client: TestClient, feed: dict
) -> None:
    response = resident_api_client.get(FEED)

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Ravi is at the gate"


def test_an_admin_has_a_feed_too(admin_api_client: TestClient, feed: dict) -> None:
    """`complaint.raised` and `access_request.created` are addressed to admins.
    A feed that refused them would mean building a second one later."""
    assert admin_api_client.get(FEED).status_code == 200


def test_the_recipient_is_the_resolved_membership(
    resident_api_client: TestClient, feed: dict
) -> None:
    resident_api_client.get(FEED)

    assert feed["membership_id"] == "resident-membership-id"


def test_a_query_parameter_cannot_choose_the_recipient(
    resident_api_client: TestClient, feed: dict
) -> None:
    """There is no recipient parameter, so nothing reads one. The RLS policy on
    `notifications` would refuse anyway -- this asserts the layer above it."""
    resident_api_client.get(f"{FEED}?membershipId=someone-else")

    assert feed["membership_id"] == "resident-membership-id"


def test_the_unread_filter_reaches_the_query(
    resident_api_client: TestClient, feed: dict
) -> None:
    resident_api_client.get(f"{FEED}?unread=true")

    assert feed["unread_only"] is True


def test_paging_is_translated_to_an_offset(
    resident_api_client: TestClient, feed: dict
) -> None:
    resident_api_client.get(f"{FEED}?page=3&pageSize=10")

    assert (feed["offset"], feed["limit"]) == (20, 10)


@pytest.mark.parametrize("query", ("page=0", "pageSize=0", "pageSize=101"))
def test_invalid_paging_is_rejected_before_the_feed_is_queried(
    resident_api_client: TestClient, feed: dict, query: str
) -> None:
    """The page bounds protect an endpoint whose backing table grows forever.

    Validation has to happen before either the page query or the badge-count
    query. Otherwise a malformed request can still spend database work even
    though its response is a 422.
    """
    response = resident_api_client.get(f"{FEED}?{query}")

    assert response.status_code == 422
    assert "membership_id" not in feed
    assert "unread_for" not in feed


def test_the_unread_count_is_the_whole_feed_not_the_page(
    resident_api_client: TestClient, feed: dict
) -> None:
    """A badge counts the feed. If it counted the page it would change as the
    resident scrolled, which is the bug this separate query exists to avoid."""
    feed["rows"] = [row(id="one"), row(id="two")]
    feed["total"] = 2
    feed["unread"] = 37

    body = resident_api_client.get(f"{FEED}?pageSize=2").json()

    assert body["total"] == 2
    assert body["unread"] == 37


def test_an_empty_feed_is_a_page_not_a_404(
    resident_api_client: TestClient, feed: dict
) -> None:
    feed["rows"] = []
    feed["total"] = 0
    feed["unread"] = 0

    response = resident_api_client.get(FEED)

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "pageSize": 20,
        "hasMore": False,
        "unread": 0,
    }


def test_the_feed_is_camel_case(resident_api_client: TestClient, feed: dict) -> None:
    item = resident_api_client.get(FEED).json()["items"][0]

    assert item["isUnread"] is True
    assert "is_unread" not in item
    assert "createdAt" in item


def test_the_raw_payload_never_reaches_the_client(
    resident_api_client: TestClient, feed: dict
) -> None:
    """The response carries rendered strings, not the stored document. This is
    what makes §10.8's one hard rule enforceable: a writer that puts a secret in
    `payload` finds it stays in the database."""
    feed["rows"] = [row(payload={"title": "Ravi is here", "securityCode": "8412"})]

    body = resident_api_client.get(FEED).text

    assert "8412" not in body
    assert "securityCode" not in body


# ---------------------------------------------------------------------------
# Marking read
# ---------------------------------------------------------------------------


def test_marking_read_returns_the_remaining_unread_count(
    resident_api_client: TestClient, csrf_headers: dict[str, str], feed: dict
) -> None:
    feed["unread"] = 2

    response = resident_api_client.post(
        f"{FEED}/notification-id/read", headers=csrf_headers
    )

    assert response.status_code == 200
    assert response.json() == {"marked": 1, "unread": 2}


def test_marking_someone_elses_notification_read_is_a_404(
    resident_api_client: TestClient, csrf_headers: dict[str, str], feed: dict
) -> None:
    """The RPC returns false for a row that does not exist and for one that is
    not the caller's, and both become the same 404. Distinguishing them would
    let a caller enumerate ids."""
    feed["marked"] = False

    response = resident_api_client.post(
        f"{FEED}/someone-elses-id/read", headers=csrf_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_marking_read_requires_csrf(
    resident_api_client: TestClient, feed: dict
) -> None:
    assert resident_api_client.post(f"{FEED}/notification-id/read").status_code == 403


def test_read_all_reports_what_moved_and_what_is_left(
    resident_api_client: TestClient, csrf_headers: dict[str, str], feed: dict
) -> None:
    """`unread` is re-read rather than assumed to be zero: a notification can
    arrive between the update and the count."""
    feed["unread"] = 1

    response = resident_api_client.post(f"{FEED}/read-all", headers=csrf_headers)

    assert response.status_code == 200
    assert response.json() == {"marked": 4, "unread": 1}
    assert feed["marked_all_for"] == "resident-membership-id"


# ---------------------------------------------------------------------------
# The projection
# ---------------------------------------------------------------------------


def test_a_payload_title_and_body_are_used_as_written() -> None:
    title, body, url = notifications_service.render(
        "notice.published",
        {"title": "Water cut", "body": "10am to noon", "url": "/notices/1"},
    )

    assert (title, body, url) == ("Water cut", "10am to noon", "/notices/1")


def test_a_missing_title_falls_back_to_one_derived_from_the_kind() -> None:
    """The writers arrive in later build steps. A kind whose author forgot a
    title should produce a dull row rather than a blank one -- an empty line in a
    feed reads as a bug in the app."""
    title, body, url = notifications_service.render("complaint.resolved", {})

    assert title == "Your complaint was resolved"
    assert (body, url) == ("", "")


def test_an_unknown_kind_still_renders() -> None:
    """Hiding it would mean a notification the system decided to send and the
    resident never learns exists."""
    title, _, _ = notifications_service.render("something.invented", None)

    assert title == "Update from your community"


def test_render_copies_no_field_it_was_not_asked_for() -> None:
    """The enforcement point for "the visitor security code may never appear in
    a push body" (§10.8). It is not a check -- there is simply no code path that
    copies a fourth key."""
    payload = {"title": "Ravi is at the gate", "securityCode": "8412", "otp": "1234"}

    rendered = notifications_service.render("visitor.approval_requested", payload)

    assert "8412" not in "".join(rendered)
    assert "1234" not in "".join(rendered)


def test_a_non_dict_payload_does_not_break_the_row() -> None:
    """`payload` is `jsonb` with no constraint, so a string or a list is
    representable even though nothing writes one."""
    title, body, url = notifications_service.render("notice.published", None)

    assert title == "New notice from your community"
    assert (body, url) == ("", "")


# ---------------------------------------------------------------------------
# Push registration
# ---------------------------------------------------------------------------


def test_the_vapid_key_is_served_to_a_member(
    resident_api_client: TestClient, push_configured: dict
) -> None:
    response = resident_api_client.get(VAPID_KEY)

    assert response.status_code == 200
    assert response.json() == {"publicKey": FAKE_PUBLIC_KEY}


def test_the_vapid_key_requires_a_session(
    api_client: TestClient, push_configured: dict
) -> None:
    """Public by construction, but an unauthenticated endpoint that names our
    push key is free reconnaissance for no benefit."""
    assert api_client.get(VAPID_KEY).status_code == 401


def test_the_private_key_is_never_served(
    resident_api_client: TestClient, push_configured: dict
) -> None:
    assert FAKE_PRIVATE_KEY not in resident_api_client.get(VAPID_KEY).text


def test_subscribing_accepts_the_browsers_own_document(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    push_configured: dict,
) -> None:
    """`PushSubscription.toJSON()`, posted unchanged. A transcription step is
    somewhere to put `auth` into the `p256dh` field, and that failure looks like
    a push that silently never decrypts."""
    response = resident_api_client.post(
        SUBSCRIPTIONS,
        headers=csrf_headers,
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
            "expirationTime": None,
            "keys": {"p256dh": "public-material", "auth": "auth-material"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"subscribed": True}
    assert push_configured["endpoint"] == "https://fcm.googleapis.com/fcm/send/abc"
    assert push_configured["p256dh"] == "public-material"
    assert push_configured["auth"] == "auth-material"


def test_a_subscription_is_bound_to_the_resolved_membership(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    push_configured: dict,
) -> None:
    """Nothing in the body says who this is for. If it did, one resident could
    subscribe a device to another's notifications."""
    resident_api_client.post(
        SUBSCRIPTIONS,
        headers=csrf_headers,
        json={
            "endpoint": "https://push.example.test/1",
            "keys": {"p256dh": "a", "auth": "b"},
        },
    )

    assert push_configured["membership_id"] == "resident-membership-id"


def test_a_subscription_without_keys_is_rejected(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    push_configured: dict,
) -> None:
    response = resident_api_client.post(
        SUBSCRIPTIONS,
        headers=csrf_headers,
        json={"endpoint": "https://push.example.test/1"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "keys",
    (
        {"p256dh": "", "auth": "auth-material"},
        {"p256dh": "public-material", "auth": ""},
    ),
)
def test_a_subscription_with_an_empty_encryption_key_is_rejected_before_storage(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    push_configured: dict,
    keys: dict[str, str],
) -> None:
    """An empty browser key would create a subscription that can never decrypt.

    This is deliberately a request-boundary test: the repository is never
    called, so an invalid browser document cannot replace a known-good device
    registration at the idempotent endpoint.
    """
    response = resident_api_client.post(
        SUBSCRIPTIONS,
        headers=csrf_headers,
        json={"endpoint": "https://push.example.test/1", "keys": keys},
    )

    assert response.status_code == 422
    assert push_configured == {}


def test_unsubscribing_takes_the_endpoint_in_the_body(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    push_configured: dict,
) -> None:
    """Not a query string: a push endpoint is a device identifier, and a request
    whose purpose is to stop tracking a device should not write it into every
    access log on the way."""
    response = resident_api_client.request(
        "DELETE",
        SUBSCRIPTIONS,
        headers=csrf_headers,
        json={"endpoint": "https://push.example.test/1"},
    )

    assert response.status_code == 200
    assert response.json() == {"subscribed": False}
    assert push_configured["removed"] is True


# ---------------------------------------------------------------------------
# Fail closed, but do not fail loudly
# ---------------------------------------------------------------------------


def test_the_vapid_key_is_a_503_when_push_is_not_configured(
    resident_api_client: TestClient, push_unconfigured: None
) -> None:
    response = resident_api_client.get(VAPID_KEY)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "push_not_configured"


def test_subscribing_is_a_503_when_push_is_not_configured(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    push_unconfigured: None,
) -> None:
    """A subscription created against no keypair is bound to nothing, and the
    resident would have spent a notification permission prompt on a channel that
    can never deliver."""
    response = resident_api_client.post(
        SUBSCRIPTIONS,
        headers=csrf_headers,
        json={
            "endpoint": "https://push.example.test/1",
            "keys": {"p256dh": "a", "auth": "b"},
        },
    )

    assert response.status_code == 503


def test_unsubscribing_works_without_a_keypair(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    push_unconfigured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Turning notifications off must not depend on an operator not having lost
    a key."""
    monkeypatch.setattr(
        push_repository, "remove_subscription", lambda *a, **k: 1
    )

    response = resident_api_client.request(
        "DELETE",
        SUBSCRIPTIONS,
        headers=csrf_headers,
        json={"endpoint": "https://push.example.test/1"},
    )

    assert response.status_code == 200


def test_the_rest_of_the_api_is_unaffected_by_missing_push_configuration(
    resident_api_client: TestClient, push_unconfigured: None, feed: dict
) -> None:
    """Push is an enhancement. An unconfigured environment must not be a broken
    environment -- the same shape as `0024` no-opping without `pg_cron`."""
    assert resident_api_client.get(FEED).status_code == 200
