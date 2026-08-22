"""`20260822120000_supervisor_triage.sql` -- what a static reader can prove
about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a live
database. It adds the four facts the supervisor dashboard needs and the model
could not say: that a supervisor has *picked a complaint up*, when a worker
actually *started*, and that a job arrived by somebody else's removal rather than
by the reader's own hand.

The properties worth asserting without a database are these.

**Does it sort last, and does it stay out of the other files' way?** Five sibling
static-check files pin earlier migrations by name. This one redeclares two
functions on purpose and must redeclare nothing else.

**Are the two copies additive?** `start_work_order` (`0039`) and
`restamp_department_supervision` (`20260821200000`) are reproduced whole under
the house convention (`20260812113000` 1) to gain one stamp each. A copy that
quietly dropped the resident notification, an `HB404`, the successor lookup or
the `get diagnostics` would not error -- it would delete behaviour. So every
non-blank line of the owning file's version is required to still be present,
verbatim, which is the check that catches a copy made by retyping.

**Do the two new columns have exactly one writer each?** `taken_up_at` is
`take_up_complaint`'s and `supervision_inherited_at` is
`restamp_department_supervision`'s. A second writer for either is a dashboard
section that fills up for reasons nobody chose.

**Is the dead column still dead?** Ruling 1 of 2026-08-21: nothing new writes
`complaints.assigned_to_membership_id` or `assignee_label`. Take-up is triage
ownership and is exactly the change most likely to be mistaken for dispatch, so
the absence is asserted rather than argued.

**Is anything destructive?** Nothing here may drop a column, a function, a table
or a policy, and nothing may delete a row. The only DDL shapes are `add column if
not exists` and `create index if not exists`.

Whether Postgres accepts the bodies is a question only Postgres answers; `pglast`
parsing it -- the whole file, and then the snapshot query on its own, because a
function body is an opaque string to the outer parse -- is as close as this suite
gets. The rest is in `docs/plans/MIGRATION_APPLY_RUNBOOK.md` 18.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

from app.core import pg_errors

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
TRIAGE = MIGRATIONS / "20260822120000_supervisor_triage.sql"

#: The file that currently owns each object this one rewrites or leans on.
WORK_ORDERS = MIGRATIONS / "0036_work_orders.sql"        # can_supervise_department
WORKER_ACTIONS = MIGRATIONS / "0039_worker_actions.sql"  # start_work_order
ROUTING = MIGRATIONS / "20260812090300_complaint_department_routing.sql"
COUPLING = MIGRATIONS / "20260813102000_status_coupling.sql"
REPOOL = MIGRATIONS / "20260813103000_resident_cancel_repool.sql"
# restamp_department_supervision
CONTINUITY = MIGRATIONS / "20260821200000_departure_continuity.sql"
DRIFT = MIGRATIONS / "20260822090000_hosted_work_order_column_drift.sql"

#: What "live" means, everywhere in this file. `staff_open_commitment_count`
#: (`0043` 253) and `restamp_department_supervision` already spell it this way
#: and all three must agree, or a job counted as live by one is invisible to the
#: other.
TERMINAL = "w.status not in ('completed', 'cancelled', 'failed')"

#: The two columns this file adds to `work_orders`, and the one function each is
#: allowed to be written by.
STAMPS = {
    "started_at": "start_work_order",
    "supervision_inherited_at": "restamp_department_supervision",
}


def sql() -> str:
    return TRIAGE.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped.

    This file's header argues every decision it makes and names most of the
    identifiers the assertions below look for -- including
    `assigned_to_membership_id`, which it mentions only to say it does not write
    it. A check that read the prose would be asserting against the explanation
    and would pass on a file that did the opposite of what it said.
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
    check below says nothing about the 90-line query that produces all four
    dashboard sections. Lifted out and parsed on its own, minus the plpgsql
    ``into``, which is not SQL.
    """
    text = sql()
    start = text.index("  with complaint_rows as (")
    end = text.index("  into v_new, v_taken, v_pending, v_progress;")
    return text[start:end] + ";"


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_the_snapshot_query_parses_on_its_own() -> None:
    """The check the whole-file parse cannot make.

    Everything interesting in this file is inside a `$$ ... $$` body, which the
    outer parse reads as one opaque string -- so a syntax error in the query that
    fills the entire dashboard would sail past `test_the_migration_parses_as_postgresql`
    and surface in the SQL editor, on a live database, in front of the owner.
    """
    parse_sql(snapshot_query())


