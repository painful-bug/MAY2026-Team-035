"""Ruling 3 on the one read the BFF composes itself.

    "Once a supervisor/manager is removed from a community and later invited to
    a different one, they must not be able to see ANYTHING from the old
    community." -- product owner, 2026-08-21.

Almost every read that ruling covers is decided in Postgres: the calendar and
job list through ``is_own_staff_assignment``, the complaint queue through
``can_supervise_department``, the mailbox and the feed through RLS policies.
None of those is reachable without a database, and all of them are asserted
statically in ``test_leadership_exclusivity_migration.py``.

``list_engagements_for_profile`` is the exception. It is four plain PostgREST
reads stitched together in Python -- and it is the *only* read that can see a
provisioned manager or supervisor at all, because leadership holds no
``service_providers`` row and every provider-keyed path is blind to it. It fills
``communities[]`` on the worker snapshot, which is where the supervisor's
Complaints screen finds a department to ask about. If it returned the ended
community-A engagement, the removed supervisor would be looking at community A's
name on their own dashboard.

So the filters are asserted where they are written, against a fake client that
records what was asked rather than what came back. Asserting the *rows* would
pass just as well against a repository with no filters at all and a fixture that
happens to contain only live ones.
"""

from __future__ import annotations

from typing import Any

from app.repositories import hiring_repository


class _Response:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _Query:
    """A PostgREST builder that writes down every predicate it is given."""

    def __init__(self, table: str, log: list[tuple[str, Any]], rows: list[dict]) -> None:
        self._table = table
        self._log = log
        self._rows = rows

    def select(self, *args: Any, **kwargs: Any) -> "_Query":
        return self

    def eq(self, column: str, value: Any) -> "_Query":
        self._log.append((self._table, ("eq", column, value)))
        return self

    def is_(self, column: str, value: Any) -> "_Query":
        self._log.append((self._table, ("is", column, value)))
        return self

    def in_(self, column: str, values: Any) -> "_Query":
        # A tuple, not a list: these entries go into a set, and the assertion
        # is about *which* memberships were asked for, not their order.
        self._log.append((self._table, ("in", column, tuple(values))))
        return self

    def execute(self) -> _Response:
        return _Response(self._rows)


class _Client:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.log: list[tuple[str, Any]] = []

    def table(self, name: str) -> _Query:
        return _Query(name, self.log, self.tables.get(name, []))


def _predicates(client: _Client, table: str) -> set[tuple[str, str, Any]]:
    return {entry for name, entry in client.log if name == table}


def _client_for_a_supervisor_who_moved() -> _Client:
    """Community A is over; community B is live.

    The ended community-A membership and its deactivated roster row are present
    in the fake tables on purpose: the repository is supposed to be the thing
    that drops them, and a fixture that omitted them would prove nothing.
    """
    return _Client(
        {
            "community_memberships": [
                {"id": "membership-b", "community_id": "community-b", "role": "worker"}
            ],
            "staff_assignments": [
                {
                    "id": "staff-b",
                    "community_id": "community-b",
                    "department_id": "department-b",
                    "membership_id": "membership-b",
                    "rank": "supervisor",
                    "job_title": "Supervisor",
                    "shift": None,
                    "status": "active",
                    "started_at": "2026-08-20",
                    "ended_at": None,
                }
            ],
            "departments": [
                {"id": "department-b", "name": "Electrical", "kind": "service"}
            ],
            "communities": [
                {"id": "community-b", "name": "Blue Waters", "city": "Kochi"}
            ],
        }
    )


def test_the_membership_read_asks_only_for_live_memberships() -> None:
    """``status = 'active'`` **and** ``ended_at is null``, both.

    They are not the same question. ``0043``'s ``remove_department_member``
    writes both, but the baseline's older paths set one or the other, and a read
    that asked for only the first would admit a membership somebody ended
    without restatusing it.
    """
    client = _client_for_a_supervisor_who_moved()

    hiring_repository.list_engagements_for_profile(
        client, profile_id="profile-id"  # type: ignore[arg-type]
    )

    predicates = _predicates(client, "community_memberships")
    assert ("eq", "profile_id", "profile-id") in predicates
    assert ("eq", "status", "active") in predicates
    assert ("is", "ended_at", None) in predicates


def test_the_roster_read_asks_only_for_live_assignments_by_default() -> None:
    """``active_only`` defaults to True, and the snapshot leaves it there.

    The parameter exists for a "communities I have worked in" screen that has
    never been built. The default is what ruling 3 rides on, so the default is
    what is pinned.
    """
    client = _client_for_a_supervisor_who_moved()

    hiring_repository.list_engagements_for_profile(
        client, profile_id="profile-id"  # type: ignore[arg-type]
    )

    predicates = _predicates(client, "staff_assignments")
    assert ("eq", "status", "active") in predicates
    # Leadership only: a roster row that also names a provider is already
    # returned by the provider-keyed read, and returning it twice would make the
    # two disagree about how many communities employ somebody.
    assert ("is", "service_provider_id", None) in predicates
    # Keyed to the memberships the first read allowed through, so an ended
    # membership's roster row is unreachable even if it were still active.
    assert ("in", "membership_id", ("membership-b",)) in predicates


def test_an_account_with_no_live_membership_gets_nothing_at_all() -> None:
    """A supervisor removed from A and not yet invited anywhere.

    The short-circuit matters: without it the roster read would run with an
    empty ``in_`` list, and an empty ``in`` is a filter that matches nothing on
    PostgREST but is a filter this code would rather not depend on.
    """
    client = _Client({"community_memberships": []})

    assert (
        hiring_repository.list_engagements_for_profile(
            client, profile_id="profile-id"  # type: ignore[arg-type]
        )
        == []
    )
    assert _predicates(client, "staff_assignments") == set()


def test_the_engagement_that_survives_is_the_live_one() -> None:
    client = _client_for_a_supervisor_who_moved()

    rows = hiring_repository.list_engagements_for_profile(
        client, profile_id="profile-id"  # type: ignore[arg-type]
    )

    assert [row["community_id"] for row in rows] == ["community-b"]
    assert rows[0]["rank"] == "supervisor"
    assert rows[0]["community_name"] == "Blue Waters"
