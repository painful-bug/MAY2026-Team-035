"""`20260823190000_assignment_write_repairs.sql` -- what a static reader can
prove about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once. It carries
two repairs whose failure modes are opposites, so the checks below are two
suites wearing one hat.

**Section 1 is a sweep**, in the shape
`20260822090000_hosted_work_order_column_drift.sql` established one table along:
the hosted `work_order_assignments` is a pre-baseline hand-built table carrying
`assigned_by_membership_id uuid NOT NULL` with no default, which no migration in
this repository has ever declared and no insert site writes -- so every write
path into the table answered SQLSTATE 23502, and the supervisor's force-assign
answered 422. A sweep's one real hazard is its protected list: a repository
column wrongly *missing* from it would have its NOT NULL dropped on the hosted
table, silently weakening a constraint the repository relies on. So that list is
not reviewed here -- it is **derived** from the three declaring migrations' own
text and compared exactly.

**Sections 2-4 are three copies**, and a copy's hazard is the reverse: not what
it adds but what it quietly drops. Each is a predecessor's body *verbatim* plus
`sa.rank = 'member'` (ruling R1: only workers hired from the servicemen pool may
hold a job; R3: strict, so a NULL rank is excluded). A `create or replace` that
lost an arm on the way through is a failure with no symptom -- the apply
succeeds and the eligibility rule quietly becomes something nobody wrote. So the
copies are diffed against their sources line by line, and the diff must contain
**no removals at all** and no executable addition beyond the clause and, in the
claim, the branch that tells leadership which door is closed.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
REPAIRS = MIGRATIONS / "20260823190000_assignment_write_repairs.sql"

#: The three files that declare `work_order_assignments`. Their text *is* the
#: protected list; nothing here retypes it.
BASELINE = MIGRATIONS / "0001_baseline.sql"
WORK_ORDERS = MIGRATIONS / "0036_work_orders.sql"
IS_FORCED = MIGRATIONS / "20260813101000_offer_consent_and_force.sql"

#: The sweep's precedent, and the two files the copied bodies come from.
PRECEDENT = MIGRATIONS / "20260822090000_hosted_work_order_column_drift.sql"
BOARD = MIGRATIONS / "20260823170000_open_jobs_board.sql"
ELIGIBILITY = MIGRATIONS / "20260823180000_resident_sets_the_time.sql"

#: (function, source file) for each body carried forward.
COPIED = (
    ("dispatch_candidates_at", ELIGIBILITY),
    ("worker_open_jobs", BOARD),
    ("claim_open_work_order", BOARD),
)

#: The clause, at each function's own indentation. Ruling R1, and R3 in the
#: `=`: a NULL rank and any future rank are excluded, not admitted.
RANK_CLAUSES = {
    "dispatch_candidates_at": "     and sa.rank = 'member'",
    "worker_open_jobs": "   and sa.rank = 'member'",
    "claim_open_work_order": "     and sa.rank = 'member'",
}

#: R2's branch: a supervisor IS on the roster, so the roster refusal above it
#: would be a lie. HB403 -- the code the function already answers both of its
#: other you-may-not-have-this-job refusals with.
LEADERSHIP_BRANCH = """\
    if exists (
      select 1
        from public.staff_assignments sa
        left join public.community_memberships m  on m.id  = sa.membership_id
        left join public.service_providers sp     on sp.id = sa.service_provider_id
       where sa.department_id = v_order.department_id
         and sa.status = 'active'
         and sa.is_active
         and sa.rank is distinct from 'member'
         and (m.profile_id = auth.uid() or sp.profile_id = auth.uid())
    ) then
      raise exception 'Supervisors and managers cannot take up jobs from the board.'
        using errcode = 'HB403';
    end if;"""


def sql() -> str:
    return REPAIRS.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped, so no check ever
    asserts against the header's prose instead of the SQL. This file's header
    quotes the very column name and the very statements the checks below reason
    about, and section 5 is nothing but commented-out queries."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def definition(text: str, name: str) -> str:
    """One function, from its `create or replace` through the end of its own
    `comment on function` -- the unit that is copied forward."""
    start = text.index(f"create or replace function public.{name}(")
    marker = text.index(f"comment on function public.{name}", start)
    return text[start : text.index("';\n", marker) + 2]


def declared_columns() -> set[str]:
    """Every `work_order_assignments` column the repository declares, from the
    files that declare them -- not from anyone's memory of them."""
    baseline = BASELINE.read_text(encoding="utf-8")
    line = next(
        ln
        for ln in baseline.splitlines()
        if ln.startswith("create table public.work_order_assignments ")
    )
    body = line[line.index("(") + 1 : line.rindex(")")]
    columns = {
        part.strip().split()[0]
        for part in body.split(", ")
        if part.strip() and not part.strip().startswith(("unique", "primary", "check"))
    }

    for path in (WORK_ORDERS, IS_FORCED):
        text = path.read_text(encoding="utf-8")
        # Only the work_order_assignments alters; both files extend other
        # tables too, and 0036 alters this one three more times for constraints.
        for block in re.findall(
            r"alter table public\.work_order_assignments\s+((?:.|\n)*?);", text
        ):
            columns.update(re.findall(r"add column if not exists\s+(\w+)", block))
    return columns


