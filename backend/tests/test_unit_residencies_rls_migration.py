from pathlib import Path

from pglast import parse_sql


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20260811192511_fix_unit_residencies_rls_recursion.sql"
)


def test_unit_residencies_policy_does_not_query_itself() -> None:
    sql = MIGRATION.read_text()
    parse_sql(sql)
    policy = sql.split("create policy unit_residencies_read", 1)[1]

    assert "public.is_current_unit_resident(unit_id)" in policy
    assert "from public.unit_residencies" not in policy
    assert "revoke all on function public.is_current_unit_resident(uuid) from public, anon" in sql
    assert "grant execute on function public.is_current_unit_resident(uuid) to authenticated" in sql
