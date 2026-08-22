"""`20260822150000_taken_up_event_word.sql` -- what a static reader can prove.

`take_up_complaint` (20260822120000) writes `event_type = 'taken_up'`;
`complaint_events_type_check` (20260813105000) enumerates the allowed words
and did not know it. The first live Take-up press answered 23514 on
2026-08-22. The cure recreates the constraint with exactly one new word.

The hazard of recreating an enumerating constraint is losing a word: any
already-allowed type missing from the new list would make the guard block
refuse the apply (good) or, were the guard wrong, poison every later insert
of that type (bad). So the word list is not reviewed here -- it is **derived**
from the creating migration's own text and compared exactly.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
CURE = MIGRATIONS / "20260822150000_taken_up_event_word.sql"

#: The file that created the constraint, and the file whose new word broke it.
CREATOR = MIGRATIONS / "20260813105000_chat_autopen_and_vocab.sql"
BREAKER = MIGRATIONS / "20260822120000_supervisor_triage.sql"


def sql() -> str:
    return CURE.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped, so no check ever
    asserts against the header's prose instead of the SQL."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def word_lists(text: str) -> list[set[str]]:
    """Each ``event_type in (...)`` list, as a set of words."""
    return [
        set(re.findall(r"'(\w+)'", group))
        for group in re.findall(
            r"event_type (?:not )?in \(((?:[^()])*?)\)", statements(text), re.S
        )
    ]


def creator_words() -> set[str]:
    """The constraint's vocabulary as the creating migration declares it --
    from its own text, not from anyone's memory of it."""
    lists = word_lists(CREATOR.read_text(encoding="utf-8"))
    # 20260813105000 states the list twice: once in its guard, once in the
    # constraint. They must agree with each other before we lean on either.
    constraint_lists = [words for words in lists if len(words) > 1]
    assert len(constraint_lists) >= 2
    assert all(words == constraint_lists[0] for words in constraint_lists)
    return constraint_lists[0]


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_sorts_after_the_creator_and_the_breaker() -> None:
    for earlier in (CREATOR, BREAKER):
        assert CURE.name > earlier.name


def test_the_new_list_is_the_old_list_plus_exactly_taken_up() -> None:
    """Held by derivation rather than review: every word the creator allowed,
    plus the one word the breaker writes, and nothing else."""
    expected = creator_words() | {"taken_up"}
    lists = word_lists(sql())
    assert len(lists) == 2, "one list in the guard, one in the constraint"
    for words in lists:
        assert words == expected, (
            f"dropped from the old constraint: {sorted(creator_words() - words)}; "
            f"invented here: {sorted(words - expected)}"
        )


def test_the_breaker_writes_no_other_new_word() -> None:
    """If 20260822120000 inserted a second unknown word, this cure would fix
    one 23514 and leave its sibling live behind a passing apply."""
    text = statements(BREAKER.read_text(encoding="utf-8"))
    written = set(re.findall(r"event_type[^']*?'(\w+)'", text))
    written.update(
        re.findall(r"values\s*\(\s*[^)]*?,\s*'(\w+)',", text)
    )
    unknown = {
        w for w in written if w not in creator_words() and w != "taken_up"
    } - {"department_assigned"}  # read in a WHERE, and already allowed anyway
    assert unknown == set(), unknown


def test_the_only_ddl_is_the_constraint_swap() -> None:
    text = statements(sql()).lower()
    alters = re.findall(r"alter table public\.(\w+)\s+(\w+ constraint)", text)
    assert alters == [
        ("complaint_events", "drop constraint"),
        ("complaint_events", "add constraint"),
    ]
    for forbidden in (
        "drop table", "drop column", "drop function", "drop policy",
        "drop trigger", "drop view", "create function", "create table",
        "create policy", "create trigger", "create view", "truncate",
        "delete from", "insert into", "update public.", "grant ", "revoke ",
        "set not null", "alter column",
    ):
        assert forbidden not in text, forbidden


def test_the_guard_refuses_and_the_verification_fails() -> None:
    """The guard runs before the DROP, so its exception leaves the old
    constraint standing. The verification may only EXCEPTION, and must prove
    the new word specifically -- a bare existence check would pass against
    the very constraint this file replaces."""
    text = statements(sql())
    do_blocks = re.findall(r"do \$\$((?:.|\n)*?)\$\$;", text)
    assert len(do_blocks) == 2

    guard, verification = do_blocks
    assert "raise exception" in guard
    assert text.index(guard) < text.index("drop constraint")

    assert "raise exception" in verification
    assert "raise notice" not in verification
    assert "taken_up" in verification
