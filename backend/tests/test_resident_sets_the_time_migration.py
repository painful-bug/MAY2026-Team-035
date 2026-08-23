"""Static contracts for the resident-scheduling migration.

The product rulings of 2026-08-23 (`docs/COMPLAINT_ENGINE_HANDOFF.md` §23, F1-F3)
and the orchestrator's adjudications G1-G11
(`docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`) are promises about SQL that no
fixture-backed API test can see -- this file is hand-applied and there is no
database in the suite. Same idiom as `test_open_jobs_board_migration.py`: parse
the file, then pin the clauses the spec froze.

**The pins that carry the most weight are the negative ones.** Three of the
decisions here are decisions *not* to add something -- no new work-order status,
no new complaint-event word, no change to the board predicate -- and each of
them is one careless edit away from a constraint rebuild on a hosted database.
The other three are the redefinitions: `sync_dispatch_tasks` and
`fire_dispatch_task` are re-issued whole, and a `create or replace` that quietly
loses an arm is a timer that stops firing with nothing in the apply output to
say so.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260823180000_resident_sets_the_time.sql"

#: The file this one had to sort after when it was written. Named rather than
#: derived from the directory (ruling G9): forward-only is a claim about ONE
#: predecessor, and "after everything that exists" expires the day the next
#: migration lands.
LATEST_PREDECESSOR = MIGRATIONS / "20260823170000_open_jobs_board.sql"

#: The closed vocabularies this file must not touch. Each costs a
#: drop-and-recreate on a constrained column of a live table, and the design
#: routes around all three (G2, and the no-new-word rule `20260823170000` D4
#: set).
UNTOUCHABLE_CONSTRAINTS = (
    "work_orders_status_check",
    "complaint_events_type_check",
)


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped.

    The header argues every decision the file makes and names most of the
    identifiers the assertions below forbid, so no check may read it."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def function_body(name: str, arguments: str) -> str:
    source = sql()
    match = re.search(
        rf"create or replace function public\.{name}\({arguments}\)"
        rf".*?as \$\$(.*?)\$\$;",
        source,
        re.DOTALL,
    )
    assert match, f"{name}({arguments}) is not defined by the migration"
    return match.group(1)


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_it_sorts_after_the_file_it_had_to_follow_and_parses() -> None:
    """Forward-only, and named: this file must land after the open-jobs board,
    whose `project_complaint_from_jobs` and board predicate it reads and does
    not replace."""
    assert LATEST_PREDECESSOR.exists(), LATEST_PREDECESSOR.name
    assert MIGRATION.name > LATEST_PREDECESSOR.name, LATEST_PREDECESSOR.name
    parse_sql(sql())


def test_it_is_the_last_word_on_every_function_it_redefines() -> None:
    """Not "it is last in the directory". The property is being last *among the
    files that declare each function*, which is what decides which body the
    database ends up holding."""
    for function in (
        "create_work_order",
        "dispatch_resident_timeout",
        "sync_dispatch_tasks",
        "fire_dispatch_task",
        "supervisor_triage_snapshot",
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
        assert declares[-1] == MIGRATION.name, function


# ---------------------------------------------------------------------------
# The three vocabularies it routes around, and the one it widens
# ---------------------------------------------------------------------------


def test_the_only_constraint_it_touches_is_the_dispatch_task_kind() -> None:
    """G2 and the no-new-word rule, stated as an absence. `work_orders` gets no
    new status and `complaint_events` no new type -- both are closed lists on
    live tables, and both refusals are what the payload discriminators exist
    for."""
    text = statements(sql())

    for constraint in UNTOUCHABLE_CONSTRAINTS:
        assert constraint not in text, constraint

    dropped = re.findall(r"drop constraint if exists (\w+)", text)
    added = re.findall(r"add constraint (\w+)", text)
    assert dropped == ["dispatch_tasks_kind_check"], dropped
    assert added == ["dispatch_tasks_kind_check"], added


def test_the_widened_kind_list_keeps_every_word_it_already_had() -> None:
    """Widening only. The old list is derived from `20260813104000`'s own text
    rather than reviewed by eye, so a word dropped in the copy fails here."""
    timers = (MIGRATIONS / "20260813104000_timers_v2.sql").read_text(encoding="utf-8")
    before = set(re.findall(r"'(\w+)'", timers[timers.index("kind in (") :].split(")")[0]))
    after = set(
        re.findall(
            r"'(\w+)'",
            statements(sql()).split("add constraint dispatch_tasks_kind_check check (kind in (")[1]
            .split(")")[0],
        )
    )

    assert before, "the old kind list could not be derived"
    assert before < after, sorted(before - after)
    assert after - before == {"facility_auto_assign"}, sorted(after - before)


def test_no_new_status_word_reaches_the_work_order_table() -> None:
    """Pick-mode is `awaiting_resident` with a NULL slot and nothing else. A
    status this file invented would be an insert the CHECK refuses at apply
    time on any database with rows."""
    text = statements(sql())
    written = set(re.findall(r"set status\s*=\s*'(\w+)'", text))
    written |= set(re.findall(r"status\s*=\s*'(\w+)',", text))

    assert written <= {
        "draft",
        "awaiting_resident",
        "offered",
        "scheduled",
        "accepted",
        "withdrawn",
    }, sorted(written)


def test_the_board_predicate_is_not_touched() -> None:
    """G8: `awaiting_resident` was already off the board, and drafts stay
    claimable -- including a facility draft inside the courtesy gate, where the
    claim simply wins and the task no-ops."""
    text = statements(sql())
    assert "worker_open_jobs" not in text
    assert "claim_open_work_order" not in text


# ---------------------------------------------------------------------------
# G4 -- one eligibility rule, asked about a hypothetical hour
# ---------------------------------------------------------------------------


def test_the_slot_finder_never_probes_by_writing_a_trial_hour() -> None:
    """Six triggers fire on `work_orders` writes, so a finder that stored a
    candidate hour to ask about it would fire all six per probe. The whole
    refactor exists to make that unnecessary."""
    finder = function_body(
        "find_first_available_slot", r"\s*p_work_order_id uuid,\s*p_from\s+timestamptz\s*"
    )

    assert "dispatch_candidates_at" in finder
    assert "update public.work_orders" not in finder
    assert "insert into" not in finder


def test_the_finder_uses_the_frozen_duration_step_and_horizon() -> None:
    """G10: hardcoded in the engine's style, like the 24-hour deadline. Two-hour
    visits, top-of-hour candidate starts, fourteen days of looking."""
    finder = function_body(
        "find_first_available_slot", r"\s*p_work_order_id uuid,\s*p_from\s+timestamptz\s*"
    )

    assert "interval '2 hours'" in finder
    assert "interval '14 days'" in finder
    assert "date_trunc('hour'" in finder
    assert "+ interval '1 hour'" in finder


def test_the_three_argument_candidates_became_a_delegate_not_a_fork() -> None:
    """One eligibility rule, one ordering, one set of grants. A second copy
    would be a second answer to "who may take this job", and the one that
    drifts is always the one nobody is testing."""
    delegate = function_body(
        "dispatch_candidates",
        r"\s*p_work_order_id uuid,\s*p_limit integer,\s*p_include_declined boolean\s*",
    )
    at = function_body(
        "dispatch_candidates_at",
        r"\s*p_work_order_id\s+uuid,\s*p_start\s+timestamptz,\s*p_end\s+timestamptz,"
        r"\s*p_limit\s+integer,\s*p_include_declined boolean\s*",
    )

    assert "dispatch_candidates_at(" in delegate
    assert "w.scheduled_start_at" in delegate
    assert "w.scheduled_end_at" in delegate
    # The delegate re-implements nothing: no eligibility clause survives in it.
    for clause in ("worker_availability_rules", "departure_bars_work", "tstzrange"):
        assert clause not in delegate, clause

    # And the parameterised body is the live one, clause for clause.
    for clause in (
        "departure_bars_work(sa.id, j.slot_start)",
        "worker_unavailability",
        "worker_availability_rules",
        "service_provider_skills",
        "said_no.status = 'declined'",
    ):
        assert clause in at, clause
    # The frozen ordering. A different one is a different worker picked.
    assert (
        "order by\n    candidate.adjacent desc,\n    candidate.load asc,\n"
        "    candidate.km asc nulls last,\n    candidate.sa_display_name" in at
    )
    # Null-slot behaviour is preserved: the guard moved onto the parameters.
    assert "p_start is not null" in at
    assert "p_end is not null" in at

    # The two-argument wrapper `20260823120000` declared is left alone.
    assert not re.search(
        r"create or replace function public\.dispatch_candidates\(\s*"
        r"p_work_order_id uuid,\s*p_limit integer default",
        sql(),
    )


# ---------------------------------------------------------------------------
# G1 -- the raise, forked on the slot
# ---------------------------------------------------------------------------


def test_a_slotless_resident_raise_becomes_a_request_to_pick() -> None:
    """Ruling F1. A resident-subject job is `awaiting_resident` either way, and
    the slot is the discriminator; the deadline arms in both modes, because
    silence is answered in both."""
    body = function_body("create_work_order", r"[^)]*")

    assert "v_status   := 'awaiting_resident';" in body
    assert "v_deadline := now() + interval '24 hours';" in body
    assert (
        "v_mode     := case when p_scheduled_start_at is null "
        "then 'pick' else 'approve' end;" in body
    )
    assert "'work_order.schedule_requested'" in body
    assert "'mode', v_mode" in body
    assert "'Pick a time for this visit'" in body


def test_a_slotless_facility_raise_stays_a_draft_and_enqueues_nothing_here() -> None:
    """The trigger arms the task from the status alone -- the rule `0037` §2 set
    and every handler since has kept. A `create_work_order` that enqueued by
    hand would arm it twice on any path that also changes the status."""
    body = function_body("create_work_order", r"[^)]*")

    assert "v_status := 'draft';" in body
    assert "enqueue_dispatch_task" not in body
    assert "facility_auto_assign" not in body


# ---------------------------------------------------------------------------
# G3 -- the resident's write
# ---------------------------------------------------------------------------


def test_the_residents_pick_checks_ownership_mode_and_the_hour_in_that_order() -> None:
    """The guard order is the contract: a stranger is refused before they learn
    anything about the job, and the mode refusal comes before the hour is even
    looked at."""
    body = function_body(
        "resident_set_work_order_schedule",
        r"\s*p_work_order_id uuid,\s*p_start\s+timestamptz,\s*p_end\s+timestamptz\s*",
    )

    positions = [
        body.index("is_own_membership"),
        body.index("There is nothing to schedule on this complaint right now."),
        body.index("The association proposed this visit''s time"),
        body.index("it must end after it starts."),
    ]
    assert positions == sorted(positions), positions

    assert "for update" in body
    assert "errcode = 'HB403'" in body
    assert "errcode = 'HB404'" in body
    assert body.count("errcode = 'HB409'") == 4


def test_the_residents_pick_moves_the_job_to_the_open_pile() -> None:
    """"Only when they set it does the job reach the open pile" (F1). `offered`
    is that pile: it arms the existing `manual_window` machinery through the
    trigger and puts the job on the open-jobs board."""
    body = function_body(
        "resident_set_work_order_schedule",
        r"\s*p_work_order_id uuid,\s*p_start\s+timestamptz,\s*p_end\s+timestamptz\s*",
    )

    assert "status               = 'offered'" in body
    assert "resident_deadline_at = null" in body
    assert "'job_scheduled'" in body
    assert "'resident_set', true" in body
    assert "'work_order.resident_scheduled'" in body


def test_pick_mode_has_no_decline() -> None:
    """Ruling F3. There was never a proposal, so there is nothing to refuse;
    the decline stays on `respond_to_work_order_schedule`, which this file does
    not touch."""
    text = statements(sql())

    # Named in a `comment on`, which is prose; neither is redeclared or called.
    for untouched in ("respond_to_work_order_schedule", "reschedule_work_order"):
        assert f"function public.{untouched}(" not in text, untouched
        assert f"public.{untouched}(p_" not in text, untouched
    # A worker's `declined` assignment is a different noun and is read by the
    # eligibility rule; what may not exist is a resident's decline.
    assert "'job_declined'" not in text
    assert "work_order.resident_declined" not in text
    body = function_body(
        "resident_set_work_order_schedule",
        r"\s*p_work_order_id uuid,\s*p_start\s+timestamptz,\s*p_end\s+timestamptz\s*",
    )
    assert "'declined'" not in body
    assert "p_response" not in body


# ---------------------------------------------------------------------------
# G5 -- twenty-four hours of silence
# ---------------------------------------------------------------------------


def test_the_timeout_branches_on_the_slot_and_keeps_the_old_arm_intact() -> None:
    """Approve-mode is untouched: a proposed hour nobody answered still
    proceeds to `offered`, with the same event and the same notification."""
    body = function_body("dispatch_resident_timeout", r"p_work_order_id uuid")

    assert "if v_order.scheduled_start_at is not null then" in body
    assert "'Proceeding without a response.'" in body
    assert "'work_order.proceeding'" in body
    assert "status               = 'offered'" in body


def test_an_expired_pick_is_booked_and_assigned_without_a_new_event_word() -> None:
    """Ruling F2, and the no-new-word rule: `job_assigned` carries
    `auto_assigned: true`, exactly as the board's claim carries `claimed`."""
    body = function_body("dispatch_resident_timeout", r"p_work_order_id uuid")

    assert "find_first_available_slot(v_order.id, now())" in body
    assert "'accepted', false, true" in body
    assert "'job_assigned'" in body
    assert "'auto_assigned', true" in body
    assert "'work_order.assigned'" in body
    assert "'work_order.auto_assigned'" in body
    # Withdrawn, not deleted -- the sweep `0036` §5 and `0037` §5 both chose.
    assert re.search(r"set status = 'withdrawn'.*status = 'offered'", body, re.DOTALL)


