"""`20260824090000_supervisor_take_up.sql` -- what a static reader can prove
about the file that reopens the door `20260823190000` closed.

That file made every assignment path member-only (rulings R1-R3), which is what
the product owner asked for and which leaves a thin department with work nobody
may hold. The owner's answer (R8) was a **separate deliberate verb**, and the
hazard of a separate verb is that it becomes a second front door: a
`p_staff_assignment_id` here, or a rank clause one word looser, and the
member-only rule is decorative. So the checks below are three suites wearing one
hat.

**Section 1 widens a closed vocabulary.** `complaint_events.event_type` is an
enumerating CHECK on a live table, so a new word is a migration -- and a
drop-and-recreate that retypes the list is one dropped word away from making
existing rows unwritable. The old list is therefore not reviewed here, it is
**derived** from `20260822170000`'s own text, and the difference must be exactly
one word.

**Section 2 is new code**, and everything that matters about it is what it will
NOT do: name somebody else, admit a caller with no leadership row, notify the
person who pressed the button, or touch `supervision_inherited_at`.

**Sections 3 and 4 are two copies**, and a copy's hazard is the reverse of new
code's: not what it adds but what it quietly drops. Each is its predecessor's
body verbatim except for one ruled diff -- R12's actor on force-assign's two
timeline rows, R13's sentence on the board's leadership refusal -- so the copies
are diffed line by line and the removals must be **exactly** the ruled lines and
nothing else. A `create or replace` that lost an arm on the way through is a
failure with no symptom: the apply succeeds and the engine quietly becomes
something nobody wrote.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
TAKE_UP = MIGRATIONS / "20260824090000_supervisor_take_up.sql"

#: The file that declares the event vocabulary the database is holding, and the
#: body section 3 carries forward. Both are this one file.
ACTIONS = MIGRATIONS / "20260822170000_supervisor_actions.sql"
#: The body section 4 carries forward, and the rule this file must not undo.
REPAIRS = MIGRATIONS / "20260823190000_assignment_write_repairs.sql"
#: The actor-resolution pattern section 2 and section 3 both copy.
TRIAGE = MIGRATIONS / "20260822120000_supervisor_triage.sql"
#: The two other files this one's reasoning rests on.
BOARD = MIGRATIONS / "20260823170000_open_jobs_board.sql"
VOCAB = MIGRATIONS / "20260822150000_taken_up_event_word.sql"

#: (function, the file whose body is carried forward).
COPIED = (
    ("force_assign_work_order", ACTIONS),
    ("claim_open_work_order", REPAIRS),
)

#: The one new word. Section 1 may add this and nothing else.
NEW_WORD = "job_taken_up"

#: R12's diff, in full. The two lines force-assign loses...
FORCE_REMOVED = [
    "    (v_order.complaint_id, v_order.supervisor_membership_id, 'job_assigned',",
    "    (v_order.complaint_id, v_order.supervisor_membership_id, 'job_force_assigned',",
]
#: ...and the two it gains in their place.
FORCE_ADDED_EVENTS = [
    "    (v_order.complaint_id, v_actor, 'job_assigned',",
    "    (v_order.complaint_id, v_actor, 'job_force_assigned',",
]
FORCE_DECLARATION = "  v_actor     uuid;"
#: `take_up_complaint`'s resolution (`20260822120000`:209-221) including its
#: assertion, which is the half that makes a null actor a refusal rather than an
#: unattributable pair of timeline rows.
ACTOR_BLOCK = """\
  select m.id into v_actor
    from public.community_memberships m
   where m.community_id = v_order.community_id
     and m.profile_id   = auth.uid()
     and m.status       = 'active'
     and m.ended_at is null;
  if v_actor is null then"""

#: R13's diff: one sentence out, one sentence in -- as two adjacent literals, so
#: the line stays inside the margin and SQL concatenates them back into one.
CLAIM_REMOVED = [
    "      raise exception 'Supervisors and managers cannot take up jobs from the board.'"
]
CLAIM_ADDED = [
    "      raise exception 'Supervisors and managers cannot claim from the board. '",
    "        'Use \"Take this job myself\" from your dashboard.'",
]


def sql() -> str:
    return TAKE_UP.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped, so no check ever
    asserts against the header's prose instead of the SQL. This file's header
    quotes the very words and the very identifiers the checks below reason
    about, and its last section is nothing but commented-out queries."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def definition(text: str, name: str) -> str:
    """One function, from its `create or replace` through the end of its own
    `comment on function` -- the unit that is copied forward."""
    start = text.index(f"create or replace function public.{name}(")
    marker = text.index(f"comment on function public.{name}", start)
    return text[start : text.index("';\n", marker) + 2]


def do_blocks(text: str | None = None) -> list[str]:
    return re.findall(r"do \$\$((?:.|\n)*?)\$\$;", statements(text or sql()))


def word_lists(text: str) -> list[set[str]]:
    """Each ``event_type in (...)`` list in ``text``, as a set of words."""
    return [
        set(re.findall(r"'(\w+)'", group))
        for group in re.findall(
            r"event_type (?:not )?in \(((?:[^()])*?)\)", statements(text), re.S
        )
    ]


def old_words() -> set[str]:
    """The vocabulary as the last file to declare it declares it -- from that
    file's own text, not from anyone's memory of it."""
    lists = [words for words in word_lists(ACTIONS.read_text(encoding="utf-8"))]
    assert len(lists) == 2, "20260822170000 states the list twice"
    assert lists[0] == lists[1], "its guard and its constraint already disagree"
    return lists[0]


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_sorts_after_every_file_it_reasons_about() -> None:
    """Filename order is apply order. This file must postdate the vocabulary it
    widens, the two bodies it carries forward, and the pattern it copies -- a
    `create or replace` that lands *before* its source is silently undone by the
    source, and a constraint recreated before this one takes the new word back
    out."""
    for earlier in (TRIAGE, VOCAB, ACTIONS, BOARD, REPAIRS):
        assert earlier.exists(), earlier.name
        assert TAKE_UP.name > earlier.name, earlier.name


def test_it_is_the_last_word_on_the_functions_it_declares() -> None:
    """Not "it is last in the directory" -- that property expires the day the
    next migration lands. The property is being last *among the files that
    declare each function*, which is what decides which body the database ends
    up holding."""
    for function in (
        "take_up_work_order",
        "force_assign_work_order",
        "claim_open_work_order",
    ):
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
        assert declares[-1] == TAKE_UP.name, function


def test_it_declares_no_function_beyond_the_three_it_carries() -> None:
    """The frozen interface: one new function, two re-issued, nothing else.
    `dispatch_candidates_at`, `worker_open_jobs` and `assign_work_order` are all
    functions this file plausibly could have touched and all three would be it
    quietly reopening the member-only rule from a second direction."""
    declared = set(
        re.findall(
            r"^create (?:or replace )?function public\.(\w+)",
            statements(sql()),
            re.M,
        )
    )
    assert declared == {
        "take_up_work_order",
        "force_assign_work_order",
        "claim_open_work_order",
    }, sorted(declared)


# ---------------------------------------------------------------------------
# Section 1 -- one word, and the list around it
# ---------------------------------------------------------------------------


def test_the_new_list_is_the_old_list_plus_exactly_one_word() -> None:
    """Held by derivation rather than review. A word dropped here makes rows the
    hosted table already holds unwritable and fails the guard halfway through
    the swap; a second word invented here is a vocabulary change nobody ruled.
    """
    expected = old_words() | {NEW_WORD}
    lists = word_lists(sql())

    assert len(lists) == 2, "one list in the guard, one in the constraint"
    for words in lists:
        assert words == expected, (
            f"dropped from the old constraint: {sorted(old_words() - words)}; "
            f"invented here: {sorted(words - expected)}"
        )
    assert expected - old_words() == {NEW_WORD}


def test_the_older_take_up_word_is_kept_and_not_reused() -> None:
    """`taken_up` is `take_up_complaint`'s and means a supervisor is looking at
    a complaint; `job_taken_up` means one is going. Reusing the first for the
    second would make the two facts indistinguishable on the timeline, and
    dropping it would break every row already written with it."""
    assert "taken_up" in old_words()
    for words in word_lists(sql()):
        assert "taken_up" in words
    body = definition(sql(), "take_up_work_order")
    assert "'job_taken_up'" in body
    assert "'taken_up'" not in body


def test_the_swap_is_guarded_before_the_drop_and_proved_after_the_add() -> None:
    """The guard runs before the DROP, so its exception leaves the old
    constraint standing rather than leaving the table with none. The
    verification may only EXCEPTION, and must prove the NEW word specifically --
    a bare existence check would pass against the very constraint being
    replaced."""
    text = statements(sql())
    guard, verification = do_blocks()[0], do_blocks()[1]

    assert text.index("event_type not in (") < text.index("drop constraint")
    assert "raise exception" in guard
    assert "Unknown existing complaint event type" in guard

    assert "raise exception" in verification
    assert f"like '%{NEW_WORD}%'" in verification

    alters = re.findall(r"alter table public\.(\w+)\s+(\w+ constraint)", text)
    assert alters == [
        ("complaint_events", "drop constraint"),
        ("complaint_events", "add constraint"),
    ], alters


# ---------------------------------------------------------------------------
# Section 2 -- the new verb, and the four things it must not do
# ---------------------------------------------------------------------------


def test_the_new_function_takes_the_frozen_signature() -> None:
    """`create or replace` would refuse a changed return type, but there is
    nothing to refuse on a first apply -- a wrong signature here simply becomes
    the signature, and the repository's RPC call answers 404 forever."""
    body = definition(sql(), "take_up_work_order")

    assert "create or replace function public.take_up_work_order(\n" in body
    assert "  p_work_order_id      uuid,\n" in body
    assert "  p_scheduled_start_at timestamptz default null,\n" in body
    assert "  p_scheduled_end_at   timestamptz default null\n" in body
    assert "returns uuid" in body
    assert "security definer" in body
    assert "set search_path = public" in body
    assert (
        "grant execute on function public.take_up_work_order(uuid, timestamptz, timestamptz)\n"
        "  to authenticated;" in sql()
    )


