"""Gate operations: the guard, the credential, the reconcile and the export.

These cases pin the four things the migration alone cannot promise, and one of
them is the reason the module exists at all.

**The credential must never leave this process in plaintext.** ``0040`` compares
hash to hash and has no way to check that the caller hashed anything --
``verify_gate_credential`` would happily accept a six-digit string and simply
match nothing. So the assertion that the repository is handed a SHA-256 digest,
and specifically not the code the guard typed, is a property no SQL test could
make and no reviewer would notice the absence of.

**The router picks a gate membership rather than the default one.** A guard who
lives in one society and works the barrier of another has a default membership
of ``resident``, and ``require_membership_role`` would refuse them their own
register. The case that pins this puts the resident membership first on purpose.

**A refusal is a `200` with a verdict.** Turning *that code is not recognised*
into a `404` would split one act across the client's success and failure paths,
so it is asserted rather than left to a reader of the docstring.

**An export is a path from the gate to a spreadsheet formula.** Every text field
on these registers is typed by whoever is standing at the barrier, so a cell
beginning `=` is reachable by anyone who can walk up to it. The neutralisation
is asserted with the payload a real attempt would use.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_membership_set, get_request_client
from app.domain.schemas import MembershipContext, MembershipSet, Principal
from app.services import security_service

POSTS = "/api/v1/security/posts"
SHIFTS = "/api/v1/security/shifts"
MOVEMENTS = "/api/v1/security/material-movements"
TANKERS = "/api/v1/security/water-tankers"
INCIDENTS = "/api/v1/security/incidents"
VERIFY = "/api/v1/security/gate/verify"
BUNDLE = "/api/v1/security/offline-bundle"
RECONCILE = "/api/v1/security/offline-reconcile"

PROFILE_ID = "guard-profile-id"
HOME_MEMBERSHIP = "membership-where-they-live"
GATE_MEMBERSHIP = "membership-where-they-work"

#: The guard's own society comes first, exactly as `get_membership_set` orders
#: it -- `is_default_community desc`. If `require_gate_membership` ever takes
#: `.default` instead of scanning, this is the fixture that fails.
MEMBERSHIPS = MembershipSet(
    memberships=[
        MembershipContext(
            id=HOME_MEMBERSHIP,
            community_id="community-where-they-live",
            role="resident",
            department_id=None,
        ),
        MembershipContext(
            id=GATE_MEMBERSHIP,
            community_id="community-with-the-gate",
            role="security",
            department_id="security-department",
        ),
    ]
)


def movement_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "movement-id",
        "community_id": "community-with-the-gate",
        "direction": "inward",
        "description": "12 bags of cement",
        "quantity": 12,
        "unit": "bags",
        "is_returnable": False,
        "expected_return_at": None,
        "returned_at": None,
        "carrier_name": "Suresh",
        "vehicle_number": "KL07AB1234",
        "unit_id": None,
        "unit_code": None,
        "post_id": "post-id",
        "post_name": "Main Gate",
        "notes": None,
        "recorded_at": "2026-08-10T09:00:00Z",
        "is_outstanding": False,
        "is_overdue": False,
    }
    base.update(overrides)
    return base


def incident_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "incident-id",
        "community_id": "community-with-the-gate",
        "category": "fire_alarm",
        "severity": "high",
        "status": "open",
        "summary": "Alarm on the third floor",
        "details": None,
        "location_text": "Block B",
        "post_id": None,
        "post_name": None,
        "occurred_at": "2026-08-10T02:00:00Z",
        "resolved_at": None,
        "reported_by_name": "Ravi Kumar",
        "created_at": "2026-08-10T02:05:00Z",
        "updated_at": "2026-08-10T02:05:00Z",
    }
    base.update(overrides)
    return base


def shift_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "shift-id",
        "community_id": "community-with-the-gate",
        "department_id": "security-department",
        "post_id": "post-id",
        "post_name": "Main Gate",
        "staff_assignment_id": "staff-id",
        "guard_name": "Ravi Kumar",
        "guard_phone_e164": "+919876543210",
        "guard_job_title": "Gate Officer",
        "guard_rank": "member",
        "starts_at": "2026-08-11T22:00:00Z",
        "ends_at": "2026-08-12T06:00:00Z",
        "status": "scheduled",
        "notes": None,
        "created_at": "2026-08-10T09:00:00Z",
        "updated_at": "2026-08-10T09:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def gate_client(api_client: TestClient) -> TestClient:
    """Signed in, holding a resident membership and a security one."""
    principal = Principal(
        user_id=PROFILE_ID,
        email="ravi@example.com",
        email_verified=True,
        full_name="Ravi Kumar",
    )
    api_client.app.dependency_overrides[get_current_user] = lambda: principal
    api_client.app.dependency_overrides[get_membership_set] = lambda: MEMBERSHIPS
    api_client.app.dependency_overrides[get_request_client] = lambda: object()
    return api_client


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Replace the repository under the live service."""
    captured: dict = {
        "calls": [],
        "verify": {
            "verdict": "admitted",
            "detail": "Admitted.",
            "pass_id": "pass-id",
            "visitor_name": "Anil",
            "guest_count": 1,
            "unit_code": "B-204",
            "resident_name": "Asha Menon",
            "valid_from": "2026-08-10T08:00:00Z",
            "valid_until": "2026-08-10T20:00:00Z",
        },
        "bundle": [
            {
                "pass_id": "pass-id",
                "code_hash": "a" * 64,
                "pass_hash": "b" * 64,
                "visitor_name": "Anil",
                "guest_count": 2,
                "unit_code": "B-204",
                "valid_from": "2026-08-10T08:00:00Z",
                "valid_until": "2026-08-10T20:00:00Z",
            }
        ],
        "reconcile": {},
        "movements": [movement_row()],
        "incidents": [incident_row()],
        "shifts": [shift_row()],
    }

    def fake_verify(
        client: Any, *, membership_id: str, credential_hash: str, presented_at: Any
    ) -> dict[str, Any]:
        captured["calls"].append(("verify", membership_id, credential_hash))
        return captured["verify"]

    def fake_bundle(client: Any, *, membership_id: str, hours: int) -> list[dict]:
        captured["calls"].append(("bundle", membership_id, hours))
        return captured["bundle"]

    def fake_reconcile(
        client: Any,
        *,
        membership_id: str,
        source_client_id: str,
        credential_hash: str,
        presented_at: str,
        claimed_verdict: str | None,
    ) -> dict[str, Any]:
        captured["calls"].append(("reconcile", source_client_id, credential_hash))
        return captured["reconcile"].get(
            source_client_id,
            {
                "source_client_id": source_client_id,
                "server_verdict": "admitted",
                "detail": "Admitted.",
                "was_replay": False,
            },
        )

    def fake_record_movement(
        client: Any, *, membership_id: str, payload: dict[str, Any]
    ) -> str:
        captured["calls"].append(("record_movement", payload))
        return "movement-id"

    def fake_record_incident(
        client: Any, *, membership_id: str, payload: dict[str, Any]
    ) -> str:
        captured["calls"].append(("record_incident", payload))
        return "incident-id"

    def fake_schedule_shift(
        client: Any, *, membership_id: str, payload: dict[str, Any]
    ) -> str:
        captured["calls"].append(("schedule_shift", membership_id, payload))
        return "shift-id"

    def fake_list_movements(client: Any, **kwargs: Any) -> list[dict[str, Any]]:
        captured["calls"].append(("list_movements", kwargs))
        return captured["movements"]

    def fake_list_incidents(client: Any, **kwargs: Any) -> list[dict[str, Any]]:
        captured["calls"].append(("list_incidents", kwargs))
        return captured["incidents"]

    def fake_list_shifts(client: Any, **kwargs: Any) -> list[dict[str, Any]]:
        captured["calls"].append(("list_shifts", kwargs))
        return captured["shifts"]

    def fake_get_movement(client: Any, *, movement_id: str) -> dict[str, Any]:
        return captured["movements"][0]

    def fake_get_incident(client: Any, *, incident_id: str) -> dict[str, Any]:
        return captured["incidents"][0]

    def fake_get_shift(client: Any, *, shift_id: str) -> dict[str, Any]:
        return captured["shifts"][0]

    repo = security_service.repo
    monkeypatch.setattr(repo, "verify_credential", fake_verify)
    monkeypatch.setattr(repo, "offline_bundle", fake_bundle)
    monkeypatch.setattr(repo, "reconcile_entry", fake_reconcile)
    monkeypatch.setattr(repo, "record_movement", fake_record_movement)
    monkeypatch.setattr(repo, "record_incident", fake_record_incident)
    monkeypatch.setattr(repo, "schedule_shift", fake_schedule_shift)
    monkeypatch.setattr(repo, "list_movements", fake_list_movements)
    monkeypatch.setattr(repo, "list_incidents", fake_list_incidents)
    monkeypatch.setattr(repo, "list_shifts", fake_list_shifts)
    monkeypatch.setattr(repo, "get_movement", fake_get_movement)
    monkeypatch.setattr(repo, "get_incident", fake_get_incident)
    monkeypatch.setattr(repo, "get_shift", fake_get_shift)
    yield captured