def test_it_sorts_after_every_file_whose_work_it_builds_on() -> None:
    """Filename order is apply order.

    `20260821200000` is the tightest: this file copies its
    `restamp_department_supervision` forward, and sorting before it would mean
    the version *without* the stamp is applied second and wins -- silently,
    because both files declare the same name. `20260822090000` matters for a
    different reason: until that file is applied nothing can insert a
    `work_orders` row at all, so a column added here would be a column on a table
    nobody can write.
    """
    for earlier in (WORK_ORDERS, WORKER_ACTIONS, ROUTING, COUPLING, REPOOL,
                    CONTINUITY, DRIFT):
        assert TRIAGE.name > earlier.name


def test_it_is_the_last_word_on_both_functions_it_copies() -> None:
    """Not "it is last in the directory" -- that property has expired four times
    in this directory already. The property is being last *among the files that
    declare this function*, which is what decides which body the database ends
    up holding.
    """
    for function in ("start_work_order", "restamp_department_supervision"):
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
        assert declares[-1] == TRIAGE.name, function


def test_it_redeclares_nothing_else_the_sibling_files_pin() -> None:
    """Two functions are copied forward and no others.

    Each name below is one a sibling static-check file guards, and each is one
    this file plausibly *could* have touched: the trigger that calls the re-stamp,
    the successor rule behind it, the status projection that gains a second writer
    for `acknowledged`, and the department queue whose read the snapshot
    generalises. Copying any of them forward to gain nothing would put this file
    in the way of the next person who needs to change one.
    """
    text = statements(sql())
    for owned in (
        "department_supervision_successor",
        "carry_department_supervision",
        "staff_supervised_work_order_count",
        "notify_complaint_staff",
        "notify_member",
        "department_staff_overview",
        "department_complaints",
        "create_work_order",
        "assign_work_order",
        "project_complaint_from_jobs",
        "can_supervise_department",
        "claim_staff_invitations",
        "remove_department_member",
        "membership_is_live",
    ):
        assert not re.search(
            r"^create (or replace )?(view|function) public\." + owned + r"\b",
            text,
            re.M,
        ), owned


def test_it_never_writes_the_dead_complaint_column() -> None:
    """Ruling 1 of 2026-08-21, restated by ruling 1 of 2026-08-22 because take-up
    is the change most easily mistaken for dispatch.

    `complaints.assigned_to_membership_id` has one writer (`update_complaint`,
    `0031`) and no reader anywhere. Take-up records who is *looking at* a
    complaint; who is going is a work-order assignment, and the whole design
    depends on not answering the second question by accident.
    """
    text = statements(sql())
    assert "assigned_to_membership_id" not in text
    assert "assignee_label" not in text


# ---------------------------------------------------------------------------
# Ruling 1: take-up
# ---------------------------------------------------------------------------


def test_take_up_is_the_only_writer_of_the_take_up_columns() -> None:
    """One writer, asserted as a count rather than promised in prose.

    A second writer -- a backfill, a trigger, a convenience `update` in the
    snapshot -- would fill the dashboard's second section for reasons nobody
    chose, and there is no error anywhere to notice it by.
    """
    text = statements(sql())
    writes = re.findall(r"taken_up_by_membership_id\s*=", text)
    # One in the `update`, one in the "already yours" comparison, and one in the
    # holder lookup -- the last two are reads.
    assert text.count("update public.complaints") == 1

    take_up = body(text, r"^create or replace function public\.take_up_complaint")
    assert "update public.complaints" in take_up
    assert "taken_up_by_membership_id = v_actor" in take_up
    assert "taken_up_at               = now()" in take_up
    assert writes, "nothing writes the take-up column at all"


def test_take_up_moves_the_status_only_from_open() -> None:
    """Ruling 2, and the half of it that is not the headline.

    `acknowledged` gains a second writer deliberately. What it must not gain is a
    path that walks a complaint *backwards*: one a worker has already started is
    `in_progress`, and a triage button is not a reason to un-start it.
    """
    take_up = body(sql(), r"^create or replace function public\.take_up_complaint")
    assert "case when status = 'open'" in take_up
    assert "then 'acknowledged'::public.complaint_status" in take_up
    assert "else status end" in take_up


