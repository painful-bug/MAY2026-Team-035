"""`20260822170000_supervisor_actions.sql` -- what a static reader can prove
about a file nobody in this repository runs.

Amendment 2 of the supervisor dashboard: the buttons on the cards. It adds a
`complaint` chat thread, four complaint verbs, a hand-operated force-assign, a
re-bucketed snapshot, and **one** new `complaint_events` word.

The properties worth asserting without a database are these.

**Is the new event word the only one, and is the constraint's old vocabulary
intact?** The 2026-08-22 lesson (runbook 19) cost a whole extra migration:
`complaint_events_type_check` enumerates its words, so a word is a migration.
Recreating an enumerating constraint risks *losing* one, and a lost word poisons
every later insert of that type. So the list is not reviewed here -- it is
**derived** from `20260822150000`'s own text plus exactly `priority_changed`,
and compared. The same derivation is applied to `dm_threads_kind_check` against
`0046`.

**Is the copy of `post_dm_message` additive?** It is `0046`'s, redeclared whole
under the house convention to admit a department to its own complaint thread.
Every non-blank line of the owning file's version has to still be present
verbatim -- the 1--4000 check, the `HB404` that hides other people's threads, the
`HB409` lock and the notification are each things that can vanish without
anything erroring.

**Does `supervisor_resolve_complaint` avoid saying the same thing twice?**
`complaints_on_resolved` (`20260813104000`) already writes the `status_changed`
event, notifies the raiser and arms both auto-close timers when the status moves.
So this file must *not* -- and must fail its own apply if that trigger is
missing, because a Resolve that tells the resident nothing is the failure with no
symptom.

**Is the dead column still dead?** Ruling 1 of 2026-08-21. Resolve, priority and
notes are all triage; nothing here writes `assigned_to_membership_id` or
`assignee_label`.

**Is anything destructive beyond what it must be?** The four `drop`s this file is
allowed are named one by one, and everything else is forbidden.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

from app.core import pg_errors

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
ACTIONS = MIGRATIONS / "20260822170000_supervisor_actions.sql"

#: The file that owns each object this one rewrites, or whose vocabulary it
#: extends.
MESSAGES = MIGRATIONS / "0046_direct_messages.sql"            # post_dm_message
WORK_ORDERS = MIGRATIONS / "0036_work_orders.sql"             # can_supervise_department
FORCE = MIGRATIONS / "20260813101000_offer_consent_and_force.sql"
TIMERS = MIGRATIONS / "20260813104000_timers_v2.sql"          # complaints_on_resolved
VOCAB = MIGRATIONS / "20260813105000_chat_autopen_and_vocab.sql"
TRIAGE = MIGRATIONS / "20260822120000_supervisor_triage.sql"  # the snapshot v1
WORD = MIGRATIONS / "20260822150000_taken_up_event_word.sql"  # the constraint, now

#: What "live" means, everywhere in this directory.
TERMINAL = "w.status not in ('completed', 'cancelled', 'failed')"

#: The five sections the frozen contract names, in the order it names them.
SECTIONS = (
    "new_complaints",
    "taken_up",
    "open_requests",
    "assigned_pending",
    "in_progress",
)


def sql() -> str:
    return ACTIONS.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped.

    This file's header argues every decision it makes and names most of the
    identifiers the assertions below look for -- including
    `assigned_to_membership_id`, which it mentions only to say it does not write
    it. A check that read the prose would be asserting against the explanation.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def body(text: str, header: str) -> str:
    """One ``create ... as $$ ... $$;`` body, by the regex that starts it."""
    start = re.search(header, text, re.M)
    assert start, f"no block matching {header!r}"
    end = text.index("$$;", text.index("as $$", start.start()))
    return text[start.start() : end]


def snapshot_query() -> str:
    """The one statement `pglast` cannot see from outside.

    A function body is a string literal to the outer parse, so the whole-file
    check says nothing about the query that fills all five dashboard sections.
    Lifted out and parsed on its own, minus the plpgsql ``into``.
    """
    text = sql()
    start = text.index("  with complaint_rows as (")
    end = text.index("  into v_new, v_taken, v_open, v_pending, v_progress;")
    return text[start:end] + ";"


def word_lists(text: str, column: str) -> list[set[str]]:
    """Each ``<column> in (...)`` list in ``text``, as a set of words."""
    return [
        set(re.findall(r"'(\w+)'", group))
        for group in re.findall(
            column + r" (?:not )?in \(((?:[^()])*?)\)", statements(text), re.S
        )
    ]


def previous_event_words() -> set[str]:
    """The complaint-event vocabulary as `20260822150000` declares it.

    From that file's own text, not from anyone's memory of it. It states the
    list twice -- once in its guard, once in the constraint -- and they must
    agree with each other before either is leaned on.
    """
    lists = [
        words
        for words in word_lists(WORD.read_text(encoding="utf-8"), "event_type")
        if len(words) > 1
    ]
    assert len(lists) >= 2
    assert all(words == lists[0] for words in lists)
    return lists[0]


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_the_snapshot_query_parses_on_its_own() -> None:
    """A syntax error in the query that fills the entire dashboard would sail
    past the whole-file parse and surface in the SQL editor, on a live database,
    in front of the owner."""
    parse_sql(snapshot_query())


def test_it_sorts_after_every_file_whose_work_it_builds_on() -> None:
    """Filename order is apply order.

    `20260822150000` is the tightest: this file recreates the same constraint,
    and applying that one afterwards would silently drop `priority_changed` back
    out of the vocabulary. `0046` matters because the `complaint` kind is an
    extension of a CHECK that file creates, and `20260822120000` because the
    snapshot replaced here is the one it declared.
    """
    for earlier in (WORK_ORDERS, MESSAGES, FORCE, TIMERS, VOCAB, TRIAGE, WORD):
        assert ACTIONS.name > earlier.name


def test_it_is_the_last_word_on_both_functions_it_replaces() -> None:
    """Not "it is last in the directory" -- that property has expired five times
    in this directory already. The property is being last *among the files that
    declare this function*, which is what decides which body the database holds.
    """
    for function in ("post_dm_message", "supervisor_triage_snapshot"):
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
        assert declares[-1] == ACTIONS.name, function


def test_it_redeclares_nothing_else_the_sibling_files_pin() -> None:
    """One function is copied forward and no others.

    Each name below is one a sibling static-check file guards and one this file
    plausibly could have touched: the engine's own force-assign it is modelled
    on, the offer path it must leave byte-for-byte alone, the thread openers
    beside its own, the auto-close trigger it depends on, and the two functions
    phase one copied forward. Copying any of them forward to gain nothing would
    put this file in the way of the next person who needs to change one.
    """
    text = statements(sql())
    for owned in (
        "dispatch_force_assign",
        "assign_work_order",
        "open_direct_thread",
        "open_work_order_thread",
        "lock_work_order_threads",
        "on_complaint_resolved",
        "dispatch_auto_close",
        "update_complaint",
        "cancel_work_order",
        "start_work_order",
        "restamp_department_supervision",
        "take_up_complaint",
        "staff_complaint_detail",
        "can_supervise_department",
        "dm_pair_allowed",
        "project_complaint_from_jobs",
    ):
        assert not re.search(
            r"^create (or replace )?(view|function) public\." + owned + r"\b",
            text,
            re.M,
        ), owned


def test_it_never_writes_the_dead_complaint_column() -> None:
    """Ruling 1 of 2026-08-21, restated for amendment 2. Resolve, priority and
    notes are triage; who is going is a work-order assignment, and the whole
    design depends on not answering the second question by accident."""
    text = statements(sql())
    assert "assigned_to_membership_id" not in text
    assert "assignee_label" not in text


# ---------------------------------------------------------------------------
# The vocabulary: one new word, nothing lost
# ---------------------------------------------------------------------------


def test_the_new_event_list_is_the_old_list_plus_exactly_priority_changed() -> None:
    """Held by derivation rather than review.

    Every word `20260822150000` allowed, plus the one word amendment 2 adds, and
    nothing else. A word dropped here would make the guard block refuse the apply
    (good) or, were the guard wrong, poison every later insert of that type
    (bad).
    """
    expected = previous_event_words() | {"priority_changed"}
    lists = [words for words in word_lists(sql(), "event_type") if len(words) > 1]
    assert len(lists) == 2, "one list in the guard, one in the constraint"
    for words in lists:
        assert words == expected, (
            f"dropped: {sorted(previous_event_words() - words)}; "
            f"invented here: {sorted(words - expected)}"
        )


def test_the_file_writes_no_event_word_the_constraint_does_not_allow() -> None:
    """The 23514 of 2026-08-22, asked of this file before it is applied rather
    than after. Every literal this file inserts as an `event_type` must be in the
    list it recreates."""
    text = statements(sql())
    written = set(
        re.findall(r"'(\w+)',\s*\n?\s*jsonb_build_object", text)
    ) | set(re.findall(r"event_type\s*=\s*'(\w+)'", text))
    allowed = previous_event_words() | {"priority_changed"}
    assert written, "no event insert found at all -- has the shape changed?"
    assert written <= allowed, sorted(written - allowed)
    assert "priority_changed" in written


def test_the_thread_kind_list_is_the_old_list_plus_exactly_complaint() -> None:
    """The same derivation for `dm_threads_kind_check`, whose two words are
    `0046`'s. Losing `work_order` here would make every job chat unwritable."""
    creator = [
        words
        for words in word_lists(MESSAGES.read_text(encoding="utf-8"), "kind")
        if len(words) > 1
    ]
    assert creator, "0046 declares no kind list"
    expected = creator[0] | {"complaint"}
    lists = [words for words in word_lists(sql(), "kind") if len(words) > 1]
    assert lists, "this file declares no kind list"
    for words in lists:
        assert words == expected, sorted(words ^ expected)