def test_api_198_the_gate_membership_is_used_not_the_default_one(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """The caller's *security* membership reaches the RPC, not their home one.

    endpoint: POST /api/v1/security/gate/verify
    input_data: a caller whose default membership is `resident` elsewhere
    expected_output: the membership forwarded is the one holding a gate role
    """
    endpoint = VERIFY
    input_data = {"credential": "483920"}
    response = gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    assert response.status_code == 200
    verify_calls = [call for call in gate["calls"] if call[0] == "verify"]
    expected_output = GATE_MEMBERSHIP
    actual_output = verify_calls[0][1]
    assert actual_output == expected_output


def test_api_199_a_caller_with_no_gate_role_is_refused_by_the_router(
    api_client: TestClient, gate: dict
) -> None:
    """A resident of one society and nothing else cannot read a register.

    endpoint: GET /api/v1/security/material-movements
    input_data: a caller holding one `resident` membership
    expected_output: 403 community_role_required, and the repository untouched
    """
    principal = Principal(
        user_id=PROFILE_ID, email="a@example.com", email_verified=True, full_name="A"
    )
    resident_only = MembershipSet(
        memberships=[
            MembershipContext(
                id="m1", community_id="c1", role="resident", department_id=None
            )
        ]
    )
    api_client.app.dependency_overrides[get_current_user] = lambda: principal
    api_client.app.dependency_overrides[get_membership_set] = lambda: resident_only
    api_client.app.dependency_overrides[get_request_client] = lambda: object()

    endpoint = MOVEMENTS
    response = api_client.get(endpoint)

    expected_output = (403, "community_role_required", [])
    actual_output = (
        response.status_code,
        response.json()["error"]["code"],
        [call for call in gate["calls"] if call[0] == "list_movements"],
    )
    assert actual_output == expected_output


def test_api_200_the_credential_is_hashed_before_it_reaches_the_database(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """The six digits a guard typed never leave this process.

    The single most important assertion in this module: `0040` compares hash to
    hash and cannot tell that the caller hashed anything, so nothing below the
    service would notice a plaintext code being sent -- it would simply match no
    row, which looks exactly like an unrecognised code.

    endpoint: POST /api/v1/security/gate/verify
    input_data: the plaintext security code `483920`
    expected_output: the repository receives its SHA-256 digest and not the code
    """
    endpoint = VERIFY
    input_data = {"credential": "483920"}
    gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    sent = [call for call in gate["calls"] if call[0] == "verify"][0][2]
    expected_output = (
        hashlib.sha256(b"483920").hexdigest(),
        False,
    )
    actual_output = (sent, "483920" in sent)
    assert actual_output == expected_output


def test_api_201_an_unrecognised_code_is_a_200_with_a_verdict(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """A refusal is an answer, not an error.

    endpoint: POST /api/v1/security/gate/verify
    input_data: a code the database does not recognise
    expected_output: 200, verdict `not_found`, with the guard's sentence
    """
    gate["verify"] = {
        "verdict": "not_found",
        "detail": "That code is not recognised at this gate.",
        "pass_id": None,
        "visitor_name": None,
        "guest_count": None,
        "unit_code": None,
        "resident_name": None,
        "valid_from": None,
        "valid_until": None,
    }
    endpoint = VERIFY
    input_data = {"credential": "000000"}
    response = gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    expected_output = (200, "not_found", "That code is not recognised at this gate.")
    body = response.json()
    actual_output = (response.status_code, body["verdict"], body["detail"])
    assert actual_output == expected_output


def test_api_202_the_offline_bundle_carries_hashes_an_expiry_and_no_codes(
    gate_client: TestClient, gate: dict
) -> None:
    """What a gate caches is hashes, scoped to a community, with a deadline.

    endpoint: GET /api/v1/security/offline-bundle
    input_data: hours=6
    expected_output: the requested window reaches the RPC, the community is the
      gate's, the algorithm is named, and every pass carries a hash
    """
    endpoint = BUNDLE
    response = gate_client.get(endpoint, params={"hours": 6})

    body = response.json()
    bundle_call = [call for call in gate["calls"] if call[0] == "bundle"][0]
    expected_output = (200, 6, "community-with-the-gate", "sha256", 64)
    actual_output = (
        response.status_code,
        bundle_call[2],
        body["communityId"],
        body["hashAlgorithm"],
        len(body["passes"][0]["codeHash"]),
    )
    assert actual_output == expected_output
    assert body["expiresAt"] > body["generatedAt"]


def test_api_203_reconcile_is_per_entry_and_counts_replays_apart(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """Each queued entry is its own call, and a replay is not an acceptance.

    A replay counted as an acceptance would tell the security manager that a
    device admitted two people when it admitted one, and the number is the whole
    reason the endpoint answers with a summary.

    endpoint: POST /api/v1/security/offline-reconcile
    input_data: three entries, one already reconciled and one refused
    expected_output: three calls, and the counts split 1/1/1
    """
    gate["reconcile"] = {
        "entry-2": {
            "source_client_id": "entry-2",
            "server_verdict": "admitted",
            "detail": "Admitted.",
            "was_replay": True,
        },
        "entry-3": {
            "source_client_id": "entry-3",
            "server_verdict": "expired",
            "detail": "That pass has expired.",
            "was_replay": False,
        },
    }
    endpoint = RECONCILE
    input_data = {
        "entries": [
            {
                "sourceClientId": f"entry-{index}",
                "credential": "483920",
                "presentedAt": "2026-08-10T09:00:00Z",
                "claimedVerdict": "admitted",
            }
            for index in (1, 2, 3)
        ]
    }
    response = gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    body = response.json()
    expected_output = (200, 3, 1, 1, 1)
    actual_output = (
        response.status_code,
        len([call for call in gate["calls"] if call[0] == "reconcile"]),
        body["accepted"],
        body["rejected"],
        body["replayed"],
    )
    assert actual_output == expected_output


def test_api_204_an_unknown_incident_category_is_refused_before_the_database(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """A typed category does not quietly become *Other*.

    Asserting the repository is **not reached** rather than only that the status
    is 422: a fall back to `other` would also produce a working request, and it
    is the silence that makes a report wrong rather than the status code.

    endpoint: POST /api/v1/security/incidents
    input_data: a category nobody has ever offered
    expected_output: 422 unknown_incident_category, and no write attempted
    """
    endpoint = INCIDENTS
    input_data = {"summary": "Something happened", "category": "Aliens"}
    response = gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    expected_output = (422, "unknown_incident_category", [])
    actual_output = (
        response.status_code,
        response.json()["error"]["code"],
        [call for call in gate["calls"] if call[0] == "record_incident"],
    )
    assert actual_output == expected_output


def test_api_205_the_stored_incident_category_is_translated_both_ways(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """The wire says `Fire alarm`; the column says `fire_alarm`.

    endpoint: POST /api/v1/security/incidents
    input_data: the frontend's own display string
    expected_output: snake case reaches the RPC and the display string comes back
    """
    endpoint = INCIDENTS
    input_data = {"summary": "Alarm on the third floor", "category": "Fire alarm"}
    response = gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    sent = [call for call in gate["calls"] if call[0] == "record_incident"][0][1]
    expected_output = (201, "fire_alarm", "Fire alarm")
    actual_output = (
        response.status_code,
        sent["p_category"],
        response.json()["category"],
    )
    assert actual_output == expected_output


def test_api_206_a_return_date_on_a_non_returnable_item_is_refused(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """The contradiction is caught in the service, not by a CHECK constraint.

    endpoint: POST /api/v1/security/material-movements
    input_data: `isReturnable: false` with an expected return date
    expected_output: 422 not_returnable, and no write attempted
    """
    endpoint = MOVEMENTS
    input_data = {
        "direction": "inward",
        "description": "12 bags of cement",
        "isReturnable": False,
        "expectedReturnAt": "2026-08-20T09:00:00Z",
    }
    response = gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    expected_output = (422, "not_returnable", [])
    actual_output = (
        response.status_code,
        response.json()["error"]["code"],
        [call for call in gate["calls"] if call[0] == "record_movement"],
    )
    assert actual_output == expected_output


def test_api_207_scheduling_a_shift_forwards_the_terms_and_nothing_else(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """One call, carrying the roster decision, with the gate membership on it.

    No in-process test can prove the exclusion constraint refuses an overlap --
    it runs in Postgres. What this proves is that the API reaches it rather than
    routing around it: nothing here checks for a clash first and nothing else is
    sent.

    endpoint: POST /api/v1/security/shifts
    input_data: a guard, a window and a post
    expected_output: one `schedule_shift` call carrying exactly those
    """
    endpoint = SHIFTS
    input_data = {
        "staffAssignmentId": "staff-id",
        "startsAt": "2026-08-11T22:00:00Z",
        "endsAt": "2026-08-12T06:00:00Z",
        "postId": "post-id",
    }
    response = gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    calls = [call for call in gate["calls"] if call[0] == "schedule_shift"]
    expected_output = (201, 1, GATE_MEMBERSHIP, "staff-id", "post-id")
    actual_output = (
        response.status_code,
        len(calls),
        calls[0][1],
        calls[0][2]["p_staff_assignment_id"],
        calls[0][2]["p_post_id"],
    )
    assert actual_output == expected_output


def test_api_208_a_shift_that_ends_before_it_starts_never_reaches_the_database(
    gate_client: TestClient, gate: dict, csrf_headers: dict[str, str]
) -> None:
    """The window is checked by the model, so the round trip is not spent.

    endpoint: POST /api/v1/security/shifts
    input_data: an end before the start
    expected_output: 422, and no write attempted
    """
    endpoint = SHIFTS
    input_data = {
        "staffAssignmentId": "staff-id",
        "startsAt": "2026-08-12T06:00:00Z",
        "endsAt": "2026-08-11T22:00:00Z",
    }
    response = gate_client.post(endpoint, json=input_data, headers=csrf_headers)

    expected_output = (422, [])
    actual_output = (
        response.status_code,
        [call for call in gate["calls"] if call[0] == "schedule_shift"],
    )
    assert actual_output == expected_output


def test_api_209_an_unknown_export_dataset_names_the_ones_that_exist(
    gate_client: TestClient, gate: dict
) -> None:
    """One route, four datasets, and a fifth is a 422 rather than an empty file.

    endpoint: GET /api/v1/security/exports/{dataset}
    input_data: a dataset nobody defined
    expected_output: 422 unknown_dataset, no read attempted
    """
    endpoint = "/api/v1/security/exports/everything"
    response = gate_client.get(endpoint)

    expected_output = (422, "unknown_dataset", [])
    actual_output = (
        response.status_code,
        response.json()["error"]["code"],
        [call for call in gate["calls"] if call[0].startswith("list_")],
    )
    assert actual_output == expected_output


def test_api_210_an_export_is_csv_named_after_its_dataset_and_oldest_first(
    gate_client: TestClient, gate: dict
) -> None:
    """The download a security manager opens for an audit.

    Oldest first, unlike every list on this surface: a spreadsheet opened for an
    audit reads forwards through time, and re-sorting is the first thing the
    reader would otherwise do.

    endpoint: GET /api/v1/security/exports/material-movements
    input_data: two entries, newest first as the view returns them
    expected_output: text/csv, an attachment filename, and the older row first
    """
    gate["movements"] = [
        movement_row(
            id="newer", description="Newer", recorded_at="2026-08-10T09:00:00Z"
        ),
        movement_row(
            id="older", description="Older", recorded_at="2026-08-09T09:00:00Z"
        ),
    ]
    endpoint = "/api/v1/security/exports/material-movements"
    response = gate_client.get(endpoint)

    lines = response.text.strip().splitlines()
    expected_output = (
        200,
        True,
        'attachment; filename="material-movements.csv"',
        True,
        True,
    )
    actual_output = (
        response.status_code,
        response.headers["content-type"].startswith("text/csv"),
        response.headers["content-disposition"],
        lines[0].startswith("Recorded at,Direction,Description"),
        "Older" in lines[1],
    )
    assert actual_output == expected_output


def test_api_211_a_formula_in_a_register_field_cannot_execute_in_a_spreadsheet(
    gate_client: TestClient, gate: dict
) -> None:
    """Every text column here is typed by whoever is standing at the barrier.

    Without the guard, an export is a path from *anyone who can walk up to the
    gate* to *code that runs when the security manager opens the audit*. `csv`
    quoting does not help -- the spreadsheet strips the quotes before evaluating
    the cell.

    A leading `-` is prefixed too and a real number is not, which is the
    distinction worth pinning: stripping the character instead would silently
    turn a quantity of `-5` into `5`.

    endpoint: GET /api/v1/security/exports/material-movements
    input_data: a description beginning `=` and a note beginning `-`
    expected_output: both neutralised with an apostrophe, the quantity untouched
    """
    gate["movements"] = [
        movement_row(
            description='=cmd|" /c calc"!A1',
            notes="-1 returned",
            quantity=12,
        )
    ]
    endpoint = "/api/v1/security/exports/material-movements"
    response = gate_client.get(endpoint)

    row = response.text.strip().splitlines()[1]
    expected_output = (True, True, True)
    actual_output = (
        "'=cmd" in row,
        "'-1 returned" in row,
        ",12," in row,
    )
    assert actual_output == expected_output


def test_api_212_the_incident_list_renders_the_stored_category_for_a_screen(
    gate_client: TestClient, gate: dict
) -> None:
    """A read translates too, not only a write.

    endpoint: GET /api/v1/security/incidents
    input_data: a stored `fire_alarm`
    expected_output: `Fire alarm` on the wire
    """
    endpoint = INCIDENTS
    response = gate_client.get(endpoint)

    expected_output = (200, "Fire alarm")
    actual_output = (response.status_code, response.json()[0]["category"])
    assert actual_output == expected_output


def test_api_232_the_roster_read_serves_the_shift_forms_guard_picker(
    gate_client: TestClient, gate: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The picker gets names with ids, and the caller's gate membership is used.

    endpoint: GET /api/v1/security/roster
    input_data: one active security-department staff row from 0047's function
    expected_output: camelCase entry carrying staffAssignmentId and name
    """

    def fake_list_roster(client: Any, *, membership_id: str) -> list[dict[str, Any]]:
        gate["calls"].append(("list_roster", membership_id))
        return [
            {
                "staff_assignment_id": "staff-id",
                "display_name": "Ravi Kumar",
                "phone_e164": "+919876543210",
                "job_title": "Gate Officer",
                "rank": "member",
                "shift": "Night",
            }
        ]

    monkeypatch.setattr(security_service.repo, "list_roster", fake_list_roster)

    endpoint = "/api/v1/security/roster"
    response = gate_client.get(endpoint)

    body = response.json()
    expected_output = (200, GATE_MEMBERSHIP, "staff-id", "Ravi Kumar", "member")
    actual_output = (
        response.status_code,
        [call for call in gate["calls"] if call[0] == "list_roster"][0][1],
        body[0]["staffAssignmentId"],
        body[0]["name"],
        body[0]["rank"],
    )
    assert actual_output == expected_output


def test_api_233_a_plain_guard_may_not_read_the_roster(
    gate_client: TestClient, gate: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """0047 refuses below security manager, and the refusal reaches the wire.

    endpoint: GET /api/v1/security/roster
    input_data: the repository raising the HB403 translation
    expected_output: 403 forbidden
    """
    from app.core.exceptions import AuthorizationError

    def fake_list_roster(client: Any, *, membership_id: str) -> list[dict[str, Any]]:
        raise AuthorizationError(
            "Only a security manager may change the roster.", code="forbidden"
        )

    monkeypatch.setattr(security_service.repo, "list_roster", fake_list_roster)

    endpoint = "/api/v1/security/roster"
    response = gate_client.get(endpoint)

    expected_output = (403, "forbidden")
    actual_output = (response.status_code, response.json()["error"]["code"])
    assert actual_output == expected_output


def test_api_234_an_empty_roster_is_an_answer_not_an_error(
    gate_client: TestClient, gate: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A community with no security department yet gets an empty list.

    endpoint: GET /api/v1/security/roster
    input_data: 0047's function returning no rows
    expected_output: 200 []
    """
    monkeypatch.setattr(
        security_service.repo,
        "list_roster",
        lambda client, *, membership_id: [],
    )

    endpoint = "/api/v1/security/roster"
    response = gate_client.get(endpoint)

    expected_output = (200, [])
    actual_output = (response.status_code, response.json())
    assert actual_output == expected_output


def test_api_235_a_shift_can_be_asked_for_by_id_without_naming_a_window(
    gate_client: TestClient, gate: dict
) -> None:
    """`?shiftId=` reaches the repository on its own, with no range beside it.

    This is what a guard arriving from `security_shift.assigned` (`0043`) sends.
    They hold an id and nothing else, and `0045` lets the shift that id names be
    weeks away -- so any window the screen guesses can miss it, and a window
    wide enough not to would risk being truncated by the 200-row cap before the
    row arrives. The filter has to travel alone.

    endpoint: GET /api/v1/security/shifts
    input_data: `?shiftId=` and no `from`, `to`, `status` or `postId`
    expected_output: the repository receives that id and no range
    """
    endpoint = f"{SHIFTS}?shiftId=shift-from-the-notification"
    response = gate_client.get(endpoint)

    assert response.status_code == 200
    kwargs = [call[1] for call in gate["calls"] if call[0] == "list_shifts"][-1]
    expected_output = {
        "shift_id": "shift-from-the-notification",
        "starts_from": None,
        "starts_to": None,
        "status": None,
        "post_id": None,
    }
    actual_output = {key: kwargs.get(key) for key in expected_output}
    assert actual_output == expected_output


def test_api_236_an_unknown_shift_id_is_an_empty_list_not_a_404(
    gate_client: TestClient, gate: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shift handed on again answers the same as a quiet fortnight.

    Deliberately *not* a `404`. The list already answers `[]` for a window with
    nothing in it, and giving the id filter a different failure would turn this
    read into a way to test whether a shift exists in a community the caller
    cannot see. The screen tells the two apart from the parameter it sent, not
    from the status code.

    endpoint: GET /api/v1/security/shifts
    input_data: an id no visible row carries
    expected_output: 200 []
    """
    monkeypatch.setattr(
        security_service.repo, "list_shifts", lambda client, **kwargs: []
    )

    endpoint = f"{SHIFTS}?shiftId=handed-on-since"
    response = gate_client.get(endpoint)

    expected_output = (200, [])
    actual_output = (response.status_code, response.json())
    assert actual_output == expected_output
