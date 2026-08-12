"""The hiring conversation, from both ends.

The plan's verification for this step is **"RLS denies a non-participant"**, and
no in-process test can prove that: the policy runs in Postgres and these tests
replace the repository. What they *can* prove is the thing that would make the
policy irrelevant -- that the API never offers a path around it. So the guard
assertions here are about absence: no route reads a caller-supplied id to decide
who may see a thread, no filter widens what the policy allows, and the two reads
answer 404 rather than 403 so threads cannot be enumerated by their refusals.

The fixture overrides **only** identity, leaving ``get_active_membership`` live.
A membership guard creeping onto this router would run the resolver against the
sentinel client and fail the test -- which matters more here than anywhere else
in this feature, because the caller this router exists for may hold no
membership in the community whose department they are talking to.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_request_client
from app.core.exceptions import AuthorizationError
from app.domain.schemas import Principal
from app.services import conversations_service

CONVERSATIONS = "/api/v1/conversations"
THREAD = f"{CONVERSATIONS}/conversation-id"
MESSAGES = f"{THREAD}/messages"

PROFILE_ID = "provider-profile-id"
PROVIDER_ID = "provider-id"


def conversation_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "conversation-id",
        "community_id": "community-id",
        "community_name": "Green Meadows",
        "department_id": "department-id",
        "department_name": "Plumbing",
        "department_kind": "service",
        "service_provider_id": PROVIDER_ID,
        "provider_display_name": "Ravi Kumar",
        "provider_headline": "Plumber, 12 years",
        "provider_profile_id": PROFILE_ID,
        "last_message_body": "Can you start Monday?",
        "message_count": 2,
        "last_message_at": "2026-08-09T10:00:00Z",
        "created_at": "2026-08-09T09:00:00Z",
    }
    base.update(overrides)
    return base


def message_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "message-id",
        "conversation_id": "conversation-id",
        "body": "Can you start Monday?",
        "author_side": "department",
        "author_name": "Priya Nair",
        "author_profile_id": "manager-profile-id",
        "created_at": "2026-08-09T10:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def talker(api_client: TestClient) -> TestClient:
    """Signed in, with **no membership override**. See the module docstring."""
    principal = Principal(
        user_id=PROFILE_ID,
        email="ravi@example.com",
        email_verified=True,
        full_name="Ravi Kumar",
    )
    api_client.app.dependency_overrides[get_current_user] = lambda: principal
    api_client.app.dependency_overrides[get_request_client] = lambda: object()
    return api_client


@pytest.fixture
def chat(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository under the live service."""
    captured: dict = {
        "conversations": [conversation_row()],
        "messages": [message_row()],
        "conversation": conversation_row(),
    }

    def fake_list(client: Any, *, department_id: str | None) -> list[dict[str, Any]]:
        captured["filtered_department"] = department_id
        return captured["conversations"]

    def fake_get(client: Any, *, conversation_id: str) -> dict[str, Any] | None:
        captured["read"] = conversation_id
        return captured["conversation"]

    def fake_messages(
        client: Any, *, conversation_id: str, limit: int
    ) -> list[dict[str, Any]]:
        captured["message_limit"] = limit
        return captured["messages"]

    def fake_get_message(client: Any, *, message_id: str) -> dict[str, Any] | None:
        return captured["messages"][0] if captured["messages"] else None

    def fake_open(
        client: Any, *, department_id: str, service_provider_id: str
    ) -> str:
        captured["opened"] = {
            "department_id": department_id,
            "service_provider_id": service_provider_id,
        }
        return "conversation-id"

    def fake_post(client: Any, *, conversation_id: str, body: str) -> str:
        captured["posted"] = {"conversation_id": conversation_id, "body": body}
        return "message-id"

    repo = conversations_service.repo
    monkeypatch.setattr(repo, "list_conversations", fake_list)
    monkeypatch.setattr(repo, "get_conversation", fake_get)
    monkeypatch.setattr(repo, "list_messages", fake_messages)
    monkeypatch.setattr(repo, "get_message", fake_get_message)
    monkeypatch.setattr(repo, "open_conversation", fake_open)
    monkeypatch.setattr(repo, "post_message", fake_post)
    yield captured


def test_api_151_the_thread_list_is_one_inbox_across_every_community(
    talker: TestClient, chat: dict
) -> None:
    """A service person hired by three societies talks to three departments and
    has one screen. Omitting `departmentId` passes `None` to the repository --
    no community scoping anywhere in the request path -- and the policy is what
    makes the result theirs rather than everyone's."""
    endpoint = "GET /api/v1/conversations"
    expected_output = {"status_code": 200, "count": 2, "department_filter": None}

    chat["conversations"] = [
        conversation_row(id="c1", community_name="Green Meadows"),
        conversation_row(id="c2", community_name="Palm Grove"),
    ]
    response = talker.get(CONVERSATIONS)
    actual_output = {
        "status_code": response.status_code,
        "count": len(response.json()),
        "department_filter": chat["filtered_department"],
    }

    assert actual_output == expected_output, endpoint


def test_api_152_the_department_filter_narrows_and_cannot_widen(
    talker: TestClient, chat: dict
) -> None:
    """`departmentId` reaches the query as a filter on top of the policy, never
    as the thing that decides visibility. A caller passing a department they
    have no part in gets an empty list rather than somebody else's threads --
    which is why it is safe to take from the query string at all."""
    endpoint = "GET /api/v1/conversations?departmentId=not-mine"
    expected_output = {"status_code": 200, "body": [], "forwarded": "not-mine"}

    chat["conversations"] = []
    response = talker.get(CONVERSATIONS, params={"departmentId": "not-mine"})
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
        "forwarded": chat["filtered_department"],
    }

    assert actual_output == expected_output, endpoint


