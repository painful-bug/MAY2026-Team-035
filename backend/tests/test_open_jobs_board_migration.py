"""Static contracts for the open-jobs board migration.

The rulings of 2026-08-23 (`docs/COMPLAINT_ENGINE_HANDOFF.md` §22) and the
orchestrator's adjudications D1-D7 (`docs/plans/OPEN_JOBS_BOARD_SPEC.md`) are
promises about SQL that no fixture-backed API test can see. Same idiom as
``test_complaint_engine_v2_repair_migration.py``: parse the file, then pin the
clauses the spec froze -- so a later edit that quietly relaxes "open", forks
the trade rule, or narrows the projection trigger back down fails here first.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
BOARD = MIGRATIONS / "20260823170000_open_jobs_board.sql"
HOSTED_HIGH_WATER = MIGRATIONS / "20260823160000_visitor_requests_sse.sql"


def sql() -> str:
    return BOARD.read_text(encoding="utf-8")


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


def test_board_sorts_after_the_hosted_high_water_mark_and_parses() -> None:
    assert BOARD.name > HOSTED_HIGH_WATER.name
    parse_sql(sql())


def test_the_board_read_is_definer_keyed_on_the_caller_alone() -> None:
    """RLS correctly hides unheld jobs from workers, so the board must be
    SECURITY DEFINER with identity from auth.uid() and no arguments a caller
    could widen."""
    source = sql()
    match = re.search(
        r"create or replace function public\.worker_open_jobs\(\)(.*?)as \$\$",
        source,
        re.DOTALL,
    )
    assert match, "worker_open_jobs() is not defined"
    head = match.group(1)
    assert "security definer" in head
    assert "set search_path = public" in head
    body = function_body("worker_open_jobs", "")
    assert "auth.uid()" in body


def test_open_means_uncommitted_and_unpromised_in_both_functions() -> None:
    """D1, stated twice on purpose: status alone cannot define open, because
    create_work_order writes `offered` with no assignment rows at all."""
    board = function_body("worker_open_jobs", "")
    claim = function_body("claim_open_work_order", r"p_work_order_id uuid")

    assert "w.status in ('draft', 'offered')" in board
    assert "a.status in ('offered', 'accepted')" in board
    assert "v_order.status not in ('draft', 'offered')" in claim
    assert "a.status in ('offered', 'accepted')" in claim
    assert "'Somebody has already taken this job.'" in claim


def test_the_trade_rule_is_the_engines_own_clause_in_both_functions() -> None:
    """D2: the short-circuit for provider-less roster rows is deliberate --
    it is dispatch_candidates' rule, and a different one here would fork
    eligibility."""
    board = function_body("worker_open_jobs", "")
    claim = function_body("claim_open_work_order", r"p_work_order_id uuid")

    assert "w.skill_id is null" in board
    assert "sa.service_provider_id is null" in board
    assert "service_provider_skills" in board
    assert "v_order.skill_id is null" in claim
    assert "v_staff.service_provider_id is null" in claim
    assert "service_provider_skills" in claim


def test_exclusion_filters_the_board_and_guards_the_claim() -> None:
    """D7 on the read, D2 on the write: the list and the click are seconds
    apart, so the claim re-checks what the board already hid."""
    board = function_body("worker_open_jobs", "")
    claim = function_body("claim_open_work_order", r"p_work_order_id uuid")

    assert "complaint_excluded_staff" in board
    assert "complaint_excluded_staff" in claim


def test_the_claim_locks_first_and_skips_slot_checks_without_a_slot() -> None:
    """The race is settled on the `for update` line, as it is on accept; and
    ruling C3 means the overlap refusal runs only when the job has a slot --
    none of the slot-dependent checks can run without one."""
    claim = function_body("claim_open_work_order", r"p_work_order_id uuid")

    assert "for update" in claim
    assert "v_order.scheduled_start_at is not null and exists" in claim
    assert "'You are already booked during that time.'" in claim
    # And no slot-null refusal: the accept path's HB409 for a missing slot
    # must NOT have been copied over.
    assert "no scheduled time" not in claim


def test_the_claimed_row_takes_the_accept_paths_exact_shape() -> None:
    """D3: accepted, not forced, not auto-assigned, slot copied from the job
    (which may be null), the job moved to `scheduled` -- the shape
    force_assign_work_order already established for scheduled+null-slot."""
    claim = function_body("claim_open_work_order", r"p_work_order_id uuid")

    assert "'accepted', false, false" in claim
    assert "set status = 'scheduled', updated_at = now()" in claim
    assert re.search(r"set status = 'withdrawn'.*status = 'offered'", claim, re.DOTALL)


def test_no_new_event_word_the_payload_carries_the_distinction() -> None:
    """D4: a new complaint-event word costs a constraint drop-and-recreate
    (runbook §19 rule); `claimed: true` inside `job_assigned` does not."""
    claim = function_body("claim_open_work_order", r"p_work_order_id uuid")

    assert "'job_assigned'" in claim
    assert "'claimed', true" in claim
    # The header may *name* the constraint; nothing may touch it.
    assert "drop constraint" not in sql()
    assert "add constraint" not in sql()


def test_the_supervisor_hears_claimed_and_not_their_own_echo() -> None:
    """D6: the resident's notification is accept's own; the supervisor's is
    the new `work_order.claimed` kind with a supplied title, skipped when the
    claimer IS that supervisor."""
    claim = function_body("claim_open_work_order", r"p_work_order_id uuid")

    assert "'work_order.assigned'" in claim
    assert "'work_order.claimed'" in claim
    assert "took up" in claim
    assert "is distinct from v_actor" in claim


def test_the_projection_trigger_treats_an_accepted_insert_as_acknowledged() -> None:
    """D5: on the offer path the complaint moved open -> acknowledged when the
    offer was inserted; a claim inserts `accepted` directly, and without this
    widening the complaint would sit at `open` with a committed job."""
    source = sql()
    body = function_body("project_complaint_from_jobs", "")

    assert "new.status in ('offered', 'accepted')" in body
    # The row-shape resolution from 20260823120000 must survive the rewrite.
    assert "tg_table_name = 'work_order_assignments'" in body
    assert "coalesce(new.complaint_id" not in body
    # Drop-before-recreate, and the widened WHEN on the recreation.
    assert (
        "drop trigger if exists work_order_assignments_project_complaint" in source
    )
    assert re.search(
        r"create trigger work_order_assignments_project_complaint\s+"
        r"after insert on public\.work_order_assignments\s+"
        r"for each row when \(new\.status in \('offered', 'accepted'\)\)",
        source,
    )


def test_execution_privileges_are_explicit_and_the_cache_is_reloaded() -> None:
    source = sql()

    assert (
        "revoke all on function public.worker_open_jobs()\n"
        "  from public, anon, authenticated;"
    ) in source
    assert "grant execute on function public.worker_open_jobs() to authenticated;" in source
    assert (
        "revoke all on function public.claim_open_work_order(uuid)\n"
        "  from public, anon, authenticated;"
    ) in source
    assert (
        "grant execute on function public.claim_open_work_order(uuid) to authenticated;"
        in source
    )
    assert "notify pgrst, 'reload schema';" in source
