"""What `capabilities` on the session promises, and who it promises it to.

`GET /auth/session` returns a list of words the frontend renders navigation
from. It is the *only* thing that decides whether an admin is offered the
resident portal at all -- there is no second check in the browser -- which makes
a wrong entry here invisible in exactly the way a wrong `portal` value is:
nothing errors, somebody is simply shown a door.

**The rule under test.** An admin is also a resident when they actually live
here. There is one `community_memberships` row per person per community
(`0001_baseline.sql`:45), so admin-ness and resident-ness are not two rows and
not two roles; resident-ness is an active `unit_residencies` row and nothing
else (product ruling, 2026-08-20). `require_resident_capability`
(`app/api/deps.py`) asks that table per request. This is the same question asked
once, at sign-in, from a read the session already performs -- so the two cannot
disagree.

They did. `capabilities.append("resident")` fired on `role == "admin"` alone,
which meant a flat-less admin -- a managing-committee member who owns nothing in
the society, which is common -- was shown the resident portal and then refused by
the guard on the first thing they clicked in it. A 403 nobody can act on is worse
than an absent menu item, because it looks like a bug in the software rather than
a fact about the account.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.schemas import Principal, Profile
from app.services import auth_service

MEMBERSHIP_ID = "22222222-2222-4222-8222-222222222222"
COMMUNITY_ID = "44444444-4444-4444-8444-444444444444"
UNIT_ID = "55555555-5555-4555-8555-555555555555"

PRINCIPAL = Principal(
    user_id="11111111-1111-4111-8111-111111111111",
    email="chair@example.com",
    email_verified=True,
    full_name="Priya Nair",
)


class _Query:
    """The slice of the PostgREST builder the session reads use."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def select(self, *_: Any, **__: Any) -> _Query:
        return self

    def eq(self, *_: Any) -> _Query:
        return self

    def is_(self, *_: Any) -> _Query:
        return self

    def limit(self, *_: Any) -> _Query:
        return self

    def execute(self) -> Any:
        return type("Result", (), {"data": self._rows})()


class _ServiceClient:
    def __init__(self, rows_by_table: dict[str, list[dict[str, Any]]]) -> None:
        self._rows = rows_by_table
        self.tables: list[str] = []

    def table(self, name: str) -> _Query:
        self.tables.append(name)
        return _Query(self._rows.get(name, []))


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch):
    """Build a session for one membership, with or without a residency.

    `_active_memberships` and the profile read are replaced rather than faked
    through the client: both are settled behaviour with tests of their own, and
    reproducing their query shapes here would make this module fail for reasons
    that have nothing to do with what it asks.
    """

    def _build(role: str, *, residency: bool) -> tuple[Any, _ServiceClient]:
        residency_rows = []
        if residency:
            residency_rows = [
                {
                    "unit_id": UNIT_ID,
                    "units": {
                        "unit_code": "4B",
                        "unit_type": "flat",
                        "buildings": {
                            "name": "Emerald",
                            "building_type": "block",
                        },
                    },
                }
            ]
        client = _ServiceClient(
            {
                "unit_residencies": residency_rows,
            }
        )
        monkeypatch.setattr(auth_service, "get_service_client", lambda: client)
        monkeypatch.setattr(
            auth_service.profiles_repository,
            "get_profile",
            lambda _client, user_id: Profile(id=user_id, full_name="Priya Nair"),
        )
        monkeypatch.setattr(
            auth_service,
            "_active_memberships",
            lambda _profile_id: [
                {
                    "id": MEMBERSHIP_ID,
                    "community_id": COMMUNITY_ID,
                    "role": role,
                    "department_id": None,
                    "is_default_community": True,
                }
            ],
        )
        return auth_service.get_session_context(object(), PRINCIPAL, "token"), client

    return _build


def test_an_admin_who_lives_here_is_also_a_resident(session) -> None:
    """Both capabilities, and the residency is what earns the second one."""
    context, _ = session("admin", residency=True)

    assert context.capabilities == ["admin", "resident"]
    assert context.membership.unit_id == UNIT_ID
    assert context.membership.unit.unit_code == "4B"
    assert context.membership.unit.building_name == "Emerald"


def test_an_admin_who_lives_nowhere_is_only_an_admin(session) -> None:
    """The defect this module exists for.

    A committee member who owns no flat is an ordinary account, not an edge
    case. The session used to hand them the resident portal on the strength of
    their role, and `require_resident_capability` would then refuse every write
    inside it -- so the menu item was real and everything behind it was a 403.
    """
    context, _ = session("admin", residency=False)

    assert context.capabilities == ["admin"]
    assert context.membership.unit_id is None


def test_the_answer_comes_from_the_residency_table(session) -> None:
    """Same table `require_resident_capability` asks, which is the whole point:
    one source, so the session and the per-request guard cannot drift."""
    _, client = session("admin", residency=False)

    assert "unit_residencies" in client.tables
    assert "units" not in client.tables


def test_a_resident_is_not_given_a_second_copy_of_their_own_capability(
    session,
) -> None:
    """The grant is admin-only. A resident's capability is their role, and the
    predicate must not have turned into "anyone with a residency"."""
    context, _ = session("resident", residency=True)

    assert context.capabilities == ["resident"]


def test_a_manager_with_a_flat_is_still_only_a_manager(session) -> None:
    """The ruling is about admins specifically, and widening it here would be a
    product decision wearing the clothes of a consistency fix. A manager who
    lives in the society reaches the resident portal the same way anybody else
    does -- by holding a `resident` membership -- and that is not this row."""
    context, _ = session("manager", residency=True)

    assert context.capabilities == ["manager"]
