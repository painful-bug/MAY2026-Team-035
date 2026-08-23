"""`backend/supabase/migrations/` as a whole -- can a database that has never
seen this project apply the directory from the top?

**This is the first suite in this repository whose subject is the directory
rather than one file.** Every other `test_*_migration.py` pins one migration and
sweeps its siblings only to prove nothing later overrides it. Nothing has ever
asked whether the set, replayed from empty, still lands -- which is how issue
#41 happened: `20260818141040_remote_schema.sql`, a 9,831-line
`supabase db diff` snapshot, was committed to `origin/main` as a migration. It
fails a fresh apply at the first generated-column `ALTER`, and on the way there
it recreates a legacy sentinel table, drops two SSE triggers without recreating
them, and swaps RLS policies. CI's `database-browser` job is the thing that
replays this directory into an empty database, so a file like that stops every
branch, not just its own. (The version carries a row in the hosted ledger --
probed 2026-08-23 -- so the file could not simply be deleted; it survives as a
comment-only tombstone, which this suite is blind to because every check below
strips whole-line `--` comments first. Runbook section 22.)

**Every SQL pattern here is case-insensitive, and that is the point of the
file.**
`supabase db diff` writes uppercase SQL. The repository's hand-written
migrations are lowercase, so are the pins that guard them, and an uppercase
`CREATE TABLE "public"."visitor_access_requests"` is invisible to every one of
them. The hazard did not slip past a weak rule; it slipped past a rule that
could not see it.

The expected sets are derived from the migration texts and from the application
code they protect, not typed in from a reviewer's notes. The one exception is
the retired-table list in `test_no_migration_recreates_a_retired_table`, which
names twenty tables that no longer exist anywhere to be derived from -- it cites
the commits that removed them instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
DASHBOARD_REPOSITORY = BACKEND / "app" / "repositories" / "dashboard_repository.py"

#: Every migration, in apply order. Sorted, because filename order *is* apply
#: order and several checks below depend on reading them that way.
FILES = sorted(MIGRATIONS.glob("*.sql"))

#: Words that are grammar rather than column names, for the one derivation that
#: has to read an expression instead of a declaration.
SQL_KEYWORDS = frozenset(
    {
        "case", "when", "then", "else", "end", "is", "not", "null", "and", "or",
        "true", "false", "between", "in", "like", "as", "cast", "distinct",
    }
)


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped, so no check ever
    asserts against a header's prose instead of the SQL. Every migration in this
    directory carries a long comment header, and several of them quote the very
    statements these tests forbid."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def sql_of(path: Path) -> str:
    return statements(path.read_text(encoding="utf-8"))


def _balanced(text: str, start: int) -> tuple[str, int]:
    """The contents of the parenthesised group whose `(` sits at ``start``, and
    the index just past its `)`. Quoted literals are skipped whole."""
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if char == "'":
            i = text.index("'", i + 1) + 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    raise AssertionError(f"unbalanced parentheses from offset {start}")


#: `create table [if not exists] [["]public["].]["]name["]` -- the three spellings
#: this directory uses plus the quoted one `supabase db diff` emits.
CREATE_TABLE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?\"?(?:public\"?\s*\.\s*\"?)?(\w+)\"?",
    re.I,
)

#: A whole `alter table` statement, so an `alter column` clause can be attributed
#: to the table it belongs to rather than to any table of the same column name.
ALTER_TABLE = re.compile(
    r"alter\s+table\s+(?:only\s+)?\"?(?:public\"?\s*\.\s*\"?)?(\w+)\"?((?:.|\n)*?);",
    re.I,
)

ALTER_COLUMN = re.compile(
    r"alter\s+column\s+\"?(\w+)\"?\s+(?:set\s+default|set\s+data\s+type|type)\b", re.I
)


def created_tables() -> dict[str, list[str]]:
    """Every table name any migration creates, mapped to the files creating it.

    `alter table ... rename to legacy_x` is deliberately **not** a creation:
    three tracked migrations park a pre-baseline table under a `legacy_` name
    (`0023`, `0030`, `0032`) and those renames must not be mistaken for the
    thing this file forbids.
    """
    created: dict[str, list[str]] = {}
    for path in FILES:
        for match in CREATE_TABLE.finditer(sql_of(path)):
            created.setdefault(match.group(1).lower(), []).append(path.name)
    return created


def generated_columns() -> dict[tuple[str, str], str]:
    """Every `generated always as (...) stored` column in the directory, as
    (table, column) -> the generating expression.

    `generated always as identity` is not one of these and is not matched: the
    pattern requires the parenthesised expression and the `stored` after it.
    """
    found: dict[tuple[str, str], str] = {}
    for path in FILES:
        text = sql_of(path)
        for match in re.finditer(r"generated\s+always\s+as\s*\(", text, re.I):
            expression, after = _balanced(text, match.end() - 1)
            if not re.match(r"\s*stored\b", text[after:], re.I):
                continue
            table = _table_before(text, match.start(), path)
            column = _column_before(text, match.start())
            found[(table, column)] = expression
    return found


def _table_before(text: str, position: int, path: Path) -> str:
    """The table the declaration at ``position`` belongs to: the nearest
    preceding `create table` or `alter table`."""
    owners = [
        match.group(1).lower()
        for match in re.finditer(
            r"(?:create|alter)\s+table\s+(?:only\s+|if\s+not\s+exists\s+)*"
            r"\"?(?:public\"?\s*\.\s*\"?)?(\w+)\"?",
            text[:position],
            re.I,
        )
    ]
    assert owners, f"{path.name}: a generated column belonging to no table"
    return owners[-1]


def _column_before(text: str, position: int) -> str:
    """The column name a `generated always as` clause at ``position`` belongs
    to: walk back over the type (which may carry its own parentheses, as
    `numeric(12, 2)` and `extensions.geography(Point, 4326)` both do) and take
    the identifier in front of it."""
    head = text[:position].rstrip()
    if head.endswith(")"):
        depth = 0
        i = len(head) - 1
        while i >= 0:
            if head[i] == ")":
                depth += 1
            elif head[i] == "(":
                depth -= 1
                if depth == 0:
                    break
            i -= 1
        head = head[:i].rstrip()
    head = re.sub(r"[\w.]+$", "", head).rstrip()
    name = re.search(r"([A-Za-z_]\w*)$", head)
    assert name is not None, f"no column name before offset {position}"
    return name.group(1).lower()


def _columns_named_in(expression: str) -> set[str]:
    """The column names an expression reads. Schema and function names are
    dropped (they are followed by `.` or `(`), so are cast targets (preceded by
    `::` or `.`), and so is SQL's own grammar."""
    columns = set()
    for match in re.finditer(r"[A-Za-z_]\w*", expression):
        before = expression[: match.start()].rstrip()
        after = expression[match.end() :].lstrip()
        if before.endswith(".") or before.endswith(":"):
            continue
        if after.startswith("(") or after.startswith("."):
            continue
        word = match.group(0).lower()
        if word in SQL_KEYWORDS:
            continue
        columns.add(word)
    return columns


