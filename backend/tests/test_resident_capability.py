"""The resident capability, which is a residency and not a role.

`require_membership_role("resident")` guarded the resident verbs -- cancel work,
reopen, confirm a resolution, answer a proposed visit -- and refused them to the
admin who owns flat B-402. That was never a policy anybody chose. One
`community_memberships` row exists per person per community
(`memberships_active_person_community`, `0001_baseline.sql:45`), so the person
who both runs the association and lives in it has exactly one membership and its
role says `admin`; the fact that they are also a resident lives in
`unit_residencies` and nowhere else.

`require_resident_capability` asks `unit_residencies`. These tests pin the three
things that makes true and the two it must not change:

1. `resident` passes with **no query at all** -- the guard runs on every one of
   these routes and the common caller must not pay for the uncommon one.
2. Any other role passes if and only if an active residency row exists.
3. The query is the one the session layer already runs
   (`app/services/auth_service.py:463-471`): `unit_residencies`, membership
   equality, `ended_at is null`, one row.
4. The refusal is byte-identical to the role guard's -- same message, same
   `community_role_required` code. Widening who passes must not be a wire change.
5. It still refuses staff who live nowhere, which is the whole reason the routes
   are guarded.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.api import deps
from app.core.exceptions import AuthorizationError
from app.domain.schemas import MembershipContext


class _Result:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _Query:
    """The slice of the PostgREST builder the residency lookup uses."""

    def __init__(self, rows: list[dict[str, Any]], log: dict[str, Any]) -> None:
        self._rows = rows
        self._log = log

    def select(self, *columns: Any, **__: Any) -> _Query:
        self._log["select"] = columns
        return self

    def eq(self, column: str, value: Any) -> _Query:
        self._log.setdefault("eq", []).append((column, value))
        return self

    def is_(self, column: str, value: Any) -> _Query:
        self._log.setdefault("is_", []).append((column, value))
        return self

    def limit(self, count: int) -> _Query:
        self._log["limit"] = count
        return self

    def execute(self) -> _Result:
        return _Result(self._rows)


class _ServiceClient:
    def __init__(self, rows: list[dict[str, Any]], log: dict[str, Any]) -> None:
        self._rows = rows
        self._log = log

    def table(self, name: str) -> _Query:
        self._log.setdefault("tables", []).append(name)
        return _Query(self._rows, self._log)


def stub_residencies(
    monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Point the guard's service client at ``rows`` and record what it asks."""
    log: dict[str, Any] = {}
    monkeypatch.setattr(deps, "get_service_client", lambda: _ServiceClient(rows, log))
    return log


def membership(role: str) -> MembershipContext:
    return MembershipContext(
        id="membership-id", community_id="community-id", role=role, department_id=None
    )


@pytest.fixture
def guard():
    """The dependency callable, built the way the routers build it."""
    return deps.require_resident_capability()


def test_a_resident_passes_without_a_single_query(
    guard, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The role is already the answer, and this guard sits on every resident
    write in the product. A round trip that could only ever confirm what the
    role column already said is a round trip on every one of them."""
    expected_output = {"passed": True, "tables": []}

    log = stub_residencies(monkeypatch, [{"id": "residency-id"}])
    result = guard(membership("resident"))
    actual_output = {
        "passed": result.role == "resident",
        "tables": log.get("tables", []),
    }

    assert actual_output == expected_output


def test_an_admin_who_lives_here_passes(
    guard, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason this exists. An admin with a flat is the resident of that flat,
    and the role column was never where that fact was recorded."""
    expected_output = "admin"

    stub_residencies(monkeypatch, [{"id": "residency-id"}])
    actual_output = guard(membership("admin")).role

    assert actual_output == expected_output


def test_an_admin_who_lives_nowhere_is_refused(
    guard, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard is not a licence for staff. An association secretary who lives
    across town still may not confirm a resolution on somebody's home; the
    admin portal's own raise endpoint is where their complaints go."""
    expected_output = {
        "code": "community_role_required",
        "message": "You do not have permission for this community action.",
    }

    stub_residencies(monkeypatch, [])
    with pytest.raises(AuthorizationError) as raised:
        guard(membership("admin"))
    actual_output = {
        "code": raised.value.code,
        "message": raised.value.message,
    }

    assert actual_output == expected_output


def test_the_refusal_is_identical_to_the_role_guard_s(
    guard, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Widening who passes is not a wire change. Every client that already
    handles the resident 403 must keep handling this one, so the two refusals
    are compared to each other rather than to a literal."""
    stub_residencies(monkeypatch, [])
    with pytest.raises(AuthorizationError) as widened:
        guard(membership("worker"))
    with pytest.raises(AuthorizationError) as original:
        deps.require_membership_role("resident")(membership("worker"))

    expected_output = (original.value.code, original.value.message)
    actual_output = (widened.value.code, widened.value.message)

    assert actual_output == expected_output


def test_the_lookup_is_the_one_the_session_layer_already_runs(
    guard, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`unit_residencies`, this membership, `ended_at is null`, one row. Two
    places answering "is this person resident here" must not be able to
    disagree, and `ended_at is null` is also the predicate the partial unique
    index `residencies_active_member_unit` is built on."""
    expected_output = {
        "tables": ["unit_residencies"],
        "eq": [("membership_id", "membership-id")],
        "is_": [("ended_at", None)],
        "limit": 1,
    }

    log = stub_residencies(monkeypatch, [{"id": "residency-id"}])
    guard(membership("admin"))
    actual_output = {
        "tables": log["tables"],
        "eq": log["eq"],
        "is_": log["is_"],
        "limit": log["limit"],
    }

    assert actual_output == expected_output


def test_one_query_and_not_two(guard, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard runs on every write it protects, so a duplicated read here is
    a duplicated read on all of them."""
    expected_output = 1

    log = stub_residencies(monkeypatch, [{"id": "residency-id"}])
    guard(membership("manager"))
    actual_output = len(log["tables"])

    assert actual_output == expected_output


def test_a_past_tenant_is_not_a_resident(
    guard, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row is filtered in the database, so "moved out" arrives here as no
    rows. Pinned because a guard that read the residencies and then decided in
    Python is one refactor away from forgetting the `ended_at` test."""
    expected_output = "community_role_required"

    stub_residencies(monkeypatch, [])
    with pytest.raises(AuthorizationError) as raised:
        guard(membership("security"))
    actual_output = raised.value.code

    assert actual_output == expected_output
