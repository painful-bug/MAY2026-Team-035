"""Which department owns a complaint.

**What these tests can and cannot prove.** The routing rule itself —
category first, the resident's pick second, the triage queue third — is
`resolve_complaint_department` in `0050`, and it is Postgres. It is stubbed
here, so nothing below shows that a "Water leakage" complaint reaches Plumbing.
No test in this repository can: no migration has ever been applied to a
database.

What they do prove is the half that is Python, and it is the half where a
mistake is silent:

* the two writes carry the caller's **own** membership id, because both RPCs
  authorize against it and a router that passed a client-supplied one would
  hand the whole surface away;
* a decision word outside ``accept|reject`` never reaches the database;
* the department is **not** taken from the request body on the move, which is
  the one field whose presence would turn "move a complaint out of my
  department" into "take a complaint out of somebody else's".
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import complaint_routing_service

COMPLAINT = "/api/v1/complaints/complaint-id"
DEPARTMENT = "/api/v1/departments/department-id"
TRIAGE = "/api/v1/unassigned-complaints"


def complaint_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "complaint-id",
        "title": "Water leaking from the ceiling",
        "description": "Since this morning.",
        "category": "Plumbing",
        "status": "open",
        "priority": "high",
        "location": "B-402",
        "created_at": "2026-08-12T06:00:00Z",
        "due_at": "2026-08-12T10:00:00Z",
        "resolved_at": None,
        "raised_by": "Priya Nair",
        "unit_code": "B-402",
        "open_request_id": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def routing(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    captured: dict = {
        "rows": [complaint_row()],
        "unassigned": [],
        "requests": [],
        "calls": [],
    }

    def fake_department_complaints(
        client: Any, *, department_id: str, status: str | None
    ) -> list[dict[str, Any]]:
        captured["listed"] = {"department_id": department_id, "status": status}
        return captured["rows"]

    def fake_unassigned(client: Any, *, community_id: str) -> list[dict[str, Any]]:
        captured["community"] = community_id
        return captured["unassigned"]

    def fake_requests(client: Any, *, department_id: str) -> list[dict[str, Any]]:
        captured["requested_for"] = department_id
        return captured["requests"]

    def fake_assign(client: Any, **kwargs: Any) -> None:
        captured["calls"].append("assign")
        captured["assigned"] = kwargs

    def fake_request(client: Any, **kwargs: Any) -> str:
        captured["calls"].append("request")
        captured["requested"] = kwargs
        return "request-id"

    def fake_decide(client: Any, **kwargs: Any) -> None:
        captured["calls"].append("decide")
        captured["decided"] = kwargs

    repo = complaint_routing_service.repo
    monkeypatch.setattr(repo, "department_complaints", fake_department_complaints)
    monkeypatch.setattr(repo, "unassigned_complaints", fake_unassigned)
    monkeypatch.setattr(repo, "department_change_requests", fake_requests)
    monkeypatch.setattr(repo, "assign_department", fake_assign)
    monkeypatch.setattr(repo, "request_department_change", fake_request)
    monkeypatch.setattr(repo, "decide_department_change", fake_decide)
    yield captured


# The two tests for the resident's own guess reaching the RPC live in
# `test_resident_complaints.py`, beside the rest of the raise path and the
# fixture that already stubs that repository. Splitting the complaint form's
# contract across two files to keep this one's subject tidy would have made the
# rule harder to find than the tidiness was worth.


# ---------------------------------------------------------------------------
# The queues
# ---------------------------------------------------------------------------


def test_api_248_a_department_queue_carries_its_open_request(
    manager_api_client: TestClient, routing: dict
) -> None:
    """The screen must know a transfer was already asked for.

    Without this field the only way to draw the button correctly would be to
    read the request list and join the two lists client-side -- and until that
    finished, a supervisor could file the same request twice and learn about it
    from a unique-index violation.
    """
    routing["rows"] = [complaint_row(open_request_id="request-id")]
    body = manager_api_client.get(f"{DEPARTMENT}/complaints").json()
    assert body[0]["openRequestId"] == "request-id"
    assert body[0]["unitCode"] == "B-402"


def test_api_249_the_status_filter_is_passed_through_not_applied_here(
    manager_api_client: TestClient, routing: dict
) -> None:
    """Filtering in Python would mean reading every complaint to show ten."""
    manager_api_client.get(f"{DEPARTMENT}/complaints?status=open")
    assert routing["listed"] == {"department_id": "department-id", "status": "open"}


def test_api_250_the_triage_queue_is_scoped_to_the_callers_community(
    admin_api_client: TestClient, routing: dict
) -> None:
    """The community comes from the session, never from a query parameter.

    There is no community id on this route and that is deliberate: it is the one
    input that would turn "my society's unrouted complaints" into "any society's"
    if a caller could supply it.
    """
    admin_api_client.get(TRIAGE)
    assert routing["community"] == "community-id"


def test_api_251_a_resident_cannot_read_the_triage_queue(
    resident_api_client: TestClient, routing: dict
) -> None:
    """It is every unrouted complaint in the society, including other people's."""
    response = resident_api_client.get(TRIAGE)
    assert response.status_code == 403


