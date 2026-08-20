"""`20260820150000_admin_raised_complaints.sql` -- what a hand-applied file
cannot be allowed to get wrong.

This migration is pasted into the Supabase SQL editor by a person, once, against
a live database. There is no local Supabase in this repository's CI, so nothing
runs it before it runs for real. That raises the value of the checks a static
reader *can* make and narrows them to three questions:

**Is it idempotent?** It says so in its own header, and the header is not the
thing that makes it true. Every DDL statement in it must be guarded, because the
recovery from a half-applied hand-run is to run it again.

**Did the view survive the copy?** `complaint_overview` is dropped and recreated
here to gain one column. A `drop view` that recreates a *slightly* different view
is the failure mode: nothing errors, and the resident's list quietly loses
`isUnread`, or its overdue rule stops matching the admin's. So the new definition
is diffed line by line against `0031`'s, which is still the latest.

**Is the resident's path untouched?** The one instruction the spec gives that
this file could violate silently.

Whether Postgres accepts the bodies is a question only Postgres answers; `pglast`
parsing it is as close as this suite gets.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
ADMIN_RAISE = MIGRATIONS / "20260820150000_admin_raised_complaints.sql"
RESIDENT_COMPLAINTS = MIGRATIONS / "0031_resident_complaints.sql"
SKILL_SOURCED = MIGRATIONS / "20260813100000_skill_sourced_complaints.sql"
COLUMN_DRIFT = MIGRATIONS / "20260820120000_hosted_complaint_column_drift.sql"


def sql() -> str:
    return ADMIN_RAISE.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped.

    This file's header explains the product ruling behind the column at length.
    A check that read the prose would be asserting against its own explanation.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def view_body(text: str) -> str:
    """The `create view public.complaint_overview` block, up to its terminator."""
    start = re.search(r"^create view public\.complaint_overview", text, re.M)
    assert start, "complaint_overview is not created here"
    end = text.index("\n) rs on true;", start.start())
    return text[start.start() : end]


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_sorts_after_everything_it_builds_on() -> None:
    """Filename order is apply order.

    `0031` owns the view this recreates, `20260813100000` owns the
    `raise_complaint` whose pipeline is mirrored, and `20260820120000` adds the
    `complaint_events.payload` that `admin_raise_complaint` writes. Sorting
    before any of them would mean this file's work is undone, or attempted
    against a column that is not there yet.
    """
    for earlier in (RESIDENT_COMPLAINTS, SKILL_SOURCED, COLUMN_DRIFT):
        assert ADMIN_RAISE.name > earlier.name


def test_nothing_later_redeclares_the_view_or_the_function() -> None:
    """Last declaration of a name wins, and this file must be it."""
    clashes = [
        (path.name, name)
        for path in MIGRATIONS.glob("*.sql")
        if path.name > ADMIN_RAISE.name
        for name in ("complaint_overview", "admin_raise_complaint")
        if re.search(
            r"^create (or replace )?(view|function) public\." + name + r"\b",
            path.read_text(encoding="utf-8"),
            re.M,
        )
    ]
    assert not clashes, f"a later migration wins over this one: {clashes}"


def test_every_ddl_statement_is_guarded() -> None:
    """Re-running a hand-applied file must be a no-op.

    Each of these is the *only* unguarded form of its statement that this file
    could plausibly have been written with, which is why they are asserted
    absent rather than the guarded forms asserted present -- present says a
    guarded one exists, absent says an unguarded one does not.
    """
    body = statements(sql())

    assert "add column if not exists raised_via" in body
    assert not re.search(r"add column raised_via", body)
    # `add constraint` has no `if not exists`; the guard is the DO block.
    assert "where conname = 'complaints_raised_via_check'" in body
    assert "drop function if exists public.admin_raise_complaint(" in body
    assert "drop view if exists public.complaint_overview;" in body


def test_the_resident_raise_is_not_touched() -> None:
    """The spec's one prohibition. `raise_complaint` keeps the body
    `20260813100000` gave it, and this file adds a sibling rather than a fork."""
    body = statements(sql())

    assert not re.search(r"(create|drop) .*function public\.raise_complaint\(", body)
    assert "alter table public.complaints alter column" not in body
    assert "drop column" not in body


def test_the_column_defaults_to_the_value_every_existing_row_already_has() -> None:
    """No backfill statement, and none needed: until this file there was no way
    to raise a complaint other than from the resident portal, so `'resident'` is
    true of every row that exists. A migration that added the column nullable and
    then backfilled would have a window in which it was neither."""
    body = statements(sql())

    assert "raised_via text not null default 'resident'" in body
    assert "update public.complaints" not in body
    assert "check (raised_via in ('resident', 'admin'))" in body


def test_the_ownership_split_is_the_two_lines_the_ruling_names() -> None:
    """The product ruling in one assertion.

    `raised_by_membership_id` is the resident when one is named and the admin
    otherwise; `raised_via` is `'admin'` **only** in the unattached case. Getting
    the second backwards is the mistake that would put every on-behalf complaint
    on nobody's resident list -- silently, since the complaint would still exist
    and the admin portal would still show it.
    """
    body = statements(sql())

    assert "v_owner := coalesce(p_for_membership_id, p_actor_membership_id);" in body
    assert (
        "v_raised_via := case when p_for_membership_id is null "
        "then 'admin' else 'resident' end;" in body
    )


def test_the_raised_event_records_the_admin_as_the_actor() -> None:
    """In both modes. The row says whose complaint it is; the timeline says who
    acted. Writing the resident's membership there would forge a history entry --
    the one thing an append-only timeline exists to prevent."""
    body = statements(sql())

    assert (
        "values (v_id, p_actor_membership_id, 'raised', jsonb_build_object(" in body
    )
    assert "'on_behalf', p_for_membership_id is not null" in body


def test_the_pipeline_is_the_one_resident_complaints_already_enter() -> None:
    """Same department resolution, same SLA, same notification fan-out. A second
    complaint pipeline is how the admin's queue and the resident's start
    disagreeing about the same complaint."""
    body = statements(sql())

    assert (
        "public.resolve_complaint_department(v_community_id, v_category, "
        "p_department_id, p_skill_id)" in body
    )
    assert body.count("public.complaint_sla_hours(v_priority)") == 2
    assert (
        "public.notify_complaint_staff(v_id, 'complaint.raised', v_payload, "
        "p_actor_membership_id)" in body
    )


def test_the_new_view_is_0031s_definition_with_one_column_added() -> None:
    """Line by line, both directions.

    A `drop view` that recreates a subtly different view raises nothing. Every
    line of `0031`'s definition must still be here, and the only line this one
    adds must be the column it was recreated for.
    """
    applied = view_body(RESIDENT_COMPLAINTS.read_text(encoding="utf-8"))
    rewritten = view_body(sql())

    missing = [
        line.strip()
        for line in applied.splitlines()
        if line.strip() and line.strip() not in rewritten
    ]
    assert not missing, "the recreated view lost lines:\n  " + "\n  ".join(missing)

    added = [
        line.strip()
        for line in statements(rewritten).splitlines()
        if line.strip() and line.strip() not in applied
    ]
    assert added == ["c.raised_via,"], added


def test_the_view_restates_what_dropping_it_took_away() -> None:
    """`drop view` takes the comment and the grant with it -- unlike
    `create or replace function`, which keeps the oid and therefore keeps both.
    Losing the grant would make the resident's list a 401 from PostgREST."""
    body = statements(sql())

    assert "grant select on public.complaint_overview to authenticated;" in body
    assert "comment on view public.complaint_overview is" in body