def protected_lists() -> list[set[str]]:
    """Each `not in (...)` list in the executable sections, as a set of names.

    Section 5's post-check repeats the list too, but it is commented out and
    `statements()` has already dropped it -- so a drift between the sweep and
    the post-check is not what this reads; the two live lists are.
    """
    return [
        set(re.findall(r"'(\w+)'", group))
        for group in re.findall(
            r"attname not in \(((?:[^()])*?)\)", statements(sql()), re.S
        )
    ]


def sweep_blocks() -> list[str]:
    return re.findall(r"do \$\$((?:.|\n)*?)\$\$;", statements(sql()))


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_sorts_after_every_file_it_reasons_about() -> None:
    """Filename order is apply order. This file must postdate every repository
    declaration it protects, the sweep it copies, and both bodies it carries
    forward -- a `create or replace` that lands *before* its source is silently
    undone by the source."""
    for earlier in (BASELINE, WORK_ORDERS, IS_FORCED, PRECEDENT, BOARD, ELIGIBILITY):
        assert earlier.exists(), earlier.name
        assert REPAIRS.name > earlier.name, earlier.name


#: Function -> the file whose body the database ends up holding. This file for
#: two of them, which nothing has touched since. **Not** for
#: `claim_open_work_order`: the 2026-08-24 addendum's ruling R13 re-issued it so
#: that the leadership refusal points at the new take-up verb, and
#: `20260824090000_supervisor_take_up.sql` is therefore the last word on that
#: one. Saying so here is the point of the check rather than a failure of it --
#: and what R13 changed is one sentence: the rank clause and the leadership
#: branch this file added are carried forward verbatim, which
#: `test_supervisor_take_up_migration.py` diffs line by line against *this*
#: file's text. The assertions further down still read this file's own body,
#: which is what was applied here.
LAST_WORD = {
    "dispatch_candidates_at": REPAIRS.name,
    "worker_open_jobs": REPAIRS.name,
    "claim_open_work_order": "20260824090000_supervisor_take_up.sql",
}


def test_it_is_the_last_word_on_the_three_functions_it_redefines() -> None:
    """Not "it is last in the directory" -- that property expires the day the
    next migration lands. The property is being last *among the files that
    declare each function*, which is what decides which body the database ends
    up holding."""
    for function, owner in LAST_WORD.items():
        declares = sorted(
            path.name
            for path in MIGRATIONS.glob("*.sql")
            if re.search(
                r"^create (or replace )?function public\." + function + r"\b",
                path.read_text(encoding="utf-8"),
                re.M,
            )
        )
        assert declares, f"nothing declares {function} at all"
        assert declares[-1] == owner, function


def test_it_declares_no_function_beyond_the_three_it_carries_forward() -> None:
    """R5 froze the interface: no new function, no new signature. Everything
    else in the eligibility chain -- the three-argument `dispatch_candidates`,
    `find_first_available_slot`, the dispatch handlers -- reaches the new rule
    through the one body section 2 rewrites, and must not be re-issued here."""
    declared = set(
        re.findall(
            r"^create (?:or replace )?function public\.(\w+)",
            statements(sql()),
            re.M,
        )
    )
    assert declared == {name for name, _ in COPIED}, sorted(declared)


# ---------------------------------------------------------------------------
# Section 1 -- the sweep, and its one real hazard
# ---------------------------------------------------------------------------