def test_nobody_free_inside_the_horizon_returns_the_job_to_the_board() -> None:
    """A job stranded in `awaiting_resident` with a dead timer is invisible to
    everybody. `draft` is claimable (C3), and the supervisor is told rather than
    left to notice."""
    body = function_body("dispatch_resident_timeout", r"p_work_order_id uuid")
    tail = body[body.index("find_first_available_slot") :]

    assert "status               = 'draft'" in tail
    assert "'work_order.no_candidates'" in tail


# ---------------------------------------------------------------------------
# G6 -- the facility job books itself, behind a courtesy gate
# ---------------------------------------------------------------------------


def test_the_facility_handler_bails_on_anything_a_human_already_moved() -> None:
    """Idempotent, because a task may fire more than once (`0037`'s lease) and
    because a board claim can win the race -- which is the outcome this task
    exists to make unnecessary, not one to fight."""
    body = function_body("dispatch_facility_auto_assign", r"p_work_order_id uuid")

    assert "for update" in body
    assert (
        "if v_order.status <> 'draft' or v_order.subject_kind <> 'facility' then"
        in body
    )
    assert "a.status in ('offered', 'accepted')" in body


def test_the_courtesy_gate_is_urgent_resident_jobs_with_nobody_on_them() -> None:
    """"Only after all urgent resident complaints in the department have been
    allotted" (F1). Allotted is asked the way the board asks it: a live offer or
    an acceptance."""
    body = function_body("dispatch_facility_auto_assign", r"p_work_order_id uuid")
    gate = body[body.index("urgent") :]

    assert "urgent.subject_kind = 'resident'" in gate
    assert "urgent.priority = 'high'" in gate
    assert "urgent.status in ('draft', 'awaiting_resident', 'offered')" in gate
    # Re-checked hourly, so a gated job is never stranded behind a backlog.
    assert "'facility_auto_assign', now() + interval '1 hour'" in gate