def test_both_constraint_swaps_are_guarded_before_the_drop() -> None:
    """`20260822150000`'s shape, twice.

    The guard runs before the DROP, so its exception leaves the old constraint
    standing untouched. Without it, a row outside the new list would fail the ADD
    with the old constraint already gone -- a table with no check on it at all.
    """
    text = statements(sql())
    for column, constraint in (
        ("kind", "drop constraint if exists dm_threads_kind_check"),
        ("event_type", "drop constraint if exists complaint_events_type_check"),
    ):
        drop_at = text.index(constraint)
        guard = text.rindex("do $$", 0, drop_at)
        block = text[guard:drop_at]
        assert "raise exception" in block, constraint
        assert f"{column} not in (" in block, constraint


def test_the_verification_proves_the_new_word_specifically() -> None:
    """A bare existence check would pass against the very constraint this file
    replaces."""
    text = statements(sql())
    after = text[text.index("add constraint complaint_events_type_check") :]
    verification = after[after.index("do $$") :]
    assert "raise exception" in verification
    assert "priority_changed" in verification


# ---------------------------------------------------------------------------
# The chat thread (ruling A1)
# ---------------------------------------------------------------------------


def test_the_complaint_thread_is_one_row_per_complaint_and_cascades() -> None:
    """`on delete cascade` is forced rather than chosen: the subject CHECK makes
    `kind = 'complaint'` and a non-null `complaint_id` the same fact, so
    `set null` would raise 23514 and refuse to delete the complaint at all."""
    text = statements(sql())
    assert (
        "add column if not exists complaint_id uuid\n"
        "    references public.complaints(id) on delete cascade" in text
    )
    assert "create unique index if not exists dm_threads_one_per_complaint" in text
    assert "where kind = 'complaint'" in text
    assert "check ((kind = 'complaint') = (complaint_id is not null))" in text


