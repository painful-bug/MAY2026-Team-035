"""Authoring the skill catalogue, and a community's categories.

The cases here divide into two ideas.

**The duplicate that must not be created.** Everything about this feature exists
to stop somebody typing "Plumbling" beside "Plumbing", and the mechanism is a
single boolean -- ``isExact`` -- computed in Postgres and never on the client.
``api_190`` pins it to the wire, and ``api_192`` pins the consequence: a name
that already exists comes back **200 with ``created: false``**, not 201 and not
an error, because somebody typing a trade that is already there has asked a
reasonable question. A test that accepted 201 either way would let the status
code become a polite fiction.

**The authorization the router does not do.** ``require_admin_or_manager`` only
asks whether the caller manages *something*. Whether they manage *this*
department is asked by ``can_manage_department`` inside each RPC, and the tests
cannot see it -- it is Postgres, stubbed here. So ``api_195`` asserts the shape
that keeps it reachable: the department id travels to the repository unchanged,
never resolved or defaulted in Python, because an id the API rewrote is an id
the database checked the wrong one of.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AuthorizationError
from app.services import service_providers_service, skills_service

SKILLS = "/api/v1/skills"
CATEGORIES = "/api/v1/complaint-categories"
DEPARTMENT_SKILLS = "/api/v1/departments/department-id/skills"


def suggestion_row(**overrides: Any) -> dict[str, Any]:
    """One ``search_skills`` row, as PostgREST would return it."""
    base: dict[str, Any] = {
        "id": "skill-plumbing",
        "name": "Plumbing",
        "category": "maintenance",
        "description": "Taps, pipes and drains",
        "is_exact": False,
        "score": 0.62,
    }
    base.update(overrides)
    return base


def category_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "category-plumbing",
        "name": "Plumbing",
        "skill_id": "skill-plumbing",
        "skill_name": "Plumbing",
        "department_count": 2,
    }
    base.update(overrides)
    return base


@pytest.fixture
def skills(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository, recording every call."""
    captured: dict = {
        "suggestions": [suggestion_row()],
        "categories": [category_row()],
        "department_skills": [
            {
                "id": "skill-plumbing",
                "name": "Plumbing",
                "category": "maintenance",
                "description": "Taps, pipes and drains",
                "created_at": "2026-08-11T09:00:00Z",
            }
        ],
        "created": True,
        "calls": [],
    }

    def fake_search(client: Any, *, query: str | None, limit: int) -> list[dict]:
        captured["searched"] = {"query": query, "limit": limit}
        return captured["suggestions"]

    def fake_create(
        client: Any, *, name: str, category: str | None, description: str | None
    ) -> dict[str, Any]:
        captured["calls"].append("create")
        captured["created_with"] = {
            "name": name,
            "category": category,
            "description": description,
        }
        return {
            "id": "skill-new",
            "name": name.strip(),
            "category": category or "other",
            "description": description or "",
            "created": captured["created"],
        }

    def fake_categories(client: Any, *, membership_id: str) -> list[dict]:
        captured["categories_for"] = membership_id
        return captured["categories"]

    def fake_list_department(client: Any, *, department_id: str) -> list[dict]:
        captured["listed_department"] = department_id
        return captured["department_skills"]

    def fake_add(client: Any, *, department_id: str, name: str) -> dict[str, Any]:
        captured["calls"].append("add")
        captured["added"] = {"department_id": department_id, "name": name}
        return {
            "id": "skill-new",
            "name": name.strip(),
            "category": "other",
            "description": "",
            "created": captured["created"],
        }

    def fake_remove(client: Any, *, department_id: str, skill_id: str) -> None:
        captured["calls"].append("remove")
        captured["removed"] = {"department_id": department_id, "skill_id": skill_id}

    def fake_set(client: Any, *, department_id: str, skill_ids: list[str]) -> None:
        captured["calls"].append("set")
        captured["set"] = {"department_id": department_id, "skill_ids": skill_ids}

    def fake_catalogue(client: Any) -> list[dict[str, Any]]:
        captured["calls"].append("catalogue")
        return [
            {
                "id": "skill-plumbing",
                "name": "Plumbing",
                "category": "maintenance",
                "description": "Taps, pipes and drains",
            }
        ]

    repo = skills_service.repo
    monkeypatch.setattr(service_providers_service.repo, "list_skills", fake_catalogue)
    monkeypatch.setattr(repo, "search_skills", fake_search)
    monkeypatch.setattr(repo, "create_skill", fake_create)
    monkeypatch.setattr(repo, "community_categories", fake_categories)
    monkeypatch.setattr(repo, "list_department_skills", fake_list_department)
    monkeypatch.setattr(repo, "add_department_skill", fake_add)
    monkeypatch.setattr(repo, "remove_department_skill", fake_remove)
    monkeypatch.setattr(repo, "set_department_skills", fake_set)
    yield captured


