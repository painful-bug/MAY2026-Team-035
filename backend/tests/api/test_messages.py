"""Direct messages: the chat dock's API.

Same posture as ``test_conversations.py``: the RLS policies and the SQL lock
run in Postgres and cannot be proven here, so these tests prove the API never
offers a path around them — the 404 that hides other people's threads, the
409 that surfaces the lock unchanged, the 422 that stops a subjectless open
before any write, and the counterpart resolution that is this service's one
piece of real shaping.

The fixture overrides **only** identity. The router must not grow a
membership guard: every portal mounts the dock, including a resident's.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_request_client
from app.core.exceptions import ConflictError
from app.domain.schemas import Principal
from app.services import messages_service

THREADS = "/api/v1/messages/threads"
THREAD = f"{THREADS}/thread-id"

ME = "bbbb-profile-id"
OTHER = "aaaa-profile-id"


def thread_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "thread-id",
        "community_id": "community-id",
        "community_name": "Green Meadows",
        "kind": "direct",
        "work_order_id": None,
        # Canonical order: a < b. The caller is b, so the counterpart is a.
        "participant_a_profile_id": OTHER,
        "participant_b_profile_id": ME,
        "participant_a_name": "Priya Nair",
        "participant_b_name": "Ravi Kumar",
        "locked_at": None,
        "last_message_at": "2026-08-10T10:00:00Z",
        "last_message_body": "See you at four.",
        "created_at": "2026-08-10T09:00:00Z",
    }
    base.update(overrides)
    return base


def message_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "message-id",
        "thread_id": "thread-id",
        "author_profile_id": OTHER,
        "body": "See you at four.",
        "created_at": "2026-08-10T10:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def talker(api_client: TestClient) -> TestClient:
    """Signed in, no membership override — see the module docstring."""
    principal = Principal(
        user_id=ME,
        email="ravi@example.com",
        email_verified=True,
        full_name="Ravi Kumar",
    )
    api_client.app.dependency_overrides[get_current_user] = lambda: principal
    api_client.app.dependency_overrides[get_request_client] = lambda: object()
    return api_client


@pytest.fixture
def mailbox(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository under the live service."""
    captured: dict = {
        "threads": [thread_row()],
        "messages": [message_row()],
        "calls": [],
    }

    def fake_list_threads(client: Any) -> list[dict[str, Any]]:
        captured["calls"].append("threads")
        return captured["threads"]

    def fake_get_thread(client: Any, *, thread_id: str) -> dict[str, Any] | None:
        captured["calls"].append("thread")
        rows = [r for r in captured["threads"] if r["id"] == thread_id]
        return rows[0] if rows else None

    def fake_list_messages(
        client: Any, *, thread_id: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        captured["calls"].append("messages")
        return captured["messages"]

    def fake_recipients(client: Any, *, community_id: str) -> list[dict[str, Any]]:
        captured["recipients_for"] = community_id
        return [{"profile_id": OTHER, "display_name": "Priya Nair", "label": "Manager"}]

    def fake_open_direct(
        client: Any, *, community_id: str, recipient_profile_id: str
    ) -> str:
        captured["calls"].append("open_direct")
        captured["opened"] = {
            "community_id": community_id,
            "recipient": recipient_profile_id,
        }
        return "thread-id"

    def fake_open_work_order(client: Any, *, work_order_id: str) -> str:
        captured["calls"].append("open_work_order")
        captured["opened"] = {"work_order_id": work_order_id}
        return "thread-id"

    def fake_post(client: Any, *, thread_id: str, body: str) -> str:
        captured["calls"].append("post")
        if captured.get("locked"):
            raise ConflictError("This conversation is closed.", code="conflict")
        captured["posted"] = {"thread_id": thread_id, "body": body}
        row = message_row(id="new-message-id", author_profile_id=ME, body=body)
        captured["messages"] = [*captured["messages"], row]
        return "new-message-id"

    repo = messages_service.repo
    monkeypatch.setattr(repo, "list_threads", fake_list_threads)
    monkeypatch.setattr(repo, "get_thread", fake_get_thread)
    monkeypatch.setattr(repo, "list_messages", fake_list_messages)
    monkeypatch.setattr(repo, "recipients", fake_recipients)
    monkeypatch.setattr(repo, "open_direct_thread", fake_open_direct)
    monkeypatch.setattr(repo, "open_work_order_thread", fake_open_work_order)
    monkeypatch.setattr(repo, "post_message", fake_post)
    yield captured


def test_api_226_the_mailbox_resolves_the_counterpart_per_caller(
    talker: TestClient, mailbox: dict
) -> None:
    """A thread stores its pair in canonical order; 'who is this with' depends
    on who is asking. The same row must answer differently for its two
    participants, and that resolution is this service's one real job."""
    endpoint = "GET /api/v1/messages/threads"
    expected_output = {
        "status_code": 200,
        "counterpart_id": OTHER,
        "counterpart_name": "Priya Nair",
    }

    response = talker.get(THREADS)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "counterpart_id": body[0]["counterpartProfileId"],
        "counterpart_name": body[0]["counterpartName"],
    }

    assert actual_output == expected_output, endpoint


