"""`GET /events` -- the canonical live-update stream, and its deprecated alias.

The fan-out and the audience filter are tested against the real asyncio
machinery in ``tests/test_realtime.py``. What is left here is the HTTP surface:
the guard, the headers a stream has to get right, and the fact that the two
paths are one handler rather than two implementations that can drift.

The service layer is replaced with a generator that ends, because the real one
does not: a live stream yields a heartbeat every 20 seconds and never stops, so
a test that read it would block until the timeout rather than pass.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import events
from app.services import dashboard_service

PATHS = ["/api/v1/events", "/api/v1/dashboard/events"]


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stand in for the stream, recording what the router handed it."""
    seen: dict = {}

    async def fake_stream(membership, last_event_id) -> AsyncIterator[str]:
        seen["role"] = membership.role
        seen["membership_id"] = membership.id
        seen["community_id"] = membership.community_id
        seen["last_event_id"] = last_event_id
        yield "id: 1\nevent: notice.published\ndata: {}\n\n"

    monkeypatch.setattr(dashboard_service, "event_stream", fake_stream)
    return seen


@pytest.mark.parametrize("path", PATHS)
def test_the_stream_requires_a_session(api_client: TestClient, path: str) -> None:
    assert api_client.get(path).status_code == 401


@pytest.mark.parametrize("path", PATHS)
def test_a_resident_may_open_the_stream(
    resident_api_client: TestClient, captured: dict, path: str
) -> None:
    """The guard is membership, not role -- it always was. What changed in
    `0028` is that the rows now carry an audience, so letting a resident in is
    no longer the same thing as showing them their neighbours' join requests."""
    response = resident_api_client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "notice.published" in response.text


@pytest.mark.parametrize("path", PATHS)
def test_the_stream_is_never_cached_or_buffered(
    admin_api_client: TestClient, captured: dict, path: str
) -> None:
    """Both are load-bearing. A cached stream is served once and never updates;
    an nginx-buffered one shows the browser nothing until the buffer fills."""
    headers = admin_api_client.get(path).headers

    assert headers["cache-control"] == "no-cache"
    assert headers["x-accel-buffering"] == "no"


@pytest.mark.parametrize("path", PATHS)
def test_the_identity_comes_from_the_resolved_membership(
    resident_api_client: TestClient, captured: dict, path: str
) -> None:
    """All three values the audience filter runs on are read off the membership
    the dependency resolved out of Postgres. Nothing here is client-supplied."""
    resident_api_client.get(path)

    assert captured["role"] == "resident"
    assert captured["membership_id"] == "resident-membership-id"
    assert captured["community_id"] == "community-id"


@pytest.mark.parametrize("path", PATHS)
def test_last_event_id_is_forwarded_as_a_cursor(
    admin_api_client: TestClient, captured: dict, path: str
) -> None:
    admin_api_client.get(path, headers={"Last-Event-ID": "41"})

    assert captured["last_event_id"] == 41


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("raw", ["", "  ", "not-a-number", "-7", "9e9e9"])
def test_a_malformed_last_event_id_reconnects_from_zero_rather_than_422(
    admin_api_client: TestClient, captured: dict, path: str, raw: str
) -> None:
    """The header is written by the browser's own `EventSource`, not by
    application code. Refusing the reconnect would leave a client with no way
    back other than to stop sending a header it is required to send."""
    response = admin_api_client.get(path, headers={"Last-Event-ID": raw})

    assert response.status_code == 200
    assert captured["last_event_id"] == 0


def test_the_cursor_can_only_seek_never_widen() -> None:
    """A negative or absent value clamps to zero; a valid one is only ever a
    position in a stream the caller is already authorized for."""
    assert events.parse_last_event_id(None) == 0
    assert events.parse_last_event_id("-1") == 0
    assert events.parse_last_event_id("12") == 12


def test_the_old_path_is_marked_deprecated_and_the_new_one_is_not(
    api_client: TestClient,
) -> None:
    """A client generated from the spec should be steered to `/events`, and the
    admin frontend that is already on the old path should keep working."""
    paths = api_client.get("/openapi.json").json()["paths"]

    assert paths["/api/v1/dashboard/events"]["get"].get("deprecated") is True
    assert paths["/api/v1/events"]["get"].get("deprecated") is not True


def test_both_paths_declare_the_stream_media_type(api_client: TestClient) -> None:
    """FastAPI defaults an un-inferable return type to `application/json`, and a
    client generated from that would try to JSON-decode a live stream."""
    paths = api_client.get("/openapi.json").json()["paths"]

    for path in PATHS:
        content = paths[path]["get"]["responses"]["200"]["content"]
        assert "text/event-stream" in content
        assert "application/json" not in content