def test_api_190_a_suggestion_says_whether_it_is_an_exact_match(
    admin_api_client: TestClient, skills: dict
) -> None:
    """`isExact` decides whether the form offers "add this as a new skill".

    It is computed in Postgres and carried to the wire because the alternative
    -- comparing strings in the browser -- is a second implementation of a
    case- and whitespace-insensitive rule, and the two would disagree on
    exactly the input that matters.
    """
    skills["suggestions"] = [
        suggestion_row(is_exact=True, score=1.0),
        suggestion_row(id="skill-painting", name="Painting", score=0.2),
    ]
    response = admin_api_client.get(SKILLS, params={"q": "plumbing"})
    assert response.status_code == 200
    body = response.json()
    assert [row["name"] for row in body] == ["Plumbing", "Painting"]


def test_api_191_the_catalogue_read_is_unchanged_without_a_query(
    admin_api_client: TestClient, skills: dict
) -> None:
    """The registration screen's grid must keep getting the whole catalogue.

    `q` was added to an endpoint that already had a consumer. If a bare
    `GET /skills` started going through the search path it would silently
    truncate to `limit`, hiding trades from somebody choosing their own.
    """
    response = admin_api_client.get(SKILLS)
    assert response.status_code == 200
    assert "searched" not in skills


def test_api_192_an_existing_skill_comes_back_200_not_201(
    admin_api_client: TestClient,
    skills: dict,
    csrf_headers: dict[str, str],
) -> None:
    """Typing a trade that already exists is not an error and not a creation.

    The status code carries the difference so a client can tell the two apart
    without parsing the body -- and so the body's `created` and the status code
    can never disagree.
    """
    skills["created"] = False
    response = admin_api_client.post(
        SKILLS, json={"name": "plumbing"}, headers=csrf_headers
    )
    assert response.status_code == 200
    assert response.json()["created"] is False

    skills["created"] = True
    response = admin_api_client.post(
        SKILLS, json={"name": "Lift Maintenance"}, headers=csrf_headers
    )
    assert response.status_code == 201
    assert response.json()["created"] is True


def test_api_193_a_category_with_no_trade_is_reported_not_hidden(
    admin_api_client: TestClient, skills: dict
) -> None:
    """A category matching no skill reaches no service person in any hiring
    search. That was true before this endpoint and invisible; the null is the
    whole reason the read exists, so it must survive serialization rather than
    being defaulted to an empty string."""
    skills["categories"] = [
        category_row(),
        category_row(
            id="category-typo",
            name="Plumbling",
            skill_id=None,
            skill_name=None,
            department_count=1,
        ),
    ]
    response = admin_api_client.get(CATEGORIES)
    assert response.status_code == 200
    body = response.json()
    assert body[1]["skillName"] is None
    assert body[1]["skillId"] is None


def test_api_194_the_add_button_is_one_call_not_two(
    admin_api_client: TestClient,
    skills: dict,
    csrf_headers: dict[str, str],
) -> None:
    """Create-and-attach is a single RPC.

    Two calls can half-fail, and the half that lands is a skill created and
    attached to nothing -- catalogue litter nobody asked for. So the API must
    not offer the two-step path even as an implementation detail: exactly one
    repository call, and it is the combined one.
    """
    response = admin_api_client.post(
        DEPARTMENT_SKILLS, json={"name": "Lift Repair"}, headers=csrf_headers
    )
    assert response.status_code == 201
    assert skills["calls"] == ["add"]
    assert skills["added"] == {
        "department_id": "department-id",
        "name": "Lift Repair",
    }