def test_only_the_thread_opener_writes_the_complaint_id() -> None:
    """One writer, asserted as a count. A second one -- a backfill, a trigger --
    would attach a conversation to a complaint nobody opened it about."""
    text = statements(sql())
    inserts = re.findall(r"insert into public\.dm_threads", text)
    assert len(inserts) == 1
    opener = body(text, r"^create or replace function public\.open_complaint_thread")
    assert "insert into public.dm_threads" in opener
    assert "'complaint', p_complaint_id" in opener


def test_the_thread_seeds_the_frozen_sentence() -> None:
    """Approved copy, and the title is interpolated rather than described."""
    opener = body(sql(), r"^create or replace function public\.open_complaint_thread")
    assert "'The department opened this chat about '''" in opener
    assert "insert into public.dm_messages" in opener


def test_the_opener_returns_the_existing_thread_before_it_resolves_a_pair() -> None:
    """"A later supervisor joins the existing thread rather than forking a second
    one" is this ordering and nothing else: the lookup happens before the pair is
    computed, so the second supervisor gets the first one's thread with their own
    right to write it coming from the policy rather than from the row."""
    opener = body(sql(), r"^create or replace function public\.open_complaint_thread")
    lookup = opener.index("select t.id into v_id")
    insert = opener.index("insert into public.dm_threads")
    assert lookup < insert
    assert opener.index("for update;") < lookup  # and the row is locked first
    assert "return v_id;" in opener[lookup:insert]


