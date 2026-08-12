"""Founder and invitation activation regressions."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_request_token
from app.api.v1.routers import invitations, onboarding
from app.core.exceptions import AuthenticationError
from app.core.web_session import INVITATION_COOKIE, sign_payload
from app.domain.schemas import CommunityOnboardingResponse, Principal
from app.services import auth_service


def _founder_payload() -> dict:
    return {
        "name": "Palm Grove Residency",
        "community_type": "apartment",
        "address_line1": "12 Palm Grove Road",
        "city": "Kolkata",
        "state": "West Bengal",
        "postal_code": "700001",
        "latitude": 22.572645,
        "longitude": 88.363892,
        "blocks": [{"id": "block-1", "name": "Block A"}],
        "block_locations": {"block-1": {"x": 50, "y": 50}},
        "admin_profile": {
            "fullName": "Founder Admin",
            "unitNumber": "A-101",
            "founderStructureId": "block-1",
        },
    }


def test_founder_creation_verifies_identity_then_calls_onboarding(
    api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = Principal(user_id="founder-id", email="founder@example.com")
    captured: list[Principal] = []
    api_client.app.dependency_overrides[get_request_token] = lambda: "access-token"
    monkeypatch.setattr(auth_service, "verified_identity", lambda _: identity)
    monkeypatch.setattr(
        onboarding.onboarding_service,
        "create_community",
        lambda _, principal: captured.append(principal)
        or CommunityOnboardingResponse(
            community={"id": "community-id"}, admin={"id": "founder-id"}
        ),
    )

    response = api_client.post(
        "/api/v1/onboarding/community", json=_founder_payload(), headers=csrf_headers
    )

    assert response.status_code == 200
    assert captured == [identity]


def test_founder_identity_failure_is_an_authentication_response(
    api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_client.app.dependency_overrides[get_request_token] = lambda: "access-token"
    monkeypatch.setattr(
        auth_service,
        "verified_identity",
        lambda _: (_ for _ in ()).throw(AuthenticationError("Invalid token.")),
    )

    response = api_client.post(
        "/api/v1/onboarding/community", json=_founder_payload(), headers=csrf_headers
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"


def test_invitation_redemption_verifies_identity_before_redeeming(
    api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = Principal(user_id="resident-id", email="resident@example.com")
    redeemed: list[tuple[dict, Principal]] = []

    class InviteQuery:
        data = [{"id": "invite-id", "invitee_email": "resident@example.com"}]

        def select(self, _: str) -> InviteQuery:
            return self

        def eq(self, _: str, __: str) -> InviteQuery:
            return self

        def limit(self, _: int) -> InviteQuery:
            return self

        def execute(self) -> InviteQuery:
            return self

    class Service:
        def table(self, _: str) -> InviteQuery:
            return InviteQuery()

    api_client.app.dependency_overrides[get_request_token] = lambda: "access-token"
    api_client.cookies.set(
        INVITATION_COOKIE, sign_payload({"invite_id": "invite-id"}, ttl_seconds=300)
    )
    monkeypatch.setattr(invitations, "get_service_client", Service)
    monkeypatch.setattr(
        invitations.auth_service, "verified_identity", lambda _: identity
    )
    monkeypatch.setattr(
        invitations.invitation_service,
        "redeem_pending_invitation",
        lambda invite, principal: redeemed.append((invite, principal)),
    )

    response = api_client.post(
        "/api/v1/invitations/redeem", json={}, headers=csrf_headers
    )

    assert response.status_code == 200
    assert redeemed == [
        ({"id": "invite-id", "invitee_email": "resident@example.com"}, identity)
    ]


def test_invitation_identity_failure_is_an_authentication_response(
    api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InviteQuery:
        data = [{"id": "invite-id", "invitee_email": "resident@example.com"}]

        def select(self, _: str) -> InviteQuery:
            return self

        def eq(self, _: str, __: str) -> InviteQuery:
            return self

        def limit(self, _: int) -> InviteQuery:
            return self

        def execute(self) -> InviteQuery:
            return self

    class Service:
        def table(self, _: str) -> InviteQuery:
            return InviteQuery()

    api_client.app.dependency_overrides[get_request_token] = lambda: "access-token"
    api_client.cookies.set(
        INVITATION_COOKIE, sign_payload({"invite_id": "invite-id"}, ttl_seconds=300)
    )
    monkeypatch.setattr(invitations, "get_service_client", Service)
    monkeypatch.setattr(
        invitations.auth_service,
        "verified_identity",
        lambda _: (_ for _ in ()).throw(AuthenticationError("Invalid token.")),
    )

    response = api_client.post(
        "/api/v1/invitations/redeem", json={}, headers=csrf_headers
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"