def test_take_up_writes_the_timeline_and_notifies_nobody() -> None:
    """A passive field change under ARCHITECTURE.md's rule.

    The resident learns the same fact from the status their screen re-snapshots
    within a beat, so a notification would be a second telling of one thing. The
    timeline entry is not the same category: it is the record, and `0020`'s
    reader renders it.
    """
    take_up = body(sql(), r"^create or replace function public\.take_up_complaint")
    assert "insert into public.complaint_events" in take_up
    assert "'taken_up'," in take_up
    assert "notify_member" not in take_up
    assert "notify_complaint_staff" not in take_up
    assert "notify_community_roles" not in take_up
    assert "notify_department_leadership" not in take_up


def test_take_up_refuses_three_ways_and_is_idempotent_for_its_owner() -> None:
    """404 unknown, 403 not yours, 409 somebody else's -- and a second press by
    the same person is a no-op rather than the 409 a naive implementation gives
    it. A double-clicked button is not an error worth a message."""
    take_up = body(sql(), r"^create or replace function public\.take_up_complaint")

    assert "'No such complaint.' using errcode = 'HB404'" in take_up
    assert take_up.count("errcode = 'HB403'") == 2  # the guard and the null actor
    assert "public.can_supervise_department(v_complaint.department_id)" in take_up
    # The 409 names whoever holds it. "Already taken up" with no name sends a
    # supervisor to ask around an office.
    assert "has already taken this complaint up." in take_up
    assert "coalesce(p.full_name, 'Another supervisor')" in take_up
    # Yours already: return, not raise.
    assert "if v_complaint.taken_up_by_membership_id = v_actor then" in take_up
    assert "return;" in take_up
    # And the row is locked before any of it, so two supervisors racing produce
    # one winner and one named 409 rather than two stamps.
    assert "for update;" in take_up


def test_take_up_refuses_an_unrouted_complaint_as_a_conflict_not_a_refusal() -> None:
    """There is no department to supervise, so `HB403` would tell a supervisor
    they lack a permission when what is missing is the routing."""
    take_up = body(sql(), r"^create or replace function public\.take_up_complaint")
    where = take_up.index("if v_complaint.department_id is null then")
    assert "using errcode = 'HB409'" in take_up[where : where + 220]


# ---------------------------------------------------------------------------
# Rulings 3 and 4: the two copied bodies
# ---------------------------------------------------------------------------


def _additive(owner: Path, header: str) -> list[str]:
    """Lines of ``owner``'s version of a function missing from this file's copy."""
    applied = body(owner.read_text(encoding="utf-8"), header)
    copied = body(sql(), header)
    return [
        line
        for line in (raw.rstrip() for raw in applied.splitlines())
        if line.strip() and line not in copied
    ]


def test_the_start_copy_is_purely_additive() -> None:
    """The house convention, checked rather than promised.

    Every non-blank line of `0039`'s `start_work_order` has to still be present.
    The resident notification, both `HB404`s, the `HB409`, the already-started
    early return and the `job_started` event are all lines that can vanish
    without anything erroring -- and the last of them is what the resident's
    timeline is built from.

    This is also why the added assignment is written leading-comma style: the
    line `set status = 'in_progress', updated_at = now()` survives verbatim, so
    the copy is *provably* additive rather than additive-looking.
    """
    missing = _additive(
        WORKER_ACTIONS, r"^create or replace function public\.start_work_order"
    )
    assert not missing, f"the copy lost these lines from {WORKER_ACTIONS.name}: {missing}"


def test_the_restamp_copy_is_purely_additive() -> None:
    """The same check for `20260821200000`'s `restamp_department_supervision`.

    The successor lookup, the "nothing to move" pre-check, the department scope on
    both the check and the update, and `get diagnostics` are each load-bearing:
    losing the scope would hand a membership's work in *every* department to
    whichever one lost them first, and losing the diagnostics would make the
    last-supervisor notice claim zero jobs moved.
    """
    missing = _additive(
        CONTINUITY,
        r"^create or replace function public\.restamp_department_supervision",
    )
    assert not missing, f"the copy lost these lines from {CONTINUITY.name}: {missing}"