def test_the_new_function_cannot_name_anybody_but_its_caller() -> None:
    """The whole of R8 in one assertion. A `p_staff_assignment_id` would make
    this "assign anybody, without the rank check" -- which is
    `20260823190000`'s rule with a hole in it, reachable by anybody who can call
    an RPC. The holder is looked up from `auth.uid()` and from nothing else."""
    body = definition(sql(), "take_up_work_order")

    assert "p_staff_assignment_id" not in body
    assert "(m.profile_id = auth.uid() or sp.profile_id = auth.uid())" in body
    assert (
        "   where sa.department_id = v_order.department_id\n"
        "     and sa.status = 'active'\n"
        "     and sa.is_active\n"
        "     and sa.rank in ('manager', 'supervisor')\n" in body
    )
    assert "'Only this department''s supervisor or manager can take up a job.'" in body
    assert body.count("using errcode = 'HB403'") == 2  # the roster row, the actor


def test_the_new_function_stamps_the_caller_on_both_timeline_rows() -> None:
    """R11's actor, and `take_up_complaint`'s assertion with it. A null actor
    would write two entries from nobody -- and `job_taken_up` exists precisely
    so that an unattributable take-up cannot happen."""
    body = definition(sql(), "take_up_work_order")

    assert ACTOR_BLOCK in body
    assert "(v_order.complaint_id, v_actor, 'job_assigned'," in body
    assert "(v_order.complaint_id, v_actor, 'job_taken_up'," in body
    assert body.count("v_order.supervisor_membership_id") == 0


