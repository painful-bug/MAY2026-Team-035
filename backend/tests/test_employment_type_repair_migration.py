"""`20260817144725_repair_staff_assignment_employment_type.sql` -- what a static
reader can prove about a file that was applied before it was ours.

The file entered this branch from `origin/main` (commit `c0956a2`, 2026-08-17)
byte for byte, because it is **already applied and ledgered** on the hosted
project under exactly this version. Nothing below asks the file to be different;
editing it here would put git and the ledger out of step under one version,
which is the disease issue #41 is about. What the tests ask is the only question
still open: whether the constraint the hosted database now carries admits every
`employment_type` this repository writes.

The hosted `staff_assignments` predates `0001_baseline.sql`. Its hand-built
`staff_assignments_employment_type_check` allowed `internal` and `vendor` only,
while every hiring path in this directory has written `staff` since `0019` gave
the column that default. Worker hiring answered 23514 on every attempt until
this file widened the list (issue #33).

The hazard of an enumerating constraint is a missing word: a value some
migration inserts that the list does not name blocks that insert forever, and
the symptom appears at the first hire rather than at the apply. So the allowed
list is not reviewed here -- it is **derived** from the file's own text, and
every `employment_type` literal any migration writes is required to be a member
of it.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
REPAIR = MIGRATIONS / "20260817144725_repair_staff_assignment_employment_type.sql"

#: The file that declares the column, and the file that gave it its default.
BASELINE = MIGRATIONS / "0001_baseline.sql"
DEFAULT_SETTER = MIGRATIONS / "0019_departments_on_baseline.sql"

CONSTRAINT = "staff_assignments_employment_type_check"


def sql() -> str:
    return REPAIR.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped, so no check ever
    asserts against a header's prose instead of the SQL."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def _balanced(text: str, start: int) -> tuple[str, int]:
    """The contents of the parenthesised group whose `(` sits at ``start``, and
    the index just past its `)`. Quoted literals are skipped whole, so a comma
    or a paren inside `'...'` cannot be mistaken for structure."""
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


def _split_top_level(body: str) -> list[str]:
    """``body`` split on the commas that are not inside a nested group or a
    quoted literal -- the only way to line a `values` list up with the column
    list above it when an item is `nullif(btrim(coalesce(x, '')), '')`."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    i = 0
    while i < len(body):
        char = body[i]
        if char == "'":
            end = body.index("'", i + 1) + 1
            current.append(body[i:end])
            i = end
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        i += 1
    parts.append("".join(current).strip())
    return parts


def _inside_a_function_body(text: str, position: int) -> bool:
    """True when ``position`` falls between a `$$` pair -- i.e. the statement is
    a line of plpgsql that runs when somebody hires, not DDL that runs when the
    file is applied. The distinction decides whether apply order matters."""
    return text.count("$$", 0, position) % 2 == 1


def allowed_values() -> set[str]:
    """The constraint's vocabulary as the repair declares it -- from its own
    text, not from anyone's memory of it."""
    text = statements(sql())
    checks = [
        set(re.findall(r"'(\w+)'", group))
        for group in re.findall(r"employment_type in \(((?:[^()])*?)\)", text, re.S)
    ]
    assert len(checks) == 1, f"expected one allowed-value list, found {len(checks)}"
    return checks[0]


def written_values() -> dict[tuple[str, int], str]:
    """Every `employment_type` literal any migration in the directory writes,
    keyed by (filename, byte offset).

    Two write shapes exist and both are read out of the files themselves: the
    column default `0019` sets, and the `insert into public.staff_assignments`
    statements inside the hiring RPCs -- which are found by lining each insert's
    `values` list up with its column list positionally, because the column is
    never named beside its value.
    """
    written: dict[tuple[str, int], str] = {}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = statements(path.read_text(encoding="utf-8"))

        for match in re.finditer(
            r"alter column\s+employment_type\s+set default\s+'(\w+)'", text
        ):
            written[(path.name, match.start())] = match.group(1)

        for match in re.finditer(r"insert into public\.staff_assignments\s*\(", text):
            columns, after = _balanced(text, match.end() - 1)
            names = [part.strip() for part in _split_top_level(columns)]
            if "employment_type" not in names:
                continue
            values_at = re.compile(r"values\s*\(").search(text, after)
            assert values_at is not None, f"{path.name}: insert with no values list"
            values, _ = _balanced(text, values_at.end() - 1)
            items = _split_top_level(values)
            assert len(items) == len(names), (
                f"{path.name}: {len(names)} columns against {len(items)} values"
            )
            item = items[names.index("employment_type")]
            literal = re.fullmatch(r"'(\w+)'", item)
            if literal:
                written[(path.name, match.start())] = literal.group(1)
    return written