def test_neither_copy_changes_its_signature_or_return_type() -> None:
    """`create or replace` refuses a changed return type and would fail on the
    hosted database; a new defaulted parameter would create an overload rather
    than replace anything, which fails silently and is worse."""
    start = body(sql(), r"^create or replace function public\.start_work_order")
    assert "start_work_order(p_work_order_id uuid)" in start
    assert "returns void" in start

    restamp = body(
        sql(), r"^create or replace function public\.restamp_department_supervision"
    )
    assert "p_department_id  uuid," in restamp
    assert "p_from_membership uuid" in restamp
    assert "returns integer" in restamp


def test_each_stamp_has_exactly_one_writer() -> None:
    """`started_at` is the worker's Start and `supervision_inherited_at` is the
    re-stamp, and neither is written anywhere else in this file.

    A stamp with two writers is a dashboard badge that appears for two different
    reasons, one of which nobody documented.
    """
    # Everything before section 7, which quotes both assignments back as
    # `prosrc like` probes and would otherwise count as a second writer.
    text = statements(sql())
    text = text[: text.index("do $$")]
    for column, owner in STAMPS.items():
        writes = [
            match.start()
            for match in re.finditer(re.escape(column) + r"\s*=\s*(coalesce|now)", text)
        ]
        assert len(writes) == 1, f"{column} is written {len(writes)} times"
        owning = body(
            text, r"^create or replace function public\." + owner + r"\b"
        )
        assert column in owning, f"{column} is not written by {owner}"


def test_the_start_stamp_cannot_be_reset() -> None:
    """`coalesce(started_at, now())`, not `now()`.

    The already-`in_progress` early return means a second press cannot reach the
    statement today. It is written defensively anyway because the dashboard's
    elapsed time is measured from this column, and a future writer that reaches
    `in_progress` some other way should not be able to restart the clock.
    """
    start = body(sql(), r"^create or replace function public\.start_work_order")
    assert "started_at = coalesce(started_at, now())" in start
    assert re.search(r"started_at\s*=\s*now\(\)", start) is None


def test_the_inherited_stamp_marks_only_what_the_restamp_moves() -> None:
    """Same row, same statement, same scope. Marking rows the re-stamp did not
    move would badge work that arrived by somebody's own hand as inherited."""
    restamp = body(
        sql(), r"^create or replace function public\.restamp_department_supervision"
    )
    update = restamp[restamp.index("update public.work_orders w") :]
    assert "supervision_inherited_at = now()" in update
    assert "supervisor_membership_id = v_target" in update
    assert update.count(TERMINAL) == 1
    assert "w.department_id            = p_department_id" in update


# ---------------------------------------------------------------------------
# The snapshot
# ---------------------------------------------------------------------------


def test_the_snapshot_asks_the_same_guard_the_department_queue_asks() -> None:
    """`can_supervise_department`, and a refusal rather than an empty snapshot.

    An empty dashboard and a refused one look identical on a screen, and the
    difference is the whole content of the answer. The predicate is the one
    `department_complaints` (`20260813103000`) and `create_work_order` (`0036`)
    already ask, so the dashboard and the verbs on it agree about who may act.
    """
    snap = body(
        sql(), r"^create or replace function public\.supervisor_triage_snapshot"
    )
    assert "public.can_supervise_department(p_department_id)" in snap
    assert "using errcode = 'HB403'" in snap
    assert "using errcode = 'HB404'" in snap


def test_the_snapshot_writes_nothing() -> None:
    """It is a read and it decides nothing -- the claim `COMPLAINT_ENGINE_HANDOFF.md`
    18 makes on this engine's behalf. `stable` is the declaration of that, and the
    absence of every write verb is the proof."""
    snap = body(
        sql(), r"^create or replace function public\.supervisor_triage_snapshot"
    )
    assert "\nstable\n" in snap
    for forbidden in ("insert into", "update public.", "delete from", "notify_"):
        assert forbidden not in snap, forbidden


