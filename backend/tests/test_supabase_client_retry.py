"""Retry behavior of the Supabase httpx transport.

Live testing on Windows showed intermittent ``httpx.ReadError: [WinError
10035]`` (WSAEWOULDBLOCK) from stale keep-alive connections to the hosted
Supabase project, surfacing as user-visible 500s even though an immediate
retry of the same request succeeds. ``_TransientRetryTransport`` absorbs that
class of transient socket failure with a bounded retry; these tests pin down
which (method, error) combinations are replayed and which must not be.
"""

from __future__ import annotations

import httpx
import pytest
from app.core.supabase_client import (
    _build_http_client,
    _TransientRetryTransport,
)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("app.core.supabase_client.time.sleep", lambda _s: None)


def _make_transport(monkeypatch, outcomes):
    """Build a retry transport whose underlying attempts yield ``outcomes``.

    Each entry is either an exception instance (raised) or an
    ``httpx.Response`` (returned). Attempts beyond the list fail the test.
    """
    transport = _TransientRetryTransport()
    attempts = []

    def fake_handle(self, request):
        assert len(attempts) < len(outcomes), "more attempts than scripted"
        attempts.append(request.method)
        outcome = outcomes[len(attempts) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fake_handle)
    return transport, attempts


def _request(method: str) -> httpx.Request:
    return httpx.Request(method, "https://example.supabase.co/rest/v1/thing")


def test_get_retries_read_error_then_succeeds(monkeypatch):
    ok = httpx.Response(200)
    transport, attempts = _make_transport(
        monkeypatch,
        [
            httpx.ReadError(
                "[WinError 10035] A non-blocking socket operation could not be "
                "completed immediately"
            ),
            httpx.ReadError("[WinError 10035] ..."),
            ok,
        ],
    )
    assert transport.handle_request(_request("GET")) is ok
    assert attempts == ["GET", "GET", "GET"]


def test_get_gives_up_after_bounded_attempts(monkeypatch):
    errors = [httpx.ReadError("[WinError 10035]") for _ in range(3)]
    transport, attempts = _make_transport(monkeypatch, errors)
    with pytest.raises(httpx.ReadError):
        transport.handle_request(_request("GET"))
    assert attempts == ["GET", "GET", "GET"]


def test_post_read_error_is_not_replayed(monkeypatch):
    """A POST whose response read fails may already have executed server-side."""
    transport, attempts = _make_transport(
        monkeypatch, [httpx.ReadError("[WinError 10035]")]
    )
    with pytest.raises(httpx.ReadError):
        transport.handle_request(_request("POST"))
    assert attempts == ["POST"]


def test_post_connect_error_is_replayed(monkeypatch):
    """Connect failures never reached the server, so any method is safe to retry."""
    ok = httpx.Response(200)
    transport, attempts = _make_transport(
        monkeypatch, [httpx.ConnectError("boom"), ok]
    )
    assert transport.handle_request(_request("POST")) is ok
    assert attempts == ["POST", "POST"]


def test_get_remote_protocol_error_is_replayed(monkeypatch):
    """Server disconnects on reused keep-alive connections are the same class."""
    ok = httpx.Response(200)
    transport, attempts = _make_transport(
        monkeypatch, [httpx.RemoteProtocolError("Server disconnected"), ok]
    )
    assert transport.handle_request(_request("GET")) is ok
    assert attempts == ["GET", "GET"]


def test_timeouts_are_not_retried(monkeypatch):
    """A read timeout means the server is slow, not that the socket glitched."""
    transport, attempts = _make_transport(
        monkeypatch, [httpx.ReadTimeout("slow")]
    )
    with pytest.raises(httpx.ReadTimeout):
        transport.handle_request(_request("GET"))
    assert attempts == ["GET"]


def test_build_http_client_uses_retry_transport():
    client = _build_http_client()
    try:
        assert isinstance(client._transport, _TransientRetryTransport)
    finally:
        client.close()