def test_the_taken_up_assignment_is_accepted_and_neither_forced_nor_automatic() -> None:
    """R11's row shape, and both flags are a sentence. Nobody's consent was
    overridden -- the holder asked for it -- and no engine decided anything.
    `is_forced` is what the worker's card reads to hide the Decline button, and
    there is nothing here to decline."""
    body = definition(sql(), "take_up_work_order")

    assert (
        "    v_order.id, v_staff.id, 'accepted', false, false,\n"
        "    now(), now(), v_start, v_end)" in body
    )
    # Withdrawn and not deleted, exactly as force-assign leaves a previous
    # holder: the history of who was booked and unbooked is the record.
    assert (
        "  update public.work_order_assignments\n"
        "     set status = 'withdrawn', responded_at = now(), ended_at = now()" in body
    )
    assert "set status             = 'scheduled'," in body


def test_the_new_function_mirrors_force_assigns_refusals_and_nothing_more() -> None:
    """The frozen interface: status gate, slot rule and overlap check all mirror
    `force_assign_work_order`. Each is a `HB409`, and each is the sentence in
    front of a constraint that would otherwise answer `23P01` with no name in
    it."""
    body = definition(sql(), "take_up_work_order")
    force = definition(sql(), "force_assign_work_order")

    assert "'No such work order.' using errcode = 'HB404'" in body
    for shared in (
        "if v_order.status in ('completed', 'cancelled', 'failed') then",
        "raise exception 'This job is no longer open.' using errcode = 'HB409';",
        "raise exception 'A job needs a valid time.' using errcode = 'HB409';",
        "  v_start := coalesce(p_scheduled_start_at, v_order.scheduled_start_at);",
        "  v_end   := coalesce(p_scheduled_end_at,   v_order.scheduled_end_at);",
    ):
        assert shared in body, shared
        assert shared in force, shared

    # The overlap refusal is force-assign's check with the claim's wording: the
    # person double-booked is the person reading it.
    assert "&& tstzrange(v_start, v_end, '[)')" in body
    assert "raise exception 'You are already booked during that time.'" in body
    assert body.count("errcode = 'HB409'") == 3


