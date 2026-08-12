"""Department CRUD, which had no API-level test file until 0048.

That gap is why this module exists and it is worth naming: the admin
departments router has shipped nine operations since 0019 with coverage only of
``_staff_payload`` (``tests/test_department_mapping.py``) and two "is it in the
spec" assertions. Everything between the view and the wire -- which column
becomes which field, and what happens to the ones that are null -- was
unasserted.

The cases below are chosen for the seams where that has actually gone wrong.

``api_180`` guards the pairing rule (R23): the view returns names and ids
ordered the same way, and the wire carries both, so a screen can render a label
and send back an id without a lookup. Two arrays that stopped agreeing
positionally would be a bug no type checker sees.

``api_182`` is the one with history. ``department_overview`` matched
``rank = 'head'`` for the head lateral; ``0035`` migrated every such row to
``'manager'`` and forbade ``'head'``, so ``head_name`` was null for every
department in the API from ``0035`` until ``skills_and_categories`` fixed the
view -- and ``0035``'s own header claimed it had already made that fix. The test cannot
reach Postgres, so it does the half it can: pin that a head the view *does*
return survives the mapping, so the next time this breaks it breaks in SQL only
and the search for it starts in the right file.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import departments_service

DEPARTMENTS = "/api/v1/departments"
ONE = f"{DEPARTMENTS}/department-id"


def department_row(**overrides: Any) -> dict[str, Any]:
    """One ``department_overview`` row, as PostgREST would return it."""
    base: dict[str, Any] = {
        "id": "department-id",
        "name": "Plumbing",
        "description": "Taps, pipes and drains",
        "contact_email": "plumbing@example.com",
        "contact_phone_e164": "+919876543210",
        "opens_at": "09:00:00",
        "closes_at": "18:00:00",
        "sla_hours": 24,
        "kind": "service",
        "status": "active",
        "created_at": "2026-08-09T09:00:00Z",
        "updated_at": "2026-08-09T09:00:00Z",
        "head_name": "Ravi Kumar",
        "head_staff_id": "staff-id",
        "staff_count": 3,
        "active_complaint_count": 2,
        "resolved_complaint_count": 7,
        "overdue_complaint_count": 1,
        "category_ids": ["category-plumbing", "category-water"],
        "category_names": ["Plumbing", "Water supply"],
        "skill_ids": ["skill-plumbing"],
        "skill_names": ["Plumbing"],
    }
    base.update(overrides)
    return base


@pytest.fixture
def departments(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository and the tenancy lookup, recording every call."""
    captured: dict = {"rows": [department_row()], "staff": [], "calls": []}

    def fake_community(client: Any, user_id: str) -> str:
        return "community-id"

    def fake_list(client: Any, community_id: str, **kwargs: Any) -> tuple[list, int]:
        captured["listed"] = kwargs
        return captured["rows"], len(captured["rows"])

    def fake_get(client: Any, community_id: str, department_id: str) -> dict:
        captured["got"] = department_id
        return captured["rows"][0]

    def fake_staff(client: Any, community_id: str, ids: list[str]) -> list[dict]:
        return captured["staff"]

    def fake_create(client: Any, community_id: str, payload: dict) -> str:
        captured["calls"].append("create")
        captured["created"] = payload
        return "department-id"

    def fake_can_hire(client: Any, department_id: str) -> bool:
        captured["asked_can_hire"] = department_id
        return captured.get("can_hire", True)

    repo = departments_service.repo
    monkeypatch.setattr(repo, "can_hire", fake_can_hire)
    monkeypatch.setattr(
        departments_service.tenancy_repo, "get_caller_community_id", fake_community
    )
    monkeypatch.setattr(repo, "list_departments", fake_list)
    monkeypatch.setattr(repo, "get_department", fake_get)
    monkeypatch.setattr(repo, "list_staff", fake_staff)
    monkeypatch.setattr(repo, "create_department", fake_create)
    yield captured