def test_the_trigger_arms_the_new_task_and_keeps_every_arm_it_had() -> None:
    """`sync_dispatch_tasks` is re-issued whole, so every arm has to be
    re-proved. The final `else` still cancels timers on a status this function
    does not recognise -- `draft` simply stopped being one of those."""
    body = function_body("sync_dispatch_tasks", "")

    assert "'resident_timeout'" in body
    assert "(case when new.priority = 'high' then 2 else 0 end)::smallint" in body
    assert "'failed_visit_escalation'" in body
    assert body.count("close_dispatch_tasks(new.id, null)") == 3
    assert (
        "if tg_op = 'INSERT' and new.subject_kind = 'facility' then" in body
    )
    assert "'facility_auto_assign', now()" in body
    # The unknown-status arm survives, last.
    assert body.rindex("elsif tg_op = 'INSERT'") > body.index("new.status = 'draft'")


def test_the_handler_table_gains_one_arm_and_loses_none() -> None:
    """`fire_dispatch_task`'s `else` silently swallows a kind nothing handles,
    so a missing arm is a task that completes with an error nobody reads."""
    body = function_body("fire_dispatch_task", r"p_task_id uuid")

    for kind in (
        "ping",
        "auto_assign",
        "resident_timeout",
        "failed_visit_escalation",
        "departure_removal",
        "manual_window",
        "auto_close_warning",
        "auto_close",
        "facility_auto_assign",
    ):
        assert f"when '{kind}' then" in body, kind
    assert "No handler for kind: " in body
    # The new arm completes its own row first: the handler's hourly re-arm would
    # otherwise be folded into this task by `dispatch_tasks_one_open_per_kind`
    # and then completed by the update at the bottom.
    facility = body[body.index("when 'facility_auto_assign' then") :]
    assert facility.index("update public.dispatch_tasks set completed_at") < facility.index(
        "dispatch_facility_auto_assign("
    )


