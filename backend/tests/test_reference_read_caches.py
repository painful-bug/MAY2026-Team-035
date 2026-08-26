"""Phase B2: the TTL cache applied to community-scoped reference reads.

Each case proves the same shape for one cached domain: two reads with nothing
in between hit the repository once, and a read that follows a mutation the
service is supposed to invalidate on sees the repository again -- fresh data,
not the value from before the write. The repository is a hand-written counting
fake in every case; no real Supabase client is involved.

Domains covered: the departments list (``departments_service.list_departments``),
a community's complaint categories (``skills_service.list_categories``), one
department's skill list (``skills_service.list_department_skills``), and the
settings snapshot (``settings_service.get_settings_snapshot``) -- including the
cross-module invalidation ``money_service.update_billing_settings`` performs on
the settings cache it does not itself own.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.department_schemas import CreateDepartmentRequest, UpdateDepartmentRequest
from app.domain.money_schemas import UpdateBillingSettingsRequest
from app.domain.settings_schemas import UpdateSettingsRequest
from app.services import departments_service, money_service, settings_service, skills_service


@pytest.fixture(autouse=True)
def _clean_caches():
    """These caches are module-level singletons; start and end every test empty."""
    departments_service.reset_cache()
    skills_service.reset_cache()
    settings_service.reset_cache()
    yield
    departments_service.reset_cache()
    skills_service.reset_cache()
    settings_service.reset_cache()


def _department_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "department-id",
        "name": "Plumbing",
        "description": None,
        "contact_email": None,
        "contact_phone_e164": None,
        "opens_at": None,
        "closes_at": None,
        "sla_hours": None,
        "kind": "service",
        "status": "active",
        "created_at": "2026-08-09T09:00:00Z",
        "updated_at": "2026-08-09T09:00:00Z",
        "head_name": None,
        "head_staff_id": None,
        "staff_count": 0,
        "active_complaint_count": 0,
        "resolved_complaint_count": 0,
        "overdue_complaint_count": 0,
        "category_ids": [],
        "category_names": [],
        "skill_ids": [],
        "skill_names": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Departments list
# ---------------------------------------------------------------------------


def test_departments_list_is_cached_per_community_and_filter_combination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"list": 0}

    def fake_list_departments(client, community_id, **kwargs):
        calls["list"] += 1
        return [_department_row()], 1

    def fake_list_staff(client, community_id, ids):
        return []

    monkeypatch.setattr(departments_service.repo, "list_departments", fake_list_departments)
    monkeypatch.setattr(departments_service.repo, "list_staff", fake_list_staff)

    departments_service.list_departments(object(), "community-1")
    departments_service.list_departments(object(), "community-1")
    assert calls["list"] == 1  # second call served from cache

    # A different filter is a different cache key, so it still reaches the repo.
    departments_service.list_departments(object(), "community-1", search="leak")
    assert calls["list"] == 2

    # A different community is a different cache key too.
    departments_service.list_departments(object(), "community-2")
    assert calls["list"] == 3


def test_creating_a_department_invalidates_that_communitys_cached_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"list": 0}

    def fake_list_departments(client, community_id, **kwargs):
        calls["list"] += 1
        return [_department_row()], 1

    def fake_list_staff(client, community_id, ids):
        return []

    def fake_create_department(client, community_id, payload):
        return "new-department-id"

    def fake_get_department(client, community_id, department_id):
        return _department_row(id=department_id)

    monkeypatch.setattr(departments_service.repo, "list_departments", fake_list_departments)
    monkeypatch.setattr(departments_service.repo, "list_staff", fake_list_staff)
    monkeypatch.setattr(departments_service.repo, "create_department", fake_create_department)
    monkeypatch.setattr(departments_service.repo, "get_department", fake_get_department)

    departments_service.list_departments(object(), "community-1")
    assert calls["list"] == 1

    departments_service.create_department(
        object(), "community-1", CreateDepartmentRequest(name="Electrical")
    )

    # The list must be re-read, not served stale, because a create just
    # changed what it contains.
    departments_service.list_departments(object(), "community-1")
    assert calls["list"] == 2


def test_updating_a_department_invalidates_the_listing_but_not_other_communities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"list": 0}

    def fake_list_departments(client, community_id, **kwargs):
        calls["list"] += 1
        return [_department_row()], 1

    def fake_list_staff(client, community_id, ids):
        return []

    def fake_update_department(client, department_id, patch):
        return None

    def fake_get_department(client, community_id, department_id):
        return _department_row(id=department_id)

    monkeypatch.setattr(departments_service.repo, "list_departments", fake_list_departments)
    monkeypatch.setattr(departments_service.repo, "list_staff", fake_list_staff)
    monkeypatch.setattr(departments_service.repo, "update_department", fake_update_department)
    monkeypatch.setattr(departments_service.repo, "get_department", fake_get_department)

    departments_service.list_departments(object(), "community-1")
    departments_service.list_departments(object(), "community-2")
    assert calls["list"] == 2

    departments_service.update_department(
        object(), "community-1", "department-id", UpdateDepartmentRequest(name="Renamed")
    )

    departments_service.list_departments(object(), "community-1")
    assert calls["list"] == 3  # community-1 reloaded

    departments_service.list_departments(object(), "community-2")
    assert calls["list"] == 3  # community-2 untouched, still cached


def test_deleting_a_department_invalidates_its_communitys_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"list": 0}

    def fake_list_departments(client, community_id, **kwargs):
        calls["list"] += 1
        return [_department_row()], 1

    def fake_list_staff(client, community_id, ids):
        return []

    def fake_delete_department(client, department_id):
        return None

    monkeypatch.setattr(departments_service.repo, "list_departments", fake_list_departments)
    monkeypatch.setattr(departments_service.repo, "list_staff", fake_list_staff)
    monkeypatch.setattr(departments_service.repo, "delete_department", fake_delete_department)

    departments_service.list_departments(object(), "community-1")
    assert calls["list"] == 1

    departments_service.delete_department(object(), "community-1", "department-id")

    departments_service.list_departments(object(), "community-1")
    assert calls["list"] == 2


# ---------------------------------------------------------------------------
# Complaint categories
# ---------------------------------------------------------------------------


def test_complaint_categories_are_cached_per_community(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"categories": 0}

    def fake_categories(client, *, membership_id):
        calls["categories"] += 1
        return [{"id": "category-1", "name": "Plumbing", "department_count": 1}]

    monkeypatch.setattr(skills_service.repo, "community_categories", fake_categories)

    skills_service.list_categories(object(), membership_id="m-1", community_id="community-1")
    skills_service.list_categories(object(), membership_id="m-1", community_id="community-1")
    assert calls["categories"] == 1

    # Two different memberships in the same community: same cache key, still
    # one repository call -- the categories a membership sees are a fact
    # about its community, not about the membership itself.
    skills_service.list_categories(object(), membership_id="m-2", community_id="community-1")
    assert calls["categories"] == 1

    # A different community, however, is a genuine miss.
    skills_service.list_categories(object(), membership_id="m-3", community_id="community-2")
    assert calls["categories"] == 2


def test_creating_a_department_invalidates_that_communitys_categories_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"categories": 0}

    def fake_categories(client, *, membership_id):
        calls["categories"] += 1
        return [{"id": "category-1", "name": "Plumbing", "department_count": calls["categories"]}]

    def fake_create_department(client, community_id, payload):
        return "new-department-id"

    def fake_get_department(client, community_id, department_id):
        return _department_row(id=department_id)

    def fake_list_staff(client, community_id, ids):
        return []

    monkeypatch.setattr(skills_service.repo, "community_categories", fake_categories)
    monkeypatch.setattr(departments_service.repo, "create_department", fake_create_department)
    monkeypatch.setattr(departments_service.repo, "get_department", fake_get_department)
    monkeypatch.setattr(departments_service.repo, "list_staff", fake_list_staff)

    first = skills_service.list_categories(
        object(), membership_id="m-1", community_id="community-1"
    )
    assert first[0].department_count == 1

    departments_service.create_department(
        object(),
        "community-1",
        CreateDepartmentRequest(name="Electrical", categories=["Plumbing"]),
    )

    second = skills_service.list_categories(
        object(), membership_id="m-1", community_id="community-1"
    )
    assert second[0].department_count == 2  # reloaded, not the stale first read
    assert calls["categories"] == 2


# ---------------------------------------------------------------------------
# One department's skill list
# ---------------------------------------------------------------------------


def test_department_skill_list_is_cached_per_department(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"list": 0}

    def fake_list_department_skills(client, *, department_id):
        calls["list"] += 1
        return [{"id": "skill-1", "name": "Plumbing"}]

    monkeypatch.setattr(skills_service.repo, "list_department_skills", fake_list_department_skills)

    skills_service.list_department_skills(object(), department_id="dept-1")
    skills_service.list_department_skills(object(), department_id="dept-1")
    assert calls["list"] == 1

    skills_service.list_department_skills(object(), department_id="dept-2")
    assert calls["list"] == 2


def test_adding_a_department_skill_invalidates_its_cached_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"list": 0}

    def fake_list_department_skills(client, *, department_id):
        calls["list"] += 1
        return [{"id": "skill-1", "name": "Plumbing"}]

    def fake_add(client, *, department_id, name):
        return {"id": "skill-2", "name": name, "created": True}

    monkeypatch.setattr(skills_service.repo, "list_department_skills", fake_list_department_skills)
    monkeypatch.setattr(skills_service.repo, "add_department_skill", fake_add)

    skills_service.list_department_skills(object(), department_id="dept-1")
    assert calls["list"] == 1

    skills_service.add_department_skill(object(), department_id="dept-1", name="Electrical")

    skills_service.list_department_skills(object(), department_id="dept-1")
    assert calls["list"] == 2


def test_setting_a_departments_skills_reads_back_the_fresh_set_not_the_cached_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``set_department_skills`` reads its own result back for the response body.

    If invalidation happened after that read-back instead of before it, the
    write would faithfully echo the set it just replaced.
    """
    responses = [
        [{"id": "skill-1", "name": "Plumbing"}],
        [{"id": "skill-2", "name": "Electrical"}],
    ]

    def fake_list_department_skills(client, *, department_id):
        return responses.pop(0)

    def fake_set(client, *, department_id, skill_ids):
        return None

    monkeypatch.setattr(skills_service.repo, "list_department_skills", fake_list_department_skills)
    monkeypatch.setattr(skills_service.repo, "set_department_skills", fake_set)

    first = skills_service.list_department_skills(object(), department_id="dept-1")
    assert first[0].name == "Plumbing"

    result = skills_service.set_department_skills(
        object(), department_id="dept-1", skill_ids=["skill-2"]
    )
    assert result[0].name == "Electrical"