def test_the_four_buckets_are_defined_here_and_only_here() -> None:
    """The frozen contract says the frontend renders the arrays as-is.

    Which means these four predicates are the definitions, not a copy of them.
    Each is asserted by the shape that makes it wrong if it drifts: `new` is
    untouched work, `taken_up` is stamped work nobody is engaged on,
    `assigned_pending` is engaged work that has not started, `in_progress` is
    what the worker started.
    """
    snap = body(
        sql(), r"^create or replace function public\.supervisor_triage_snapshot"
    )
    assert "where cr.status = 'open' and cr.taken_up_at is null" in snap
    assert "where cr.taken_up_at is not null" in snap
    assert "and not cr.has_engaged_work" in snap
    assert "where wr.engaged and wr.status <> 'in_progress'" in snap
    assert "where wr.status = 'in_progress'" in snap

    # `engaged`: an open offer or acceptance, or a booked job.
    assert "a.status in ('offered', 'accepted')" in snap
    assert "w.status = 'scheduled'" in snap
    # Live, spelled the way every other file in this directory spells it.
    assert TERMINAL in snap


def test_every_section_is_newest_first() -> None:
    """One ordering, four times. The urgent stack is the frontend's own pinning
    and is deliberately not sorted for here -- a server that pre-pinned would be
    deciding a layout."""
    snap = body(
        sql(), r"^create or replace function public\.supervisor_triage_snapshot"
    )
    assert snap.count("jsonb_agg(to_jsonb(sec) order by sec.created_at desc)") == 4
    assert "priority desc" not in snap


def test_the_snapshot_never_translates_a_vocabulary() -> None:
    """`app/domain/vocabularies.py` is the one place this codebase maps a stored
    word to a rendered one. A `case` in SQL turning `high` into `High` would be a
    second copy of that table, free to disagree with it, in a language where
    nobody would think to look for it."""
    snap = body(
        sql(), r"^create or replace function public\.supervisor_triage_snapshot"
    )
    for wire_word in ("'High'", "'Medium'", "'Low'", "'Pending'", "'In Progress'"):
        assert wire_word not in snap, wire_word


def test_the_reroute_marker_is_derived_from_the_timeline_and_not_a_column() -> None:
    """`reroutedAt` is the newest `department_assigned` event naming *this*
    department as the destination.

    `raise_complaint` writes `raised` rather than `department_assigned`
    (`20260812090300` 3), so automatic routing at raise time is correctly not a
    reroute -- only an admin allotting, a manager moving, or an accepted transfer
    request is. A column would also have been wrong: a complaint can arrive here
    more than once, and the events already record every arrival.
    """
    snap = body(
        sql(), r"^create or replace function public\.supervisor_triage_snapshot"
    )
    assert "ev.event_type   = 'department_assigned'" in snap
    assert "ev.payload->>'to_department_id' = p_department_id::text" in snap
    assert "order by ev.created_at desc" in snap

    text = statements(sql())
    assert "rerouted_at" in text
    assert "add column if not exists rerouted_at" not in text


def test_the_snapshot_reads_the_two_new_stamps() -> None:
    """The columns exist for these two sections and would otherwise be write-only.

    `startedAt` is what makes "being worked right now" show for how long, and
    `inheritedAt` is the badge ruling 3 partially reversed `16`'s "no new column"
    to make possible.
    """
    snap = body(
        sql(), r"^create or replace function public\.supervisor_triage_snapshot"
    )
    assert "w.started_at," in snap
    assert "w.supervision_inherited_at              as inherited_at," in snap


# ---------------------------------------------------------------------------
# The columns, and what the file may not do
# ---------------------------------------------------------------------------


def test_the_four_columns_are_added_additively_and_nullable() -> None:
    """`add column if not exists`, which is what has always applied cleanly around
    the hosted tables' legacy columns (`20260820120000`, `20260822090000`).

    Nullable with no default, deliberately: `taken_up_at is null` **is** the
    answer to "is this untouched", and a default would make every row that
    predates this file claim a moment nobody lived through.
    """
    text = statements(sql())
    for column in (
        "taken_up_by_membership_id uuid",
        "taken_up_at timestamptz",
        "started_at               timestamptz",
        "supervision_inherited_at timestamptz",
    ):
        assert f"add column if not exists {column}" in text, column

    assert "references public.community_memberships(id) on delete set null" in text
    # No default and no NOT NULL on any of the four.
    columns_block = text[text.index("alter table public.complaints") : text.index(
        "comment on column"
    )]
    assert "not null" not in columns_block
    assert "default" not in columns_block