def test_api_195_the_department_id_reaches_the_database_unchanged(
    admin_api_client: TestClient,
    skills: dict,
    csrf_headers: dict[str, str],
) -> None:
    """The only authorization that matters here runs in Postgres.

    `can_manage_department` asks whether the caller manages *this* department;
    the router guard only asks whether they manage anything. That check is
    reachable only if the id in the path is the id the RPC receives, so an id
    resolved, defaulted or rewritten in Python would mean the database checked
    a different department from the one being edited.
    """
    admin_api_client.put(
        DEPARTMENT_SKILLS,
        json={"skillIds": ["skill-plumbing"]},
        headers=csrf_headers,
    )
    assert skills["set"]["department_id"] == "department-id"

    admin_api_client.delete(f"{DEPARTMENT_SKILLS}/skill-plumbing", headers=csrf_headers)
    assert skills["removed"] == {
        "department_id": "department-id",
        "skill_id": "skill-plumbing",
    }


def test_api_196_replacing_the_set_reads_it_back_rather_than_echoing(
    admin_api_client: TestClient,
    skills: dict,
    csrf_headers: dict[str, str],
) -> None:
    """The database is the authority on what landed.

    An echo of the request would report success for ids the RPC dropped, which
    is exactly the case a caller needs to be told about.
    """
    skills["department_skills"] = [
        {
            "id": "skill-plumbing",
            "name": "Plumbing",
            "category": "maintenance",
            "description": "Taps, pipes and drains",
            "created_at": "2026-08-11T09:00:00Z",
        }
    ]
    response = admin_api_client.put(
        DEPARTMENT_SKILLS,
        json={"skillIds": ["skill-plumbing", "skill-retired"]},
        headers=csrf_headers,
    )
    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["Plumbing"]
    assert skills["listed_department"] == "department-id"


def test_api_197_a_manager_of_another_department_is_refused(
    admin_api_client: TestClient,
    skills: dict,
    monkeypatch: pytest.MonkeyPatch,
    csrf_headers: dict[str, str],
) -> None:
    """`can_manage_department` raising HB403 must surface as 403, not 500.

    The RPC is the only thing that can answer this, so the API's job is to let
    its refusal through with its meaning intact.
    """

    def refuse(client: Any, **kwargs: Any) -> None:
        raise AuthorizationError("You do not manage this department.")

    monkeypatch.setattr(skills_service.repo, "set_department_skills", refuse)
    response = admin_api_client.put(
        DEPARTMENT_SKILLS, json={"skillIds": []}, headers=csrf_headers
    )
    assert response.status_code == 403


def test_api_198_a_resident_cannot_reach_the_authoring_surface(
    resident_api_client: TestClient,
    skills: dict,
    csrf_headers: dict[str, str],
) -> None:
    """The catalogue is global, so a careless guard here would let any member of
    any community write a word every other community then sees."""
    assert resident_api_client.post(
        SKILLS, json={"name": "Anything"}, headers=csrf_headers
    ).status_code == 403
    assert resident_api_client.get(CATEGORIES).status_code == 403
    assert resident_api_client.get(DEPARTMENT_SKILLS).status_code == 403


def test_api_199_a_blank_skill_name_is_refused_before_the_database(
    admin_api_client: TestClient,
    skills: dict,
    csrf_headers: dict[str, str],
) -> None:
    """`min_length=1` on the wire, and a matching check inside the RPC.

    Both, deliberately: the schema keeps whitespace-only names out of the
    request, and the RPC keeps them out of a catalogue that another caller
    might reach another way.
    """
    assert admin_api_client.post(
        SKILLS, json={"name": ""}, headers=csrf_headers
    ).status_code == 422
    assert skills["calls"] == []