def test_the_new_function_tells_the_resident_and_the_department_but_not_itself() -> None:
    """The frozen interface's audiences. The resident gets force-assign's own
    notice, url included, because the fact is the same fact. The department gets
    `job.taken_up`. The caller gets nothing -- they pressed the button -- and
    that is done with `notify_complaint_staff`'s exclusion argument rather than a
    branch, which is how `claim_open_work_order` avoids the same echo."""
    body = definition(sql(), "take_up_work_order")

    assert "'job.taken_up'," in body
    assert (
        "  perform public.notify_complaint_staff(\n"
        "    v_order.complaint_id, 'job.taken_up'," in body
    )
    assert "                       'complaint_id', v_order.complaint_id),\n    v_actor);" in body

    assert "v_complaint.raised_by_membership_id, 'work_order.assigned'," in body
    assert "'title', 'Someone is coming for your complaint'," in body
    assert (
        "'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,"
        in body
    )
    # No worker notice: force-assign tells the assignee they have been given a
    # job, and here the assignee is the caller.
    assert "'You have been assigned a job'" not in body
    assert "v_staff.membership_id" not in body


# ---------------------------------------------------------------------------
# Sections 3 and 4 -- two copies, diffed against what they copied
# ---------------------------------------------------------------------------


def diff(function: str, source: Path) -> tuple[list[str], list[str]]:
    """(removed, added) for ``function`` against its predecessor's body.

    This is the check the whole "verbatim except the ruled diff" promise rests
    on. `added_lines` in `test_assignment_write_repairs_migration.py` could
    assert *no* removals at all, because that file only ever inserted clauses;
    both diffs here replace a line, so the removals are pinned by name instead
    -- which is the stricter statement of the same property.
    """
    before = definition(source.read_text(encoding="utf-8"), function).splitlines()
    after = definition(sql(), function).splitlines()

    lines = list(difflib.unified_diff(before, after, n=0, lineterm=""))
    removed = [
        line[1:] for line in lines if line.startswith("-") and not line.startswith("---")
    ]
    added = [
        line[1:] for line in lines if line.startswith("+") and not line.startswith("+++")
    ]
    return removed, added