def test_the_protected_list_is_exactly_the_repository_declaration() -> None:
    """Held by derivation rather than by review.

    A repository column missing from the list would get its NOT NULL dropped on
    the hosted table; a name in the list that no migration declares would
    protect a legacy column and leave the 422 alive behind a passing apply.
    """
    declared = declared_columns()
    lists = protected_lists()

    assert declared, "the repository declaration could not be derived"
    assert len(lists) == 2, "one list in the sweep, one in the verification"
    for protected in lists:
        assert protected == declared, (
            f"missing from the file: {sorted(declared - protected)}; "
            f"declared by no migration: {sorted(protected - declared)}"
        )


def test_the_sweep_touches_only_insert_blocking_columns() -> None:
    """Nullable legacy columns, and NOT NULL ones with a default, block no
    insert and must be left exactly as they are -- which is why the legacy
    status-ish column that defaults to 'assigned' is not this file's business.
    """
    text = statements(sql())
    assert text.count("and a.attnotnull") == 2
    assert text.count("and not a.atthasdef") == 2
    assert text.count("and not a.attisdropped") == 2


def test_the_only_ddl_in_the_sweep_is_the_widening() -> None:
    """One dynamic statement shape, and it can only loosen. `set not null`
    anywhere in this file would be it tightening the very thing section 1
    exists to loosen, and every other verb below is out of scope for a drift
    reconciliation by definition."""
    text = statements(sql()).lower()

    executes = re.findall(r"execute format\(\s*'([^']*)'", text)
    assert executes == [
        "alter table public.work_order_assignments alter column %i drop not null"
    ]

    for forbidden in (
        "set not null",
        "drop table",
        "drop column",
        "drop function",
        "drop policy",
        "drop trigger",
        "drop constraint",
        "add constraint",
        "create table",
        "create policy",
        "create trigger",
        "create view",
        "truncate",
        "delete from",
    ):
        assert forbidden not in text, forbidden

    # And section 1 writes no rows at all: it reconciles a declaration, so an
    # insert or an update inside it would be the sweep changing data on its way
    # past. (The claim's own `insert into work_order_assignments` is section
    # 4's, copied forward from the accept path, and is not this check's
    # business.)
    for block in sweep_blocks()[:2]:
        for forbidden in ("insert into", "update public.", "delete from"):
            assert forbidden not in block.lower(), forbidden


def test_the_sweep_reports_and_the_verification_fails() -> None:
    """The sweep may only NOTICE -- an exception there aborts a partial fix into
    no fix. The verification may only EXCEPTION -- a NOTICE there is the file
    reporting success it has not checked. Idempotence is the zero-found notice:
    re-running the file finds nothing and says so."""
    blocks = sweep_blocks()
    assert len(blocks) == 3, "the sweep, its verification, and the copies' proof"

    sweep, verification, _ = blocks
    assert "raise notice" in sweep
    assert "raise exception" not in sweep
    assert "v_dropped = 0" in sweep

    assert "raise exception" in verification
    assert "raise notice" not in verification


def test_the_sweep_is_the_first_thing_the_transaction_does() -> None:
    """R5 fixed the order. The two 2026-08-23 auto-assign handlers write into
    this table; widening it before the eligibility rule changes means no window
    in which a newly eligible path meets the un-widened column."""
    text = statements(sql())
    assert text.index("drop not null") < text.index("create or replace function")


def test_the_column_that_answered_every_assign_with_a_422_is_not_special_cased() -> None:
    """R4: the fix is a sweep, not a named repair. `assigned_by_membership_id`
    must appear nowhere in the executable SQL -- naming it there would be this
    file encoding a hosted-only legacy column, which is the drift it exists to
    undo, in the other direction."""
    assert "assigned_by_membership_id" not in statements(sql())
    # It is named in the header and in section 5's commented post-check, which
    # is where a legacy column's name belongs: in the explanation.
    assert "assigned_by_membership_id" in sql()


# ---------------------------------------------------------------------------
# Sections 2-4 -- three copies, diffed against what they copied
# ---------------------------------------------------------------------------


def added_lines(function: str, source: Path) -> list[str]:
    """The lines this file adds to ``function``'s predecessor body, asserting
    on the way that it removes none.

    This is the check the whole "verbatim plus one clause" promise rests on: a
    `create or replace` that dropped a guard, an ordering term or a
    notification would apply perfectly and change what the engine does.
    """
    before = definition(source.read_text(encoding="utf-8"), function).splitlines()
    after = definition(sql(), function).splitlines()

    diff = list(difflib.unified_diff(before, after, n=0, lineterm=""))
    removed = [
        line[1:]
        for line in diff
        if line.startswith("-") and not line.startswith("---")
    ]
    assert removed == [], f"{function} lost lines its predecessor had: {removed}"

    return [
        line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")
    ]


