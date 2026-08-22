"""`20260822090000_hosted_work_order_column_drift.sql` -- what a static reader
can prove about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a
live database whose `work_orders` table predates `0001_baseline.sql` and
carries hand-built legacy columns the repository has never declared. One of
them (`title`, NOT NULL, no default) rejected every `create_work_order` insert
with SQLSTATE 23502 -- found live on 2026-08-22, when a supervisor's "Raise it"
button answered 422 "Could not raise that job."

The file is a sweep, not a named fix, because `20260820120000` 3 taught the
lesson that these constraints bite one behind the other. A sweep's one real
hazard is its protected list: a repository column wrongly *missing* from that
list would have its NOT NULL dropped on the hosted table, silently weakening a
constraint the repository relies on. So the list is not reviewed here -- it is
**derived** from the declaring migrations' own text and compared exactly.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
DRIFT = MIGRATIONS / "20260822090000_hosted_work_order_column_drift.sql"

#: The three files whose declarations are the protected list, and the sibling
#: whose pattern this file follows.
BASELINE = MIGRATIONS / "0001_baseline.sql"
WORK_ORDERS = MIGRATIONS / "0036_work_orders.sql"
CANCELLED_BY = MIGRATIONS / "20260813101000_offer_consent_and_force.sql"
PRECEDENT = MIGRATIONS / "20260820120000_hosted_complaint_column_drift.sql"


def sql() -> str:
    return DRIFT.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped, so no check ever
    asserts against the header's prose instead of the SQL."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def declared_columns() -> set[str]:
    """Every `work_orders` column the repository declares, from the files that
    declare them -- not from anyone's memory of them."""
    baseline = BASELINE.read_text(encoding="utf-8")
    line = next(
        ln for ln in baseline.splitlines()
        if ln.startswith("create table public.work_orders ")
    )
    body = line[line.index("(") + 1 : line.rindex(")")]
    columns = {
        part.strip().split()[0]
        for part in body.split(", ")
        if part.strip() and not part.strip().startswith(("unique", "primary", "check"))
    }

    for path in (WORK_ORDERS, CANCELLED_BY):
        text = path.read_text(encoding="utf-8")
        # Only the work_orders alters; 0036 also extends other tables.
        for block in re.findall(
            r"alter table public\.work_orders\s+((?:.|\n)*?);", text
        ):
            columns.update(
                re.findall(r"add column if not exists\s+(\w+)", block)
            )
    return columns


def protected_lists() -> list[set[str]]:
    """Each ``not in (...)`` list in the file, as a set of column names."""
    lists = []
    for group in re.findall(
        r"column_name not in \(((?:[^()])*?)\)", statements(sql()), re.S
    ):
        lists.append(set(re.findall(r"'(\w+)'", group)))
    return lists


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_sorts_after_every_file_it_reasons_about() -> None:
    """Filename order is apply order. This file must postdate the last
    repository declaration it protects and the precedent it cites -- and, as
    of the day it was written, everything else in the directory."""
    for earlier in (BASELINE, WORK_ORDERS, CANCELLED_BY, PRECEDENT):
        assert DRIFT.name > earlier.name


def test_the_protected_list_is_exactly_the_repository_declaration() -> None:
    """The sweep's one real hazard, held by derivation rather than review.

    A repository column missing from the list would get its NOT NULL dropped
    on the hosted table; a name in the list that no migration declares would
    protect a legacy column and leave the 422 alive behind a passing apply.
    """
    declared = declared_columns()
    lists = protected_lists()

    assert len(lists) == 2, "one list in the sweep, one in the verification"
    for protected in lists:
        assert protected == declared, (
            f"missing from the file: {sorted(declared - protected)}; "
            f"declared by no migration: {sorted(protected - declared)}"
        )


def test_the_sweep_touches_only_insert_blocking_columns() -> None:
    """Nullable legacy columns, and NOT NULL ones with a default, block no
    insert and must be left exactly as they are."""
    text = statements(sql())
    assert text.count("c.is_nullable  = 'NO'") == 2
    assert text.count("c.column_default is null") == 2


def test_the_only_ddl_is_the_widening() -> None:
    """One dynamic statement shape, and it can only loosen. `set not null`
    anywhere here would be the file tightening the very thing it exists to
    loosen; everything else on the forbidden list is out of scope for a drift
    reconciliation by definition."""
    text = statements(sql()).lower()

    executes = re.findall(r"execute format\(\s*'([^']*)'", text)
    assert executes == [
        "alter table public.work_orders alter column %i drop not null"
    ]

    for forbidden in (
        "set not null",
        "drop table",
        "drop column",
        "drop function",
        "drop policy",
        "drop trigger",
        "drop view",
        "create function",
        "create table",
        "create policy",
        "create trigger",
        "create view",
        "truncate",
        "delete from",
        "insert into",
        "update public.",
        "grant ",
        "revoke ",
    ):
        assert forbidden not in text, forbidden


def test_the_sweep_reports_and_the_verification_fails() -> None:
    """The sweep may only NOTICE -- an exception there aborts a partial fix
    into no fix. The verification may only EXCEPTION -- a NOTICE there is the
    file reporting success it has not checked. Idempotence is the zero-found
    notice: re-running the file finds nothing and says so."""
    text = statements(sql())
    do_blocks = re.findall(r"do \$\$((?:.|\n)*?)\$\$;", text)
    assert len(do_blocks) == 2

    sweep, verification = do_blocks
    assert "raise notice" in sweep
    assert "raise exception" not in sweep
    assert "v_dropped = 0" in sweep

    assert "raise exception" in verification
    assert "raise notice" not in verification
