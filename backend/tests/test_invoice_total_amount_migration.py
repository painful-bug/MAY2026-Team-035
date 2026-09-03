"""`20260830093000_invoice_total_amount_generated.sql` -- putting the GENERATED
modifier back on `invoice_line_items.total_amount`.

`0021_money_on_baseline.sql` declares the column as
`generated always as (round(quantity * unit_amount, 2)) stored`. The hosted
database carries it as a plain `not null` column instead
(`pg_attribute.attgenerated = ''`), and that single difference is why every
invoice create fails: `issue_invoice`'s line insert (0021:450-462) does not list
`total_amount`, because it does not have to on the declared shape, so on the
drifted shape it violates the NOT NULL. The RPC's own drift-defence -- the
`update ... set total_amount = round(...)` at 0021:466-476 -- runs *after* those
inserts and is therefore never reached. Issue #54.

The file's promises, each pinned below:

* **It only acts on the drifted shape.** `attgenerated = 's'` is a notice and a
  `return`; anything other than `''` or `'s'` raises rather than guesses. A
  fresh replay of this directory reaches this file with `0021`'s generated
  column already in place, so the no-op branch is the one CI takes.
* **The expression is `0021`'s, verbatim.** Read out of `0021` here rather than
  typed, so a repair that installed a *different* total than the one the
  baseline declares would fail this suite instead of quietly disagreeing with
  it.
* **No CASCADE, ever.** The repository census found nothing that depends on the
  column -- `invoice_overview` and `resident_invoice_overview` read
  `invoices.total_amount`, a different table's column, and neither selects from
  `invoice_line_items` at all. That census is re-derived below rather than
  taken on the migration's word, and the file additionally probes `pg_depend`
  at apply time and refuses by name if hosted carries a dependent this tree
  never declared.
* **It touches one column of one table.** No row is written, no sibling column
  moves, no policy or constraint is redefined.

**Not verifiable statically:** that the hosted column is in fact drifted before
the apply, that no hosted-only view depends on it, and that `issue_invoice`
then succeeds end to end. All three need the applied database; runbook
section 36's pre- and post-checks are where they are proved.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260830093000_invoice_total_amount_generated.sql"

#: The file that declares the column this one restores, and the shape it is
#: restored to. Read, never quoted from memory.
BASELINE = MIGRATIONS / "0021_money_on_baseline.sql"

TABLE = "public.invoice_line_items"
COLUMN = "total_amount"


def statements(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def sql() -> str:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def flat() -> str:
    """The SQL with whitespace collapsed, for assertions that span lines."""
    return " ".join(sql().split())


def declared_expression() -> str:
    """`0021`'s generating expression for `invoice_line_items.total_amount`,
    whitespace-collapsed."""
    found = re.search(
        r"add column if not exists total_amount\s+numeric\(12, 2\)\s+"
        r"generated always as \((.*?)\) stored",
        statements(BASELINE.read_text(encoding="utf-8")),
        re.S,
    )
    assert found is not None, "0021 no longer declares total_amount as generated"
    return " ".join(found.group(1).split())


def _end_of_statement(text: str, start: int) -> int:
    """The index just past the `;` that ends the statement beginning at
    ``start``, skipping over single-quoted literals so a `concat_ws(' ', ...)`
    inside a view body cannot be mistaken for one."""
    i = start
    while i < len(text):
        if text[i] == "'":
            i = text.index("'", i + 1) + 1
            continue
        if text[i] == ";":
            return i + 1
        i += 1
    raise AssertionError(f"unterminated statement from offset {start}")


def view_bodies() -> dict[str, str]:
    """Every `create [or replace] [materialized] view` statement in the
    directory, by view name."""
    bodies: dict[str, str] = {}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = statements(path.read_text(encoding="utf-8"))
        for match in re.finditer(
            r"create\s+(?:or\s+replace\s+)?(?:materialized\s+)?view\s+"
            r"(?:if\s+not\s+exists\s+)?\"?(?:public\"?\s*\.\s*\"?)?(\w+)\"?",
            text,
            re.I,
        ):
            end = _end_of_statement(text, match.end())
            bodies[f"{path.name}:{match.group(1)}"] = text[match.start() : end]
    return bodies


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_the_migration_file_exists_under_the_frozen_name() -> None:
    """The runbook section, the changelog entry and the ledger insert all name
    this exact string."""
    assert MIGRATION.exists(), MIGRATION.name
    assert MIGRATION.name == "20260830093000_invoice_total_amount_generated.sql"


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(MIGRATION.read_text(encoding="utf-8"))


def test_it_sorts_after_the_file_that_declares_the_column() -> None:
    """Forward-only. Filename order is apply order: a repair that sorted before
    `0021` would run against a table that does not have the column yet, and
    then `0021` would re-declare whatever it liked afterwards."""
    assert BASELINE.exists(), BASELINE.name
    assert MIGRATION.name > BASELINE.name, BASELINE.name


def test_it_is_the_last_word_on_this_column() -> None:
    """Not "it is last in the directory" -- what decides the shape the database
    ends up holding is being last among the files that declare or alter this
    column."""
    declarers = sorted(
        path.name
        for path in MIGRATIONS.glob("*.sql")
        if re.search(
            r"(?:add|drop|alter)\s+column\s+(?:if\s+not\s+exists\s+)?total_amount",
            statements(path.read_text(encoding="utf-8")),
            re.I,
        )
        and "invoice_line_items" in path.read_text(encoding="utf-8")
    )
    assert declarers, "nothing declares total_amount at all"
    assert declarers[-1] == MIGRATION.name, declarers


# ---------------------------------------------------------------------------
# It only acts on the drifted shape
# ---------------------------------------------------------------------------


def test_it_guards_on_attgenerated_for_this_exact_column() -> None:
    """`pg_attribute.attgenerated` is the only thing that distinguishes the two
    shapes: same name, same type, same NOT NULL. A guard on `information_schema`
    or on a column count would not see the difference at all."""
    text = flat()

    assert "attgenerated" in text
    assert "from pg_attribute a" in text
    assert f"a.attrelid = '{TABLE}'::regclass" in text
    assert f"a.attname = '{COLUMN}'" in text
    # Dropped columns keep their pg_attribute row; reading one would report the
    # shape of a column that is not there.
    assert "not a.attisdropped" in text


def test_an_already_generated_column_is_a_clean_no_op() -> None:
    """The `'s'` branch raises a notice and returns, and it returns BEFORE the
    drop. This is the branch every fresh replay of the directory takes -- `0021`
    creates the generated column a few files earlier -- so a file that acted
    unconditionally would drop and rebuild a correct column on every new
    database, and would not be re-runnable on the hosted one either."""
    text = flat()

    guard = text.index("if v_generated = 's' then")
    ret = text.index("return;")
    drop = text.index(f"alter table {TABLE} drop column {COLUMN};")

    assert guard < ret < drop
    assert "raise notice" in text[guard:ret]


def test_an_unrecognised_shape_stops_rather_than_guesses() -> None:
    """Two shapes are known: `''` (drifted) and `'s'` (declared). A virtual
    generated column (`'v'`), or a column that is not there at all, is a
    database nobody has looked at, and repairing it blind is how a repair
    becomes an incident."""
    text = flat()

    assert "if v_generated is null then" in text
    assert "if v_generated <> '' then" in text
    assert text.count("raise exception") >= 2
    # The absent-column arm names the file that should have created it, so the
    # owner is told what is actually wrong.
    assert "0021" in MIGRATION.read_text(encoding="utf-8")


def test_the_repair_is_a_drop_and_a_re_add_in_that_order() -> None:
    text = flat()

    drop = text.index(f"alter table {TABLE} drop column {COLUMN};")
    add = text.index(f"alter table {TABLE} add column {COLUMN}")

    assert drop < add


# ---------------------------------------------------------------------------
# The expression is `0021`'s, verbatim
# ---------------------------------------------------------------------------


def test_the_column_is_re_added_with_the_declared_expression() -> None:
    """Derived from `0021`, not typed here. The point of the repair is that the
    database agrees with the baseline; a test carrying its own copy of the
    expression would let the two drift apart in exactly the way this file
    exists to stop."""
    expression = declared_expression()
    assert expression == "round(quantity * unit_amount, 2)", expression

    assert (
        f"add column {COLUMN} numeric(12, 2) "
        f"generated always as ({expression}) stored;" in flat()
    )


def test_the_new_column_keeps_the_declared_type() -> None:
    """`numeric(12, 2)`. A generated column with a wider or narrower type is a
    different column that happens to share a name."""
    assert f"add column {COLUMN} numeric(12, 2)" in flat()


# ---------------------------------------------------------------------------
# No CASCADE, ever
# ---------------------------------------------------------------------------


def test_the_repository_census_still_finds_no_dependent_view() -> None:
    """The claim the plain `drop column` rests on, re-derived rather than
    trusted: no view or materialized view anywhere in this directory selects
    from `invoice_line_items`.

    `invoice_overview` (0021) and `resident_invoice_overview` (0033) both carry
    a column literally called `total_amount`, which is `invoices.total_amount`
    -- the invoice's own total, a different table. Matching on the column name
    alone would find them and be wrong; the table is what is checked.
    """
    offenders = {
        name: body
        for name, body in view_bodies().items()
        if "invoice_line_items" in body
    }
    assert offenders == {}, (
        "a view selects from invoice_line_items, so the drop needs that view "
        f"dropped and re-created around it: {sorted(offenders)}"
    )
    # The census is only meaningful if the scan actually found the views.
    names = view_bodies()
    assert any(name.endswith(":invoice_overview") for name in names), names
    assert any(
        name.endswith(":resident_invoice_overview") for name in names
    ), names


def test_no_index_in_the_directory_names_the_column() -> None:
    """The other thing a `drop column` takes with it. The one index on this
    table is `(invoice_id, sort_order)`."""
    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = statements(path.read_text(encoding="utf-8"))
        for match in re.finditer(
            r"create\s+(?:unique\s+)?index[^;]*?on\s+public\.invoice_line_items\s*\(([^)]*)\)",
            text,
            re.I | re.S,
        ):
            assert COLUMN not in match.group(1), (path.name, match.group(0))


def test_the_migration_never_cascades() -> None:
    """`drop column ... cascade` would delete whatever depended on the column
    and report success. The whole point of the census above is that this word
    is not needed; its absence is what makes an undeclared hosted dependent
    stop the apply instead of disappearing into it.

    Checked against the DDL rather than against the whole text: the refusal
    message the file raises says the word ("this file will not cascade them
    away") and saying so is the opposite of doing it.
    """
    text = flat().lower()

    assert f"drop column {COLUMN} cascade" not in text
    offences = re.findall(r"drop\s+\w+[^;']*?\bcascade\b", text)
    assert offences == [], offences


def test_it_probes_pg_depend_and_refuses_by_name() -> None:
    """Hosted has already proved it carries objects this tree never declared,
    so the static census is not the only check. Views, materialized views and
    rules are found through `pg_rewrite`; indexes through `pg_class`. Both are
    scoped to this column's `attnum`, not to the table -- a dependent on
    `quantity` is none of this file's business."""
    text = flat()

    assert "pg_depend" in text
    assert "join pg_rewrite r on r.oid = d.objid" in text
    assert "d.refobjsubid = v_attnum" in text
    assert "c.relkind = 'i'" in text

    probe = text.index("pg_depend")
    refusal = text.index("is depended on by:")
    drop = text.index(f"alter table {TABLE} drop column {COLUMN};")
    assert probe < refusal < drop


# ---------------------------------------------------------------------------
# It touches one column of one table
# ---------------------------------------------------------------------------


def test_the_sibling_amount_column_is_left_alone() -> None:
    """`invoice_line_items.amount` is the baseline's own total and `0021` keeps
    it equal to the computed one. It is not this file's business, and a repair
    that also rewrote it would be changing a number the owner was not told
    about."""
    text = flat()

    assert "drop column amount" not in text
    assert "add column amount" not in text
    assert "set amount" not in text


def test_it_writes_no_row() -> None:
    """The recomputation happens because the column is generated, not because
    this file updates anything. No `update`, no `insert`, no `delete` -- the
    only counting statement is a `select count(*)` feeding a notice."""
    text = flat().lower()

    assert "update public." not in text
    assert "insert into" not in text
    assert "delete from" not in text
    assert "truncate" not in text


def test_it_alters_no_other_table_and_redefines_no_rule() -> None:
    """One table, by name, three times: the two `alter table`s and the
    `comment on column`."""
    text = flat().lower()

    altered = set(re.findall(r"alter table (\S+)", text))
    assert altered == {TABLE}, altered

    for forbidden in (
        "create table", "drop table", "create policy", "drop policy",
        "create trigger", "drop trigger", "create view", "drop view",
        "create function", "drop function", "add constraint", "drop constraint",
        "alter type",
    ):
        assert forbidden not in text, forbidden


# ---------------------------------------------------------------------------
# The file proves its own work
# ---------------------------------------------------------------------------


def test_it_reads_back_the_column_it_installed() -> None:
    """A `do` block that took the no-op branch and a `do` block that repaired
    the column both end without error, so the only proof the apply did what the
    header claims is a second read of the catalogue afterwards."""
    text = flat()

    verification = text.index("v_generated <> 's' then")
    assert verification > text.index(
        f"add column {COLUMN} numeric(12, 2)"
    ), "the read-back runs before the repair"

    assert "pg_get_expr(d.adbin, d.adrelid)" in text
    assert "left join pg_attrdef d" in text
    assert "the drop ran and the add did not" in text


def test_it_reloads_the_postgrest_schema_cache() -> None:
    """Dropping and re-adding a column changes the shape PostgREST advertises;
    without the reload it answers from its old picture until the next
    restart."""
    assert "notify pgrst, 'reload schema';" in flat()


def test_the_header_states_the_recomputation_and_names_the_runbook_section() -> None:
    """The owner applies this by hand and the header is what they read first.
    It has to say that existing rows change value, and where the pre-checks
    that quantify it live."""
    header = MIGRATION.read_text(encoding="utf-8")

    assert "#54" in header
    assert "section 36" in header
    assert "Hand-applied by the owner" in header
    assert "round(quantity * unit_amount, 2)" in header
    assert "ROLLBACK:" in header
    # The sibling column is named as untouched, not merely omitted.
    assert "`amount` column is NOT touched" in header
