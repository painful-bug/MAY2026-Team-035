"""Which portal a membership lands in.

`portal` is the single value the frontend routes on -- `PORTAL_ROUTES` in
`frontend/src/routes/authRoutes.js` maps it to a landing route and
`applicationUser()` turns `security-manager` into the one role label four
screens and a route guard branch on. So a wrong answer here does not produce an
error anywhere; it produces a person who quietly never sees their own portal.

That is exactly what happened. `security-manager` was derived from a `manager`
membership naming a security department, and **nothing in the system writes a
`manager` membership** -- `hire_service_applicant` (`0035:918`) mints `security`
or `worker` and no other code path mints one at all. The portal was satisfiable
by no user the product can create, which is a defect no test could see because
no test asked. These are those questions.

The seam under test is `_portal_for`, called with a membership row exactly as
`get_session_context` reads it. `get_service_client` is monkeypatched, so the
last assertion in each case -- *which tables were read* -- is available, and it
is worth having: the roster read must not fire for a resident.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import auth_service

MEMBERSHIP_ID = "22222222-2222-4222-8222-222222222222"
DEPARTMENT_ID = "33333333-3333-4333-8333-333333333333"


class _Result:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _Query:
    """The slice of the PostgREST builder `_portal_for` uses."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def select(self, *_: Any, **__: Any) -> _Query:
        return self

    def eq(self, *_: Any) -> _Query:
        return self

    def in_(self, *_: Any) -> _Query:
        return self

    def limit(self, *_: Any) -> _Query:
        return self

    def execute(self) -> _Result:
        return _Result(self._rows)


class _ServiceClient:
    def __init__(self, rows_by_table: dict[str, list[dict[str, Any]]]) -> None:
        self._rows = rows_by_table
        self.tables: list[str] = []

    def table(self, name: str) -> _Query:
        self.tables.append(name)
        return _Query(self._rows.get(name, []))


@pytest.fixture
def service_client(monkeypatch: pytest.MonkeyPatch):
    def _install(**rows_by_table: list[dict[str, Any]]) -> _ServiceClient:
        client = _ServiceClient(rows_by_table)
        monkeypatch.setattr(auth_service, "get_service_client", lambda: client)
        return client

    return _install


def membership(role: str, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": MEMBERSHIP_ID,
        "community_id": "44444444-4444-4444-8444-444444444444",
        "role": role,
        "department_id": None,
        "is_default_community": True,
    }
    row.update(overrides)
    return row


def test_resident_admin_and_worker_are_their_own_portal(service_client) -> None:
    client = service_client()
    for role in ("resident", "admin", "worker"):
        assert auth_service._portal_for(membership(role), role) == role
    # No lookup at all off the two branches: three roles, zero reads.
    assert client.tables == []


def test_plain_guard_stays_at_the_gate(service_client) -> None:
    client = service_client(staff_assignments=[])
    assert auth_service._portal_for(membership("security"), "security") == "security"
    assert client.tables == ["staff_assignments"]


@pytest.mark.parametrize("rank", ["manager", "supervisor"])
def test_security_rank_seniority_opens_the_manager_portal(service_client, rank) -> None:
    """The spelling real people have.

    `gate_admin_community_for` (`0040:589`) admits a `security` membership whose
    active roster row ranks manager or supervisor, and `supervisor` is in that
    list deliberately -- a supervisor holds the manager's writes, so the guard
    portal would leave them permissions with no screen.
    """
    client = service_client(staff_assignments=[{"id": "roster-row", "rank": rank}])
    portal = auth_service._portal_for(membership("security"), "security")
    assert portal == "security-manager"
    assert client.tables == ["staff_assignments"]


def test_manager_of_a_security_department_still_resolves(service_client) -> None:
    """Unreachable today, and kept: `manager` is a real `membership_role`."""
    service_client(departments=[{"kind": "security"}])
    row = membership("manager", department_id=DEPARTMENT_ID)
    assert auth_service._portal_for(row, "manager") == "security-manager"


def test_manager_of_a_service_department_is_not_a_gate_manager(service_client) -> None:
    """The `departments.kind` question is the reason that branch exists."""
    service_client(departments=[{"kind": "service"}])
    row = membership("manager", department_id=DEPARTMENT_ID)
    assert auth_service._portal_for(row, "manager") == "manager"


def test_manager_without_a_department_reads_nothing(service_client) -> None:
    client = service_client()
    assert auth_service._portal_for(membership("manager"), "manager") == "manager"
    assert client.tables == []