# ---------------------------------------------------------------------------
# G7 -- the sixth triage bucket
# ---------------------------------------------------------------------------


def test_the_snapshot_gains_a_bucket_and_narrows_open_requests() -> None:
    """A job waiting on a resident is not an open request: nothing on it is the
    supervisor's to move. The narrowing is the other half of the change and is
    the part that would go unnoticed -- the new section would fill and the old
    one would keep double-counting."""
    body = function_body("supervisor_triage_snapshot", r"p_department_id uuid")

    assert "wr.status = 'awaiting_resident'" in body
    assert "wr.status in ('draft', 'offered')" in body
    assert "'awaiting_resident',  v_awaiting" in body
    assert "'open_requests',      v_open" in body
    # Six sections, one ordering, still no vocabulary translated here.
    assert body.count("jsonb_agg(to_jsonb(sec) order by sec.created_at desc)") == 6
    for wire_word in ("'High'", "'Medium'", "'Low'", "'In Progress'"):
        assert wire_word not in body, wire_word


def test_the_python_wire_model_agrees_with_the_new_snapshot() -> None:
    """The half-landed change this catches: the SQL ships and the service reads
    a key the function does not emit, which is a silently empty dashboard
    section rather than an error."""
    from app.domain.supervisor_triage_schemas import (
        TriageComplaint,
        TriageSnapshot,
        TriageWorkOrder,
    )

    body = function_body("supervisor_triage_snapshot", r"p_department_id uuid")
    sections = (
        "new_complaints",
        "taken_up",
        "awaiting_resident",
        "open_requests",
        "assigned_pending",
        "in_progress",
    )
    for section in sections:
        assert f"'{section}'," in body, section
    assert set(sections) <= set(TriageSnapshot.model_fields)

    for field in TriageComplaint.model_fields:
        assert field in body, f"TriageComplaint.{field} is not projected"
    for field in TriageWorkOrder.model_fields:
        if field in {"complaint_id"}:  # `w.complaint_id`, not aliased
            continue
        assert field in body, f"TriageWorkOrder.{field} is not projected"


