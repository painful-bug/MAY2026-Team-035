"""Regression checks for the membership-centred database contract.

They complement, rather than replace, applying the migrations to Supabase.
"""

from pathlib import Path

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"


def _migration(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_baseline_contains_core_tenant_tables() -> None:
    sql = _migration("0001_baseline.sql")
    for table in (
        "communities",
        "community_memberships",
        "community_admin_terms",
        "unit_residencies",
        "resident_invites",
        "access_requests",
        "visitor_requests",
        "complaints",
        "work_orders",
        "amenity_bookings",
        "invoices",
        "payments",
    ):
        assert f"public.{table}" in sql


def test_baseline_preserves_key_invariants() -> None:
    sql = _migration("0001_baseline.sql")
    assert "community_admin_one_active" in sql
    assert "residencies_active_member_unit" in sql
    assert "exclude using gist" in sql


def test_baseline_uses_membership_scoped_workflows() -> None:
    sql = _migration("0001_baseline.sql")
    assert "community_memberships" in sql
    assert "claim_email_invitation" in sql
    assert "create_founder_community" in sql
    assert "enable row level security" in sql


def test_registration_baseline_has_search_and_atomic_request_workflows() -> None:
    sql = _migration("0001_baseline.sql")
    for fragment in (
        "applicant_profile_id uuid not null",
        "access_requests_one_pending_per_profile_community",
        "search_joinable_communities",
        "approve_access_request",
        "reject_access_request",
        "access_requests_applicant_read",
        "communities_active_name_trgm",
        "community_admin_terms",
    ):
        assert fragment in sql
