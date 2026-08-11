"""The launch funnel stores only allowlisted, anonymous events."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.web_session import cookie_name
from app.repositories import service_signup_telemetry_repository as telemetry_repo


class _Call:
    def __init__(self, captured: list[dict[str, Any]], *, fails: bool = False) -> None:
        self.captured = captured
        self.fails = fails

    def execute(self) -> None:
        if self.fails:
            raise RuntimeError("database unavailable")


class _Client:
    def __init__(self, captured: list[dict[str, Any]], *, fails: bool = False) -> None:
        self.captured = captured
        self.fails = fails

    def rpc(self, name: str, payload: dict[str, Any]) -> _Call:
        self.captured.append({"name": name, "payload": payload})
        return _Call(self.captured, fails=self.fails)


def test_event_is_allowlisted_and_cookie_identity_is_reused(
    api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(telemetry_repo, "get_service_client", lambda: _Client(captured))

    first = api_client.post(
        "/api/v1/telemetry/service-signup",
        json={"eventName": "cta_impression"},
        headers=csrf_headers,
    )
    second = api_client.post(
        "/api/v1/telemetry/service-signup",
        json={"eventName": "cta_clicked"},
        headers=csrf_headers,
    )

    assert first.status_code == second.status_code == 200
    assert api_client.cookies.get(cookie_name("service_funnel"))
    first_visitor = captured[0]["payload"]["p_visitor_id"]
    assert first_visitor == captured[1]["payload"]["p_visitor_id"]
    assert set(captured[0]["payload"]) == {"p_visitor_id", "p_event_name"}


def test_every_event_reissues_the_visitor_cookie_so_its_window_slides(
    api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 30 days are 30 days of silence, not 30 days from the first event.

    Written once, the cookie expires 30 days after ``cta_impression`` whatever
    the visitor does next -- so somebody who sees the CTA, waits five weeks and
    then signs up arrives as a *new* visitor. The funnel's denominator counts
    them and its numerator does not, and nothing about that is visible in the
    data. Re-issuing on every event makes the two agree.
    """
    name = cookie_name("service_funnel")
    monkeypatch.setattr(telemetry_repo, "get_service_client", lambda: _Client([]))

    first = api_client.post(
        "/api/v1/telemetry/service-signup",
        json={"eventName": "cta_impression"},
        headers=csrf_headers,
    )
    minted = api_client.cookies.get(name)
    second = api_client.post(
        "/api/v1/telemetry/service-signup",
        json={"eventName": "cta_clicked"},
        headers=csrf_headers,
    )

    assert name in first.headers.get("set-cookie", "")
    # The second event carries a cookie already, and must still refresh it.
    assert name in second.headers.get("set-cookie", "")
    assert "Max-Age=2592000" in second.headers["set-cookie"]
    # Refreshed, not replaced: a slid window that changed the id would split one
    # visitor into two and defeat the deduplication the primary key exists for.
    assert api_client.cookies.get(name) == minted


def test_unknown_event_and_missing_csrf_are_rejected(
    api_client: TestClient, csrf_headers: dict[str, str]
) -> None:
    unknown = api_client.post(
        "/api/v1/telemetry/service-signup",
        json={"eventName": "gps_captured"},
        headers=csrf_headers,
    )
    no_csrf = api_client.post(
        "/api/v1/telemetry/service-signup",
        json={"eventName": "cta_clicked"},
    )

    assert unknown.status_code == 422
    assert no_csrf.status_code == 403


def test_storage_failure_never_blocks_the_funnel(
    api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        telemetry_repo, "get_service_client", lambda: _Client([], fails=True)
    )

    response = api_client.post(
        "/api/v1/telemetry/service-signup",
        json={"eventName": "auth_completed"},
        headers=csrf_headers,
    )

    assert response.status_code == 200
