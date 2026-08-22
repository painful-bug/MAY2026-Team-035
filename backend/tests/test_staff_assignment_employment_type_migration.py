"""Regression contract for the service-hiring employment type."""

from pathlib import Path

from pglast import parse_sql


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20260817144725_repair_staff_assignment_employment_type.sql"
)


def test_hiring_employment_type_remains_valid_for_the_hiring_rpc() -> None:
    sql = MIGRATION.read_text()
    parse_sql(sql)
    assert "staff_assignments_employment_type_check" in sql
    assert "employment_type in ('internal', 'vendor', 'staff')" in sql
