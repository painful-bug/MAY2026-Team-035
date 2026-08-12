"""The tenancy seam, after it learned about more than one community.

`app/api/deps.py` used to resolve exactly one membership -- `order by
is_default_community desc limit 1` -- and every handler in the product was
written against that. A service person breaks the assumption: they belong to as
many communities as have hired them, and their calendar is the union of all of
them.

The change was made additively, and **additive is a claim these tests exist to
check.** Three properties, in order of how expensive they would be to discover
in production:

1. `get_active_membership` still returns what it returned before, still takes a
   `Principal`, and can still be called directly rather than through FastAPI.
   The last of those is not decoration -- `tests/api/test_session_flow.py` calls
   it positionally to prove the role comes from `community_memberships` and not
   from a token claim, and an earlier draft of this change broke that by
   declaring `Depends(get_membership_set)` in its signature. To FastAPI the two
   read identically; to a caller they do not.
2. Ordering is preserved: default first, then oldest.
3. `require_community_role` refuses a community the caller is not in, which is
   what stops a resource id in a URL from being an authorization decision.

`app/api/deps.py` belongs to the parallel auth workstream. These tests are the
evidence offered with that review request.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.api import deps
from app.core.exceptions import AuthorizationError
from app.domain.schemas import MembershipSet, Principal

PROFILE_ID = "11111111-1111-4111-8111-111111111111"


class _Result:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _Query:
    """The narrow slice of the PostgREST builder the resolver uses."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def select(self, *_: Any, **__: Any) -> _Query:
        return self

    def eq(self, *_: Any) -> _Query:
        return self

    def is_(self, *_: Any) -> _Query:
        return self

    def order(self, *_: Any, **__: Any) -> _Query:
        return self

    def execute(self) -> _Result:
        return _Result(self._rows)


class _ServiceClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.tables: list[str] = []

    def table(self, name: str) -> _Query:
        self.tables.append(name)
        return _Query(self._rows)


def membership_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "membership-id",
        "community_id": "community-id",
        "role": "resident",
        "department_id": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def principal() -> Principal:
    return Principal(user_id=PROFILE_ID, email_verified=True)


def stub_rows(
    monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]
) -> _ServiceClient:
    client = _ServiceClient(rows)
    monkeypatch.setattr(deps, "get_service_client", lambda: client)
    return client


def test_a_single_membership_caller_gets_exactly_what_they_got_before(
    monkeypatch: pytest.MonkeyPatch, principal: Principal
) -> None:
    """The overwhelmingly common case, and the one every existing handler is
    written against."""
    expected_output = {
        "id": "membership-id",
        "community_id": "community-id",
        "role": "resident",
    }

    stub_rows(monkeypatch, [membership_row()])
    membership = deps.get_active_membership(principal)
    actual_output = {
        "id": membership.id,
        "community_id": membership.community_id,
        "role": membership.role,
    }

    assert actual_output == expected_output


def test_get_active_membership_is_still_callable_with_a_principal(
    monkeypatch: pytest.MonkeyPatch, principal: Principal
) -> None:
    """The regression that a draft of this change actually introduced.

    Declaring `Depends(get_membership_set)` on this function reads identically to
    FastAPI and breaks every direct call, including the session-flow test that
    proves the role is not read from the token."""
    expected_output = {"raises": False, "role": "resident"}

    stub_rows(monkeypatch, [membership_row()])
    membership = deps.get_active_membership(principal)
    actual_output = {"raises": False, "role": membership.role}

    assert actual_output == expected_output


def test_the_default_membership_is_the_first_row(
    monkeypatch: pytest.MonkeyPatch, principal: Principal
) -> None:
    """`is_default_community desc, created_at` is applied by Postgres, so the
    resolver must not re-sort -- it must trust position."""
    expected_output = "default-community"

    stub_rows(
        monkeypatch,
        [
            membership_row(id="m1", community_id="default-community"),
            membership_row(id="m2", community_id="other-community", role="worker"),
        ],
    )
    actual_output = deps.get_active_membership(principal).community_id

    assert actual_output == expected_output


