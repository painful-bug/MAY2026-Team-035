"""Executable contracts for the two forward-only professional-flow migrations.

These checks complement the local-Supabase CI job; they do not pretend a SQL
parser is a running Postgres database.
"""

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
SERVICE = MIGRATIONS / "20260811162409_service_professional_onboarding.sql"
TELEMETRY = MIGRATIONS / "20260811163408_service_signup_funnel_telemetry.sql"


def test_new_migrations_parse_as_postgresql() -> None:
    parse_sql(SERVICE.read_text())
    parse_sql(TELEMETRY.read_text())


def test_proximity_is_radius_bounded_stable_and_capped() -> None:
    sql = SERVICE.read_text().lower()
    assert sql.count("extensions.st_dwithin") >= 4
    assert "v_provider.service_radius_km * 1000" in sql
    assert "p.service_radius_km * 1000" in sql
    assert "st_dwithin(p.location, v_community.location, 500000)" in sql
    assert "least(coalesce(p_limit, 20), 20)" in sql
    assert "lower(c.name), c.id" in sql
    assert "lower(p.display_name), p.id" in sql
    assert "provider_location_required" not in sql  # typed through HBLOC mapping
    assert "using errcode = 'HBLOC'" in SERVICE.read_text()


def test_registration_and_hiring_remain_database_atomic() -> None:
    sql = SERVICE.read_text().lower()
    assert "create or replace function public.register_service_provider" in sql
    assert "perform public.set_service_provider_skills(p_skill_ids)" in sql
    assert "for update" in sql
    assert "insert into public.community_memberships" in sql
    assert "insert into public.staff_assignments" in sql
    assert "a professional account cannot mix worker and security memberships" in sql
    assert "public.can_hire_for_department" in sql
    assert "not exists (select 1 from manager_recipients)" in sql
    assert "array['admin', 'manager']" not in sql


def test_definer_functions_have_explicit_execution_grants() -> None:
    sql = SERVICE.read_text().lower()
    public_rpcs = {
        (
            "register_service_provider(text, text, text, numeric, numeric, "
            "numeric, uuid[])"
        ),
        "set_my_community_location(uuid, numeric, numeric)",
        "search_serviceable_communities(text, integer, integer)",
        "search_hireable_service_providers(uuid, text, integer, integer)",
        "apply_to_department(uuid, text)",
        "invite_service_provider(uuid, uuid, text, text, text, text)",
        "decide_service_application(uuid, text, text, text, text, text)",
    }
    for signature in public_rpcs:
        assert f"revoke all on function public.{signature} from public, anon" in sql
        assert f"grant execute on function public.{signature} to authenticated" in sql
    for signature in (
        "hiring_department_managers(uuid)",
        "professional_membership_role(text)",
        "enforce_professional_membership_mode()",
        "notify_hiring_deciders(uuid, text, jsonb)",
    ):
        assert (
            f"revoke all on function public.{signature} "
            "from public, anon, authenticated"
        ) in sql


def test_funnel_table_is_narrow_allowlisted_and_retained_for_30_days() -> None:
    sql = TELEMETRY.read_text().lower()
    table = re.search(
        r"create table public\.service_signup_funnel_events \((.*?)\);",
        sql,
        re.DOTALL,
    )
    assert table
    columns = table.group(1)
    assert "visitor_id uuid" in columns
    assert "event_name text" in columns
    assert "occurred_at timestamptz" in columns
    prohibited_columns = (
        "email",
        "profile_id",
        "latitude",
        "longitude",
        "payload",
        "user_agent",
        "ip",
    )
    for prohibited in prohibited_columns:
        assert prohibited not in columns
    for event in (
        "cta_impression",
        "cta_clicked",
        "auth_completed",
        "provider_profile_completed",
        "first_application_submitted",
    ):
        assert event in columns
    assert "primary key (visitor_id, event_name)" in columns
    assert "interval '30 days'" in sql
    assert "create extension if not exists pg_cron" in sql
    assert "cron.schedule(" in sql