def dynamic_trigger_names(text: str) -> tuple[set[str], set[str]]:
    """The trigger names a `do $$ ... $$` block drops and creates through
    `execute format(...)`.

    `0007_dashboard_realtime_outbox.sql` and `0018_settings_on_baseline.sql`
    both loop a literal array of table names and build `dashboard_sse_%I` from
    each. Read literally those files drop triggers nothing creates, which is
    exactly the shape of the hazard, so the names are expanded from the arrays
    rather than the loops being excused.
    """
    dropped: set[str] = set()
    created: set[str] = set()
    for block in re.findall(r"do\s+\$\$((?:.|\n)*?)\$\$\s*;", text, re.I):
        tables: set[str] = set()
        for group in re.findall(r"array\s*\[((?:[^\[\]])*?)\]", block, re.S | re.I):
            tables.update(re.findall(r"'(\w+)'", group))
        if not tables:
            continue
        for verb, prefix in re.findall(
            r"(drop|create)\s+trigger\s+(?:if\s+exists\s+)?(\w+)%I", block, re.I
        ):
            names = {f"{prefix}{table}".lower() for table in tables}
            (dropped if verb.lower() == "drop" else created).update(names)
    return dropped, created


def dropped_and_created_triggers(text: str) -> tuple[set[str], set[str]]:
    dropped, created = dynamic_trigger_names(text)
    # Anchored at the start of a line so the `execute format('drop trigger …')`
    # templates are left to the expansion above, and quote-tolerant because a
    # `db diff` snapshot writes every identifier as `"name"`.
    dropped.update(
        name.lower()
        for name in re.findall(
            r"^\s*drop\s+trigger\s+(?:if\s+exists\s+)?\"?(\w+)\"?", text, re.I | re.M
        )
    )
    created.update(
        name.lower()
        for name in re.findall(r"^\s*create\s+trigger\s+\"?(\w+)\"?", text, re.I | re.M)
    )
    return dropped, created