def test_it_verifies_its_own_work_before_reporting_success() -> None:
    """The house shape for a hand-applied file: five claims, each of which fails
    the run rather than letting somebody believe it took."""
    body = statements(sql())

    for claim in (
        "raise exception 'complaints.raised_via missing or nullable'",
        "raise exception 'complaints_raised_via_check missing'",
        "raise exception 'admin_raise_complaint must have 9 arguments'",
        "raise exception 'raise_complaint is no longer the 8-argument function'",
        "raise exception 'complaint_overview does not expose raised_via'",
    ):
        assert claim in body


def test_the_function_the_backend_calls_is_the_function_that_exists() -> None:
    """The argument names are the RPC contract: PostgREST binds by name, so a
    rename on either side is a 404 at runtime and nothing at import time."""
    from app.repositories import complaints_repository

    source = Path(complaints_repository.__file__).read_text(encoding="utf-8")
    declared = re.search(
        r"create function public\.admin_raise_complaint\((.*?)\) returns uuid",
        sql(),
        re.S,
    )
    assert declared

    arguments = {
        match.group(1)
        for match in re.finditer(r"^\s*(p_\w+)\s+\w", declared.group(1), re.M)
    }
    assert arguments == {
        "p_actor_membership_id",
        "p_title",
        "p_description",
        "p_category",
        "p_priority",
        "p_location",
        "p_department_id",
        "p_skill_id",
        "p_for_membership_id",
    }
    for argument in arguments:
        assert f'"{argument}"' in source, f"{argument} is never sent by the repository"