def test_the_lock_mirrors_the_job_thread_and_reopens_what_a_job_cannot() -> None:
    """`closed | cancelled` shuts the channel and says so in it; anything else
    opens it again. The `else` arm is the one difference from `0046`'s trigger,
    and it exists because a complaint can be reopened and a job cannot."""
    lock = body(sql(), r"^create or replace function public\.lock_complaint_threads")
    assert "new.status in ('closed', 'cancelled')" in lock
    assert "locked_at = coalesce(locked_at, now())" in lock
    assert "insert into public.dm_messages" in lock
    assert "set locked_at = null" in lock
    text = statements(sql())
    assert "after insert or update of status on public.complaints" in text


def test_reading_and_writing_a_complaint_thread_ask_the_same_question() -> None:
    """One rule, three places, and they cannot drift because all three call it.

    A read policy that admitted the department while `post_dm_message` did not
    would be a chat a supervisor can open, watch, and never answer in.
    """
    text = statements(sql())
    assert text.count("create or replace function public.can_supervise_complaint") == 1
    for policy in ("dm_threads_read", "dm_messages_read"):
        assert f"drop policy if exists {policy}" in text
        assert f"create policy {policy}" in text
    assert text.count("public.can_supervise_complaint(") >= 3
    post = body(text, r"^create or replace function public\.post_dm_message")
    assert "public.can_supervise_complaint(v_thread.complaint_id)" in post


def _additive(owner: Path, header: str) -> list[str]:
    """Lines of ``owner``'s version of a function missing from this file's copy."""
    applied = body(owner.read_text(encoding="utf-8"), header)
    copied = body(sql(), header)
    return [
        line
        for line in (raw.rstrip() for raw in applied.splitlines())
        if line.strip() and line not in copied
    ]


def test_the_post_message_copy_is_purely_additive() -> None:
    """The house convention, checked rather than promised.

    Every non-blank line of `0046`'s `post_dm_message` has to still be present.
    The length check, the `HB404` that hides other people's threads, the `HB409`
    lock, the `last_message_at` bump and the counterpart notification are all
    lines that can vanish without anything erroring -- and the lock is the whole
    of amendment 2's write-locking requirement.
    """
    missing = _additive(
        MESSAGES, r"^create or replace function public\.post_dm_message"
    )
    assert not missing, f"the copy lost these lines from {MESSAGES.name}: {missing}"


def test_the_post_message_copy_keeps_its_signature_and_return_type() -> None:
    """`create or replace` refuses a changed return type and would fail on the
    hosted database; a new defaulted parameter would create an overload rather
    than replace anything, which fails silently and is worse."""
    post = body(sql(), r"^create or replace function public\.post_dm_message")
    assert "p_thread_id uuid," in post
    assert "p_body      text" in post
    assert "returns uuid" in post


# ---------------------------------------------------------------------------
# Resolve (ruling A2)
# ---------------------------------------------------------------------------


def test_resolve_refuses_a_running_job_and_a_settled_complaint() -> None:
    """The refusal the button exists to produce well. Somebody is inside a
    resident's flat: the honest answers are to let them finish or to cancel the
    visit, and both are somebody's deliberate act."""
    resolve = body(
        sql(), r"^create or replace function public\.supervisor_resolve_complaint"
    )
    assert "w.status = 'in_progress'" in resolve
    assert "Finish or cancel the running job first." in resolve
    assert "if v_complaint.status in ('resolved', 'closed') then" in resolve
    assert "This complaint was cancelled." in resolve
    assert resolve.count("using errcode = 'HB409'") == 4
    assert "for update;" in resolve