def test_every_migration_parses_as_postgresql() -> None:
    """(a) The floor. A file that does not parse cannot apply, and the whole
    directory is replayed into an empty database by CI's `database-browser`
    job on every push."""
    assert FILES, "no migrations found -- the glob is wrong"
    for path in FILES:
        try:
            parse_sql(path.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001 - the failure is the report
            pytest.fail(f"{path.name} does not parse: {error}")


def test_no_migration_alters_a_generated_column_or_one_it_depends_on() -> None:
    """(b) The statement `20260818141040_remote_schema.sql` dies on, at its own
    line 1314.

    Postgres refuses `set default` on a generated column and refuses
    `set data type` on any column a generated expression reads. A `db diff`
    snapshot emits both, because it re-states every column of every table it
    saw. Both sides are derived: the generated columns from the
    `generated always as (...) stored` declarations, the columns they depend on
    from the identifiers inside those expressions.
    """
    generated = generated_columns()
    assert generated, "no generated column found -- the derivation is broken"

    protected: set[tuple[str, str]] = set(generated)
    for (table, _), expression in generated.items():
        protected.update((table, column) for column in _columns_named_in(expression))

    offences = []
    for path in FILES:
        text = sql_of(path)
        for statement in ALTER_TABLE.finditer(text):
            table = statement.group(1).lower()
            for clause in ALTER_COLUMN.finditer(statement.group(2)):
                column = clause.group(1).lower()
                if (table, column) in protected:
                    offences.append((path.name, table, column, clause.group(0)))

    assert offences == [], (
        "a migration alters a generated column or a column one is generated "
        f"from; a fresh apply stops here: {offences}. Protected today: "
        f"{sorted(protected)}"
    )


def test_no_migration_creates_the_legacy_sentinel_table() -> None:
    """(c) `schema_generation()` decides which schema the backend is talking to
    by asking whether one table exists. Create that table in a migration and
    every fresh database reports itself as the pre-baseline legacy schema, and
    the dashboard reads projections that were never built for it.

    The name is read out of `dashboard_repository.py` rather than typed here, so
    this test tracks the code it protects: if the probe ever changes table, the
    guard follows it instead of quietly protecting the wrong name.
    """
    source = DASHBOARD_REPOSITORY.read_text(encoding="utf-8")
    body = re.search(
        r"def schema_generation\(\)(?:.|\n)*?(?=\n(?:def |@))", source
    )
    assert body is not None, "schema_generation() not found where it is expected"
    probed = re.findall(r"\.table\(\"([^\"]+)\"\)", body.group(0))
    assert len(probed) == 1, f"expected one probed table, found {probed}"
    sentinel = probed[0].lower()

    creators = created_tables().get(sentinel, [])
    assert creators == [], (
        f"{sentinel} is the legacy-schema sentinel {DASHBOARD_REPOSITORY.name} "
        f"probes for; creating it makes every fresh database claim to be the "
        f"legacy schema: {creators}"
    )


def test_no_migration_drops_a_trigger_the_directory_never_recreates() -> None:
    """(d) The `db diff` snapshot drops `dashboard_sse_amenity_bookings` and
    `dashboard_sse_visitor_requests` and recreates neither, so the dashboard's
    realtime feed goes silent with nothing in the apply output to say so.

    Recreation is looked for across the whole directory, not just the dropping
    file, because `0045` legitimately re-lays two of `0043`'s triggers. The
    dynamic `dashboard_sse_%I` loops are expanded from their own table arrays.
    """
    drops: dict[str, set[str]] = {}
    creates: dict[str, set[str]] = {}
    for path in FILES:
        drops[path.name], creates[path.name] = dropped_and_created_triggers(
            sql_of(path)
        )

    ever_created: set[str] = set().union(*creates.values())
    orphans = {
        name: sorted(dropped - ever_created)
        for name, dropped in drops.items()
        if dropped - ever_created
    }
    assert orphans == {}, (
        f"triggers dropped by a migration and created by none: {orphans}"
    )

    # The same question asked in apply order, which is the version that catches
    # a snapshot taken late in the directory's life: a `create trigger` in a
    # file that already ran cannot undo a drop in a file that runs after it.
    # Every drop in this directory is paired with its own recreation in its own
    # file, so both readings agree here -- they stop agreeing the moment
    # somebody appends a file that drops what an earlier one built.
    stranded = {}
    for name, dropped in drops.items():
        still_created: set[str] = set()
        for other, made in creates.items():
            if other >= name:
                still_created |= made
        if dropped - still_created:
            stranded[name] = sorted(dropped - still_created)
    assert stranded == {}, (
        "a migration drops a trigger that only an *earlier* migration creates, "
        f"so the replay ends without it: {stranded}"
    )


def created_objects() -> set[str]:
    """Every policy and named constraint the directory itself creates, however
    it spells the creation: `create policy`, `add constraint`, or a `constraint`
    clause inside a `create table`."""
    names: set[str] = set()
    for path in FILES:
        text = sql_of(path)
        names.update(
            n.lower() for n in re.findall(r"create\s+policy\s+\"?(\w+)\"?", text, re.I)
        )
        names.update(
            n.lower() for n in re.findall(r"add\s+constraint\s+\"?(\w+)\"?", text, re.I)
        )
        names.update(
            n.lower()
            for n in re.findall(
                r"\bconstraint\s+\"?(\w+)\"?\s+"
                r"(?:check|unique|primary\s+key|foreign\s+key|exclude)\b",
                text,
                re.I,
            )
        )
    return names


def test_every_unguarded_drop_is_followed_by_its_own_recreation() -> None:
    """(e) A `drop policy` or `drop constraint` that neither says `if exists`
    nor puts the object back is a silent removal: the apply succeeds and the
    rule the repository thought it had is gone. That is how the `db diff`
    snapshot swaps RLS policies -- it drops names `0033` and `0043` created and
    re-adds its own reading of them, or nothing at all.

    Only names the directory itself creates are in scope; a hand-applied file
    may legitimately drop a hosted-only legacy object it did not make. The five
    unguarded drops here are all inside `if exists (select 1 from pg_constraint
    ...)` blocks and all re-add the same name a few lines later, which is the
    other way to be safe.
    """
    known = created_objects()
    offences = []
    for path in FILES:
        text = sql_of(path)
        for match in re.finditer(
            r"drop\s+(policy|constraint)\s+(?!if\s+exists\b)\"?(\w+)\"?", text, re.I
        ):
            kind, name = match.group(1).lower(), match.group(2).lower()
            if name not in known:
                continue
            recreated = re.search(
                rf"(?:add\s+constraint|create\s+policy)\s+{re.escape(name)}\b",
                text[match.end() :],
                re.I,
            )
            if recreated is None:
                offences.append((path.name, kind, name))

    assert offences == [], (
        "an unguarded drop of an object this directory creates, with no "
        f"same-file recreation -- the rule just disappears: {offences}"
    )


def test_no_migration_recreates_a_retired_table() -> None:
    """(f) Twenty tables were deleted from this project's schema by
    `origin/main` @ `94556e5` and `76e1b15`, the pair of commits that replaced
    `0001_init.sql`/`0002_rls.sql`/`0003_access_token_hook.sql` with
    `0001_baseline.sql`. Nothing in the repository declares them any more, so
    unlike every other check in this file the list cannot be derived -- it is
    written out, with its provenance, and it is the one hardcoded set here.

    A `db diff` snapshot taken against a database whose history includes them
    brings them back, and a fresh database then carries tables the code reads
    only in its `legacy=True` branch.

    Three tracked migrations **rename** a pre-baseline table into this
    namespace -- `0023` parks four `amenity_*` tables as `legacy_*`, `0030`
    renames `notifications`, `0032` renames `visitor_events`. Those renames are
    house-approved and conditional, and only `create table` is checked here so
    that they cannot trip it.
    """
    retired = {
        "amenity_rules",
        "booking_guests",
        "community_registration_requests",
        "legacy_amenity_booking_charges",
        "legacy_amenity_booking_occurrences",
        "legacy_amenity_booking_series",
        "legacy_amenity_financial_events",
        "legacy_notifications",
        "legacy_visitor_events",
        "media_assets",
        "notification_deliveries",
        "policies",
        "policy_revisions",
        "saved_visitors",
        "visitor_access_requests",
        "visitor_attachments",
        "work_order_attachments",
        "work_order_completion_verifications",
        "work_order_proposals",
        "work_order_views",
    }
    created = created_tables()
    resurrected = {
        name: created[name] for name in sorted(retired) if name in created
    }
    assert resurrected == {}, (
        "a migration creates a table retired by 94556e5/76e1b15; renaming into "
        f"the legacy namespace is fine, creating is not: {resurrected}"
    )
