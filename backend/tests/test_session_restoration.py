"""Regression checks for the bounded, uncached session restoration path."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.requests import Request

from app.api import deps
from app.core.exceptions import AuthenticationError
from app.domain.schemas import Principal, Profile
from app.services import auth_service

PRINCIPAL = Principal(
    user_id="11111111-1111-4111-8111-111111111111",
    email="resident@example.com",
    email_verified=True,
)


class _Result:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.projection = ""

    def select(self, projection: str) -> _Query:
        self.projection = projection
        return self

    def eq(self, *_: Any) -> _Query:
        return self

    def is_(self, *_: Any) -> _Query:
        return self

    def order(self, *_: Any, **__: Any) -> _Query:
        return self

    def limit(self, *_: Any) -> _Query:
        return self

    def execute(self) -> _Result:
        return _Result(self.rows)


class _ServiceClient:
    def __init__(self, membership: dict[str, Any]) -> None:
        self.membership = membership
        self.tables: list[str] = []
        self.query: _Query | None = None

    def table(self, name: str) -> _Query:
        self.tables.append(name)
        rows = [self.membership] if name == "community_memberships" else []
        self.query = _Query(rows)
        return self.query


def test_established_member_session_uses_two_database_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = {
        "id": "membership-id",
        "community_id": "community-id",
        "role": "admin",
        "department_id": None,
        "is_default_community": True,
        "departments": None,
        "staff_assignments": [],
        "unit_residencies": [
            {
                "unit_id": "unit-id",
                "ended_at": None,
                "units": {
                    "unit_code": "4B",
                    "unit_type": "flat",
                    "buildings": {"name": "Emerald", "building_type": "block"},
                },
            }
        ],
    }
    service = _ServiceClient(membership)
    profile_reads: list[str] = []
    monkeypatch.setattr(auth_service, "get_service_client", lambda: service)
    monkeypatch.setattr(
        auth_service.profiles_repository,
        "get_profile",
        lambda _client, user_id: profile_reads.append(user_id)
        or Profile(id=user_id, full_name="Priya Nair"),
    )

    context = auth_service.get_session_context(object(), PRINCIPAL, "access-token")

    assert profile_reads == [PRINCIPAL.user_id]
    assert service.tables == ["community_memberships"]
    assert service.query is not None
    projection = service.query.projection
    assert "unit_residencies!unit_residencies_membership_id_fkey" in projection
    assert "departments!community_memberships_department_id_fkey" in projection
    assert "staff_assignments!staff_assignments_membership_id_fkey" in projection
    assert context.capabilities == ["admin", "resident"]
    assert context.membership.unit.unit_code == "4B"


def test_request_dependencies_decode_and_build_the_user_client_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/session",
            "headers": [(b"cookie", b"hb_access=access-token")],
        }
    )
    decoded: list[str] = []
    clients: list[str] = []
    monkeypatch.setattr(deps, "cookie_name", lambda kind: f"hb_{kind}")
    monkeypatch.setattr(
        deps,
        "decode_token",
        lambda token: decoded.append(token) or PRINCIPAL,
    )
    monkeypatch.setattr(
        deps,
        "get_user_client",
        lambda token: clients.append(token) or object(),
    )

    assert deps.get_current_user(request, None) == PRINCIPAL
    assert deps.get_request_token(request, None) == "access-token"
    first = deps.get_request_client(request, None)
    assert deps.get_request_client(request, None) is first
    assert decoded == ["access-token"]
    assert clients == ["access-token"]


def test_only_a_present_refresh_cookie_marks_a_missing_access_as_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deps, "cookie_name", lambda kind: f"hb_{kind}")
    refreshable = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/session",
            "headers": [(b"cookie", b"hb_refresh=refresh-token")],
        }
    )
    signed_out = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/session",
            "headers": [],
        }
    )

    with pytest.raises(AuthenticationError) as refresh_error:
        deps.get_current_user(refreshable, None)
    with pytest.raises(AuthenticationError) as signed_out_error:
        deps.get_current_user(signed_out, None)

    assert refresh_error.value.code == "token_expired"
    assert signed_out_error.value.code == "authentication_error"