def test_api_227_an_open_with_no_subject_or_two_never_reaches_the_database(
    talker: TestClient, mailbox: dict, csrf_headers: dict[str, str]
) -> None:
    """Exactly one subject: a person or a job. Both and neither are 422s
    decided in the service, so a request that cannot mean anything writes
    nothing."""
    endpoint = "POST /api/v1/messages/threads"
    expected_output = {"status_codes": [422, 422], "writes": []}

    both = talker.post(
        THREADS,
        json={
            "communityId": "community-id",
            "recipientProfileId": OTHER,
            "workOrderId": "work-order-id",
        },
        headers=csrf_headers,
    )
    neither = talker.post(THREADS, json={}, headers=csrf_headers)
    actual_output = {
        "status_codes": [both.status_code, neither.status_code],
        "writes": [call for call in mailbox["calls"] if call.startswith("open")],
    }

    assert actual_output == expected_output, endpoint


def test_api_228_a_direct_open_without_a_community_is_refused_first(
    talker: TestClient, mailbox: dict, csrf_headers: dict[str, str]
) -> None:
    """The pair rule is per community — a manager here is a stranger there —
    so a direct open without the community that scopes it cannot be checked
    and is refused before the RPC."""
    endpoint = "POST /api/v1/messages/threads"
    expected_output = {"status_code": 422, "writes": []}

    response = talker.post(
        THREADS, json={"recipientProfileId": OTHER}, headers=csrf_headers
    )
    actual_output = {
        "status_code": response.status_code,
        "writes": [call for call in mailbox["calls"] if call.startswith("open")],
    }

    assert actual_output == expected_output, endpoint


def test_api_229_the_lock_surfaces_as_a_409_not_a_swallowed_error(
    talker: TestClient, mailbox: dict, csrf_headers: dict[str, str]
) -> None:
    """A finished job's channel refuses new messages — the protection the
    product owner asked for. The 409 is the feature; smoothing it into a 200
    would reopen the line the lock exists to close."""
    endpoint = "POST /api/v1/messages/threads/{threadId}/messages"
    expected_output = {"status_code": 409}

    mailbox["locked"] = True
    response = talker.post(
        f"{THREAD}/messages", json={"body": "One more thing."}, headers=csrf_headers
    )
    actual_output = {"status_code": response.status_code}

    assert actual_output == expected_output, endpoint


def test_api_230_a_thread_the_policy_hides_reads_no_messages_at_all(
    talker: TestClient, mailbox: dict
) -> None:
    """404 covers missing and not-yours alike, and the message read happens
    only after the thread read succeeds — otherwise a guessed uuid pulls a
    transcript the policy meant to hide."""
    endpoint = "GET /api/v1/messages/threads/{threadId}"
    expected_output = {"status_code": 404, "messages_read": False}

    mailbox["threads"] = []
    response = talker.get(THREAD)
    actual_output = {
        "status_code": response.status_code,
        "messages_read": "messages" in mailbox["calls"],
    }

    assert actual_output == expected_output, endpoint


def test_api_231_a_sent_message_comes_back_as_the_database_stored_it(
    talker: TestClient, mailbox: dict, csrf_headers: dict[str, str]
) -> None:
    """The response is read back through the view rather than echoed from the
    request — the same _read_back discipline every write on this API keeps."""
    endpoint = "POST /api/v1/messages/threads/{threadId}/messages"
    expected_output = {
        "status_code": 201,
        "id": "new-message-id",
        "author": ME,
        "body": "See you at four.",
    }

    response = talker.post(
        f"{THREAD}/messages", json={"body": "See you at four."}, headers=csrf_headers
    )
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "id": body["id"],
        "author": body["authorProfileId"],
        "body": body["body"],
    }

    assert actual_output == expected_output, endpoint