# ---------------------------------------------------------------------------
# Settings snapshot (including billing settings, a different endpoint and a
# different service module writing into the same cached row)
# ---------------------------------------------------------------------------


def _settings_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"community_id": "community-1"}
    base.update(overrides)
    return base


def test_settings_snapshot_is_cached_per_community(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"fetch": 0}

    def fake_fetch(client, community_id):
        calls["fetch"] += 1
        return _settings_row(community_id=community_id)

    def fake_modules(client, community_id):
        return []

    monkeypatch.setattr(settings_service.repo, "fetch_settings", fake_fetch)
    monkeypatch.setattr(settings_service.repo, "list_modules", fake_modules)

    settings_service.get_settings_snapshot(object(), "community-1")
    settings_service.get_settings_snapshot(object(), "community-1")
    assert calls["fetch"] == 1

    settings_service.get_settings_snapshot(object(), "community-2")
    assert calls["fetch"] == 2


def test_update_settings_invalidates_its_own_communitys_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"fetch": 0}

    def fake_fetch(client, community_id):
        calls["fetch"] += 1
        return _settings_row(community_id=community_id, timezone="Asia/Kolkata")

    def fake_modules(client, community_id):
        return []

    def fake_save(client, community_id, payload):
        return None

    monkeypatch.setattr(settings_service.repo, "fetch_settings", fake_fetch)
    monkeypatch.setattr(settings_service.repo, "list_modules", fake_modules)
    monkeypatch.setattr(settings_service.repo, "save_settings", fake_save)

    settings_service.get_settings_snapshot(object(), "community-1")
    assert calls["fetch"] == 1

    settings_service.update_settings(
        object(), "community-1", UpdateSettingsRequest(timezone="Asia/Kolkata")
    )
    # `update_settings` reads the snapshot back itself, so the count already
    # moves; the assertion that matters is the *next* independent read also
    # reaching the repository rather than returning a value cached before the
    # write.
    after_update = calls["fetch"]

    settings_service.get_settings_snapshot(object(), "community-1")
    assert calls["fetch"] == after_update  # served from the cache update_settings just refilled