# ---------------------------------------------------------------------------
# Grants, the cache, and the in-transaction proof
# ---------------------------------------------------------------------------


def test_the_dispatch_internals_stay_shut_and_the_resident_verb_opens() -> None:
    """The internals expose roster data and bypass request-level role checks, so
    only definer callers reach them -- `0037` §8's posture. The one function a
    person calls resolves the caller from `auth.uid()` and refuses a stranger
    itself, which is why `authenticated` is the right audience for it."""
    source = sql()

    for internal in (
        "public.dispatch_candidates_at(\n  uuid, timestamptz, timestamptz, integer, boolean)",
        "public.find_first_available_slot(uuid, timestamptz)",
        "public.dispatch_facility_auto_assign(uuid)",
    ):
        assert f"revoke all on function {internal}\n  from public, anon, authenticated;" in source, internal
        assert f"grant execute on function {internal} to authenticated" not in source, internal

    assert (
        "grant execute on function public.resident_set_work_order_schedule(\n"
        "  uuid, timestamptz, timestamptz) to authenticated;"
    ) in source
    assert (
        "grant execute on function public.fire_dispatch_task(uuid) to service_role;"
        in source
    )
    assert "notify pgrst, 'reload schema';" in source


def test_it_verifies_itself_in_the_same_transaction() -> None:
    """`20260822090000` §2's shape: a file that claims to have added something
    fails rather than reporting success. The redefinition probes matter most --
    an older body winning is a failure with no symptom."""
    text = statements(sql())
    verification = text[text.rindex("do $$") :]

    assert "raise exception" in verification
    for probe in (
        "dispatch_candidates_at",
        "find_first_available_slot",
        "resident_set_work_order_schedule",
        "dispatch_facility_auto_assign",
        "facility_auto_assign",
        "v_awaiting",
    ):
        assert probe in verification, probe
    assert "raise notice" in verification
    # It reports, and it writes nothing.
    assert "update public.work_orders" not in verification
    assert "insert into" not in verification


def test_every_sqlstate_it_raises_is_one_the_api_can_map() -> None:
    """A SQLSTATE `pg_errors` has never heard of surfaces as a 500 with a
    generic message -- the one failure mode a resident cannot act on, because
    the sentence the RPC wrote never reaches them."""
    from app.core import pg_errors

    raised = set(re.findall(r"errcode = '(HB[A-Z0-9]{3})'", sql()))
    assert raised == {"HB403", "HB404", "HB409"}
    assert raised <= set(pg_errors._CUSTOM)
    standard = set(re.findall(r"errcode = '(\d[A-Z0-9]{4})'", sql()))
    assert standard <= set(pg_errors._STANDARD), standard
