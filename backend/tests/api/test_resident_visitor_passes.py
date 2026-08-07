"""The resident visitor-pass surface -- six operations and one projection.

The group that matters most here is the third. Everything a visitor pass does
turns on **a secret appearing exactly once**, and that is a property no ordinary
response assertion catches: a test that reads a field cannot notice a field that
should not have been there. So there is a set below whose whole job is to assert
absence -- on the list, on the detail read, and on all three decisions.

The others follow the pattern of the complaint suite: the HTTP surface with the
repository replaced, the projection through the service directly, and a
recording stand-in for the Supabase client asserting what the query is pointed
at.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ConflictError, NotFoundError
from app.core.tokens import hash_secret
from app.repositories import resident_visitor_passes_repository
from app.services import resident_visitor_passes_service as service

PATH = "/api/v1/visitor-passes"


def row(**overrides: Any) -> dict[str, Any]:
    """A complete `visitor_pass_overview` row, as PostgREST would return it."""
    base: dict[str, Any] = {
        "id": "pass-id",
        "visitor_name": "Anita Rao",
        "purpose": "Guest",
        "purpose_details": "",
        "guest_count": 3,
        "status": "expected",
        "valid_from": "2026-08-04T16:00:00+00:00",
        "valid_until": "2026-08-04T18:00:00+00:00",
        "checked_in_at": None,
        "checked_out_at": None,
        "decided_at": None,
        "cancelled_at": None,
        "created_at": "2026-08-04T09:00:00+00:00",
        "is_current": True,
        "is_lapsed": False,
    }
    base.update(overrides)
    return base


@pytest.fixture
def passes(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace every repository call. Records arguments, returns what is staged."""
    captured: dict = {
        "rows": [row()],
        "total": None,
        "detail": row(),
        "calls": [],
        # Exceptions `create_pass` raises on successive calls, oldest first.
        # Staged rather than patched per test so a retry can be watched across
        # several attempts in the order the service makes them.
        "create_errors": [],
    }

    def fake_list_mine(client: Any, **kwargs: Any) -> tuple[list[dict], int]:
        captured["calls"].append(("list_mine", kwargs))
        rows = captured["rows"]
        total = captured["total"]
        return rows, (len(rows) if total is None else total)

    def fake_get_mine(client: Any, **kwargs: Any) -> dict[str, Any] | None:
        captured["calls"].append(("get_mine", kwargs))
        return captured["detail"]

    def fake_create(client: Any, **kwargs: Any) -> str:
        captured["calls"].append(("create_pass", kwargs))
        if captured["create_errors"]:
            raise captured["create_errors"].pop(0)
        return "pass-id"

    def fake_decide(client: Any, **kwargs: Any) -> None:
        captured["calls"].append(("decide", kwargs))

    for name, replacement in {
        "list_mine": fake_list_mine,
        "get_mine": fake_get_mine,
        "create_pass": fake_create,
        "decide": fake_decide,
    }.items():
        monkeypatch.setattr(resident_visitor_passes_repository, name, replacement)
    return captured


def every(captured: dict, name: str) -> list[dict[str, Any]]:
    return [kwargs for call, kwargs in captured["calls"] if call == name]


def only(captured: dict, name: str) -> dict[str, Any]:
    matches = every(captured, name)
    assert len(matches) == 1, f"expected one {name} call, saw {len(matches)}"
    return matches[0]


def create(client: TestClient, csrf: dict[str, str], **overrides: Any) -> Any:
    body = {"visitorName": "Anita Rao", "purpose": "Guest", "guestCount": 3}
    body.update(overrides)
    return client.post(PATH, json=body, headers=csrf)


# ---------------------------------------------------------------------------
# The guards
# ---------------------------------------------------------------------------


def test_the_list_requires_a_session(api_client: TestClient) -> None:
    assert api_client.get(PATH).status_code == 401


