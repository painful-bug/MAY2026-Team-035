"""Residence-claim capture on the join flow (2026-08-27 rulings).

The applicant states where they live as free text at request time; the two
fields travel `CreateAccessRequest` -> `access_requests` insert ->
`AccessRequestResponse` untouched, except that whitespace is stripped at the
schema boundary and a blank claim collapses to ``None`` rather than being
stored as an empty string.
"""

from __future__ import annotations

import pytest

from app.domain.schemas import ApproveAccessRequest, CreateAccessRequest, Principal
from app.repositories import access_requests_repository
from app.services import access_request_service


# ---------------------------------------------------------------------------
# Schema boundary: strip, and blank -> None
# ---------------------------------------------------------------------------


def test_residence_text_is_stripped_and_blank_collapses_to_none() -> None:
    request = CreateAccessRequest(
        community_id="community-id",
        requested_building_text="  C ",
        requested_unit_text="   ",
    )
    assert request.requested_building_text == "C"
    assert request.requested_unit_text is None

    untouched = CreateAccessRequest(community_id="community-id")
    assert untouched.requested_building_text is None
    assert untouched.requested_unit_text is None


def test_residence_text_longer_than_the_column_check_is_refused() -> None:
    with pytest.raises(ValueError):
        CreateAccessRequest(
            community_id="community-id", requested_unit_text="x" * 121
        )


# ---------------------------------------------------------------------------
# Service create(): the claim reaches the insert payload as given
# ---------------------------------------------------------------------------


class _TableQuery:
    def __init__(self, rows: list[dict]) -> None:
        self.data = rows

    def select(self, _: str) -> "_TableQuery":
        return self

    def eq(self, _: str, __: object) -> "_TableQuery":
        return self

    def is_(self, _: str, __: object) -> "_TableQuery":
        return self

    def limit(self, _: int) -> "_TableQuery":
        return self

    def order(self, _: str, **__: object) -> "_TableQuery":
        return self

    def execute(self) -> "_TableQuery":
        return self


class _TablesClient:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self._tables = tables

    def table(self, name: str) -> _TableQuery:
        return _TableQuery(self._tables.get(name, []))


def test_create_stores_the_residence_claim_and_echoes_it_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_data = CreateAccessRequest(
        community_id="community-id",
        requested_relationship="tenant",
        requested_building_text="C",
        requested_unit_text="505",
    )
    principal = Principal(
        user_id="resident-profile-id",
        email="resident@example.com",
        email_verified=True,
    )
    captured_input: dict[str, object] = {}

    client = _TablesClient(
        {
            "communities": [
                {
                    "id": "community-id",
                    "name": "Palm Residency",
                    "community_type": "apartment",
                    "status": "active",
                }
            ]
        }
    )
    monkeypatch.setattr(
        access_request_service, "get_service_client", lambda: client
    )
    monkeypatch.setattr(
        access_request_service.profiles_repository,
        "get_profile",
        lambda _client, _user_id: type(
            "Profile", (), {"full_name": "Ravi Kumar", "phone": None}
        )(),
    )
    monkeypatch.setattr(
        access_request_service.access_requests_repository,
        "find_pending",
        lambda _client, **_kwargs: None,
    )
    monkeypatch.setattr(
        access_request_service.access_requests_repository,
        "list_for_profile",
        lambda _client, _profile_id: [],
    )

    def insert(_client: object, payload: dict) -> dict:
        captured_input.update(payload)
        return {"id": "request-id", **payload}

    monkeypatch.setattr(
        access_request_service.access_requests_repository, "insert", insert
    )

    response = access_request_service.create(input_data, principal)

    assert captured_input["requested_building_text"] == "C"
    assert captured_input["requested_unit_text"] == "505"
    assert response.requested_building_text == "C"
    assert response.requested_unit_text == "505"
    assert response.community.community_type == "apartment"


# ---------------------------------------------------------------------------
# Approve canonicalisation happens in the service, once
# ---------------------------------------------------------------------------


def test_approve_reuses_the_one_normalizer_for_the_tower_flat_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """('C', 'C-505') is already qualified: the repository must receive
    'C-505', not the C-C-505 double prefix the frontend bug produces."""
    monkeypatch.setattr(
        access_request_service,
        "get_service_client",
        lambda: _TablesClient(
            {
                "community_memberships": [
                    {"id": "admin-membership-id", "community_id": "community-id"}
                ]
            }
        ),
    )
    monkeypatch.setattr(
        access_request_service.access_requests_repository,
        "get",
        lambda _client, _request_id: {
            "id": "request-id",
            "community_id": "community-id",
        },
    )
    captured_input: dict[str, object] = {}

    def approve(_client: object, **kwargs: object) -> dict:
        captured_input.update(kwargs)
        return {"request_id": "request-id", "status": "approved"}

    monkeypatch.setattr(
        access_request_service.access_requests_repository, "approve", approve
    )

    access_request_service.approve(
        "request-id",
        ApproveAccessRequest(unit_code="C-505", building_code="C"),
        Principal(user_id="admin-profile-id", email="admin@example.com"),
    )

    assert captured_input["unit_code"] == "C-505"
    assert captured_input["building_code"] == "C"
    assert captured_input["unit_id"] is None


# ---------------------------------------------------------------------------
# Repository: the RPC payload degrades gracefully before the migration
# ---------------------------------------------------------------------------


class _RpcClient:
    """Captures the rpc name and payload the repository sends."""

    def __init__(self) -> None:
        self.name: str | None = None
        self.payload: dict | None = None

    def rpc(self, name: str, payload: dict) -> "_RpcClient":
        self.name = name
        self.payload = payload
        return self

    def execute(self) -> "_RpcClient":
        self.data = [{"request_id": "request-id", "status": "approved"}]
        return self


def test_repository_sends_unit_code_arguments_only_when_present() -> None:
    without = _RpcClient()
    access_requests_repository.approve(
        without,
        request_id="request-id",
        reviewer_profile_id="admin-profile-id",
        unit_id="unit-id",
        relationship="tenant",
    )
    # The old 4-argument shape, so a backend deployed before the hand-applied
    # migration still dispatches against the old RPC signature.
    assert without.payload == {
        "p_request_id": "request-id",
        "p_reviewer_profile_id": "admin-profile-id",
        "p_unit_id": "unit-id",
        "p_relationship": "tenant",
    }

    with_codes = _RpcClient()
    access_requests_repository.approve(
        with_codes,
        request_id="request-id",
        reviewer_profile_id="admin-profile-id",
        unit_id=None,
        relationship=None,
        unit_code="C-505",
        building_code="C",
    )
    assert with_codes.payload == {
        "p_request_id": "request-id",
        "p_reviewer_profile_id": "admin-profile-id",
        "p_unit_id": None,
        "p_relationship": None,
        "p_unit_code": "C-505",
        "p_building_code": "C",
    }
