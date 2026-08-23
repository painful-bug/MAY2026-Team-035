"""`20260823160000_visitor_requests_sse.sql` -- `0007`'s own trigger for
`visitor_requests`, arriving twenty-five files late.

`0007_dashboard_realtime_outbox.sql` loops twelve table names and builds
`dashboard_sse_%I` on each one that exists. `visitor_requests` is in that array,
so a fresh database has had the trigger since `0007`. Hosted has not: when
`0007` was applied there the baseline table did not yet exist -- `0032` created
it -- the `to_regclass` guard skipped it, and nothing revisited the question.
The owner's probe of 2026-08-23 found `visitor_requests` carrying no trigger at
all while holding the only three real visitor requests in the project (runbook
§22 probes (g) and (h), §26).

So the file must not invent a trigger; it must reproduce the one `0007` would
have made. That is the derivation this suite is built on: the name, the events,
the row/statement level and the function are all read out of `0007`'s own loop
template and compared against the statement in this file. If `0007` is ever
edited, these tests fail rather than letting the two definitions drift.

The other end is pinned too: the table this trigger fires on is read out of
`dashboard_repository.list_visitors`, because a realtime signal on a table the
dashboard does not read would be a refresh that shows nothing new.

**Not verifiable statically:** whether hosted's `emit_dashboard_sse_event` is
`0007`'s. It is a `create or replace` in `0007` and no later file touches it,
which is checked below; the rest is the apply's business.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260823160000_visitor_requests_sse.sql"
OUTBOX = MIGRATIONS / "0007_dashboard_realtime_outbox.sql"
DASHBOARD_REPOSITORY = BACKEND / "app" / "repositories" / "dashboard_repository.py"

PREVIOUS_SHARED_MIGRATION = (
    MIGRATIONS / "20260823120000_complaint_engine_v2_repairs.sql"
)
MIGRATIONS_ADDED_TOGETHER = (
    "20260823150000_hosted_invite_claim_names.sql",
    "20260823153000_hosted_request_status_withdrawn.sql",
    "20260823160000_visitor_requests_sse.sql",
)

TABLE = "visitor_requests"


def statements(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def sql() -> str:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def outbox_template() -> tuple[str, str]:
    """`0007`'s `create trigger` template, as (name prefix, tail after the
    table name) -- the shape its loop stamps onto every table in its array."""
    text = statements(OUTBOX.read_text(encoding="utf-8"))
    template = re.search(
        r"'create trigger (\w+)%I (after[^']*?) on public\.%I ([^']*?)'", text
    )
    assert template is not None, "0007's create-trigger template not found"
    return template.group(1), f"{template.group(2)} {template.group(3)}"


def outbox_tables() -> set[str]:
    """The table names `0007`'s loop iterates."""
    text = statements(OUTBOX.read_text(encoding="utf-8"))
    array = re.search(r"array\s*\[((?:[^\[\]])*?)\]", text, re.S)
    assert array is not None, "0007's table array not found"
    return set(re.findall(r"'(\w+)'", array.group(1)))


def visitor_table_the_dashboard_reads() -> str:
    """The table `dashboard_repository.list_visitors` projects -- derived, the
    same way the directory guard derives the legacy sentinel."""
    source = DASHBOARD_REPOSITORY.read_text(encoding="utf-8")
    body = re.search(r"def list_visitors\((?:.|\n)*?(?=\n(?:def |@))", source)
    assert body is not None, "list_visitors() not found where it is expected"
    read = re.findall(r"client\.table\(\"([^\"]+)\"\)", body.group(0))
    assert len(read) == 1, f"expected one table read, found {read}"
    return read[0]


def migration_trigger() -> tuple[str, str]:
    """This file's trigger, as (name, everything after the table name)."""
    found = re.search(
        rf"create or replace trigger (\w+)\s+(after[^;]*?)"
        rf" on public\.{TABLE}\s+([^;]*?);",
        " ".join(sql().split()),
    )
    assert found is not None, "the create-or-replace trigger statement was not found"
    return found.group(1), f"{found.group(2)} {found.group(3)}"


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(MIGRATION.read_text(encoding="utf-8"))


