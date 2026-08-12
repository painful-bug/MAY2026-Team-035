"""The Web Push sender.

What is covered, stated plainly because it is easy to overclaim: **this exercises
our half.** The HTTP call to Google, Mozilla or Apple is replaced, and no browser
is involved -- there is no service worker in the frontend yet (§10.6), so push
ships backend-complete and unverifiable end to end until one exists. What is
tested is claiming, payload construction, per-subscription isolation, and the
failure rules -- which is where the decisions are.

The rule these tests exist to protect is the one the SSE hub does not have:

    The hub may drop. The sender may not duplicate.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core import supabase_client
from app.core.push import PushSender
from app.core.push_config import get_push_settings
from app.repositories import push_repository
from app.services import push_service

FAKE_PUBLIC_KEY = "B" + "x" * 86
FAKE_PRIVATE_KEY = "p" * 43


def claimed(**overrides: Any) -> dict[str, Any]:
    """One row as `claim_push_batch` returns it."""
    base: dict[str, Any] = {
        "notification_id": "notification-id",
        "profile_id": "resident-profile-id",
        "kind": "visitor.approval_requested",
        "payload": {
            "title": "Ravi is at the gate",
            "body": "Delivery for flat A-402",
            "url": "/resident/visitors/visit-id",
        },
        "created_at": "2026-08-04T09:30:00Z",
    }
    base.update(overrides)
    return base


def subscription(endpoint: str = "https://push.example.test/1") -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "p256dh_key": "public-material",
        "auth_key": "auth-material",
    }


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", FAKE_PUBLIC_KEY)
    monkeypatch.setenv("VAPID_PRIVATE_KEY", FAKE_PRIVATE_KEY)
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:ops@example.test")
    get_push_settings.cache_clear()
    monkeypatch.setattr(supabase_client, "get_service_client", lambda: object())
    yield
    get_push_settings.cache_clear()


@pytest.fixture
def unconfigured(monkeypatch: pytest.MonkeyPatch):
    for name in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(name, raising=False)
    get_push_settings.cache_clear()
    yield
    get_push_settings.cache_clear()


# ---------------------------------------------------------------------------
# Starting, and not starting
# ---------------------------------------------------------------------------


def test_the_sender_does_not_start_without_a_keypair(unconfigured: None) -> None:
    """Not an error. An environment with no VAPID keys is one where push is off,
    not one that is broken -- the same shape as `0024` no-opping without
    `pg_cron`."""
    sender = PushSender()

    asyncio.run(sender.start())

    assert sender.running is False


def test_the_sender_starts_when_configured(configured: None) -> None:
    async def run() -> bool:
        sender = PushSender()
        await sender.start()
        started = sender.running
        await sender.stop()
        return started

    assert asyncio.run(run()) is True


@pytest.mark.parametrize(
    "problem",
    [
        {"VAPID_SUBJECT": "ops@example.test"},  # no scheme
        {"VAPID_PUBLIC_KEY": "not+base64url/"},
        {"VAPID_PRIVATE_KEY": "tooshort"},
    ],
)
def test_malformed_configuration_is_treated_as_no_configuration(
    configured: None, monkeypatch: pytest.MonkeyPatch, problem: dict[str, str]
) -> None:
    """Checked at startup so the answer is known before a resident subscribes,
    rather than discovered on the first send -- a browser allowed to subscribe
    against a key we cannot sign with silently never receives anything."""
    for name, value in problem.items():
        monkeypatch.setenv(name, value)
    get_push_settings.cache_clear()

    assert get_push_settings().enabled is False


def test_the_configuration_problem_never_echoes_key_material(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It is written to a log line. Half a private key in a log file is a leaked
    private key."""
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "short+not+base64url")
    get_push_settings.cache_clear()

    problem = get_push_settings().configuration_problem() or ""

    assert "short+not+base64url" not in problem


# ---------------------------------------------------------------------------
# What a push carries
# ---------------------------------------------------------------------------


def test_the_push_is_rendered_from_the_stored_notification() -> None:
    """One source, so the feed row and the lock-screen line can never tell
    different stories about the same event (§10.8)."""
    payload = push_service.push_payload(claimed())

    assert payload["title"] == "Ravi is at the gate"
    assert payload["body"] == "Delivery for flat A-402"
    assert payload["data"]["url"] == "/resident/visitors/visit-id"


def test_the_push_carries_the_detail_rather_than_open_the_app() -> None:
    """`US-2.1`'s pain point is a notification that makes a sound and shows
    nothing. A generic push would be a milder version of the exact failure the
    story exists to fix, and a resident being asked to approve someone needs the
    name to decide."""
    payload = push_service.push_payload(claimed())

    assert "Ravi" in payload["title"]
    assert payload["title"] != "Update from your community"


def test_a_push_never_carries_a_field_it_was_not_asked_for() -> None:
    """The one thing that may never appear in a push body is the visitor
    security code (§5.4, §10.8). Enforced by construction: the renderer reads
    three keys and copies nothing else."""
    row = claimed(payload={"title": "Ravi is here", "securityCode": "8412"})

    payload = push_service.push_payload(row)

    assert "8412" not in repr(payload)
    assert set(payload) == {"title", "body", "tag", "data"}
    assert set(payload["data"]) == {"notificationId", "kind", "url"}