def test_every_active_membership_is_returned_not_just_the_first(
    monkeypatch: pytest.MonkeyPatch, principal: Principal
) -> None:
    """The whole reason the seam changed: a service person hired by three
    societies has three memberships and one calendar."""
    expected_output = ["a", "b", "c"]

    stub_rows(
        monkeypatch,
        [
            membership_row(id="m1", community_id="a", role="worker"),
            membership_row(id="m2", community_id="b", role="worker"),
            membership_row(id="m3", community_id="c", role="security"),
        ],
    )
    actual_output = deps.get_membership_set(principal).community_ids

    assert actual_output == expected_output


def test_the_resolver_reads_community_memberships_once(
    monkeypatch: pytest.MonkeyPatch, principal: Principal
) -> None:
    """Dropping `limit 1` must not have cost a second round trip. Membership is
    resolved on every single request; a duplicated read here is a duplicated read
    everywhere."""
    expected_output = ["community_memberships"]

    client = stub_rows(monkeypatch, [membership_row()])
    deps.get_active_membership(principal)
    actual_output = client.tables

    assert actual_output == expected_output


def test_a_caller_with_no_active_membership_is_still_refused(
    monkeypatch: pytest.MonkeyPatch, principal: Principal
) -> None:
    """Unchanged behaviour, and worth pinning: this 403 is what stands between a
    signed-in stranger and every membership-guarded route in the product."""
    expected_output = "active_membership_required"

    stub_rows(monkeypatch, [])
    with pytest.raises(AuthorizationError) as raised:
        deps.get_active_membership(principal)
    actual_output = raised.value.code

    assert actual_output == expected_output


def test_for_community_returns_none_rather_than_guessing(
    monkeypatch: pytest.MonkeyPatch, principal: Principal
) -> None:
    """`MembershipSet` deliberately carries no raising method -- the 403 lives in
    `deps.py`, so `app/domain` never has to import `app/core`."""
    expected_output = {"known": "worker", "unknown": None}

    stub_rows(
        monkeypatch,
        [membership_row(community_id="a", role="worker")],
    )
    memberships = deps.get_membership_set(principal)
    found = memberships.for_community("a")
    actual_output = {
        "known": found.role if found else None,
        "unknown": memberships.for_community("b"),
    }

    assert actual_output == expected_output


def test_require_community_role_refuses_a_community_the_caller_is_not_in() -> None:
    """The point of the helper. A community id arriving on a resource -- a job, an
    application, a department -- must never be an authorization decision by
    itself."""
    expected_output = "community_role_required"

    memberships = MembershipSet(
        memberships=[
            deps.MembershipContext(
                id="m1", community_id="a", role="worker", department_id=None
            )
        ]
    )
    with pytest.raises(AuthorizationError) as raised:
        deps.require_community_role("b", memberships, "worker")
    actual_output = raised.value.code

    assert actual_output == expected_output


def test_require_community_role_refuses_the_right_community_with_the_wrong_role() -> (
    None
):
    """Being in the community is not being entitled in it."""
    expected_output = "community_role_required"

    memberships = MembershipSet(
        memberships=[
            deps.MembershipContext(
                id="m1", community_id="a", role="resident", department_id=None
            )
        ]
    )
    with pytest.raises(AuthorizationError) as raised:
        deps.require_community_role("a", memberships, "worker", "security")
    actual_output = raised.value.code

    assert actual_output == expected_output


def test_require_community_role_allows_any_role_when_none_is_named() -> None:
    """"Are you in this community at all" is a real question, asked by every
    read a member of it may make."""
    expected_output = "resident"

    memberships = MembershipSet(
        memberships=[
            deps.MembershipContext(
                id="m1", community_id="a", role="resident", department_id=None
            )
        ]
    )
    actual_output = deps.require_community_role("a", memberships).role

    assert actual_output == expected_output