def test_the_eligibility_body_is_verbatim_plus_the_one_clause() -> None:
    """`dispatch_candidates_at` is the ONE implementation behind the picker,
    the slot finder and five dispatch handlers. Every clause of
    `20260823180000` §2 survives; the join gains one line and nothing else
    executable moves."""
    added = added_lines("dispatch_candidates_at", ELIGIBILITY)
    executable = [line for line in added if not line.lstrip().startswith("--")]

    assert executable == [RANK_CLAUSES["dispatch_candidates_at"]], executable
    # And it landed on the roster join, not somewhere that reads the same.
    body = definition(sql(), "dispatch_candidates_at")
    assert (
        "    join public.staff_assignments sa\n"
        "      on sa.department_id = j.department_id\n"
        "     and sa.status = 'active'\n"
        "     and sa.is_active\n"
        "     and sa.membership_id is not null\n"
        "     and sa.rank = 'member'\n" in body
    )
    # The frozen ordering is untouched -- a different one is a different worker.
    assert (
        "order by\n    candidate.adjacent desc,\n    candidate.load asc,\n"
        "    candidate.km asc nulls last,\n    candidate.sa_display_name" in body
    )


def test_the_board_body_is_verbatim_plus_the_one_clause() -> None:
    """R2: the board is a door onto assignment, so it takes the same clause on
    the same kind of join -- and keeps D1's both-halves predicate, the trade
    short-circuit and the exclusion filter exactly as `20260823170000` wrote
    them."""
    added = added_lines("worker_open_jobs", BOARD)
    executable = [line for line in added if not line.lstrip().startswith("--")]

    assert executable == [RANK_CLAUSES["worker_open_jobs"]], executable

    body = definition(sql(), "worker_open_jobs")
    assert (
        "  join public.staff_assignments sa\n"
        "    on sa.department_id = w.department_id\n"
        "   and sa.status = 'active'\n"
        "   and sa.is_active\n"
        "   and sa.rank = 'member'\n" in body
    )
    for kept in (
        "w.status in ('draft', 'offered')",
        "a.status in ('offered', 'accepted')",
        "complaint_excluded_staff",
        "order by w.scheduled_start_at asc nulls last, w.created_at desc;",
    ):
        assert kept in body, kept


def test_the_claim_gains_the_clause_and_a_refusal_that_names_the_reason() -> None:
    """R2 again, on the write side. The roster re-check is what a deep-linked
    claim meets when the board never showed the job, so the clause belongs
    there -- and the branch under it exists because a supervisor genuinely IS on
    the roster, and answering them "you are not on this department's roster"
    would be a lie told to the one person able to check it."""
    added = added_lines("claim_open_work_order", BOARD)
    executable = [line for line in added if not line.lstrip().startswith("--")]

    assert executable == [
        RANK_CLAUSES["claim_open_work_order"],
        *LEADERSHIP_BRANCH.splitlines(),
    ], executable

    body = definition(sql(), "claim_open_work_order")
    assert (
        "   where sa.department_id = v_order.department_id\n"
        "     and sa.status = 'active'\n"
        "     and sa.is_active\n"
        "     and sa.rank = 'member'\n" in body
    )
    # The original refusal is still under the new one: an outsider is still
    # told they are not on the roster, which for them is true.
    assert "'You are not on this department''s roster.'" in body
    # And the guards the claim already had are all still there.
    for kept in (
        "for update",
        "'Somebody has already taken this job.'",
        "'This job needs a trade you have not listed.'",
        "'You are already booked during that time.'",
        "'accepted', false, false",
        "'work_order.claimed'",
    ):
        assert kept in body, kept