def test_api_180_names_and_ids_arrive_paired_for_both_vocabularies(
    admin_api_client: TestClient, departments: dict
) -> None:
    """R23: every label the wire carries comes with the id that names it.

    The view orders both arrays the same way, so position `n` of `categories`
    and position `n` of `categoryIds` are the same thing. A screen renders the
    first and submits the second without a second request. `skills` and
    `skillIds` are the same rule applied to the vocabulary 0048 added -- and
    are asserted here so the new pair cannot quietly drift out of order while
    the old one holds.
    """
    response = admin_api_client.get(DEPARTMENTS)
    assert response.status_code == 200
    row = response.json()["items"][0]
    assert row["categories"] == ["Plumbing", "Water supply"]
    assert row["categoryIds"] == ["category-plumbing", "category-water"]
    assert row["skills"] == ["Plumbing"]
    assert row["skillIds"] == ["skill-plumbing"]


def test_api_181_a_department_with_no_skills_reports_an_empty_list(
    admin_api_client: TestClient, departments: dict
) -> None:
    """Skills are never inherited from categories, so empty is the normal case.

    Every department that existed before 0048 has no skills and must not
    acquire any by accident -- least of all from its categories, which answer a
    different question. Null from the view has to become `[]` on the wire, not
    null, because the screen maps over it.
    """
    departments["rows"] = [department_row(skill_ids=None, skill_names=None)]
    response = admin_api_client.get(DEPARTMENTS)
    row = response.json()["items"][0]
    assert row["skills"] == []
    assert row["skillIds"] == []
    # The categories are untouched: this department still has two.
    assert row["categories"] == ["Plumbing", "Water supply"]


def test_api_182_the_head_survives_the_mapping(
    admin_api_client: TestClient, departments: dict
) -> None:
    """`head` is the wire word; `manager` is what the column stores.

    The view's head lateral matched `rank = 'head'` from 0019 until 0048, while
    0035 had migrated every such row to `'manager'` and forbidden `'head'` --
    so `headName` was null for every department, and 0035's header said it had
    already fixed the view it did not touch. That fault was in SQL, which these
    tests cannot reach. What they can do is hold the other half still: if
    `headName` ever goes missing again, this passing proves the mapping is not
    where to look.
    """
    response = admin_api_client.get(ONE)
    assert response.status_code == 200
    body = response.json()
    assert body["head"] == "Ravi Kumar"
    assert body["headStaffId"] == "staff-id"

    departments["rows"] = [department_row(head_name=None, head_staff_id=None)]
    body = admin_api_client.get(ONE).json()
    assert body["head"] is None


def test_api_183_creating_with_no_categories_sends_an_empty_list_not_nothing(
    admin_api_client: TestClient,
    departments: dict,
    csrf_headers: dict[str, str],
) -> None:
    """The RPC distinguishes an absent key from an empty one.

    A department with no categories is a real choice, and `categories` is
    therefore always sent. Dropping the key when the list is empty would mean
    "leave them alone", which on a create is a different -- and unaskable --
    instruction.
    """
    response = admin_api_client.post(
        DEPARTMENTS,
        json={"name": "Gardening", "categories": []},
        headers=csrf_headers,
    )
    assert response.status_code == 201
    assert departments["created"]["categories"] == []


def test_api_184_the_status_vocabulary_is_translated_not_passed_through(
    admin_api_client: TestClient, departments: dict
) -> None:
    """`active`/`archived` is stored; `Active`/`Inactive` is what the wire says.

    Two vocabularies for one fact, with the seam in `vocabularies.py`. A screen
    reading the storage word would render "archived" in a filter offering
    "Inactive" and match nothing.
    """
    body = admin_api_client.get(ONE).json()
    assert body["status"] == "Active"

    departments["rows"] = [department_row(status="archived")]
    assert admin_api_client.get(ONE).json()["status"] == "Inactive"