def test_it_sorts_after_every_file_that_already_existed() -> None:
    """Pin the parent tree's tip; later migrations are not predecessors."""
    earlier = sorted(
        path.name
        for path in MIGRATIONS.glob("*.sql")
        if path.name < MIGRATIONS_ADDED_TOGETHER[0]
    )
    assert earlier, "no pre-existing migrations found -- the glob is wrong"
    assert PREVIOUS_SHARED_MIGRATION.exists()
    assert MIGRATIONS_ADDED_TOGETHER == tuple(sorted(MIGRATIONS_ADDED_TOGETHER))
    assert MIGRATION.name in MIGRATIONS_ADDED_TOGETHER
    assert earlier[-1] == PREVIOUS_SHARED_MIGRATION.name, earlier[-1]
    assert MIGRATIONS_ADDED_TOGETHER[0] > earlier[-1], earlier[-1]


def test_it_sorts_after_the_outbox_and_after_the_table_it_triggers() -> None:
    """The trigger function comes from `0007` and the table from `0032`; a
    fresh replay must have both before this file runs."""
    creators = [
        path.name
        for path in sorted(MIGRATIONS.glob("*.sql"))
        if re.search(
            rf"create\s+table\s+(?:if\s+not\s+exists\s+)?public\.{TABLE}\b",
            statements(path.read_text(encoding="utf-8")),
            re.I,
        )
    ]
    assert creators, f"nothing creates public.{TABLE} -- the derivation is broken"
    assert MIGRATION.name > max(creators), creators
    assert MIGRATION.name > OUTBOX.name


def test_the_trigger_is_the_one_0007_would_have_built() -> None:
    """Name and definition both derived from `0007`'s loop template, so the
    trigger a fresh database gets from `0007` and the trigger hosted gets from
    here are the same trigger -- including the `delete` arm, which the outbox
    fires on and a hand-written pair might have left out."""
    prefix, tail = outbox_template()
    name, definition = migration_trigger()

    assert name == f"{prefix}{TABLE}"
    assert definition == tail, (definition, tail)
    assert "after insert or update or delete" in tail
    assert "for each row" in tail
    assert "public.emit_dashboard_sse_event()" in tail


def test_the_table_is_one_0007_already_names() -> None:
    """This is `0007` finishing its own job, not a thirteenth table being
    added to the outbox by a side door. `visitor_requests` has been in that
    array since the file was written; it was skipped by the `to_regclass`
    guard on a database where the table did not exist yet."""
    assert TABLE in outbox_tables()


def test_the_table_is_the_one_the_dashboard_reads() -> None:
    """The realtime half and the read half of the split-brain fix must point at
    the same table, or the refresh arrives about rows nobody projects."""
    assert visitor_table_the_dashboard_reads() == TABLE


def test_every_definition_of_the_trigger_function_is_already_applied() -> None:
    """`emit_dashboard_sse_event` is written by `0007` and rewritten once, by
    `0028_event_audience.sql`, which retargets `dashboard.refresh` at the
    `{admin, manager}` audience. Both sort before this file, which is what makes
    "the same trigger a fresh database has" a settled statement: whichever
    database this runs on, the function the trigger names is already in its
    final form. A future rewrite sorting *after* this file would be fine for the
    trigger and is still worth being told about -- the emitted audience is the
    thing that decides whether an admin's dashboard hears about a visitor at
    all.
    """
    definers = [
        path.name
        for path in sorted(MIGRATIONS.glob("*.sql"))
        if re.search(
            r"create\s+(or\s+replace\s+)?function\s+public\.emit_dashboard_sse_event\b",
            statements(path.read_text(encoding="utf-8")),
            re.I,
        )
    ]
    assert definers, "nothing defines emit_dashboard_sse_event -- derivation broken"
    assert definers[0] == OUTBOX.name, definers
    assert [name for name in definers if name > MIGRATION.name] == [], definers


def test_it_drops_nothing_and_is_idempotent() -> None:
    """`create or replace trigger` rather than a drop-and-create pair: there is
    no window in which the table has no trigger, and a second run replaces the
    file's own work rather than removing somebody else's."""
    text = sql().lower()

    assert "create or replace trigger" in text
    assert len(re.findall(r"create or replace trigger", text)) == 1
    for forbidden in (
        "drop trigger", "drop function", "drop table", "drop policy",
        "create table", "create function", "create policy", "alter table",
        "alter type", "truncate", "delete from", "insert into", "update public.",
    ):
        assert forbidden not in text, forbidden


def test_it_verifies_the_trigger_it_claims_to_have_made() -> None:
    """A named check rather than a bare existence one: the table already had no
    trigger, so 'some trigger is present' would pass against nothing useful."""
    text = " ".join(sql().split())
    assert f"tgrelid = 'public.{TABLE}'::regclass" in text
    assert f"tgname = 'dashboard_sse_{TABLE}'" in text
    assert "raise exception" in text