def test_resolve_cancels_every_other_live_job_and_tells_its_worker_why() -> None:
    """Ruling A2's other half, with the frozen reason. A worker holding an offer
    must not find out from an empty queue, and an assignment is withdrawn rather
    than deleted -- one holder at a time, and the history survives."""
    resolve = body(
        sql(), r"^create or replace function public\.supervisor_resolve_complaint"
    )
    assert "'Complaint resolved by the department'" in resolve
    assert "'draft', 'awaiting_resident', 'offered', 'scheduled'" in resolve
    assert "a.status in ('offered', 'accepted')" in resolve
    assert "set status = 'withdrawn', responded_at = now(), ended_at = now()" in resolve
    assert "'job.cancelled'," in resolve
    assert "'job_cancelled'," in resolve
    assert "status               = 'cancelled'," in resolve


def test_resolve_leaves_the_status_event_and_the_notification_to_the_trigger() -> None:
    """`complaints_on_resolved` (`20260813104000`) writes the `status_changed`
    row, notifies the raiser `complaint.resolved` and arms both auto-close timers
    when the status moves. This function moves the status, so all four happen in
    the same transaction. Writing them here as well would put two "Status changed
    to Resolved" lines on one timeline and buzz one phone twice.
    """
    resolve = body(
        sql(), r"^create or replace function public\.supervisor_resolve_complaint"
    )
    assert "'status_changed'" not in resolve
    assert "complaint.resolved" not in resolve
    assert "status            = 'resolved'," in resolve
    assert "resolved_at       = coalesce(resolved_at, now())," in resolve


def test_the_file_refuses_to_apply_without_the_auto_close_trigger() -> None:
    """Because the paragraph above is a dependency and not a comment. A hosted
    database missing `complaints_on_resolved` would give this feature a Resolve
    button that tells the resident nothing, with nothing anywhere erroring."""
    text = statements(sql())
    verification = text[text.rindex("do $$") :]
    assert "complaints_on_resolved" in verification
    assert "from pg_trigger" in verification
    assert "raise exception" in verification


# ---------------------------------------------------------------------------
# Priority, notes
# ---------------------------------------------------------------------------


def test_priority_is_one_way_and_stops_at_high() -> None:
    """A supervisor who could lower a priority could quietly un-escalate
    something somebody else escalated -- a different decision, worth a different
    verb and a different audit line."""
    raise_priority = body(
        sql(), r"^create or replace function public\.raise_complaint_priority"
    )
    assert "when 'low'    then 'medium'" in raise_priority
    assert "when 'medium' then 'high'" in raise_priority
    assert "else null" in raise_priority
    assert "This complaint is already at the highest priority." in raise_priority
    assert "using errcode = 'HB409'" in raise_priority
    # Nothing anywhere walks it back down.
    assert "then 'low'" not in raise_priority


def test_priority_moves_the_live_jobs_with_the_complaint() -> None:
    """A job's urgency *is* its complaint's urgency -- `create_work_order` never
    took a priority argument for exactly that reason. A live job left at the old
    value is a dispatcher acting on the answer before the escalation."""
    raise_priority = body(
        sql(), r"^create or replace function public\.raise_complaint_priority"
    )
    assert "update public.work_orders" in raise_priority
    assert "status not in ('completed', 'cancelled', 'failed')" in raise_priority
    # And the SLA promise already made to the resident is not moved.
    assert "expected_resolution_at" not in raise_priority


def test_priority_writes_the_event_in_storage_vocabulary_and_notifies_nobody() -> None:
    """The payload carries `medium`/`high`; the sentence the resident reads says
    *Medium*/*High*, and `app/domain/vocabularies.py` is the seam. A `case` in SQL
    would be a second copy of that table in a language nobody would look in."""
    raise_priority = body(
        sql(), r"^create or replace function public\.raise_complaint_priority"
    )
    assert "'priority_changed'," in raise_priority
    assert "'from', coalesce(v_complaint.priority, 'low')," in raise_priority
    assert "'to',   v_to)" in raise_priority
    for wire_word in ("'High'", "'Medium'", "'Low'"):
        assert wire_word not in raise_priority, wire_word
    assert "notify_" not in raise_priority