def test_force_assign_is_verbatim_except_the_actor_it_stamps() -> None:
    """R12, closing R7. The guard, the roster check, the status gate, the slot
    rule, the named overlap refusal, the withdraw, the insert, the `scheduled`
    update and all three notifications survive line for line -- the only lines
    that leave are the two that stamped the department's supervisor of record on
    work somebody else did."""
    removed, added = diff("force_assign_work_order", ACTIONS)

    assert removed == FORCE_REMOVED, removed

    executable = [line for line in added if not line.lstrip().startswith("--")]
    allowed = (
        set(ACTOR_BLOCK.splitlines())
        | {FORCE_DECLARATION}
        | set(FORCE_ADDED_EVENTS)
        # The tail of the pinned actor block: its refusal reuses the sentence
        # the guard above it already answers with, so both lines are the
        # predecessor's own and appear in the diff only by position.
        | {
            "    raise exception 'You do not supervise this department.' using errcode = 'HB403';",
            "  end if;",
            "",
        }
    )
    assert set(executable) <= allowed, sorted(set(executable) - allowed)

    body = definition(sql(), "force_assign_work_order")
    assert ACTOR_BLOCK in body
    assert FORCE_DECLARATION in body
    for line in FORCE_ADDED_EVENTS:
        assert line in body, line
    # And everything the copy must still be doing.
    for kept in (
        "public.can_supervise_department(v_order.department_id)",
        "'That person is not on this department roster.'",
        "'accepted', true, false,",
        "'job.force_assigned',",
        "'You have been assigned a job',",
        "'Someone is coming for your complaint',",
    ):
        assert kept in body, kept


def test_the_claim_keeps_the_board_shut_and_changes_only_the_sentence() -> None:
    """R13, with R2 standing underneath it. The rank clause, the leadership
    branch, the roster refusal below it, the trade guard, the exclusion guard,
    the overlap refusal, the row shape and the `work_order.claimed` notice are
    all `20260823190000`'s and are reproduced unchanged; one refusal now names
    the door that IS open."""
    removed, added = diff("claim_open_work_order", REPAIRS)

    assert removed == CLAIM_REMOVED, removed
    assert added == CLAIM_ADDED, added

    body = definition(sql(), "claim_open_work_order")
    assert "     and sa.rank = 'member'\n" in body
    assert "     and sa.rank is distinct from 'member'\n" in body
    assert "'You are not on this department''s roster.'" in body
    assert body.count("errcode = 'HB403'") == 3
    for kept in (
        "for update",
        "'Somebody has already taken this job.'",
        "'This job needs a trade you have not listed.'",
        "'accepted', false, false",
        "'work_order.claimed'",
    ):
        assert kept in body, kept


def test_the_leadership_refusal_reads_as_one_sentence() -> None:
    """Two adjacent literals, which SQL concatenates -- the line stays inside
    this directory's margin and the supervisor reads one sentence. The joined
    text is asserted here so that a stray comma or a lost space cannot turn it
    into two."""
    body = definition(sql(), "claim_open_work_order")
    literals = re.findall(r"raise exception ((?:'[^']*'\s*)+)\n?\s*using", body)
    joined = [
        "".join(re.findall(r"'([^']*)'", group)) for group in literals
    ]
    assert (
        'Supervisors and managers cannot claim from the board. '
        'Use "Take this job myself" from your dashboard.' in joined
    ), joined


# ---------------------------------------------------------------------------
# What it deliberately does not do
# ---------------------------------------------------------------------------


def test_every_sqlstate_it_raises_is_one_the_api_can_map() -> None:
    """R13's other half: the whole file raises only the three codes this surface
    already answers, so `pg_errors.py` gains no entry. A SQLSTATE it has never
    heard of surfaces as a 500 with a generic message -- and the sentence the
    RPC wrote never reaches the person it was written for."""
    from app.core import pg_errors

    raised = set(re.findall(r"errcode = '(HB[A-Z0-9]{3})'", sql()))
    assert raised == {"HB403", "HB404", "HB409"}
    assert raised <= set(pg_errors._CUSTOM)
    standard = set(re.findall(r"errcode = '(\d[A-Z0-9]{4})'", sql()))
    assert standard <= set(pg_errors._STANDARD), standard


def test_no_other_closed_vocabulary_and_no_task_kind_is_touched() -> None:
    """One CHECK is widened and it is named in section 1. Each of the others is
    a closed list on a live table that a drop-and-recreate would put at risk for
    nothing: this feature adds no status, no assignment state, no roster rank
    and no dispatch-task kind."""
    text = statements(sql())
    for constraint in (
        "work_orders_status_check",
        "work_order_assignments_status_check",
        "dispatch_tasks_kind_check",
        "staff_assignments_rank_check",
    ):
        assert constraint not in text, constraint
    assert "dispatch_tasks" not in text
    assert text.count("complaint_events_type_check") == 3  # drop, add, and the proof


