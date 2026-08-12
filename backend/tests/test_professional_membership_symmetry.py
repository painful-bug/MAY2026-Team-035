"""The separate-account rule, enforced in both directions.

`20260812113000_professional_membership_symmetry.sql` is the product owner's
2026-08-12 ruling on `docs/potential issues/16`: a registered service
professional is assumed not to live in any association, so the rule is identity
separation and the direction nobody was watching -- register as a professional
first, join as a resident second -- has to be refused too.

These are static checks, like `test_service_professional_migrations.py`. They
cannot show that Postgres refuses the insert; the CI job that resets a local
Supabase and applies every migration could, and does not cover this yet. What
they can show is that the statement the database will run says what the ruling
says, and that the refusal it raises is one the API knows how to shape -- which
is the half that would otherwise be found by an administrator staring at a 500.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pglast import parse_sql

from app.core.exceptions import ConflictError
from app.repositories import memberships_repository

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
SYMMETRY = MIGRATIONS / "20260812113000_professional_membership_symmetry.sql"
SERVICE = MIGRATIONS / "20260811162409_service_professional_onboarding.sql"


def _trigger_body(sql: str) -> str:
    """The one function body this file redefines."""
    after = sql.split(
        "create or replace function public.enforce_professional_membership_mode()", 1
    )[1]
    return after.split("$$;", 1)[0]


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(SYMMETRY.read_text())


def test_it_sorts_after_the_last_unapplied_migration() -> None:
    """Forward-only: filename order is apply order, and `090300` is the floor.

    Not "is the last file in the directory". That was the original assertion and
    it was wrong within the day: `20260812120000` was written after this one, and
    a later migration arriving is the system working, not a regression here.
    What has to hold is that this file lands after everything it depends on --
    `20260811162409`, whose trigger body it extends, and the four `20260812090…`
    files that were the unapplied frontier when it was written.
    """
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert SYMMETRY.name in names
    assert SYMMETRY.name > "20260812090300_complaint_department_routing.sql"
    assert SYMMETRY.name > SERVICE.name


def test_a_professional_is_refused_a_resident_manager_or_admin_membership() -> None:
    body = _trigger_body(SYMMETRY.read_text())
    refusal = body.split("raise exception", 1)[1]

    assert "new.role not in ('worker', 'security')" in body
    assert "new.status = 'active'" in body
    assert "new.ended_at is null" in body
    assert (
        "exists (select 1 from public.service_providers "
        "where profile_id = new.profile_id)"
    ) in body
    assert "registered as a service professional" in refusal
    assert "using errcode = 'HBSEP'" in refusal


def test_the_worker_security_refusal_it_was_extracted_from_survives() -> None:
    """The body is a copy of an applied one; the copy must not lose anything."""
    body = _trigger_body(SYMMETRY.read_text())
    applied = _trigger_body(SERVICE.read_text())

    for statement in (
        "and m.role in ('worker', 'security')",
        "and m.role <> new.role",
        "raise exception 'A professional account cannot mix worker and security "
        "memberships.' using errcode = 'HB409';",
    ):
        assert statement in applied
        assert statement in body
    # Every line of the applied body still appears, so the extraction is
    # provably additive rather than a rewrite that happens to look similar.
    for line in (line.strip() for line in applied.splitlines()):
        if line:
            assert line in body


def test_the_new_predicate_is_marked_as_the_difference() -> None:
    """House discipline: a copied body marks every departure `-- CHANGED`."""
    body = _trigger_body(SYMMETRY.read_text())
    assert "-- CHANGED" in body
    assert body.index("-- CHANGED") < body.index("raise exception")


def test_the_definer_function_keeps_its_execute_revocation() -> None:
    sql = SYMMETRY.read_text()
    assert (
        "revoke all on function public.enforce_professional_membership_mode() "
        "from public, anon, authenticated"
    ) in sql


def test_existing_violations_are_reported_and_never_repaired() -> None:
    """Which identity to keep is the account holder's decision, not a DDL file's.

    Ending the membership evicts a household from its portal; deleting the
    provider row destroys hiring history. A migration that picked one would be
    making that call for every affected account at once, in the dark.
    """
    sql = SYMMETRY.read_text().lower()
    assert "raise notice" in sql
    for destructive in (
        "delete from public.community_memberships",
        "delete from public.service_providers",
        "update public.community_memberships",
        "update public.service_providers",
    ):
        assert destructive not in sql


def test_no_applied_migration_was_edited_to_make_room_for_this() -> None:
    """The refusal is added forward; `…162409` still reads as it was applied."""
    applied = _trigger_body(SERVICE.read_text())
    assert "HBSEP" not in applied
    assert "HBSEP" not in SERVICE.read_text()


def test_the_stale_search_comment_is_reissued_against_the_installed_body() -> None:
    """`0034:531` still promises behaviour `…162409` replaced.

    The comment says a community with no coordinates "sorts last rather than
    being hidden". The body installed today filters on `c.location is not null`
    and orders by a distance with no `nulls last`, so such a community is
    hidden. A `comment on` is what `\\df+` shows a reader inside the database,
    where there is no migration file beside it to correct the record.
    """
    stale = (MIGRATIONS / "0034_service_providers.sql").read_text()
    installed = (SERVICE.read_text()).split(
        "create or replace function public.search_serviceable_communities", 1
    )[1]
    sql = SYMMETRY.read_text()

    assert "last rather than being hidden" in stale
    assert "c.location is not null" in installed
    assert "nulls last" not in installed.split("$$;", 1)[0]

    comment = sql.split(
        "comment on function public.search_serviceable_communities"
        "(text, integer, integer) is",
        1,
    )[1]
    assert "is excluded, not " in comment
    assert "sorted last" in comment
    # Documentation only: nothing about the search is redefined here.
    assert "create or replace function public.search_serviceable_communities" not in sql


# ---------------------------------------------------------------------------
# The refusal, arriving at the API
#
# Two RPCs can now raise `HBSEP`: `approve_access_request`, covered in
# `tests/api/test_access_requests.py`, and `claim_email_invitation`, which is
# below because its call site had no error handling at all -- the SDK's
# exception went to the 500 handler, which tells somebody holding a valid
# invitation that the server broke and to try again.
# ---------------------------------------------------------------------------


class _RefusingRpc:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def rpc(self, _name: str, _params: dict) -> _RefusingRpc:
        return self

    def execute(self) -> None:
        raise self._exc


class _FakeAPIError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def test_claiming_an_invite_on_a_professional_account_is_a_conflict() -> None:
    error = _FakeAPIError(
        "HBSEP",
        "This account is registered as a service professional. Use a separate "
        "account to join a community as a resident, manager or administrator.",
    )
    with pytest.raises(ConflictError) as raised:
        memberships_repository.claim_resident_invite(
            _RefusingRpc(error), invite_id="invite-id", profile_id="profile-id"
        )
    assert raised.value.code == "professional_account_separate"
    assert "separate account" in raised.value.message


def test_an_unrecognised_claim_failure_does_not_leak_postgres_text() -> None:
    with pytest.raises(Exception) as raised:
        memberships_repository.claim_resident_invite(
            _RefusingRpc(_FakeAPIError("XX000", 'relation "secret_table" is dead')),
            invite_id="invite-id",
            profile_id="profile-id",
        )
    assert "secret_table" not in str(raised.value)
    assert "This invite could not be claimed." in str(raised.value)
