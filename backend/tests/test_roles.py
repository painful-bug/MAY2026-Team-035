"""Unit tests for the RBAC hierarchy."""

from __future__ import annotations

from app.domain.roles import Role, parse_role, role_satisfies, satisfies_any


def test_admin_satisfies_resident() -> None:
    assert role_satisfies(Role.ADMIN, Role.RESIDENT) is True


def test_admin_satisfies_admin() -> None:
    assert role_satisfies(Role.ADMIN, Role.ADMIN) is True


def test_resident_does_not_satisfy_admin() -> None:
    assert role_satisfies(Role.RESIDENT, Role.ADMIN) is False


def test_staff_roles_are_independent() -> None:
    assert role_satisfies(Role.SECURITY, Role.RESIDENT) is False
    assert role_satisfies(Role.WORKER, Role.SECURITY) is False
    assert role_satisfies(Role.MANAGER, Role.ADMIN) is False


def test_satisfies_any() -> None:
    assert satisfies_any(Role.ADMIN, (Role.MANAGER, Role.RESIDENT)) is True
    assert satisfies_any(Role.SECURITY, (Role.MANAGER, Role.WORKER)) is False


def test_parse_role_is_case_insensitive_and_safe() -> None:
    assert parse_role("admin") is Role.ADMIN
    assert parse_role("ADMIN") is Role.ADMIN
    assert parse_role("technician") is Role.WORKER
    assert parse_role("serviceman") is Role.WORKER
    assert parse_role("nope") is None
    assert parse_role(None) is None
    assert parse_role("") is None