def test_the_single_writer_of_the_inherited_stamp_is_left_alone() -> None:
    """R11, and the invariant `test_supervisor_triage_migration.py`:371 holds:
    `supervision_inherited_at` has exactly one writer,
    `restamp_department_supervision`. A supervisor choosing a job is not a
    supervisor being handed one, and a stamp with two writers is a dashboard
    badge that appears for two reasons nobody documented."""
    assert "supervision_inherited_at" not in statements(sql())
    assert "restamp_department_supervision" not in statements(sql())
    # Nor does it touch the triage stamps, which answer a different question.
    assert "taken_up_by_membership_id" not in statements(sql())
    assert "taken_up_at" not in statements(sql())


def test_the_audiences_are_stated_and_the_catalogue_is_reloaded() -> None:
    """`create or replace` preserves the ACLs of the two carried-forward
    functions, so those grants are a restatement -- but the new function's is
    not: a function created without one is callable by nobody, and PostgREST
    answers 404 for a route that exists until it is told to look again."""
    source = sql()

    assert (
        "revoke all on function public.take_up_work_order(uuid, timestamptz, timestamptz)\n"
        "  from public, anon, authenticated;" in source
    )
    assert (
        "grant execute on function public.force_assign_work_order(uuid, uuid, timestamptz, timestamptz)\n"
        "  to authenticated;" in source
    )
    assert (
        "grant execute on function public.claim_open_work_order(uuid) to authenticated;"
        in source
    )
    assert "notify pgrst, 'reload schema';" in source


def test_the_in_transaction_proof_looks_for_all_three_diffs() -> None:
    """A `create or replace` that silently lost its diff looks exactly like a
    successful apply -- the button answers HB403, or the timeline names the
    wrong person, and nothing in the output said so. The file refuses to be one
    of those."""
    proof = do_blocks()[2]

    for signature in (
        "public.take_up_work_order(uuid,timestamptz,timestamptz)",
        "public.force_assign_work_order(uuid,uuid,timestamptz,timestamptz)",
        "public.claim_open_work_order(uuid)",
    ):
        assert f"'{signature}'" in proof, signature
        assert "to_regprocedure" in proof

    assert "'sa.rank in (''manager'', ''supervisor'')'" in proof
    assert "'v_actor, ''job_taken_up'''" in proof
    # R12 proved as an absence: the old spelling must be gone, not merely
    # joined by the new one.
    assert "'v_order.supervisor_membership_id, ''job_assigned'''" in proof
    assert "'v_actor, ''job_force_assigned'''" in proof
    # R13, and R2 still standing under it.
    assert "'Take this job myself'" in proof
    assert "'sa.rank = ''member'''" in proof
    assert proof.count("raise exception") == 9


def test_the_post_checks_are_comment_only_and_guard_free() -> None:
    """Runbook section 28's lesson: the SQL editor has no `auth.uid()` and this
    deployment's departments carry `kind` NULL, so a post-check that calls a
    guarded verb answers HB403 or HB404 and proves nothing. The post-checks here
    inspect structure -- `pg_get_functiondef`, `pg_get_constraintdef`, `pg_proc`
    -- and are commented out so they never run inside the apply's transaction.
    """
    section = sql()[sql().index("-- Post-checks, to be run AFTER") :]
    # The queries themselves, told from the prose around them by the indent
    # under the `--`; the prose necessarily *names* the things the queries may
    # not call.
    queries = "\n".join(
        line for line in section.splitlines() if re.match(r"^--\s{3,}", line)
    )

    assert "pg_get_functiondef" in queries
    assert "pg_get_constraintdef" in queries
    for guarded in ("auth.uid()", "kind = 'service'", "my_membership_in"):
        assert guarded not in queries, guarded
    # Comment-only: nothing in the section survives the comment strip.
    assert statements(section).strip() == ""