def test_nothing_is_destructive() -> None:
    """This file adds. It may not remove anything, and it has no view or trigger
    to drop and recreate -- so unlike its siblings, the count of `drop` statements
    it is allowed is zero."""
    text = statements(sql()).lower()

    for forbidden in (
        "drop table",
        "drop column",
        "drop function",
        "drop policy",
        "drop view",
        "drop trigger",
        "drop index",
        "truncate",
        "delete from",
        "create policy",
        "alter column",
    ):
        assert forbidden not in text, forbidden

    # Exactly two `alter table`s, both `add column if not exists`.
    assert text.count("alter table") == 2
    assert text.count("add column if not exists") == 4
    # One `update` statement per function that is supposed to have one, and no
    # others: take-up, the start stamp, the re-stamp.
    assert text.count("update public.") == 3


def test_every_sqlstate_it_raises_is_one_the_api_can_map() -> None:
    """A SQLSTATE `pg_errors` has never heard of surfaces as a 500 with a generic
    message -- which is the one failure mode a supervisor cannot act on, because
    the sentence the RPC wrote never reaches them."""
    raised = set(re.findall(r"errcode = '(HB[A-Z0-9]{3})'", sql()))
    assert raised == {"HB403", "HB404", "HB409"}
    assert raised <= set(pg_errors._CUSTOM)


def test_it_verifies_itself_in_the_same_transaction() -> None:
    """`20260822090000` 2's shape: a file that claims to have added something
    fails rather than reporting success.

    The two `prosrc` probes are the ones that matter most, because a
    `create or replace` losing its stamp is the failure with no symptom -- the
    dashboard section simply stays empty and nothing anywhere errors.
    """
    text = statements(sql())
    verification = text[text.index("do $$") :]

    assert "raise exception" in verification
    assert "information_schema.columns" in verification
    assert "from pg_proc" in verification
    for probe in (
        "started_at = coalesce(started_at, now())",
        "supervision_inherited_at",
    ):
        assert probe in verification, probe
    # It reports, and it writes nothing.
    assert "raise notice" in verification
    assert "update public." not in verification
    assert "insert into" not in verification


def current_snapshot_body() -> str:
    """`supervisor_triage_snapshot` as the **last** file to declare it writes it.

    This file declared it first; `20260822170000` dropped and recreated it with
    five sections (amendment 2, ruling A3). The DTOs describe whatever is
    actually applied last, so this reads the directory rather than this file --
    the same derivation `test_it_is_the_last_word_on_both_functions_it_copies`
    makes, for the same reason: a remembered list expires.
    """
    owners = sorted(
        path
        for path in MIGRATIONS.glob("*.sql")
        if re.search(
            r"^create (or replace )?function public\.supervisor_triage_snapshot\b",
            path.read_text(encoding="utf-8"),
            re.M,
        )
    )
    assert owners, "nothing declares supervisor_triage_snapshot at all"
    return body(
        owners[-1].read_text(encoding="utf-8"),
        r"^create (or replace )?function public\.supervisor_triage_snapshot",
    )


def test_the_python_wire_model_agrees_with_the_rpc() -> None:
    """The half-landed change this catches: the SQL ships and the service reads a
    key the function does not emit, which is a silently empty dashboard section
    rather than an error."""
    from app.domain.supervisor_triage_schemas import TriageComplaint, TriageWorkOrder

    snap = current_snapshot_body()
    for section in (
        "'department_id',",
        "'new_complaints',",
        "'taken_up',",
        "'assigned_pending',",
        "'in_progress',",
    ):
        assert section in snap, section

    # Every field the DTOs carry is a column the query projects. `id` is the one
    # exception worth naming: it is `c.id` / `w.id` rather than a labelled alias.
    for field in TriageComplaint.model_fields:
        assert field in snap, f"TriageComplaint.{field} is not projected"
    for field in TriageWorkOrder.model_fields:
        if field in {"complaint_id"}:  # `w.complaint_id`, not aliased
            continue
        assert field in snap, f"TriageWorkOrder.{field} is not projected"
