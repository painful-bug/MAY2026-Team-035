"""`GET /amenities/available` -- the resident amenity catalogue.

Two things are being tested and they are worth keeping apart.

The **HTTP surface**: who may call it, which community it reads, and the fact
that the response cannot carry an admin field. The repository is replaced so
nothing touches Supabase; the substitute records its arguments, which is how the
tenancy assertions are made -- checking that the community reaching the query is
the one the membership resolved, not something a caller supplied.

The **projection**: what a database row becomes. Those tests go through the
service directly rather than over HTTP, because the interesting cases are row
shapes (a null capacity, a zero maximum, a closure written as an empty object)
and routing one through a request would only add noise between the input and the
assertion.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.repositories import resident_amenities_repository
from app.services import resident_amenities_service

PATH = "/api/v1/amenities/available"


def row(**overrides: Any) -> dict[str, Any]:
    """A complete amenity row, as PostgREST would return it.

    Spelled out in full rather than built from defaults so a test that overrides
    one field still shows what the other twenty-four were.
    """
    base: dict[str, Any] = {
        "id": "amenity-id",
        "name": "Community Hall",
        "description": "Ground floor, seats 80",
        "category": "Hall",
        "location": "Block A",
        "image_url": "https://example.test/hall.jpg",
        "capacity": 80,
        "booking_mode": "exclusive",
        "approval_required": True,
        "opening_time": "06:00:00",
        "closing_time": "22:00:00",
        "slot_duration_minutes": 60,
        "minimum_booking_duration_minutes": 60,
        "maximum_booking_duration_minutes": 180,
        "advance_booking_window_days": 30,
        "max_active_bookings_per_resident": 2,
        "closed_days": [7],
        "allow_private_booking": True,
        "allow_guest_booking": True,
        "allow_recurring_booking": False,
        "allow_same_day_booking": False,
        "booking_fee": "500.00",
        "security_deposit": "2000.00",
        "currency_code": "inr",
        "refund_policy": "Full refund up to 48 hours before",
        "temporary_closure": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def catalogue(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace the query. Records its arguments and returns whatever is staged."""
    captured: dict = {"rows": [row()], "total": None}

    def fake_list_bookable(
        client: Any, community_id: str
    ) -> tuple[list[dict[str, Any]], int]:
        captured["client"] = client
        captured["community_id"] = community_id
        rows = captured["rows"]
        # `total` stays None unless a test is about truncation, so every other
        # test in this file describes the ordinary case: the bound was not
        # reached and the count agrees with the rows.
        total = captured["total"]
        return rows, (len(rows) if total is None else total)

    # One patch covers both call sites: the service imports the module, not the
    # function, so `repo.list_bookable` resolves at call time.
    monkeypatch.setattr(
        resident_amenities_repository, "list_bookable", fake_list_bookable
    )
    return captured


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


def test_the_catalogue_requires_a_session(api_client: TestClient) -> None:
    assert api_client.get(PATH).status_code == 401