def test_a_note_is_flagged_internal_and_bounded() -> None:
    """Ruling A5: the flag is on the payload rather than in a new event word --
    which would have cost the constraint rebuild a second time -- so the admin's
    resident-visible notes, which carry no flag, are untouched."""
    note = body(
        sql(), r"^create or replace function public\.add_complaint_note_internal"
    )
    assert "'note_added'," in note
    assert "jsonb_build_object('note', v_note, 'internal', true)" in note
    assert "length(v_note) > 2000" in note
    assert "using errcode = 'HB422'" in note
    # The author is named, because a staff timeline entry from nobody is a note
    # whose next question ("who says?") has no answer.
    assert "actor_label" in note
    assert "coalesce(p.full_name, 'The department')" in note


def test_every_complaint_verb_asks_the_same_guard_the_snapshot_asks() -> None:
    """One predicate, five callers. A verb that asked a different question from
    the dashboard it is pressed on would put a button on a card that refuses it.
    """
    text = statements(sql())
    for function in (
        "supervisor_resolve_complaint",
        "raise_complaint_priority",
        "add_complaint_note_internal",
        "open_complaint_thread",
        "supervisor_triage_snapshot",
    ):
        block = body(text, r"^create (or replace )?function public\." + function)
        assert "public.can_supervise_department(" in block, function
        assert "using errcode = 'HB403'" in block, function


def test_an_unrouted_complaint_is_a_conflict_and_not_a_refusal() -> None:
    """Phase one's call, ratified by the orchestrator and applied to all four
    verbs: there is no department to supervise, so `HB403` would tell a
    supervisor they lack a permission when what is missing is the routing."""
    text = statements(sql())
    for function in (
        "supervisor_resolve_complaint",
        "raise_complaint_priority",
        "add_complaint_note_internal",
        "open_complaint_thread",
    ):
        block = body(text, r"^create or replace function public\." + function)
        where = block.index("if v_complaint.department_id is null then")
        assert "using errcode = 'HB409'" in block[where : where + 220], function


# ---------------------------------------------------------------------------
# Force-assign (ruling A4)
# ---------------------------------------------------------------------------


def test_force_assign_is_the_engine_s_mechanics_with_a_guard() -> None:
    """Modelled on `dispatch_force_assign` and deliberately not a second
    mechanism: the same `is_forced` accepted row, the same two timeline events,
    the same notifications. What it adds is the guard the dispatcher does not
    need -- this caller is a person."""
    force = body(sql(), r"^create or replace function public\.force_assign_work_order")
    assert "public.can_supervise_department(v_order.department_id)" in force
    assert "using errcode = 'HB403'" in force
    assert "'accepted', true, false," in force  # is_forced, not auto-assigned
    assert "'job_assigned'," in force
    assert "'job_force_assigned'," in force
    assert "'job.force_assigned'," in force
    assert "status             = 'scheduled'," in force
    # And the engine's own version is left exactly where it is: neither
    # redeclared nor called. Calling it would hand the pick back to the ranking
    # this route exists to override.
    text = statements(sql())
    assert "function public.dispatch_force_assign" not in text
    assert "perform public.dispatch_force_assign" not in text


def test_force_assign_withdraws_the_previous_holder_and_refuses_a_closed_job() -> None:
    """The assign idiom: one holder at a time, withdrawn rather than deleted, and
    a terminal job refused. Forcing overrides the worker's consent, not the
    state machine."""
    force = body(sql(), r"^create or replace function public\.force_assign_work_order")
    assert "status in ('offered', 'accepted')" in force
    assert "set status = 'withdrawn', responded_at = now(), ended_at = now()" in force
    assert "if v_order.status in ('completed', 'cancelled', 'failed') then" in force
    assert "This job is no longer open." in force
    assert "That person is not on this department roster." in force
    assert "is already booked during that time." in force
    assert "for update;" in force


def test_force_assign_takes_the_frozen_two_arguments_and_defaults_the_rest() -> None:
    """The spec froze `force_assign_work_order(work_order_id,
    staff_assignment_id)`. The two slot parameters default to null, so that call
    is exactly this function -- and a supervisor who picked the person and the
    hour in one gesture does not need a second round trip to set the time."""
    force = body(sql(), r"^create or replace function public\.force_assign_work_order")
    assert "p_work_order_id      uuid," in force
    assert "p_staff_assignment_id uuid," in force
    assert "p_scheduled_start_at timestamptz default null," in force
    assert "p_scheduled_end_at   timestamptz default null" in force
    assert "returns uuid" in force