def test_api_185_a_resident_cannot_read_the_department_admin_surface(
    resident_api_client: TestClient, departments: dict
) -> None:
    """`require_admin` on the router, and it is the only thing standing here.

    These routes resolve the community from the caller's membership rather than
    from the request, so a resident reaching them would be reading their own
    society's roster -- which is exactly the read the directory endpoint exists
    to serve in a redacted form.
    """
    assert resident_api_client.get(DEPARTMENTS).status_code == 403
    assert resident_api_client.get(ONE).status_code == 403


def test_api_186_the_whole_guard_table_holds_for_a_manager(
    manager_api_client: TestClient,
    departments: dict,
    csrf_headers: dict[str, str],
) -> None:
    """**This test is the safety net for a change in how the router is guarded.**

    `departments.py` used to carry `require_admin` at the router level. The
    manager portal needs to read its own department, and FastAPI cannot remove a
    router dependency for one route -- so the router now carries the *looser*
    `require_admin_or_manager` and four routes carry `require_admin`
    explicitly.

    That inverts the failure mode. Before, forgetting a guard on a new route was
    harmless because the router caught it; now, forgetting one leaves it open to
    every manager in the community. So the table is asserted whole rather than
    per route, and a new endpoint added without `ADMIN_ONLY` fails here.

    **The four `.../staff` routes this table used to cover are gone.**
    `PUT`/`POST /departments/{id}/staff` and `PATCH`/`DELETE
    /departments/{id}/staff/{staffId}` were retired: nothing had called them
    since the `0035` hiring flow replaced roster writes with applications,
    invitations, `POST .../members/{staffId}/remove` and `POST .../blacklist`
    (`department_hiring.py`), and `Departments.jsx` had not sent a non-empty
    `staff` array since. See the money-and-admins staff-writes verdict.
    """
    refused = [
        ("get", DEPARTMENTS, None),
        ("post", DEPARTMENTS, {"name": "X", "categories": []}),
        ("patch", ONE, {"name": "X"}),
        ("delete", ONE, None),
    ]
    for method, path, body in refused:
        call = getattr(manager_api_client, method)
        response = (
            call(path, json=body, headers=csrf_headers)
            if body is not None
            else call(path, headers=csrf_headers)
        )
        assert response.status_code == 403, (
            f"{method.upper()} {path} is open to a manager"
        )

    # The one read a manager may make. `can_manage_department` in Postgres is
    # what narrows it to *their* department; this only proves the route is
    # reachable, which is the half the router decides.
    assert manager_api_client.get(ONE).status_code == 200


# ---------------------------------------------------------------------------
# Who may hire, which stopped being a property of the caller
# ---------------------------------------------------------------------------


def test_api_246_the_department_read_answers_can_hire_for_this_caller(
    admin_api_client: TestClient, departments: dict
) -> None:
    """The screen asks the same function the RPC applies, not a role check.

    `can_hire_for_department` gives hiring to the department's own active
    manager -- by membership *or* by roster rank -- and admits community admins
    as a fallback **only while it has neither**. So the same admin may hire for
    one department and not the next, and no property of the caller can say
    which. Reimplementing that in the browser would be a second copy of a
    three-branch rule, and the copy is the one nobody notices going stale.
    """
    departments["can_hire"] = False
    body = admin_api_client.get(ONE).json()
    assert body["canHire"] is False
    assert departments["asked_can_hire"] == "department-id"


def test_api_247_the_list_leaves_can_hire_unanswered(
    admin_api_client: TestClient, departments: dict
) -> None:
    """`null` means *not asked*, which is different from *no*.

    It is one round trip per department and the list has no control that needs
    it. Defaulting to `false` instead would have told twelve screens that the
    admin may not hire for any of them.
    """
    row = admin_api_client.get(DEPARTMENTS).json()["items"][0]
    assert row["canHire"] is None
    assert "asked_can_hire" not in departments