def test_api_153_a_thread_the_policy_hides_is_a_404_not_a_403(
    talker: TestClient, chat: dict
) -> None:
    """The policy hides the row rather than refusing it, so the read cannot tell
    a stranger that a thread exists. A 403 here would make a department's
    conversations with every other provider enumerable by walking ids and
    reading which refusals came back."""
    endpoint = "GET /api/v1/conversations/conversation-id"
    expected_output = {"status_code": 404, "code": "conversation_not_found"}

    chat["conversation"] = None
    response = talker.get(THREAD)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_154_the_thread_read_returns_its_messages_in_one_response(
    talker: TestClient, chat: dict
) -> None:
    """One response rather than two round trips, because 'a thread with no
    messages' and 'a thread you cannot see' are different answers -- 200 with an
    empty list and 404 -- and splitting the read would deliver them separately.
    `authorSide` is what a renderer switches on; the two sides live in two
    different tables and the view collapses that into one word."""
    endpoint = "GET /api/v1/conversations/conversation-id"
    expected_output = {
        "status_code": 200,
        "conversation_id": "conversation-id",
        "sides": ["department", "provider"],
        "bounded": True,
    }

    chat["messages"] = [
        message_row(id="m1", author_side="department"),
        message_row(id="m2", author_side="provider", author_name="Ravi Kumar"),
    ]
    response = talker.get(THREAD)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "conversation_id": body["conversation"]["id"],
        "sides": [message["authorSide"] for message in body["messages"]],
        "bounded": chat["message_limit"] > 0,
    }

    assert actual_output == expected_output, endpoint


def test_api_155_opening_a_thread_is_idempotent_and_returns_the_whole_thread(
    talker: TestClient, chat: dict, csrf_headers: dict[str, str]
) -> None:
    """There is exactly one thread per (department, provider) pair -- a unique
    constraint, not a convention -- so this is what a 'Message' button calls
    every time it is pressed. The response is the full thread because one that
    already existed already has messages, and the caller is about to render
    them."""
    endpoint = "POST /api/v1/conversations"
    input_data = {"departmentId": "department-id", "serviceProviderId": PROVIDER_ID}
    expected_output = {
        "status_code": 201,
        "conversation_id": "conversation-id",
        "message_count": 1,
        "forwarded": input_data,
    }

    response = talker.post(CONVERSATIONS, json=input_data, headers=csrf_headers)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "conversation_id": body["conversation"]["id"],
        "message_count": len(body["messages"]),
        "forwarded": {
            "departmentId": chat["opened"]["department_id"],
            "serviceProviderId": chat["opened"]["service_provider_id"],
        },
    }

    assert actual_output == expected_output, endpoint


def test_api_156_a_message_is_returned_as_stored_not_as_sent(
    talker: TestClient, chat: dict, csrf_headers: dict[str, str]
) -> None:
    """The body is trimmed by the RPC and the author's name and side are
    resolved from the thread, none of which the caller supplied. A client that
    appended its own request to the list would be showing a message that differs
    from what everyone else sees."""
    endpoint = "POST /api/v1/conversations/conversation-id/messages"
    input_data = {"body": "Monday works."}
    expected_output = {
        "status_code": 201,
        "author_name": "Priya Nair",
        "author_side": "department",
        "forwarded_body": "Monday works.",
        "forwarded_thread": "conversation-id",
    }

    response = talker.post(MESSAGES, json=input_data, headers=csrf_headers)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "author_name": body["authorName"],
        "author_side": body["authorSide"],
        "forwarded_body": chat["posted"]["body"],
        "forwarded_thread": chat["posted"]["conversation_id"],
    }

    assert actual_output == expected_output, endpoint


def test_api_157_an_empty_message_is_refused_before_the_database_sees_it(
    talker: TestClient, chat: dict, csrf_headers: dict[str, str]
) -> None:
    """`min_length` matches the CHECK in 0038, so a blank body is a 422 naming
    the field rather than a 422 naming a constraint. The repository is not
    reached -- asserted, because a validator that fires after the write is not a
    validator."""
    endpoint = "POST /api/v1/conversations/conversation-id/messages"
    input_data = {"body": ""}
    expected_output = {"status_code": 422, "reached_repository": False}

    response = talker.post(MESSAGES, json=input_data, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "posted" in chat,
    }

    assert actual_output == expected_output, endpoint


def test_api_158_a_non_participant_is_refused_by_the_database_not_by_this_layer(
    talker: TestClient,
    chat: dict,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The router declares identity only and the service contains no
    participation check, so the 403 a stranger gets comes from
    `post_conversation_message` raising HB403. That is the whole design: one
    definition of who is in a thread, next to the data, rather than a copy here
    that can drift from the policy enforcing it."""
    endpoint = "POST /api/v1/conversations/conversation-id/messages"
    expected_output = {"status_code": 403, "code": "forbidden"}

    def refuse(client: Any, *, conversation_id: str, body: str) -> str:
        raise AuthorizationError(
            "You are not part of this conversation.", code="forbidden"
        )

    monkeypatch.setattr(conversations_service.repo, "post_message", refuse)
    response = talker.post(MESSAGES, json={"body": "Hello?"}, headers=csrf_headers)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_159_posting_without_the_csrf_pair_is_refused(
    talker: TestClient, chat: dict
) -> None:
    """No role guard on this router at all, so CSRF is the only thing between a
    cross-site form post and a message somebody did not send."""
    endpoint = "POST /api/v1/conversations/conversation-id/messages"
    expected_output = {"status_code": 403, "reached_repository": False}

    response = talker.post(MESSAGES, json={"body": "Hello?"})
    actual_output = {
        "status_code": response.status_code,
        "reached_repository": "posted" in chat,
    }

    assert actual_output == expected_output, endpoint