def test_creating_requires_csrf(resident_api_client: TestClient, passes: dict) -> None:
    response = resident_api_client.post(
        PATH, json={"visitorName": "Anita Rao", "purpose": "Guest"}
    )

    assert response.status_code == 403
    assert passes["calls"] == []


def test_cancelling_requires_csrf(
    resident_api_client: TestClient, passes: dict
) -> None:
    assert resident_api_client.post(f"{PATH}/pass-id/cancel").status_code == 403
    assert passes["calls"] == []


def test_an_admin_may_hold_visitor_passes_too(
    admin_api_client: TestClient, passes: dict
) -> None:
    """No role guard on this surface. An admin has visitors like anyone else, and
    the passes they get back are the ones they raised."""
    admin_api_client.get(PATH)

    assert only(passes, "list_mine")["membership_id"] == "admin-membership-id"


# ---------------------------------------------------------------------------
# The secret appears exactly once
#
# The property the whole feature turns on, and the one an ordinary response
# assertion cannot catch: a test that reads a field never notices a field that
# should not have been there.
# ---------------------------------------------------------------------------


SECRET_FIELDS = ("securityCode", "passToken", "codeHash", "passHash")


def test_creating_returns_the_security_code(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    response = create(resident_api_client, csrf_headers)

    assert response.status_code == 201
    body = response.json()
    assert len(body["securityCode"]) == 6
    assert body["securityCode"].isdigit()
    assert body["passToken"]


def test_the_list_carries_no_secret_on_any_row(
    resident_api_client: TestClient, passes: dict
) -> None:
    item = resident_api_client.get(PATH).json()["items"][0]

    for field in SECRET_FIELDS:
        assert field not in item


def test_reading_one_pass_back_carries_no_secret(
    resident_api_client: TestClient, passes: dict
) -> None:
    """The QR screen's read. A resident who lost the code cannot recover it here
    -- that is the cost §5.4 accepts, and this is the test that keeps it paid."""
    body = resident_api_client.get(f"{PATH}/pass-id").json()

    for field in SECRET_FIELDS:
        assert field not in body


@pytest.mark.parametrize("action", ["approve", "reject", "cancel"])
def test_no_decision_response_carries_a_secret(
    action: str,
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    passes: dict,
) -> None:
    body = resident_api_client.post(
        f"{PATH}/pass-id/{action}", headers=csrf_headers
    ).json()

    for field in SECRET_FIELDS:
        assert field not in body


def test_the_plaintext_code_is_never_sent_to_the_database(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """Not "is hashed before storage" -- *never sent*. There is no statement log,
    slow-query log or replication stream in which it could appear."""
    plaintext = create(resident_api_client, csrf_headers).json()["securityCode"]
    sent = only(passes, "create_pass")

    assert plaintext not in sent.values()
    assert sent["code_hash"] == hash_secret(plaintext)
    assert len(sent["code_hash"]) == 64


def test_the_pass_token_is_hashed_the_same_way(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    token = create(resident_api_client, csrf_headers).json()["passToken"]
    sent = only(passes, "create_pass")

    assert token not in sent.values()
    assert sent["pass_hash"] == hash_secret(token)


def test_two_passes_do_not_get_the_same_code(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """A weak assertion on its own -- two draws from a CSPRNG could collide. It
    is here to catch the strong failure: a constant, or a code derived from the
    request, which is what a hurried implementation produces."""
    codes = {
        create(resident_api_client, csrf_headers).json()["securityCode"]
        for _ in range(12)
    }

    assert len(codes) > 1


def test_the_code_is_drawn_from_the_csprng_not_the_random_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`random` is seeded and predictable to anyone who has seen a few outputs.
    For something that opens a gate, the module is the security property."""
    seen: list[int] = []

    def fake_randbelow(upper: int) -> int:
        seen.append(upper)
        return 0

    monkeypatch.setattr(service.secrets, "randbelow", fake_randbelow)

    assert service._mint_security_code() == "100000"
    assert seen == [900000]


# ---------------------------------------------------------------------------
# What is sent, and what comes back
# ---------------------------------------------------------------------------


def test_the_validity_window_is_not_accepted_from_the_client(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """A resident who could choose it could mint a pass valid for a year. The
    window is the community's TTL setting, applied in the database."""
    create(
        resident_api_client,
        csrf_headers,
        validUntil="2027-01-01T00:00:00Z",
        validFrom="2020-01-01T00:00:00Z",
    )
    sent = only(passes, "create_pass")

    assert "valid_until" not in sent
    assert "valid_from" not in sent


def test_the_expected_arrival_reaches_the_rpc(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    create(resident_api_client, csrf_headers, expectedAt="2026-08-04T16:00:00Z")

    assert only(passes, "create_pass")["expected_at"].startswith("2026-08-04T16:00")


def test_no_expected_arrival_leaves_the_default_to_the_database(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """`None` rather than `now()` computed here: the pass is timestamped against
    the database's clock, which is the same one `validUntil` is measured from."""
    create(resident_api_client, csrf_headers)

    assert only(passes, "create_pass")["expected_at"] is None


def test_a_guest_count_below_one_is_refused(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """The slice does `Math.max(1, ...)` in the browser, which is a display
    default rather than a constraint."""
    assert create(resident_api_client, csrf_headers, guestCount=0).status_code == 422
    assert passes["calls"] == []


# ---------------------------------------------------------------------------
# The name the form does not collect
#
# The resident's pre-approval screen asks for a purpose, a date, a time and a
# guest count. There is no name field on it, and `visitor_name` is `not null`.
# ---------------------------------------------------------------------------


def test_a_pass_can_be_created_without_a_name_because_the_form_has_no_name_field(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    body = {"purpose": "Guest", "guestCount": 3}

    response = resident_api_client.post(PATH, json=body, headers=csrf_headers)

    assert response.status_code == 201
    assert only(passes, "create_pass")["visitor_name"] == "Guest group"


def test_the_derived_name_matches_the_label_the_prototype_builds(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """`createVisitorsSlice.js` uses the free text when the purpose is `Other`
    and the selected option otherwise. One rule, and this is where it lives."""
    create(
        resident_api_client,
        csrf_headers,
        visitorName="",
        purpose="Other",
        purposeDetails="Family event",
    )

    assert only(passes, "create_pass")["visitor_name"] == "Family event group"


def test_other_with_no_detail_still_produces_a_name(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """The column is `not null`; there is no input that may reach it empty."""
    create(resident_api_client, csrf_headers, visitorName="", purpose="Other")

    assert only(passes, "create_pass")["visitor_name"] == "Other group"


def test_a_whitespace_only_name_derives_rather_than_failing(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """Trimmed to empty by the schema, so it takes the same path as absent --
    rather than a 422 about a field the caller was never asked to send."""
    create(resident_api_client, csrf_headers, visitorName="   ", purpose="Service")

    assert only(passes, "create_pass")["visitor_name"] == "Service group"


def test_a_name_that_is_supplied_is_the_one_used(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """The gate's own screen does collect a name. Nothing is derived over it."""
    create(resident_api_client, csrf_headers, visitorName="Anita Rao")

    assert only(passes, "create_pass")["visitor_name"] == "Anita Rao"


# ---------------------------------------------------------------------------
# A code the community is already using
#
# `0032` makes `(community_id, code_hash)` unique across live passes. Six digits
# in one community's live set will collide eventually, and the database cannot
# resolve it -- it holds a hash and no way back to a code. Re-minting can only
# happen where the plaintext is.
# ---------------------------------------------------------------------------


def _duplicate() -> ConflictError:
    return ConflictError("duplicate", code="unique_violation")


def test_a_colliding_code_is_redrawn_rather_than_reported(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    passes["create_errors"] = [_duplicate()]

    response = create(resident_api_client, csrf_headers)
    attempts = every(passes, "create_pass")

    assert response.status_code == 201
    assert len(attempts) == 2


def test_the_redraw_is_a_new_code_not_the_same_one_again(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """Retrying the same hash would be a slower way to fail the same way."""
    passes["create_errors"] = [_duplicate()]

    create(resident_api_client, csrf_headers)
    first, second = every(passes, "create_pass")

    assert first["code_hash"] != second["code_hash"]


def test_the_token_is_not_reminted_with_the_code(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """32 bytes from the CSPRNG do not collide. Only the six digits are redrawn,
    so the QR handle a client is about to be handed stays the one that was
    minted for it."""
    passes["create_errors"] = [_duplicate()]

    create(resident_api_client, csrf_headers)
    first, second = every(passes, "create_pass")

    assert first["pass_hash"] == second["pass_hash"]


def test_the_redraw_gives_up_rather_than_looping_forever(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """An unbounded retry against a full code space is an outage, not a retry."""
    passes["create_errors"] = [_duplicate() for _ in range(service._CODE_ATTEMPTS)]

    response = create(resident_api_client, csrf_headers)

    assert response.status_code == 409
    assert len(every(passes, "create_pass")) == service._CODE_ATTEMPTS


def test_a_conflict_that_is_not_a_duplicate_key_is_not_retried(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    """Every other conflict is a fact about the request, and a fresh code would
    not change it."""
    passes["create_errors"] = [ConflictError("used", code="pass_already_used")]

    response = create(resident_api_client, csrf_headers)

    assert response.status_code == 409
    assert len(every(passes, "create_pass")) == 1


@pytest.mark.parametrize(
    ("action", "decision"),
    [("approve", "approve"), ("reject", "reject"), ("cancel", "cancel")],
)
def test_each_route_sends_its_own_decision(
    action: str,
    decision: str,
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    passes: dict,
) -> None:
    resident_api_client.post(f"{PATH}/pass-id/{action}", headers=csrf_headers)

    assert only(passes, "decide")["decision"] == decision


def test_a_decision_reads_the_pass_back_rather_than_assuming_the_state(
    resident_api_client: TestClient, csrf_headers: dict[str, str], passes: dict
) -> None:
    passes["detail"] = row(status="cancelled", is_current=False)

    body = resident_api_client.post(
        f"{PATH}/pass-id/cancel", headers=csrf_headers
    ).json()

    assert body["status"] == "Cancelled"
    assert body["isCurrent"] is False


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_the_current_tab_filters_on_the_computed_column(
    resident_api_client: TestClient, passes: dict
) -> None:
    resident_api_client.get(f"{PATH}?view=current")

    assert only(passes, "list_mine")["current"] is True


def test_the_history_tab_is_the_same_column_inverted(
    resident_api_client: TestClient, passes: dict
) -> None:
    resident_api_client.get(f"{PATH}?view=history")

    assert only(passes, "list_mine")["current"] is False


def test_no_view_returns_both(resident_api_client: TestClient, passes: dict) -> None:
    resident_api_client.get(PATH)

    assert only(passes, "list_mine")["current"] is None


def test_an_unknown_view_is_the_unfiltered_list_not_a_422(
    resident_api_client: TestClient, passes: dict
) -> None:
    """Unlike the complaint status filter, and deliberately. `view` is a tab
    selector with two known values; the honest answer to a third is everything,
    not a 422 about a parameter the caller did not mean to constrain."""
    response = resident_api_client.get(f"{PATH}?view=nonsense")

    assert response.status_code == 200
    assert only(passes, "list_mine")["current"] is None


# ---------------------------------------------------------------------------
# The projection
# ---------------------------------------------------------------------------


def project(**overrides: Any) -> dict[str, Any]:
    return service._to_pass(row(**overrides)).model_dump(by_alias=True)


def test_denied_reads_as_rejected() -> None:
    """The one status where the column and the screen genuinely disagree. Every
    view in the prototype says `Rejected`; the enum says `denied`."""
    assert project(status="denied")["status"] == "Rejected"


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        ("expected", "Expected"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("checked_in", "Checked In"),
        ("checked_out", "Checked Out"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ],
)
def test_every_other_status_round_trips(stored: str, shown: str) -> None:
    assert project(status=stored)["status"] == shown


def test_an_unknown_status_renders_rather_than_breaking_the_list() -> None:
    assert project(status="teleported")["status"] == "Expected"


def test_a_missing_purpose_reads_as_guest() -> None:
    assert project(purpose=None)["purpose"] == "Guest"


def test_a_lapsed_pass_is_surfaced_as_its_own_fact() -> None:
    """Still open, past its window. The client should say *lapsed* rather than
    leaving a resident to compare two timestamps."""
    assert project(is_lapsed=True, is_current=False)["isLapsed"] is True


# ---------------------------------------------------------------------------
# What the queries are pointed at
# ---------------------------------------------------------------------------


class _RecordingQuery:
    def __init__(self, call: dict[str, Any]) -> None:
        self._call = call

    def select(self, columns: str, count: str | None = None) -> _RecordingQuery:
        self._call["columns"] = columns
        self._call["count"] = count
        return self

    def eq(self, column: str, value: Any) -> _RecordingQuery:
        self._call.setdefault("filters", {})[column] = value
        return self

    def order(self, column: str, desc: bool = False) -> _RecordingQuery:
        self._call["order"] = (column, desc)
        return self

    def range(self, start: int, end: int) -> _RecordingQuery:
        self._call["range"] = (start, end)
        return self

    def limit(self, count: int) -> _RecordingQuery:
        self._call["limit"] = count
        return self

    def execute(self) -> Any:
        return type("Result", (), {"data": [], "count": 0})()


class _RecordingClient:
    def __init__(self) -> None:
        self.call: dict[str, Any] = {}

    def table(self, name: str) -> _RecordingQuery:
        self.call["relation"] = name
        return _RecordingQuery(self.call)


def test_the_list_is_read_from_the_overview_view() -> None:
    client = _RecordingClient()

    resident_visitor_passes_repository.list_mine(
        client, membership_id="m", current=None, offset=0, limit=20
    )

    assert client.call["relation"] == "visitor_pass_overview"


def test_neither_hash_is_ever_selected() -> None:
    """The columns exist on `visitor_requests`. They are not on the view, and
    they are not asked for -- so no refactor of this query can start returning
    one."""
    client = _RecordingClient()

    resident_visitor_passes_repository.list_mine(
        client, membership_id="m", current=None, offset=0, limit=20
    )

    assert "code_hash" not in client.call["columns"]
    assert "pass_hash" not in client.call["columns"]


def test_the_list_filters_on_the_callers_membership() -> None:
    client = _RecordingClient()

    resident_visitor_passes_repository.list_mine(
        client, membership_id="membership-id", current=None, offset=0, limit=20
    )

    assert client.call["filters"] == {"requested_by_membership_id": "membership-id"}
    assert client.call["order"] == ("created_at", True)


def test_one_pass_is_looked_up_by_id_and_owner_together() -> None:
    """So a pass belonging to someone else cannot be told from one that does not
    exist -- not by status code, and not by response time."""
    client = _RecordingClient()

    resident_visitor_passes_repository.get_mine(
        client, membership_id="membership-id", pass_id="pass-id"
    )

    assert client.call["filters"] == {
        "id": "pass-id",
        "requested_by_membership_id": "membership-id",
    }


# ---------------------------------------------------------------------------
# Errors out of the service
# ---------------------------------------------------------------------------


def test_a_missing_pass_is_a_not_found() -> None:
    class _Empty:
        def table(self, name: str) -> Any:
            return _RecordingQuery({})

    with pytest.raises(NotFoundError):
        service.get_mine(_Empty(), membership_id="m", pass_id="nope")