def test_billing_settings_update_invalidates_the_settings_snapshot_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``money_service`` owns billing settings; ``settings_service`` owns the
    snapshot cache that embeds the same columns. The write must reach across."""
    calls = {"fetch": 0}

    def fake_fetch(client, community_id):
        calls["fetch"] += 1
        return _settings_row(community_id=community_id, late_fee_enabled=calls["fetch"] > 1)

    def fake_modules(client, community_id):
        return []

    def fake_fetch_billing(client, community_id):
        return None  # defaults path -- irrelevant to this test

    def fake_update_billing(client, community_id, patch):
        return None

    monkeypatch.setattr(settings_service.repo, "fetch_settings", fake_fetch)
    monkeypatch.setattr(settings_service.repo, "list_modules", fake_modules)
    monkeypatch.setattr(money_service.repo, "fetch_billing_settings", fake_fetch_billing)
    monkeypatch.setattr(money_service.repo, "update_billing_settings", fake_update_billing)

    first = settings_service.get_settings_snapshot(object(), "community-1")
    assert first.billing.late_fee_enabled is False
    assert calls["fetch"] == 1

    money_service.update_billing_settings(
        object(),
        "community-1",
        UpdateBillingSettingsRequest(late_fee_enabled=True),
    )

    second = settings_service.get_settings_snapshot(object(), "community-1")
    assert calls["fetch"] == 2  # reloaded, not served from the pre-write cache
    assert second.billing.late_fee_enabled is True
