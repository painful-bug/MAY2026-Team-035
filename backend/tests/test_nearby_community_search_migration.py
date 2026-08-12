from pathlib import Path

from pglast import parse_sql


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20260812181443_search_nearby_communities.sql"
)


def test_nearby_search_keeps_nearby_communities_without_open_matching_work() -> None:
    sql = MIGRATION.read_text()
    parse_sql(sql)
    lowered = sql.lower()
    assert "left join matching_departments" in lowered
    assert "jsonb_agg" in lowered
    assert "filter (where md.department_id is not null)" in lowered
