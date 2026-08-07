"""The resident complaint surface -- six operations and one projection.

Three groups, kept apart because they answer different questions.

The **HTTP surface**: who may call each route, that the caller's own membership
is the only scope, and that a complaint belonging to someone else is
indistinguishable from one that does not exist. The repository is replaced, so
nothing reaches Supabase and the assertions are about arguments rather than rows.

The **projection**: what a `complaint_overview` row becomes on the wire, and what
a timeline event becomes as a sentence. Those go through the service directly --
routing a row shape through a request would put noise between the input and the
assertion.

The **query shape**: a recording stand-in for the Supabase client, asserting the
relation and the predicates. Everything above replaces the repository, so nothing
above would notice if the read were pointed at `complaints` instead of the view,
or if the ownership predicate were dropped -- which is the mistake that matters
most here.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories import resident_complaints_repository
from app.services import resident_complaints_service as service

PATH = "/api/v1/complaints"


def row(**overrides: Any) -> dict[str, Any]:
    """A complete `complaint_overview` row, as PostgREST would return it."""
    base: dict[str, Any] = {
        "id": "complaint-id",
        "title": "Lift stuck between floors",
        "description": "The B-block lift has been stopping between 3 and 4.",
        "category": "Elevator",
        "status": "in_progress",
        "priority": "high",
        "location": "B Block",
        "progress_percent": 40,
        "assignee_label": "Ravi Kumar",
        "created_at": "2026-08-01T09:00:00+00:00",
        "updated_at": "2026-08-02T09:00:00+00:00",
        "last_activity_at": "2026-08-02T09:00:00+00:00",
        "expected_resolution_at": "2026-08-02T09:00:00+00:00",
        "resolved_at": None,
        "is_overdue": False,
        "is_unread": True,
        "reopened_count": 0,
        "comment_count": 2,
        "resolution_rating": None,
        "resident_feedback": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def complaints(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace every repository call. Records arguments, returns what is staged."""
    captured: dict = {
        "rows": [row()],
        "total": None,
        "detail": row(),
        # Staged in the order the repository returns them: **newest first**. The
        # service reverses them for display, so a test that stages them
        # chronologically would be asserting against a list the repository never
        # produces.
        "events": [],
        "comments": [],
        "events_truncated": False,
        "comments_truncated": False,
        "calls": [],
    }

    def fake_list_mine(client: Any, **kwargs: Any) -> tuple[list[dict], int]:
        captured["calls"].append(("list_mine", kwargs))
        rows = captured["rows"]
        total = captured["total"]
        return rows, (len(rows) if total is None else total)

    def fake_get_mine(client: Any, **kwargs: Any) -> dict[str, Any] | None:
        captured["calls"].append(("get_mine", kwargs))
        return captured["detail"]

    def fake_timeline(client: Any, **kwargs: Any) -> tuple[list[dict], bool]:
        captured["calls"].append(("timeline", kwargs))
        return captured["events"], captured["events_truncated"]

    def fake_comments(client: Any, **kwargs: Any) -> tuple[list[dict], bool]:
        captured["calls"].append(("comments", kwargs))
        return captured["comments"], captured["comments_truncated"]

    def fake_raise(client: Any, **kwargs: Any) -> str:
        captured["calls"].append(("raise_complaint", kwargs))
        return "new-complaint-id"

    def fake_reopen(client: Any, **kwargs: Any) -> None:
        captured["calls"].append(("reopen", kwargs))

    def fake_confirm(client: Any, **kwargs: Any) -> None:
        captured["calls"].append(("confirm_resolution", kwargs))

    def fake_mark_read(client: Any, **kwargs: Any) -> None:
        captured["calls"].append(("mark_read", kwargs))

    for name, replacement in {
        "list_mine": fake_list_mine,
        "get_mine": fake_get_mine,
        "timeline": fake_timeline,
        "comments": fake_comments,
        "raise_complaint": fake_raise,
        "reopen": fake_reopen,
        "confirm_resolution": fake_confirm,
        "mark_read": fake_mark_read,
    }.items():
        monkeypatch.setattr(resident_complaints_repository, name, replacement)
    return captured