# ---------------------------------------------------------------------------
# The snapshot, re-bucketed (ruling A3)
# ---------------------------------------------------------------------------


def test_the_five_buckets_are_defined_here_and_only_here() -> None:
    """The frozen contract says the frontend renders the arrays as-is, which
    means these five predicates are the definitions and not a copy of them.

    *Committed* replaces phase one's *engaged* and the difference is one word:
    an `offered` assignment no longer counts, because a job nobody has accepted
    is an open request rather than assigned work.
    """
    snap = body(sql(), r"^create function public\.supervisor_triage_snapshot")
    assert "where cr.status = 'open' and cr.taken_up_at is null" in snap
    assert "where cr.taken_up_at is not null" in snap
    assert snap.count("cr.live_work_order_count = 0") == 2
    assert "where not wr.committed" in snap
    assert "wr.status in ('draft', 'awaiting_resident', 'offered')" in snap
    assert "where wr.committed and wr.status <> 'in_progress'" in snap
    assert "where wr.status = 'in_progress'" in snap

    # `committed`: somebody said yes, or the job is booked. An open offer is
    # explicitly not enough -- the whole of ruling A3.
    assert "and a.status = 'accepted'" in snap
    assert "a.status in ('offered', 'accepted')" not in snap
    assert TERMINAL in snap


def test_the_two_complaint_sections_exclude_any_live_work_order() -> None:
    """"Furthest stage wins": a complaint with a job appears once, as that job,
    in whichever of sections 3-5 it has reached. Phase one excluded only
    *engaged* work, which put an unaccepted job's complaint in section 2 and its
    work order nowhere."""
    snap = body(sql(), r"^create function public\.supervisor_triage_snapshot")
    assert "has_engaged_work" not in snap
    assert "as live_work_order_count" in snap


def test_the_two_names_are_two_facts() -> None:
    """`assigneeName` is the person who accepted; `offeredToName` is the person
    who has been asked. One field carrying both would make a section-3 card read
    "Ravi is coming" about a job Ravi has not answered."""
    snap = body(sql(), r"^create function public\.supervisor_triage_snapshot")
    accepted = snap.index("as assignee_name")
    offered = snap.index("as offered_to_name")
    assert "and woa.status = 'accepted'" in snap[:accepted]
    assert "and woa.status = 'offered'" in snap[accepted:offered]


def test_the_snapshot_is_replaced_wholesale_and_still_writes_nothing() -> None:
    """Dropped and recreated rather than replaced, because it is a different
    answer to the same question and the old one should not be reachable by a
    caller who missed the change. It remains a read: `stable`, and no write verb
    anywhere in it."""
    text = statements(sql())
    assert "drop function if exists public.supervisor_triage_snapshot(uuid);" in text
    snap = body(text, r"^create function public\.supervisor_triage_snapshot")
    assert "\nstable\n" in snap
    for forbidden in ("insert into", "update public.", "delete from", "notify_"):
        assert forbidden not in snap, forbidden
    # A dropped function takes its ACL with it.
    assert (
        "grant execute on function public.supervisor_triage_snapshot(uuid)"
        " to authenticated;"
        in text
    )


def test_every_section_is_newest_first_and_translates_no_vocabulary() -> None:
    """One ordering, five times. The urgent stack is the frontend's own pinning
    and is deliberately not sorted for here."""
    snap = body(sql(), r"^create function public\.supervisor_triage_snapshot")
    assert snap.count("jsonb_agg(to_jsonb(sec) order by sec.created_at desc)") == 5
    assert "priority desc" not in snap
    for wire_word in ("'High'", "'Medium'", "'Low'", "'Pending'", "'In Progress'"):
        assert wire_word not in snap, wire_word