def test_the_leadership_refusal_reuses_the_functions_own_error_family() -> None:
    """The frozen interface says pick the closest existing HB code, do not
    invent a numbering scheme. `claim_open_work_order` already answers both of
    its you-may-not-have-this-job refusals -- the roster miss and the trade miss
    -- with HB403, and this is the third of them."""
    body = definition(sql(), "claim_open_work_order")
    codes = re.findall(
        r"raise exception '([^']*(?:''[^']*)*)'\s*\n?\s*using errcode = '(HB\d{3})'",
        body,
    )
    leadership = [
        code for message, code in codes if "Supervisors and managers" in message
    ]
    assert leadership == ["HB403"], codes
    assert body.count("errcode = 'HB403'") == 3


def test_every_sqlstate_it_raises_is_one_the_api_can_map() -> None:
    """A SQLSTATE `pg_errors` has never heard of surfaces as a 500 with a
    generic message -- and the sentence the RPC wrote never reaches the person
    it was written for."""
    from app.core import pg_errors

    raised = set(re.findall(r"errcode = '(HB[A-Z0-9]{3})'", sql()))
    assert raised == {"HB403", "HB404", "HB409"}
    assert raised <= set(pg_errors._CUSTOM)
    standard = set(re.findall(r"errcode = '(\d[A-Z0-9]{4})'", sql()))
    assert standard <= set(pg_errors._STANDARD), standard


# ---------------------------------------------------------------------------
# What it deliberately does not do
# ---------------------------------------------------------------------------


def test_no_closed_vocabulary_and_no_task_kind_is_touched() -> None:
    """R5's frozen interface: no status word, no event word, no dispatch-task
    kind. Each of the three is a CHECK on a live table, and each costs a
    drop-and-recreate that this file has no reason to spend."""
    text = statements(sql())
    for constraint in (
        "work_orders_status_check",
        "complaint_events_type_check",
        "work_order_assignments_status_check",
        "dispatch_tasks_kind_check",
        "staff_assignments_rank_check",
    ):
        assert constraint not in text, constraint
    assert "dispatch_tasks" not in text


def test_the_audiences_are_restated_and_the_catalogue_is_reloaded() -> None:
    """`create or replace` preserves ACLs, so these are a restatement -- but an
    ACL nobody can see in the file is an ACL nobody checks. The internal stays
    definer-only; the two board verbs stay `authenticated`."""
    source = sql()

    assert (
        "revoke all on function public.dispatch_candidates_at(\n"
        "  uuid, timestamptz, timestamptz, integer, boolean)\n"
        "  from public, anon, authenticated;" in source
    )
    assert "grant execute on function public.dispatch_candidates_at" not in source
    assert (
        "grant execute on function public.worker_open_jobs() to authenticated;"
        in source
    )
    assert (
        "grant execute on function public.claim_open_work_order(uuid) to authenticated;"
        in source
    )
    assert "notify pgrst, 'reload schema';" in source


def test_the_in_transaction_proof_looks_for_the_clause_in_all_three() -> None:
    """A `create or replace` that silently lost the clause looks exactly like a
    successful apply. The file refuses to be one of those."""
    proof = sweep_blocks()[2]

    for function in ("dispatch_candidates_at", "worker_open_jobs", "claim_open_work_order"):
        assert f"to_regprocedure(\n    'public.{function}(" in proof or (
            f"to_regprocedure('public.{function}(" in proof
        ), function
        assert f"'public.{function}(" in proof
    assert proof.count("'sa.rank = ''member'''") == 3
    # The delegate is still a delegate: nothing here re-implemented eligibility.
    assert "the three-argument dispatch_candidates is no longer the delegate" in proof


def test_the_post_checks_are_comment_only_and_guard_free() -> None:
    """Runbook §28's lesson: the SQL editor has no `auth.uid()` and this
    deployment's departments carry `kind` NULL, so a post-check that calls a
    guarded verb answers HB403 or HB404 and proves nothing. Section 5 inspects
    structure -- `pg_get_functiondef` and `pg_attribute` -- and is commented out
    so it never runs inside the apply's transaction."""
    section = sql()[sql().index("-- 5. Post-checks") :]
    # The queries themselves, told from the prose around them by the indent
    # under the `--`; the prose necessarily *names* the things the queries may
    # not call.
    queries = "\n".join(
        line for line in section.splitlines() if re.match(r"^--\s{3,}", line)
    )

    assert "pg_get_functiondef" in queries
    assert "pg_attribute" in queries
    for guarded in ("auth.uid()", "kind = 'service'", "my_membership_in"):
        assert guarded not in queries, guarded
    # Comment-only: nothing in section 5 survives the comment strip.
    assert statements(section).strip() == ""