def only(captured: dict, name: str) -> dict[str, Any]:
    """The keyword arguments of the single call to ``name``."""
    matches = [kwargs for call, kwargs in captured["calls"] if call == name]
    assert len(matches) == 1, f"expected one {name} call, saw {len(matches)}"
    return matches[0]


# ---------------------------------------------------------------------------
# The guards
# ---------------------------------------------------------------------------


def test_the_list_requires_a_session(api_client: TestClient) -> None:
    assert api_client.get(PATH).status_code == 401


def test_a_resident_may_list_their_complaints(
    resident_api_client: TestClient, complaints: dict
) -> None:
    response = resident_api_client.get(PATH)

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Lift stuck between floors"


def test_an_admin_listing_gets_their_own_complaints_not_the_queue(
    admin_api_client: TestClient, complaints: dict
) -> None:
    """The route is scoped to the caller whatever their role. One path that
    answers `mine` for one caller and `everyone's` for another is the shape 5.1
    exists to prevent; the admin queue is `GET /dashboard/snapshot`."""
    admin_api_client.get(PATH)

    assert only(complaints, "list_mine")["membership_id"] == "admin-membership-id"


def test_reopening_is_refused_to_an_admin(
    admin_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    """Not because an admin could not press the button, but because reopening is
    the resident's verdict on the association's work."""
    response = admin_api_client.post(
        f"{PATH}/complaint-id/reopen",
        json={"reason": "Still broken"},
        headers=csrf_headers,
    )

    assert response.status_code == 403
    assert complaints["calls"] == []


def test_confirming_a_resolution_is_refused_to_an_admin(
    admin_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    response = admin_api_client.post(
        f"{PATH}/complaint-id/resolution",
        json={"rating": 5},
        headers=csrf_headers,
    )

    assert response.status_code == 403


def test_raising_requires_csrf(
    resident_api_client: TestClient, complaints: dict
) -> None:
    response = resident_api_client.post(
        PATH, json={"title": "T", "category": "Water"}
    )

    assert response.status_code == 403
    assert complaints["calls"] == []


# ---------------------------------------------------------------------------
# Tenancy and scope
# ---------------------------------------------------------------------------


def test_the_membership_comes_from_the_session_not_the_request(
    resident_api_client: TestClient, complaints: dict
) -> None:
    resident_api_client.get(f"{PATH}?membershipId=someone-else")

    assert only(complaints, "list_mine")["membership_id"] == "resident-membership-id"


def test_reading_one_complaint_is_scoped_to_the_caller(
    resident_api_client: TestClient, complaints: dict
) -> None:
    """The membership is part of the lookup, not a check afterwards. There is no
    code path in which "not yours" and "not there" could be told apart."""
    resident_api_client.get(f"{PATH}/complaint-id")

    call = only(complaints, "get_mine")
    assert call["membership_id"] == "resident-membership-id"
    assert call["complaint_id"] == "complaint-id"


def test_someone_elses_complaint_is_a_404(
    resident_api_client: TestClient, complaints: dict
) -> None:
    complaints["detail"] = None

    response = resident_api_client.get(f"{PATH}/not-mine")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Raising
# ---------------------------------------------------------------------------


def test_raising_a_complaint_returns_the_created_complaint(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    """201 and the detail, not an acknowledgement: the response carries the SLA
    deadline the database computed, which the client could not have known."""
    response = resident_api_client.post(
        PATH,
        json={
            "title": "Lift stuck between floors",
            "description": "Stopping between 3 and 4.",
            "category": "Elevator",
            "urgency": "High",
            "location": "B Block",
        },
        headers=csrf_headers,
    )

    assert response.status_code == 201
    assert response.json()["expectedResolutionAt"] is not None


def test_the_urgency_is_translated_to_the_stored_priority(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    resident_api_client.post(
        PATH,
        json={"title": "T", "category": "Water", "urgency": "High"},
        headers=csrf_headers,
    )

    assert only(complaints, "raise_complaint")["priority"] == "high"


def test_an_unknown_urgency_is_refused_rather_than_defaulted(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    """A silent default would file the complaint under a deadline the resident
    did not choose, and the form would show no sign of it."""
    response = resident_api_client.post(
        PATH,
        json={"title": "T", "category": "Water", "urgency": "Urgent"},
        headers=csrf_headers,
    )

    assert response.status_code == 422
    assert not [c for c, _ in complaints["calls"] if c == "raise_complaint"]


def test_a_whitespace_only_title_is_refused_at_the_edge(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    """The database refuses it too, correctly. The model refuses it first, so
    the caller gets a 422 naming the field rather than one raised three layers
    in -- which is what `min_length` alone would have produced, since three
    spaces satisfy it."""
    response = resident_api_client.post(
        PATH, json={"title": "   ", "category": "Water"}, headers=csrf_headers
    )

    assert response.status_code == 422
    assert complaints["calls"] == []


def test_the_client_cannot_send_its_own_sla(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    """The rule the frontend store carries is a product decision applied in the
    database. A resident who could send this could send themselves a one-minute
    deadline."""
    resident_api_client.post(
        PATH,
        json={
            "title": "T",
            "category": "Water",
            "expectedResolutionAt": "2026-08-04T09:01:00Z",
        },
        headers=csrf_headers,
    )

    assert "expected_resolution_at" not in only(complaints, "raise_complaint")


# ---------------------------------------------------------------------------
# Reopening, confirming, marking read
# ---------------------------------------------------------------------------


def test_reopening_passes_the_reason_through(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    resident_api_client.post(
        f"{PATH}/complaint-id/reopen",
        json={"reason": "  The lift stopped again  "},
        headers=csrf_headers,
    )

    assert only(complaints, "reopen")["reason"] == "The lift stopped again"


def test_reopening_without_a_reason_is_refused(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    response = resident_api_client.post(
        f"{PATH}/complaint-id/reopen", json={"reason": ""}, headers=csrf_headers
    )

    assert response.status_code == 422


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_a_rating_outside_one_to_five_is_refused(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    complaints: dict,
    rating: int,
) -> None:
    response = resident_api_client.post(
        f"{PATH}/complaint-id/resolution",
        json={"rating": rating},
        headers=csrf_headers,
    )

    assert response.status_code == 422


def test_confirming_without_feedback_is_a_complete_answer(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    response = resident_api_client.post(
        f"{PATH}/complaint-id/resolution",
        json={"rating": 4},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    assert only(complaints, "confirm_resolution")["feedback"] == ""


def test_marking_read_is_scoped_to_the_callers_own_membership(
    resident_api_client: TestClient, csrf_headers: dict[str, str], complaints: dict
) -> None:
    """Per membership, so an admin opening a complaint cannot clear the
    resident's marker."""
    response = resident_api_client.post(
        f"{PATH}/complaint-id/read", headers=csrf_headers
    )

    assert response.status_code == 200
    assert only(complaints, "mark_read")["membership_id"] == "resident-membership-id"


# ---------------------------------------------------------------------------
# Filtering and paging
# ---------------------------------------------------------------------------


def test_a_status_filter_is_translated_before_it_reaches_the_query(
    resident_api_client: TestClient, complaints: dict
) -> None:
    """And to **every** stored status that renders as the word asked for.
    `acknowledged` and `in_progress` both display as `In Progress`; a filter
    carrying only the second hides rows the same list shows under the caller's
    own word."""
    resident_api_client.get(f"{PATH}?status=In%20Progress")

    assert sorted(only(complaints, "list_mine")["statuses"]) == [
        "acknowledged",
        "in_progress",
    ]


def test_filtering_by_resolved_finds_complaints_the_resident_has_closed(
    resident_api_client: TestClient, complaints: dict
) -> None:
    """`closed` renders as `Resolved` -- it is what a complaint becomes when the
    resident confirms it. Filtering with the write-side map would have returned a
    list missing exactly the complaints they had finished with, which reads as
    lost data rather than as a filter."""
    resident_api_client.get(f"{PATH}?status=Resolved")

    assert sorted(only(complaints, "list_mine")["statuses"]) == [
        "closed",
        "resolved",
    ]


def test_an_unknown_status_filter_is_a_422_not_an_empty_page(
    resident_api_client: TestClient, complaints: dict
) -> None:
    """An empty page is what "you have no resolved complaints" looks like. A
    filter typo must not be indistinguishable from a true answer."""
    response = resident_api_client.get(f"{PATH}?status=Nonsense")

    assert response.status_code == 422
    assert complaints["calls"] == []


def test_the_unread_filter_reaches_the_query(
    resident_api_client: TestClient, complaints: dict
) -> None:
    resident_api_client.get(f"{PATH}?unread=true")

    assert only(complaints, "list_mine")["unread_only"] is True


def test_a_later_page_offsets_rather_than_re_reading_the_first(
    resident_api_client: TestClient, complaints: dict
) -> None:
    resident_api_client.get(f"{PATH}?page=3&pageSize=10")

    assert only(complaints, "list_mine")["offset"] == 20


def test_has_more_is_true_while_rows_remain(
    resident_api_client: TestClient, complaints: dict
) -> None:
    complaints["rows"] = [row(id=f"c-{index}") for index in range(20)]
    complaints["total"] = 41

    body = resident_api_client.get(PATH).json()

    assert body["total"] == 41
    assert body["hasMore"] is True


def test_an_empty_list_is_a_page_not_a_404(
    resident_api_client: TestClient, complaints: dict
) -> None:
    complaints["rows"] = []

    response = resident_api_client.get(PATH)

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["hasMore"] is False


# ---------------------------------------------------------------------------
# The projection
# ---------------------------------------------------------------------------


def project(**overrides: Any) -> dict[str, Any]:
    """One row through the summary mapper, as it would go on the wire."""
    return service._to_summary(row(**overrides)).model_dump(by_alias=True)


def test_the_stored_status_becomes_the_frontend_word() -> None:
    assert project(status="in_progress")["status"] == "In Progress"
    assert project(status="open")["status"] == "Pending"


def test_closed_renders_as_resolved() -> None:
    """The frontend's select has three options and closed is not one of them.
    The database keeps a distinction the UI does not show."""
    assert project(status="closed")["status"] == "Resolved"


def test_an_unknown_status_renders_rather_than_raising() -> None:
    """A status this map has not heard of means the enum grew. A complaint list
    that refuses to render is a worse answer than one optimistic row."""
    assert project(status="escalated")["status"] == "Pending"


def test_the_priority_becomes_the_forms_urgency() -> None:
    assert project(priority="high")["urgency"] == "High"


def test_an_unassigned_complaint_says_so() -> None:
    assert project(assignee_label=None)["assignee"] == "Unassigned"


def test_null_text_reads_as_empty_string_not_null() -> None:
    item = project(location=None)
    assert item["location"] == ""


def test_a_missing_category_falls_back_to_general() -> None:
    assert project(category=None)["category"] == "General"


def test_the_response_carries_no_internal_identifiers() -> None:
    """A resident shown a membership id learns an identifier they have no
    endpoint for, and `departmentId` is who inside the association is carrying
    the work."""
    item = project()
    for field in ("raisedByMembershipId", "communityId", "departmentId"):
        assert field not in item


def test_the_detail_extends_the_summary_rather_than_restating_it() -> None:
    """So a field can never be present in a list row and missing from the detail
    of the same complaint."""
    detail = service._to_detail(
        row(),
        events=[],
        events_truncated=False,
        thread=[],
        thread_truncated=False,
    ).model_dump(by_alias=True)
    for field in project():
        assert field in detail


# ---------------------------------------------------------------------------
# The timeline
# ---------------------------------------------------------------------------


def event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "event-id",
        "event_type": event_type,
        "actor_label": "Ravi Kumar",
        "payload": payload,
        "created_at": "2026-08-02T09:00:00+00:00",
    }


def message(event_type: str, payload: dict[str, Any]) -> str:
    return service._to_event(event(event_type, payload)).message


def test_a_status_change_reads_in_the_frontends_vocabulary() -> None:
    """Not `open -> in_progress`. The timeline is read by the resident, and the
    words on it should be the words on the rest of the screen."""
    assert message("status_changed", {"from": "open", "to": "in_progress"}) == (
        "Status changed from Pending to In Progress."
    )


def test_a_reopen_shows_the_residents_reason() -> None:
    assert message("reopened", {"reason": "The lift stopped again"}) == (
        "The lift stopped again"
    )


def test_a_comment_event_says_nothing_because_the_comment_is_in_the_thread() -> None:
    assert message("comment_added", {"comment_id": "x", "visibility": "public"}) == ""


def test_an_unknown_event_type_renders_an_empty_message_not_a_payload_dump() -> None:
    """A generic dump would put whatever a future writer stored -- including, one
    day, something not meant for the person who raised the complaint -- straight
    onto their screen."""
    assert message("escalated", {"internal_note": "chase the vendor"}) == ""


def test_an_internal_comment_leaves_no_shadow_on_the_timeline() -> None:
    """`0020` writes a timeline event for every comment, internal ones included,
    and the policy on `complaint_events` scopes rows to the complaint rather than
    to visibility -- so the event reaches this surface even though the comment
    does not. A row saying a comment exists, leading to a thread where nothing
    new is visible, tells the resident something was said and refuses to say
    what."""
    detail = service._to_detail(
        row(),
        # Newest first, as the repository returns them.
        events=[
            event("note_added", {"note": "Technician booked"}),
            event("comment_added", {"comment_id": "b", "visibility": "internal"}),
            event("comment_added", {"comment_id": "a", "visibility": "public"}),
        ],
        events_truncated=False,
        thread=[],
        thread_truncated=False,
    )

    assert len(detail.timeline) == 2
    assert [entry.type for entry in detail.timeline] == [
        "comment_added",
        "note_added",
    ]


def test_an_event_with_no_actor_label_reads_as_management() -> None:
    raw = event("note_added", {"note": "Technician booked"})
    raw["actor_label"] = None

    assert service._to_event(raw).actor == "Management"


def test_a_payload_that_is_not_an_object_does_not_break_the_timeline() -> None:
    raw = event("note_added", {})
    raw["payload"] = None

    assert service._to_event(raw).message == ""


def test_an_event_carries_a_readable_heading_as_well_as_its_raw_type() -> None:
    """Both, not one. The client keys behaviour off `type`, which never changes;
    the resident reads `label`, which is free to."""
    rendered = service._to_event(event("status_changed", {"from": "open"}))

    assert rendered.type == "status_changed"
    assert rendered.label == "Status changed"


def test_an_unknown_event_type_falls_back_to_the_type_as_its_heading() -> None:
    """A timeline that silently omits an entry is worse than one with an ugly
    row: the gap is invisible and the ugly row is a bug report."""
    assert service._to_event(event("escalated", {})).label == "escalated"


def test_a_truncated_timeline_says_so_rather_than_looking_complete(
    resident_api_client: TestClient, complaints: dict
) -> None:
    """The one kind of truncation a client cannot detect for itself."""
    complaints["events_truncated"] = True

    body = resident_api_client.get(f"{PATH}/complaint-id").json()

    assert body["hasOlderEvents"] is True
    assert body["hasOlderComments"] is False


def test_a_complete_timeline_does_not_claim_missing_history(
    resident_api_client: TestClient, complaints: dict
) -> None:
    body = resident_api_client.get(f"{PATH}/complaint-id").json()

    assert body["hasOlderEvents"] is False
    assert body["hasOlderComments"] is False


def test_the_detail_puts_the_timeline_back_into_reading_order(
    resident_api_client: TestClient, complaints: dict
) -> None:
    """The repository reads newest-first so the bound keeps the recent end; the
    screen reads downwards. The reversal happens once, in the service."""
    first = event("raised", {})
    first["created_at"] = "2026-08-01T09:00:00+00:00"
    latest = event("note_added", {"note": "Technician booked"})
    latest["created_at"] = "2026-08-03T09:00:00+00:00"
    complaints["events"] = [latest, first]

    body = resident_api_client.get(f"{PATH}/complaint-id").json()

    assert [entry["type"] for entry in body["timeline"]] == ["raised", "note_added"]


# ---------------------------------------------------------------------------
# What the queries are pointed at
#
# Everything above replaces the repository, so nothing above would notice if the
# read were pointed at `complaints` rather than the view, or if the ownership
# predicate were dropped. These go the other way.
# ---------------------------------------------------------------------------


class _RecordingQuery:
    """Records a PostgREST builder chain instead of issuing it."""

    def __init__(self, call: dict[str, Any]) -> None:
        self._call = call

    def select(self, columns: str, count: str | None = None) -> _RecordingQuery:
        self._call["columns"] = columns
        self._call["count"] = count
        return self

    def eq(self, column: str, value: Any) -> _RecordingQuery:
        self._call.setdefault("filters", {})[column] = value
        return self

    def in_(self, column: str, values: list[Any]) -> _RecordingQuery:
        self._call.setdefault("filters", {})[column] = list(values)
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

    resident_complaints_repository.list_mine(
        client,
        membership_id="membership-id",
        statuses=None,
        category=None,
        unread_only=False,
        offset=0,
        limit=20,
    )

    assert client.call["relation"] == "complaint_overview"


def test_the_list_filters_on_the_callers_membership() -> None:
    """Not the security boundary -- `0031` puts a policy on `complaints` -- but
    the difference between "mine" and "everything I may see"."""
    client = _RecordingClient()

    resident_complaints_repository.list_mine(
        client,
        membership_id="membership-id",
        statuses=None,
        category=None,
        unread_only=False,
        offset=0,
        limit=20,
    )

    assert client.call["filters"] == {"raised_by_membership_id": "membership-id"}
    assert client.call["order"] == ("created_at", True)


def test_one_complaint_is_looked_up_by_id_and_owner_together() -> None:
    client = _RecordingClient()

    resident_complaints_repository.get_mine(
        client, membership_id="membership-id", complaint_id="complaint-id"
    )

    assert client.call["filters"] == {
        "id": "complaint-id",
        "raised_by_membership_id": "membership-id",
    }


def test_the_comment_thread_asks_for_public_comments_only() -> None:
    """The RLS policy is what makes it true. This predicate is what makes it
    obvious to the next person reading the query."""
    client = _RecordingClient()

    resident_complaints_repository.comments(client, complaint_id="complaint-id")

    assert client.call["filters"]["visibility"] == "public"


def test_the_timeline_reads_the_newest_end_even_though_it_displays_oldest_first(
) -> None:
    """The order and the bound are not independent choices. Ordering ascending
    and stopping at the limit keeps the *opening* of a long complaint and throws
    away everything since -- so on the one screen where the bound would ever
    bite, the resident sees a complaint frozen on the day they raised it. The
    service reverses these rows; the query keeps the end that matters."""
    client = _RecordingClient()

    resident_complaints_repository.timeline(client, complaint_id="complaint-id")

    assert client.call["order"] == ("created_at", True)


def test_the_thread_reads_one_row_past_the_bound() -> None:
    """A read of exactly the limit cannot be told from a truncated one. The extra
    row is what turns `hasOlderEvents` into something measured."""
    client = _RecordingClient()

    resident_complaints_repository.comments(client, complaint_id="complaint-id")

    assert client.call["limit"] == resident_complaints_repository._THREAD_LIMIT + 1


def test_a_thread_longer_than_the_bound_reports_that_it_was_cut() -> None:
    rows = [{"id": str(index)} for index in range(202)]
    kept, truncated = resident_complaints_repository._bounded(rows)

    assert truncated is True
    assert len(kept) == resident_complaints_repository._THREAD_LIMIT


def test_a_thread_of_exactly_the_bound_is_not_reported_as_cut() -> None:
    """The off-by-one that would make every busy complaint claim missing
    history."""
    rows = [{"id": str(index)} for index in range(200)]
    kept, truncated = resident_complaints_repository._bounded(rows)

    assert truncated is False
    assert len(kept) == 200


# ---------------------------------------------------------------------------
# Errors out of the service
# ---------------------------------------------------------------------------


def test_the_service_raises_not_found_for_a_missing_complaint() -> None:
    class _Empty:
        def table(self, name: str) -> Any:
            return _RecordingQuery({})

    with pytest.raises(NotFoundError):
        service.get_mine(
            _Empty(), membership_id="membership-id", complaint_id="nope"
        )


def test_the_service_refuses_an_unknown_status_filter() -> None:
    with pytest.raises(ValidationError):
        service.list_mine(object(), membership_id="m", status="Nonsense")