def test_api_252_the_triage_queue_is_not_a_child_of_complaints(
    admin_api_client: TestClient, routing: dict
) -> None:
    """It was, once, and `resident_complaints.py` swallowed it.

    That router owns `GET /complaints/{complaint_id}`, and FastAPI matches
    across aggregated routers in registration order -- so `/complaints/
    unassigned` resolved as a complaint whose id is the word "unassigned" and
    ran the resident's read against it. Declaring this route earlier would have
    fixed it and would have left the triage queue's correctness depending on
    which order two files are included in.

    This test pins the shape rather than the ordering: the path is a sibling of
    `/complaints`, not a child, so nothing anybody adds later can capture it.
    """
    assert not TRIAGE.startswith("/api/v1/complaints/")
    response = admin_api_client.get(TRIAGE)
    assert response.status_code == 200
    assert "community" in routing


# ---------------------------------------------------------------------------
# The writes
# ---------------------------------------------------------------------------


def test_api_253_assigning_uses_the_callers_own_membership(
    admin_api_client: TestClient, routing: dict, csrf_headers: dict[str, str]
) -> None:
    """`assign_complaint_department` authorizes against this id.

    It is taken from the resolved session and never from the body. A router that
    accepted a membership id from the client would hand the entire surface to
    whoever could guess one.
    """
    admin_api_client.patch(
        f"{COMPLAINT}/department",
        json={"departmentId": "plumbing", "membershipId": "somebody-else"},
        headers=csrf_headers,
    )
    assert routing["assigned"]["membership_id"] == "admin-membership-id"
    assert routing["assigned"]["department_id"] == "plumbing"


def test_api_254_a_resident_cannot_move_a_complaint(
    resident_api_client: TestClient, routing: dict, csrf_headers: dict[str, str]
) -> None:
    """Including their own: which department fixes it is not theirs to decide."""
    response = resident_api_client.patch(
        f"{COMPLAINT}/department",
        json={"departmentId": "plumbing"},
        headers=csrf_headers,
    )
    assert response.status_code == 403
    assert routing["calls"] == []


def test_api_255_a_transfer_request_may_name_no_destination(
    manager_api_client: TestClient, routing: dict, csrf_headers: dict[str, str]
) -> None:
    """"This isn't ours" is worth saying without knowing whose it is.

    A supervisor who knows a lift complaint is not plumbing usually does not
    know which department owns lifts, and requiring a destination would either
    silence them or make them guess -- and a guess here becomes somebody else's
    queue.
    """
    response = manager_api_client.post(
        f"{COMPLAINT}/department-requests",
        json={"reason": "Not a plumbing job."},
        headers=csrf_headers,
    )
    assert response.status_code == 201
    assert routing["requested"]["to_department_id"] is None
    assert routing["requested"]["reason"] == "Not a plumbing job."


def test_api_256_an_unknown_decision_never_reaches_the_database(
    manager_api_client: TestClient, routing: dict, csrf_headers: dict[str, str]
) -> None:
    """Two words, and a 422 that names both.

    The RPC checks this too. Checking it here as well is what turns a database
    error the client has to interpret into a message that says which words are
    legal.
    """
    response = manager_api_client.patch(
        f"{COMPLAINT}/department-requests/request-id",
        json={"decision": "maybe"},
        headers=csrf_headers,
    )
    assert response.status_code == 422
    assert routing["calls"] == []


def test_api_257_a_decision_may_override_the_suggested_destination(
    manager_api_client: TestClient, routing: dict, csrf_headers: dict[str, str]
) -> None:
    """The manager is the one being asked, and knows the society better."""
    manager_api_client.patch(
        f"{COMPLAINT}/department-requests/request-id",
        json={"decision": "Accept", "toDepartmentId": "lifts"},
        headers=csrf_headers,
    )
    assert routing["decided"]["decision"] == "accept"
    assert routing["decided"]["to_department_id"] == "lifts"
