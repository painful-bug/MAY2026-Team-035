"""Static contracts for the forward-only Complaint Engine v2 repair."""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
REPAIR = MIGRATIONS / "20260823120000_complaint_engine_v2_repairs.sql"
LATEST_PREDECESSOR = MIGRATIONS / "20260820150000_admin_raised_complaints.sql"


def sql() -> str:
    return REPAIR.read_text(encoding="utf-8")


def function_body(name: str, arguments: str) -> str:
    source = sql()
    match = re.search(
        rf"create or replace function public\.{name}\(\s*{arguments}\s*\)"
        rf".*?as \$\$(.*?)\$\$;",
        source,
        re.DOTALL,
    )
    assert match, f"{name}({arguments}) is not defined by the repair"
    return match.group(1)


def test_repair_is_forward_only_and_parses_as_postgresql() -> None:
    assert REPAIR.name > LATEST_PREDECESSOR.name
    parse_sql(sql())


def test_manual_window_priority_matches_the_smallint_queue_contract() -> None:
    body = function_body("sync_dispatch_tasks", "")
    assert "(case when new.priority = 'high' then 2 else 0 end)::smallint" in body


def test_projector_resolves_each_trigger_row_shape_before_field_access() -> None:
    body = function_body("project_complaint_from_jobs", "")
    assert "if tg_table_name = 'work_orders' then" in body
    assert "elsif tg_table_name = 'work_order_assignments' then" in body
    assert "coalesce(new.complaint_id" not in body


def test_decline_override_is_internal_and_normal_dispatch_stays_strict() -> None:
    source = sql()
    override = function_body(
        "dispatch_candidates",
        r"p_work_order_id uuid,\s*p_limit integer,\s*p_include_declined boolean",
    )
    strict = function_body(
        "dispatch_candidates",
        r"p_work_order_id uuid,\s*p_limit integer default 5",
    )

    assert "p_include_declined" in override
    assert "said_no.status = 'declined'" in override
    assert "dispatch_candidates(p_work_order_id, p_limit, false)" in strict
    assert (
        "revoke all on function public.dispatch_candidates(uuid, integer, boolean)"
        in source
    )
    assert not re.search(
        r"grant execute on function public\.dispatch_candidates"
        r"\(uuid, integer, boolean\) to authenticated",
        source,
    )


def test_supervisor_picker_can_show_declined_workers_as_excluded() -> None:
    body = function_body(
        "work_order_candidates",
        r"p_work_order_id uuid,\s*p_include_excluded boolean default false",
    )
    assert "p_include_excluded" in body
    assert "exists (" in body
    assert "from excluded_staff" in body


def test_force_assignment_bypasses_the_supervisor_rpc_but_keeps_eligibility() -> None:
    body = function_body("dispatch_force_assign", r"p_work_order_id uuid")
    assert "dispatch_candidates(p_work_order_id, 100, true)" in body
    assert "work_order_candidates(" not in body
    assert "departure_bars_work" not in body  # enforced by dispatch_candidates
    assert "worker_unavailability" not in body  # enforced by dispatch_candidates


def test_worker_notification_and_postgrest_cache_use_current_main_behavior() -> None:
    source = sql()
    force_body = function_body("dispatch_force_assign", r"p_work_order_id uuid")
    assert "'/worker?job='" in force_body
    assert "'/worker/jobs?job='" not in force_body
    assert "notify pgrst, 'reload schema';" in source


def test_repaired_execution_privileges_are_explicit() -> None:
    source = sql()
    assert (
        "revoke all on function public.dispatch_force_assign(uuid)\n"
        "  from public, anon, authenticated;"
    ) in source
    assert (
        "grant execute on function public.dispatch_force_assign(uuid) to service_role;"
        in source
    )
    assert (
        "grant execute on function public.work_order_candidates(uuid, boolean)\n"
        "  to authenticated;"
    ) in source