def test_a_resident_may_read_the_catalogue(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    """The whole point of the endpoint. Before it, the only path to an amenity
    id was `GET /dashboard/snapshot`, which a resident is refused."""
    response = resident_api_client.get(PATH)

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Community Hall"


def test_an_admin_may_read_the_catalogue_too(
    admin_api_client: TestClient, catalogue: dict
) -> None:
    """The guard is any active membership, not `resident`. Nothing in this
    response is per-resident, so there is nothing role-shaped to scope."""
    assert admin_api_client.get(PATH).status_code == 200


def test_the_community_comes_from_the_membership(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    """Tenancy is the community `get_active_membership` resolved out of
    Postgres. There is no community parameter on this route, so this is the only
    value that can reach the query."""
    resident_api_client.get(PATH)

    assert catalogue["community_id"] == "community-id"


def test_an_unknown_query_parameter_cannot_widen_the_read(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    """FastAPI ignores undeclared query parameters rather than rejecting them,
    so the guarantee has to be that nothing reads them -- not that nobody sends
    them."""
    resident_api_client.get(f"{PATH}?communityId=someone-elses-community")

    assert catalogue["community_id"] == "community-id"


# ---------------------------------------------------------------------------
# What the response may and may not contain
# ---------------------------------------------------------------------------


def test_the_response_carries_no_admin_figures(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    """`pendingRequests` and `outstandingDues` are on the admin card and are the
    reason this projection is a separate model. If either ever appears here, the
    endpoint has been pointed at `amenity_overview`."""
    item = resident_api_client.get(PATH).json()["items"][0]

    for field in ("pendingRequests", "outstandingDues", "maintenanceNotes", "version"):
        assert field not in item


def test_the_response_is_camel_case(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    item = resident_api_client.get(PATH).json()["items"][0]

    assert item["requiresApproval"] is True
    assert item["slotDurationMinutes"] == 60
    assert "requires_approval" not in item


def test_an_empty_catalogue_is_a_page_not_a_404(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    catalogue["rows"] = []

    response = resident_api_client.get(PATH)

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "pageSize": 0,
        "hasMore": False,
    }


def test_the_page_reports_the_whole_catalogue(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    """Unpaged on purpose -- `hasMore` false means the client has everything."""
    catalogue["rows"] = [row(id=f"amenity-{index}") for index in range(3)]

    body = resident_api_client.get(PATH).json()

    assert body["total"] == 3
    assert body["hasMore"] is False
    assert body["page"] == 1


def test_a_truncated_catalogue_says_so_rather_than_claiming_completeness(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    """The read is bounded. If the bound ever cuts the catalogue short, the
    envelope has to say so: `hasMore: false` over a truncated list is the
    endpoint claiming completeness it did not check, and a client has no way to
    detect it."""
    catalogue["rows"] = [row(id=f"amenity-{index}") for index in range(3)]
    catalogue["total"] = 9

    body = resident_api_client.get(PATH).json()

    assert len(body["items"]) == 3
    assert body["total"] == 9
    assert body["hasMore"] is True


def test_a_closed_amenity_is_not_reported_as_a_further_page(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    """A row dropped by the closure test was returned by the query, not withheld
    by the bound. Counting it as more to fetch would send a client after a row it
    is never meant to see."""
    catalogue["rows"] = [row(id="open"), row(id="shut", temporary_closure={"r": 1})]
    catalogue["total"] = 2

    body = resident_api_client.get(PATH).json()

    assert [item["id"] for item in body["items"]] == ["open"]
    assert body["hasMore"] is False


# ---------------------------------------------------------------------------
# The projection
# ---------------------------------------------------------------------------


def project(**overrides: Any) -> dict[str, Any]:
    """One row through the mapper, as it would go on the wire."""
    return resident_amenities_service._to_bookable(row(**overrides)).model_dump(
        by_alias=True
    )


def test_times_are_truncated_to_the_minute() -> None:
    """Postgres sends `06:00:00`; an `<input type="time">` needs `06:00`."""
    item = project()

    assert item["openingTime"] == "06:00"
    assert item["closingTime"] == "22:00"


def test_a_missing_opening_hour_reads_as_midnight_not_null() -> None:
    """Weaker than it looks, and deliberately: the booking RPC refuses a slot
    outside opening hours, not this string. What it buys is a client that does
    not have to special-case absence when comparing times."""
    item = project(opening_time=None, closing_time=None)

    assert item["openingTime"] == "00:00"
    assert item["closingTime"] == "00:00"


def test_amounts_survive_arriving_as_strings() -> None:
    """PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it
    as a string on some versions. Parsed once, at the boundary."""
    item = project(booking_fee="500.00", security_deposit="2000.00")

    assert item["bookingFee"] == 500.0
    assert item["securityDeposit"] == 2000.0


def test_an_unparseable_amount_reads_as_zero_rather_than_failing() -> None:
    item = project(booking_fee="free")

    assert item["bookingFee"] == 0.0


def test_closed_days_become_weekday_names() -> None:
    item = project(closed_days=[7, 1])

    assert item["closedDays"] == ["Sunday", "Monday"]


def test_an_out_of_range_closed_day_is_dropped_not_rendered() -> None:
    item = project(closed_days=[7, 99])

    assert item["closedDays"] == ["Sunday"]


def test_booking_mode_is_translated_to_the_wire_vocabulary() -> None:
    assert project(booking_mode="exclusive")["bookingMode"] == "Exclusive"
    assert project(booking_mode="shared")["bookingMode"] == "Shared"


def test_a_zero_limit_reads_as_no_limit() -> None:
    """A maximum duration of zero would be read by a booking form as "no booking
    is long enough", which is never what the column meant."""
    item = project(maximum_booking_duration_minutes=0, capacity=0)

    assert item["maximumBookingDurationMinutes"] is None
    assert item["capacity"] is None


def test_a_missing_slot_duration_falls_back_to_an_hour() -> None:
    """The one limit that cannot be null on the wire: a client divides the day
    by it, and dividing by nothing is worse than dividing by the schema
    default."""
    assert project(slot_duration_minutes=None)["slotDurationMinutes"] == 60


def test_the_currency_is_upper_cased() -> None:
    assert project(currency_code="inr")["currencyCode"] == "INR"


def test_null_text_reads_as_empty_string_not_null() -> None:
    item = project(description=None, location=None, image_url=None, refund_policy=None)

    assert item["description"] == ""
    assert item["location"] == ""
    assert item["image"] == ""
    assert item["refundPolicy"] == ""


def test_a_missing_category_falls_back_to_utility() -> None:
    assert project(category=None)["category"] == "Utility"


# ---------------------------------------------------------------------------
# Temporary closure
# ---------------------------------------------------------------------------


def test_a_temporarily_closed_amenity_is_not_offered(
    resident_api_client: TestClient, catalogue: dict
) -> None:
    catalogue["rows"] = [
        row(id="open"),
        row(id="shut", temporary_closure={"reason": "Repainting"}),
    ]

    body = resident_api_client.get(PATH).json()

    assert [item["id"] for item in body["items"]] == ["open"]
    assert body["total"] == 1


@pytest.mark.parametrize("cleared", [None, {}, []])
def test_a_cleared_closure_leaves_the_amenity_bookable(
    resident_api_client: TestClient, catalogue: dict, cleared: Any
) -> None:
    """`temporary_closure` is unconstrained jsonb, so SQL can ask whether it is
    null but not whether it is empty. Truthiness is the test the admin service
    already applies to the same column, and two readers disagreeing about
    whether the pool is shut is worse than either answer."""
    catalogue["rows"] = [row(temporary_closure=cleared)]

    assert resident_api_client.get(PATH).json()["total"] == 1


# ---------------------------------------------------------------------------
# What the query is pointed at
#
# The rest of this file replaces the repository, so nothing above would notice
# if the query were repointed at `amenities` or `amenity_overview`. These two go
# the other way: a recording stand-in for the Supabase client, asserting the
# relation and the predicate rather than the rows. `0029` and the checklist item
# in RESIDENT_BACKEND_DESIGN.md 12 are the reason they exist.
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

    def order(self, column: str) -> _RecordingQuery:
        self._call["order"] = column
        return self

    def limit(self, count: int) -> _RecordingQuery:
        self._call["limit"] = count
        return self

    def execute(self) -> Any:
        return type("Result", (), {"data": [], "count": 0})()


class _RecordingClient:
    def __init__(self) -> None:
        self.call: dict[str, Any] = {}
        self.query_class: type[_RecordingQuery] = _RecordingQuery

    def table(self, name: str) -> _RecordingQuery:
        self.call["relation"] = name
        return self.query_class(self.call)


def test_the_catalogue_is_read_from_the_bookable_view() -> None:
    """Not `amenities`, and emphatically not `amenity_overview` -- reading the
    admin projection would put `outstandingDues` one column away from this
    response."""
    client = _RecordingClient()

    resident_amenities_repository.list_bookable(client, "community-id")

    assert client.call["relation"] == "bookable_amenity"


def test_the_query_filters_on_the_community_and_nothing_else() -> None:
    """The view has already applied `status`, `is_active` and the closure test,
    so tenancy is all that is left -- and it is the whole tenancy boundary,
    because `amenities` carries no RLS policy of its own."""
    client = _RecordingClient()

    resident_amenities_repository.list_bookable(client, "community-id")

    assert client.call["filters"] == {"community_id": "community-id"}
    assert client.call["order"] == "name"
    assert "status" not in client.call["columns"]


def test_the_read_is_bounded_and_asks_how_much_it_left_behind() -> None:
    """The bound alone would truncate silently. The count is what lets the
    service tell a whole catalogue from a cut-off one."""
    client = _RecordingClient()

    resident_amenities_repository.list_bookable(client, "community-id")

    assert client.call["limit"] == 500
    assert client.call["count"] == "exact"


def test_a_client_that_reports_no_count_is_read_as_a_whole_catalogue() -> None:
    """Not every SDK version surfaces `count`. Falling back to the rows in hand
    keeps the endpoint claiming exactly what it claimed before the count
    existed, rather than inventing a truncation that did not happen."""

    class _NoCount(_RecordingQuery):
        def execute(self) -> Any:
            return type("Result", (), {"data": [{"id": "a"}], "count": None})()

    client = _RecordingClient()
    client.query_class = _NoCount

    rows, total = resident_amenities_repository.list_bookable(client, "community-id")

    assert total == len(rows) == 1