def test_the_python_wire_model_agrees_with_the_rpc() -> None:
    """The half-landed change this catches: the SQL ships and the service reads a
    key the function does not emit, which is a silently empty dashboard section
    rather than an error."""
    from app.domain.supervisor_triage_schemas import (
        TriageComplaint,
        TriageSnapshot,
        TriageWorkOrder,
    )

    snap = body(sql(), r"^create function public\.supervisor_triage_snapshot")
    for section in SECTIONS:
        assert f"'{section}'," in snap, section
    assert set(SECTIONS) <= set(TriageSnapshot.model_fields)

    for field in TriageComplaint.model_fields:
        assert field in snap, f"TriageComplaint.{field} is not projected"
    for field in TriageWorkOrder.model_fields:
        if field in {"complaint_id"}:  # `w.complaint_id`, not aliased
            continue
        assert field in snap, f"TriageWorkOrder.{field} is not projected"


# ---------------------------------------------------------------------------
# What the file may not do
# ---------------------------------------------------------------------------


def test_the_only_ddl_is_what_this_file_declares_it_makes() -> None:
    """Four `drop`s, each named, and nothing else destructive.

    The snapshot is dropped because it is being replaced by a different answer;
    the two policies and the trigger are dropped because `create policy` and
    `create trigger` have no `or replace`. Everything else -- a table, a column, a
    view, an index, a row -- is out of bounds.
    """
    text = statements(sql()).lower()

    alters = re.findall(
        r"alter table public\.(\w+)\s+(add column|drop constraint|add constraint)",
        text,
    )
    assert alters == [
        ("dm_threads", "add column"),
        ("dm_threads", "drop constraint"),
        ("dm_threads", "add constraint"),
        ("dm_threads", "add constraint"),
        ("complaint_events", "drop constraint"),
        ("complaint_events", "add constraint"),
    ], alters

    assert text.count("drop function") == 1
    assert "drop function if exists public.supervisor_triage_snapshot(uuid)" in text
    assert text.count("drop policy") == 2
    assert text.count("drop trigger") == 1
    assert text.count("create policy") == 2
    assert text.count("create trigger") == 1

    for forbidden in (
        "drop table",
        "drop column",
        "drop view",
        "drop index",
        "drop type",
        "truncate",
        "delete from",
        "alter column",
        "set not null",
    ):
        assert forbidden not in text, forbidden


def test_every_sqlstate_it_raises_is_one_the_api_can_map() -> None:
    """A SQLSTATE `pg_errors` has never heard of surfaces as a 500 with a generic
    message -- the one failure mode a supervisor cannot act on, because the
    sentence the RPC wrote never reaches them."""
    raised = set(re.findall(r"errcode = '(HB[A-Z0-9]{3})'", sql()))
    assert raised == {"HB403", "HB404", "HB409", "HB422"}
    assert raised <= set(pg_errors._CUSTOM)
    standard = set(re.findall(r"errcode = '(\d[A-Z0-9]{4})'", sql()))
    assert standard <= set(pg_errors._STANDARD), standard


def test_it_verifies_itself_in_the_same_transaction() -> None:
    """`20260822090000` 2's shape: a file that claims to have added something
    fails rather than reporting success. The two `prosrc` probes are the ones
    that matter most -- a `create or replace` that lost the department clause
    from `post_dm_message`, or an older snapshot winning, are both failures with
    no symptom."""
    text = statements(sql())
    verification = text[text.rindex("do $$") :]

    assert "raise exception" in verification
    assert "from pg_proc" in verification
    for probe in (
        "open_requests",
        "offered_to_name",
        "can_supervise_complaint",
        "dm_threads_one_per_complaint",
        "complaints_on_resolved",
    ):
        assert probe in verification, probe
    # It reports, and it writes nothing.
    assert "raise notice" in verification
    assert "update public." not in verification
    assert "insert into" not in verification


def test_every_new_function_is_granted_to_somebody() -> None:
    """A definer function nobody may execute is a feature that fails with 42501
    at the first press. The trigger function is the deliberate exception: it runs
    as the trigger's owner and has no business being callable."""
    text = statements(sql())
    declared = set(
        re.findall(r"^create (?:or replace )?function public\.(\w+)", text, re.M)
    )
    granted = set(re.findall(r"grant execute on function public\.(\w+)", text))
    assert declared - granted == {"lock_complaint_threads"}, declared - granted
    assert "revoke all on function public.lock_complaint_threads()" in text
