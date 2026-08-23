"""`20260823153000_hosted_request_status_withdrawn.sql` -- a value the
application has always been entitled to write, and one database that never
learned it.

`0001_baseline.sql` declares `access_requests.status` as text with a check
naming four words, `withdrawn` among them. Hosted predates that file and holds
the column as the enum `public.request_status`, whose four labels are
`{pending, approved, rejected, cancelled}` -- probed 2026-08-23, runbook §22
probe (f), §25. So `POST /access-requests/{id}/withdraw` answers 22P02 there and
an applicant cannot take their own request back.

The derivations that make this file honest rather than plausible:

* the label added is the literal the withdraw path actually writes, read out of
  `access_requests_repository.py`;
* that literal is one `0001_baseline.sql`'s own check already allows, so this
  is hosted catching up with the baseline rather than a fifth state being
  invented;
* nothing in this directory creates a type named `request_status`, so the guard
  is false on a fresh database and the file is a no-op there -- checked across
  every file, not assumed.

**Not verifiable statically:** that hosted's enum has exactly the four labels
the probe reported. `add value if not exists` is correct for any superset of
them, and the verification block at the end of the file is the only thing that
can see the real answer.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260823153000_hosted_request_status_withdrawn.sql"
BASELINE = MIGRATIONS / "0001_baseline.sql"
ACCESS_REQUESTS_REPOSITORY = (
    BACKEND / "app" / "repositories" / "access_requests_repository.py"
)

NEW_FILES = {
    "20260823150000_hosted_invite_claim_names.sql",
    "20260823153000_hosted_request_status_withdrawn.sql",
    "20260823160000_visitor_requests_sse.sql",
}

ENUM = "request_status"


def statements(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def sql() -> str:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def added_label() -> str:
    """The one label this file adds, from its own text."""
    added = re.findall(
        rf"alter type public\.{ENUM} add value if not exists ''(\w+)''", sql()
    )
    assert len(added) == 1, f"expected one added label, found {added}"
    return added[0]


def baseline_status_words() -> set[str]:
    """The words `0001_baseline.sql`'s check on `access_requests.status`
    allows -- the fresh database's answer to the same question."""
    line = next(
        ln
        for ln in BASELINE.read_text(encoding="utf-8").splitlines()
        if ln.startswith("create table public.access_requests ")
    )
    group = re.search(
        r"status text not null default 'pending' check \(status in \(([^)]*)\)\)", line
    )
    assert group is not None, "access_requests.status check not found in the baseline"
    return set(re.findall(r"'(\w+)'", group.group(1)))


def status_written_by_the_withdraw_path() -> str:
    """The literal `access_requests_repository.withdraw` sets -- derived, so the
    pin follows the code."""
    source = ACCESS_REQUESTS_REPOSITORY.read_text(encoding="utf-8")
    body = re.search(r"def withdraw\((?:.|\n)*?(?=\n(?:def |@|\Z))", source)
    assert body is not None, "withdraw() not found where it is expected"
    written = re.findall(r"\.update\(\{\"status\": \"(\w+)\"\}\)", body.group(0))
    assert len(written) == 1, f"expected one status write, found {written}"
    return written[0]


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(MIGRATION.read_text(encoding="utf-8"))


def test_it_sorts_after_every_file_that_already_existed() -> None:
    existing = sorted(
        path.name for path in MIGRATIONS.glob("*.sql") if path.name not in NEW_FILES
    )
    assert existing, "no pre-existing migrations found -- the glob is wrong"
    assert MIGRATION.name > existing[-1], existing[-1]


def test_the_label_added_is_the_one_the_application_writes() -> None:
    """The defect, stated as a derivation. A file that added some other word
    would leave the 22P02 exactly where it was."""
    assert added_label() == status_written_by_the_withdraw_path()


def test_the_label_is_one_the_baseline_check_already_allows() -> None:
    """This is hosted catching up with `0001_baseline.sql`, not a fifth request
    state being invented. If the two ever disagreed, the fix would belong on
    whichever side is wrong -- not here."""
    assert added_label() in baseline_status_words()


def test_the_baseline_column_is_text_with_a_check_and_no_enum() -> None:
    """Why the file is a no-op on a fresh database, read off the baseline: the
    column is text, the four words live in a check constraint, and no type of
    this name is ever created."""
    line = next(
        ln
        for ln in BASELINE.read_text(encoding="utf-8").splitlines()
        if ln.startswith("create table public.access_requests ")
    )
    assert "status text not null default 'pending' check (status in (" in line
    assert ENUM not in line


def test_nothing_in_this_directory_creates_the_enum_type() -> None:
    """The guard's condition, proved false on any database built from these
    files. `public.request_status` is a pre-baseline artefact of the hosted
    project and exists nowhere in this repository."""
    creators = [
        path.name
        for path in sorted(MIGRATIONS.glob("*.sql"))
        if re.search(
            rf"create\s+type\s+public\.{ENUM}\b",
            statements(path.read_text(encoding="utf-8")),
            re.I,
        )
    ]
    assert creators == [], creators


def test_the_alter_runs_only_where_the_enum_exists() -> None:
    """Guarded on the type's presence in `pg_type` as an enum (`typtype = 'e'`),
    not merely on a name being taken -- and executed dynamically, which is what
    lets the statement be conditional at all."""
    text = " ".join(sql().split())
    assert "t.typname = 'request_status'" in text
    assert "t.typtype = 'e'" in text
    assert "execute 'alter type public.request_status add value if not exists" in text


def test_it_adds_and_never_removes_or_retypes() -> None:
    """Widening only. Retyping a live column or dropping the enum would be a
    table rewrite and a lost guarantee; neither is in the file."""
    text = sql().lower()

    assert len(re.findall(r"alter type", text)) == 1
    for forbidden in (
        "drop type", "alter column", "drop constraint", "add constraint",
        "drop table", "create table", "create type", "insert into",
        "update public.", "delete from", "create function", "create trigger",
    ):
        assert forbidden not in text, forbidden


def test_the_new_label_is_never_used_as_a_value_in_this_file() -> None:
    """PostgreSQL 12+ allows `add value` inside a transaction block on the one
    condition that the new label is not *used* until the commit. The file's only
    other statement reads `pg_enum`, which is a catalogue read and not a use of
    the value -- so the paste is safe as one transaction. This is the check that
    keeps it that way."""
    label = added_label()
    text = " ".join(sql().split())

    #: Every place the word appears *as a literal*, with enough text in front
    #: of it to say what it is doing there. The doubled quotes are the literal
    #: as it sits inside the dynamic `alter type` string. Unquoted mentions are
    #: the raise message's prose and are not values.
    windows = [
        text[max(0, match.start() - 40) : match.end() + 1]
        for match in re.finditer(rf"'{label}'", text)
    ]
    assert windows, "the label appears nowhere -- the derivation is broken"
    for window in windows:
        assert (
            f"add value if not exists ''{label}''" in window  # the add itself
            or f"e.enumlabel = '{label}'" in window  # a catalogue text read
        ), window

    # A cast would be a use of the value, and there is none of either spelling.
    assert f"::public.{ENUM}" not in text
    assert f"::{ENUM}" not in text


def test_the_verification_is_itself_conditional() -> None:
    """The end-of-file check must not raise on a fresh database, where the type
    it asks about does not exist. It fires only where the enum is present and
    the label is still missing."""
    verification = sql().split("$$;", 1)[1]
    assert "raise exception" in verification
    # The existence of the type is re-established before the label is demanded.
    assert verification.index("t.typname = 'request_status'") < verification.index(
        "e.enumlabel = 'withdrawn'"
    )
