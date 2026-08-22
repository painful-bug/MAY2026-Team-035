"""Privacy-safe request timing and session cache-control contracts."""

from __future__ import annotations

import logging
import re

from fastapi.testclient import TestClient


def test_request_timing_uses_the_route_template_not_query_values(
    api_client: TestClient,
    caplog,
) -> None:
    with caplog.at_level(logging.INFO, logger="homebandhu.requests"):
        response = api_client.get("/health?token=must-not-be-logged")

    assert response.status_code == 200
    assert re.fullmatch(r"app;dur=\d+\.\d{2}", response.headers["server-timing"])
    message = next(
        record.message
        for record in caplog.records
        if record.name == "homebandhu.requests"
    )
    assert "route=/health" in message
    assert "must-not-be-logged" not in message


def test_session_responses_are_never_cacheable(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store, private"
    assert response.headers["pragma"] == "no-cache"
    assert "server-timing" in response.headers