def test_the_tag_defaults_to_the_notification_id() -> None:
    """Unique, so it never coalesces. Wrongly merging two complaints into one
    line loses a notification; wrongly showing two lines costs a scroll."""
    assert push_service.push_payload(claimed())["tag"] == "notification-id"


def test_a_writer_opts_into_coalescing_with_a_tag() -> None:
    """Three gate attempts for one visitor should collapse into one
    notification, not stack into three."""
    row = claimed(payload={"title": "Ravi is at the gate", "tag": "visit-id"})

    assert push_service.push_payload(row)["tag"] == "visit-id"


# ---------------------------------------------------------------------------
# Delivery outcomes
# ---------------------------------------------------------------------------


def _record(monkeypatch: pytest.MonkeyPatch) -> dict:
    outcomes: dict = {"success": [], "failure": []}
    monkeypatch.setattr(
        push_repository,
        "record_success",
        lambda client, *, endpoint: outcomes["success"].append(endpoint),
    )
    monkeypatch.setattr(
        push_repository,
        "record_failure",
        lambda client, *, endpoint, gone: outcomes["failure"].append((endpoint, gone)),
    )
    return outcomes


def test_a_delivered_push_clears_the_failure_streak(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcomes = _record(monkeypatch)
    sender = PushSender()
    monkeypatch.setattr(sender, "_post", lambda *a, **k: None)

    sender._send_one(subscription(), "{}")

    assert outcomes["success"] == ["https://push.example.test/1"]
    assert outcomes["failure"] == []


@pytest.mark.parametrize("status", [404, 410])
def test_a_gone_subscription_is_deleted_not_retried(
    configured: None, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """Retrying a dead endpoint forever is how you get rate-limited by a push
    service, and no amount of retrying revives it."""
    outcomes = _record(monkeypatch)
    sender = PushSender()
    monkeypatch.setattr(sender, "_post", lambda *a, **k: status)

    sender._send_one(subscription(), "{}")

    assert outcomes["failure"] == [("https://push.example.test/1", True)]


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_transient_failure_is_counted_not_deleted(
    configured: None, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """The subscription is dropped after five of these, in SQL. Nothing here
    retries the send: the next notification is the retry, because retrying one
    against a struggling service is how a backlog becomes a herd."""
    outcomes = _record(monkeypatch)
    sender = PushSender()
    monkeypatch.setattr(sender, "_post", lambda *a, **k: status)

    sender._send_one(subscription(), "{}")

    assert outcomes["failure"] == [("https://push.example.test/1", False)]


# ---------------------------------------------------------------------------
# One notification, several devices
# ---------------------------------------------------------------------------


def test_every_registered_device_is_sent_to(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resident with a phone and a laptop has two subscriptions and both
    should buzz."""
    sent: list[str] = []
    monkeypatch.setattr(
        push_repository,
        "subscriptions_for",
        lambda client, *, profile_id: [
            subscription("https://push.example.test/phone"),
            subscription("https://push.example.test/laptop"),
        ],
    )
    sender = PushSender()
    monkeypatch.setattr(
        sender, "_send_one", lambda sub, body: sent.append(sub["endpoint"])
    )

    asyncio.run(sender._deliver(claimed()))

    assert sorted(sent) == [
        "https://push.example.test/laptop",
        "https://push.example.test/phone",
    ]


def test_one_dead_device_does_not_stop_the_others(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each subscription is dispatched with its exception captured, so a
    subscription that raises cannot stall a batch."""
    sent: list[str] = []
    monkeypatch.setattr(
        push_repository,
        "subscriptions_for",
        lambda client, *, profile_id: [
            subscription("https://push.example.test/broken"),
            subscription("https://push.example.test/fine"),
        ],
    )
    sender = PushSender()

    def send_one(sub: dict[str, Any], body: str) -> None:
        if sub["endpoint"].endswith("broken"):
            raise RuntimeError("this device explodes")
        sent.append(sub["endpoint"])

    monkeypatch.setattr(sender, "_send_one", send_one)

    asyncio.run(sender._deliver(claimed()))

    assert sent == ["https://push.example.test/fine"]


def test_a_recipient_with_no_devices_is_not_an_error(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ordinary case for a resident who never granted permission. The
    notification is in the feed; there is simply no phone to reach."""
    monkeypatch.setattr(
        push_repository, "subscriptions_for", lambda client, *, profile_id: []
    )
    sender = PushSender()
    monkeypatch.setattr(
        sender,
        "_send_one",
        lambda *a, **k: pytest.fail("nothing should be sent"),
    )

    asyncio.run(sender._deliver(claimed()))


def test_a_claimed_row_without_a_recipient_is_skipped(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        push_repository,
        "subscriptions_for",
        lambda client, *, profile_id: pytest.fail("should not be reached"),
    )

    asyncio.run(PushSender()._deliver(claimed(profile_id=None)))