def apply_time_writers() -> set[str]:
    """The files whose `employment_type` write is DDL -- it happens when the
    migration is applied, so its order against the constraint is real. Writes
    inside a `$$` body happen when somebody hires, long after every file in the
    directory has been applied, and have no order to keep."""
    writers: set[str] = set()
    for (name, position), _ in written_values().items():
        path = MIGRATIONS / name
        text = statements(path.read_text(encoding="utf-8"))
        if not _inside_a_function_body(text, position):
            writers.add(name)
    return writers


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_the_only_ddl_is_the_constraint_swap() -> None:
    """One drop and one add, both naming the same constraint on the same table.
    A file that is already ledgered on hosted can never be corrected in place,
    so what it does has to be exactly what its name says."""
    text = statements(sql()).lower()

    swaps = re.findall(
        r"alter table public\.(\w+)\s+(drop constraint if exists|add constraint)\s+(\w+)",
        text,
    )
    assert swaps == [
        ("staff_assignments", "drop constraint if exists", CONSTRAINT),
        ("staff_assignments", "add constraint", CONSTRAINT),
    ], swaps

    for forbidden in (
        "drop table", "drop column", "drop function", "drop policy",
        "drop trigger", "drop view", "create function", "create table",
        "create policy", "create trigger", "create view", "truncate",
        "delete from", "insert into", "update public.", "grant ", "revoke ",
        "set not null", "alter column",
    ):
        assert forbidden not in text, forbidden


def test_the_allowed_list_is_the_two_legacy_words_plus_staff() -> None:
    """Derived from the file, then compared: the legacy pair the hosted
    constraint already carried, and the one word the repository writes."""
    assert allowed_values() == {"internal", "vendor", "staff"}


def test_every_employment_type_any_migration_writes_is_allowed() -> None:
    """The whole point of the file, held by derivation rather than review.

    A value written by some hiring path and missing from the list is a 23514 at
    that path's first use -- which is exactly how issue #33 was found, on the
    `staff` this file adds. Order does not enter into it: the inserts live in
    function bodies and run long after every migration is applied.
    """
    allowed = allowed_values()
    written = written_values()
    assert written, "no employment_type write found -- the derivation is broken"

    unallowed = {
        where: value for where, value in written.items() if value not in allowed
    }
    assert unallowed == {}, (
        f"written but not allowed by {CONSTRAINT}: {unallowed}; "
        f"allowed: {sorted(allowed)}"
    )


def test_the_baseline_declares_the_column_with_no_check_of_its_own() -> None:
    """On a fresh database the constraint does not exist until this file makes
    it. `0001_baseline.sql` declares a bare `text not null`, which is why the
    repair is a `drop ... if exists` before the add rather than a plain add,
    and why nothing before 2026-08-17 ever noticed the hosted list was short.
    """
    line = next(
        ln
        for ln in BASELINE.read_text(encoding="utf-8").splitlines()
        if ln.startswith("create table public.staff_assignments ")
    )
    body = line[line.index("(") + 1 : line.rindex(")")]
    declaration = next(
        part.strip()
        for part in body.split(", ")
        if part.strip().startswith("employment_type ")
    )
    assert declaration == "employment_type text not null"
    assert CONSTRAINT not in line
    assert not re.search(r"check\s*\([^()]*employment_type", line), line


def test_it_sorts_after_every_apply_time_declaration_of_the_column() -> None:
    """Filename order is apply order, and only apply-time writes have an order
    to keep: the column's declaration and the default `0019` sets. Two files
    that write `staff` (`20260821140000`, `20260821170000`) sort *after* this
    one and that is correct -- their write is a line of plpgsql inside
    `claim_staff_invitations`, which runs when a manager claims an invitation,
    not when the migration is applied. Membership in the allowed list, asserted
    above, is what protects them; order cannot.
    """
    assert REPAIR.name > BASELINE.name
    assert REPAIR.name > DEFAULT_SETTER.name

    late = {name for name in apply_time_writers() if name > REPAIR.name}
    assert late == set(), (
        "a migration sorting after the repair sets an employment_type at apply "
        f"time, so the constraint is added before its value exists: {late}"
    )
