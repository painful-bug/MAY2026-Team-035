"""Regression checks for the membership-centred database contract.

They complement, rather than replace, applying the migrations to Supabase.
"""

from pathlib import Path

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"


def _migration(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_domain_migration_contains_core_tenant_tables() -> None:
    sql = _migration("0004_community_domain.sql")
    for table in (
        "communities",
        "community_memberships",
        "community_admin_terms",
        "unit_residencies",
        "resident_invites",
        "access_requests",
        "visitor_access_requests",
        "complaints",
        "work_orders",
        "amenity_booking_occurrences",
        "invoices",
        "payments",
    ):
        assert f"public.{table}" in sql


def test_domain_migration_preserves_key_invariants() -> None:
    sql = _migration("0004_community_domain.sql")
    assert "community_admin_terms_one_active_admin" in sql
    assert "unit_residencies_one_active_primary_contact" in sql
    assert "amenity_booking_occurrences_no_approved_overlap" in sql


def test_rls_migration_uses_membership_scoped_workflows() -> None:
    sql = _migration("0005_tenant_rls_and_workflows.sql")
    assert "current_user_has_community_role" in sql
    assert "claim_resident_invite" in sql
    assert "approve_access_request" in sql
    assert "transfer_community_admin" in sql
