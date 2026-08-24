"""The resident's money surface — four operations and two projections.

The group that matters most is the last. A payment endpoint has two properties no
ordinary response assertion catches: **a card number must not reach the
database**, and **a decline must not be an HTTP error**. Both are asserted
directly, because a test that reads the fields of a successful response cannot
notice either one going wrong.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.repositories import resident_money_repository
from app.services import resident_money_service as service

INVOICES = "/api/v1/invoices/mine"
BOOKINGS = "/api/v1/amenity-bookings/mine"

GOOD_CARD = "4242424242424242"


def invoice_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "invoice-id",
        "invoice_number": "INV-0001",
        "invoice_type": "maintenance",
        "title": "August maintenance",
        "status": "Unpaid",
        "stored_status": "issued",
        "issued_on": "2026-08-01",
        "due_on": "2026-08-10",
        "total_amount": "4250.00",
        "amount_paid": "0.00",
        "outstanding_amount": "4250.00",
        "currency_code": "INR",
        "notes": "",
        "paid_at": None,
        "payment_method": None,
        "instrument_label": None,
        "is_overdue": False,
        "is_payable": True,
        "created_at": "2026-08-01T09:00:00+00:00",
    }
    base.update(overrides)
    return base


def booking_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "booking-id",
        "booking_series_id": "series-id",
        "amenity_id": "amenity-id",
        "amenity_name": "Clubhouse",
        "title": "Birthday",
        "booking_date": "2026-08-20",
        "starts_at": "2026-08-20T16:00:00+00:00",
        "ends_at": "2026-08-20T20:00:00+00:00",
        "status": "Pending",
        "stored_status": "requested",
        "guest_count": 12,
        "is_private": True,
        "notes": "",
        "cancellation_reason": "",
        "rejection_reason": "",
        "total_amount": "2000.00",
        "amount_paid": "0.00",
        "outstanding_amount": "2000.00",
        "is_payable": True,
        "is_upcoming": True,
        "created_at": "2026-08-04T09:00:00+00:00",
    }
    base.update(overrides)
    return base


@pytest.fixture
def money(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace every repository call. Records arguments, returns what is staged."""
    captured: dict = {
        "invoices": [invoice_row()],
        "bookings": [booking_row()],
        "invoice": invoice_row(),
        "booking": booking_row(),
        # What a prior attempt under the same idempotency key looks like. `None`
        # is the ordinary case: this key has never been seen.
        "replay": None,
        "calls": [],
    }

    def fake_list_invoices(client: Any, **kwargs: Any) -> tuple[list[dict], int]:
        captured["calls"].append(("list_invoices", kwargs))
        rows = captured["invoices"]
        return rows, len(rows)

    def fake_get_invoice(client: Any, **kwargs: Any) -> dict | None:
        captured["calls"].append(("get_invoice", kwargs))
        return captured["invoice"]

    def fake_list_bookings(client: Any, **kwargs: Any) -> tuple[list[dict], int]:
        captured["calls"].append(("list_bookings", kwargs))
        rows = captured["bookings"]
        return rows, len(rows)

    def fake_get_booking(client: Any, **kwargs: Any) -> dict | None:
        captured["calls"].append(("get_booking", kwargs))
        return captured["booking"]

    def recorded(payment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """What the RPC hands back: the row as stored, not an echo of the request.

        The distinction is invisible on a fresh settlement and is the whole point
        on a replay, so the stand-in has to have the same shape as the real one.
        """
        return {
            "payment_id": payment_id,
            "status": payload["status"],
            "failure_code": payload["failure_code"],
            "instrument_label": payload["instrument_label"],
            "amount": payload["amount"],
        }

    def fake_find_invoice_payment(client: Any, **kwargs: Any) -> dict | None:
        captured["calls"].append(("find_invoice_payment", kwargs))
        return captured["replay"]

    def fake_find_booking_payment(client: Any, **kwargs: Any) -> dict | None:
        captured["calls"].append(("find_booking_payment", kwargs))
        return captured["replay"]

    def fake_settle_invoice(client: Any, **kwargs: Any) -> dict[str, Any]:
        captured["calls"].append(("settle_invoice", kwargs))
        return recorded("payment-id", kwargs["payload"])

    def fake_settle_booking(client: Any, **kwargs: Any) -> dict[str, Any]:
        captured["calls"].append(("settle_booking", kwargs))
        return recorded("event-id", kwargs["payload"])

    for name, replacement in {
        "list_invoices": fake_list_invoices,
        "get_invoice": fake_get_invoice,
        "list_bookings": fake_list_bookings,
        "get_booking": fake_get_booking,
        "find_invoice_payment": fake_find_invoice_payment,
        "find_booking_payment": fake_find_booking_payment,
        "settle_invoice": fake_settle_invoice,
        "settle_booking": fake_settle_booking,
    }.items():
        monkeypatch.setattr(resident_money_repository, name, replacement)
    return captured


def only(captured: dict, name: str) -> dict[str, Any]:
    matches = [kwargs for call, kwargs in captured["calls"] if call == name]
    assert len(matches) == 1, f"expected one {name} call, saw {len(matches)}"
    return matches[0]


def pay(
    client: TestClient, csrf: dict[str, str], path: str = INVOICES, **overrides: Any
) -> Any:
    body: dict[str, Any] = {
        "amount": "4250.00",
        "idempotencyKey": "attempt-00000001",
        "method": "upi",
    }
    body.update(overrides)
    target = (
        "/api/v1/invoices/invoice-id/pay"
        if path == INVOICES
        else "/api/v1/amenity-bookings/booking-id/pay"
    )
    return client.post(target, json=body, headers=csrf)


# ---------------------------------------------------------------------------
# The guards
# ---------------------------------------------------------------------------


def test_the_invoice_list_requires_a_session(api_client: TestClient) -> None:
    assert api_client.get(INVOICES).status_code == 401


def test_paying_requires_csrf(resident_api_client: TestClient, money: dict) -> None:
    response = resident_api_client.post(
        "/api/v1/invoices/invoice-id/pay",
        json={"amount": "1.00", "idempotencyKey": "attempt-00000001"},
    )

    assert response.status_code == 403
    assert money["calls"] == []


def test_an_admin_may_have_their_own_bills_too(
    admin_api_client: TestClient, money: dict
) -> None:
    """No role guard. An admin living in the community owes maintenance like
    anybody else, and the bills they get back are their own -- ownership being
    the view's `is_mine`, which is `is_own_invoice` itself."""
    admin_api_client.get(INVOICES)

    assert only(money, "list_invoices")["community_id"] == "community-id"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def test_the_unpaid_tab_filters_on_the_word_the_screen_shows(
    resident_api_client: TestClient, money: dict
) -> None:
    """Not on `is_payable`. The two agree on every bill a resident normally has
    and part company on the ones that matter -- see the next test."""
    resident_api_client.get(f"{INVOICES}?view=unpaid")

    assert only(money, "list_invoices")["status"] == "Unpaid"


def test_the_paid_tab_is_paid_and_not_merely_unpayable(
    resident_api_client: TestClient, money: dict
) -> None:
    """`is_payable` is false for four different reasons -- paid, void, draft, and
    nothing outstanding. Defining the Paid tab as its inverse puts somebody's
    cancelled bill in the list of bills they have settled."""
    resident_api_client.get(f"{INVOICES}?view=paid")

    assert only(money, "list_invoices")["status"] == "Paid"


def test_no_view_returns_both(resident_api_client: TestClient, money: dict) -> None:
    resident_api_client.get(INVOICES)

    assert only(money, "list_invoices")["status"] is None


def test_an_unknown_view_is_the_unfiltered_list(
    resident_api_client: TestClient, money: dict
) -> None:
    resident_api_client.get(f"{INVOICES}?view=overdue")

    assert only(money, "list_invoices")["status"] is None


def test_an_invoice_carries_both_vocabularies(
    resident_api_client: TestClient, money: dict
) -> None:
    """`Payments.jsx` splits on Unpaid and Paid and has no third branch, so
    `partially_paid` reads as Unpaid -- which is what it is to whoever owes the
    balance. The real one travels beside it."""
    money["invoices"] = [invoice_row(status="Unpaid", stored_status="partially_paid")]

    item = resident_api_client.get(INVOICES).json()["items"][0]

    assert item["status"] == "Unpaid"
    assert item["storedStatus"] == "partially_paid"


def test_amounts_survive_as_decimals(
    resident_api_client: TestClient, money: dict
) -> None:
    """Money is never a float in this codebase. `0.1 + 0.2` is the reason."""
    item = resident_api_client.get(INVOICES).json()["items"][0]

    assert item["totalAmount"] == "4250.00"
    assert item["outstandingAmount"] == "4250.00"


def test_the_booking_list_is_the_callers_own(
    resident_api_client: TestClient, money: dict
) -> None:
    resident_api_client.get(f"{BOOKINGS}?view=upcoming")
    sent = only(money, "list_bookings")

    assert sent["membership_id"] == "resident-membership-id"
    assert sent["upcoming"] is True


def test_the_booking_status_crosses_the_wire_as_a_machine_value(
    resident_api_client: TestClient, money: dict
) -> None:
    """`resident_booking_overview.status` is Title-case for a human to read.

    Passing it through made this the one booking endpoint whose status could not
    be compared against any other's -- 'Pending' here, 'pending' from the admin
    amenity endpoints (issue #48 D4). `storedStatus` survives as a frozen wire
    key and now agrees, keeping only the enum's own name for this state.
    """
    item = resident_api_client.get(BOOKINGS).json()["items"][0]

    assert item["status"] == "pending"
    assert item["storedStatus"] == "requested"


def test_a_two_word_booking_status_folds_to_its_machine_value(
    resident_api_client: TestClient, money: dict
) -> None:
    """'No Show' is the display rendering of `no_show`. The worst case for a
    naive lowercase, and the one a case-sensitive client would miss twice."""
    money["bookings"] = [booking_row(status="No Show", stored_status="no_show")]
    item = resident_api_client.get(BOOKINGS).json()["items"][0]

    assert item["status"] == "no_show"


# ---------------------------------------------------------------------------
# Paying, and the two things a payment endpoint must get right
# ---------------------------------------------------------------------------


def test_a_successful_payment_is_a_200_with_an_outcome(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    response = pay(resident_api_client, csrf_headers)
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "succeeded"
    assert body["failureCode"] is None
    assert body["paymentId"] == "payment-id"


def test_a_declined_payment_is_also_a_200(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """§11.5. The request was well-formed, authorized, processed and produced a
    durable record; the *payment* failed. A 402 would put an ordinary business
    outcome in the same client branch as "your session expired"."""
    response = pay(resident_api_client, csrf_headers, upi={"vpa": "failure@okaxis"})
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "failed"
    assert body["failureCode"] == "payment_declined"


def test_a_decline_is_still_written_to_the_database(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """The difference between this and the admin's `record_payment`. A failed row
    is what a support conversation is reconstructed from, and it never enters a
    balance because every recomputation sums `succeeded` only."""
    pay(resident_api_client, csrf_headers, upi={"vpa": "failure@okaxis"})
    sent = only(money, "settle_invoice")["payload"]

    assert sent["status"] == "failed"
    assert sent["failure_code"] == "payment_declined"


def test_the_card_number_never_reaches_the_database(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """Not "is masked before storage" -- *never sent*. §11.3."""
    pay(
        resident_api_client,
        csrf_headers,
        method="card",
        card={
            "number": GOOD_CARD,
            "cvv": "123",
            "expiryMonth": 12,
            "expiryYear": 2030,
        },
    )
    rendered = str(only(money, "settle_invoice")["payload"])

    assert GOOD_CARD not in rendered
    assert "123" not in rendered
    assert "2030" not in rendered


def test_what_is_stored_is_a_receipt_line(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    pay(
        resident_api_client,
        csrf_headers,
        method="card",
        card={
            "number": GOOD_CARD,
            "cvv": "123",
            "expiryMonth": 12,
            "expiryYear": 2030,
        },
    )

    assert only(money, "settle_invoice")["payload"]["instrument_label"] == "•••• 4242"


def test_the_response_never_carries_the_card_either(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    body = pay(
        resident_api_client,
        csrf_headers,
        method="card",
        card={
            "number": GOOD_CARD,
            "cvv": "999",
            "expiryMonth": 12,
            "expiryYear": 2030,
        },
    ).json()

    assert GOOD_CARD not in str(body)
    assert "999" not in str(body)


def test_the_idempotency_key_reaches_the_rpc(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """One key per press of Pay. It is what stops a double-tap paying twice, and
    the database is where it is enforced."""
    pay(resident_api_client, csrf_headers, idempotencyKey="press-0000000042")

    assert only(money, "settle_invoice")["payload"]["idempotency_key"] == (
        "press-0000000042"
    )


def test_a_missing_idempotency_key_is_refused(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """A payment endpoint that accepts a request with no key is one that will
    charge somebody twice on a flaky connection."""
    response = resident_api_client.post(
        "/api/v1/invoices/invoice-id/pay",
        json={"amount": "4250.00", "method": "upi"},
        headers=csrf_headers,
    )

    assert response.status_code == 422
    assert money["calls"] == []


def test_paying_by_card_with_no_card_is_refused(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    response = pay(resident_api_client, csrf_headers, method="card")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "card_required"


def test_someone_elses_invoice_is_a_404(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """Identical to one that does not exist. Ownership is part of the lookup
    rather than a check afterwards."""
    money["invoice"] = None

    response = pay(resident_api_client, csrf_headers)

    assert response.status_code == 404
    assert not [call for call, _ in money["calls"] if call == "settle_invoice"]


def test_the_settled_status_is_read_back_rather_than_assumed(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """The invoice status after a payment is the database's answer -- the RPC
    recomputes it from the payments, and a client told what this function guessed
    would be told wrong the first time a partial payment existed."""
    money["invoice"] = invoice_row(status="Paid", stored_status="paid")

    body = pay(resident_api_client, csrf_headers).json()

    assert body["settledStatus"] == "Paid"


def test_paying_a_booking_goes_through_the_booking_rpc(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """`US-2.12`: payment and confirmation are one statement. Two calls here --
    one to settle, one to confirm -- would be the exact failure the story
    describes."""
    pay(resident_api_client, csrf_headers, path=BOOKINGS, amount="2000.00")

    assert only(money, "settle_booking")["booking_id"] == "booking-id"


def test_a_declined_booking_payment_leaves_the_booking_alone(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """The half that gets forgotten. A failed payment must not leave a
    half-confirmed booking somebody believes they hold."""
    body = pay(
        resident_api_client,
        csrf_headers,
        path=BOOKINGS,
        amount="2000.00",
        upi={"vpa": "failure@okaxis"},
    ).json()

    assert body["status"] == "failed"
    assert body["settledStatus"] == "Pending"


# ---------------------------------------------------------------------------
# Replaying a key
#
# The group that exists because the first version of this endpoint got it wrong
# in a way no assertion above would have caught: it asked the gateway first and
# checked for a duplicate afterwards, then described the retry using the fresh
# verdict rather than the stored row.
# ---------------------------------------------------------------------------


def test_a_replay_never_reaches_the_gateway(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """The ordering is invisible with a pure simulator and is a double charge
    with a real provider behind the same seam -- which is the entire claim this
    module makes. The lookup comes first, and a hit ends the request."""
    money["replay"] = {
        "payment_id": "first-attempt",
        "status": "succeeded",
        "failure_code": None,
        "instrument_label": "•••• 4242",
        "amount": "4250.00",
    }

    response = pay(resident_api_client, csrf_headers)

    assert response.status_code == 200
    assert not [call for call, _ in money["calls"] if call == "settle_invoice"]


def test_a_replay_is_described_from_the_row_that_recorded_it(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """A retry carrying a card that would decline must still be told what
    happened, not what would have happened. Answering with the new verdict
    produces a body reading `failed` beside a `settledStatus` of `Paid`."""
    money["invoice"] = invoice_row(status="Paid", stored_status="paid")
    money["replay"] = {
        "payment_id": "first-attempt",
        "status": "succeeded",
        "failure_code": None,
        "instrument_label": "•••• 4242",
        "amount": "4250.00",
    }

    body = pay(
        resident_api_client,
        csrf_headers,
        method="card",
        card={
            "number": "4000000000000002",
            "cvv": "123",
            "expiryMonth": 12,
            "expiryYear": 2030,
        },
    ).json()

    assert body["status"] == "succeeded"
    assert body["paymentId"] == "first-attempt"
    assert body["settledStatus"] == "Paid"


def test_the_key_is_looked_up_against_this_invoice(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    """The database refuses a key that already settled a different bill. The
    friendly answer -- hand back the other invoice's payment -- reports
    `succeeded` for an invoice that remains entirely unpaid."""
    pay(resident_api_client, csrf_headers, idempotencyKey="press-0000000042")

    assert only(money, "find_invoice_payment") == {
        "invoice_id": "invoice-id",
        "key": "press-0000000042",
    }


def test_a_booking_replay_short_circuits_too(
    resident_api_client: TestClient, csrf_headers: dict[str, str], money: dict
) -> None:
    money["replay"] = {
        "payment_id": "first-attempt",
        "status": "failed",
        "failure_code": "card_declined",
        "instrument_label": "•••• 0002",
        "amount": "2000.00",
    }

    body = pay(
        resident_api_client, csrf_headers, path=BOOKINGS, amount="2000.00"
    ).json()

    assert body["failureCode"] == "card_declined"
    assert not [call for call, _ in money["calls"] if call == "settle_booking"]


# ---------------------------------------------------------------------------
# What the query is pointed at
#
# The rest of this file replaces the repository, so nothing above would notice
# if the invoice list were filtered on `membership_id` -- which is how the first
# version hid, from the person who owed it, a bill raised against their flat
# rather than against them. `0033` §2 calls that the worst possible bug in the
# file; these two are what would have caught it.
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

    def order(self, column: str, desc: bool = False) -> _RecordingQuery:
        self._call.setdefault("order", []).append(column)
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


def test_the_invoice_list_filters_on_the_write_paths_own_predicate() -> None:
    """`is_mine` is `is_own_invoice`, the function the settlement RPC calls.
    Filtering on `membership_id` is a *narrower* rule than the one that decides
    whether the payment will be accepted, and the gap between them is a bill the
    resident can pay and cannot see."""
    client = _RecordingClient()

    resident_money_repository.list_invoices(
        client, community_id="community-id", status=None, offset=0, limit=20
    )

    assert client.call["relation"] == "resident_invoice_overview"
    assert client.call["filters"] == {"community_id": "community-id", "is_mine": True}


def test_one_invoice_is_fetched_through_the_same_predicate() -> None:
    """The read that produces the 404 and the read that fills the list have to
    agree about ownership, or a bill is payable from one screen and missing from
    the other."""
    client = _RecordingClient()

    resident_money_repository.get_invoice(
        client, community_id="community-id", invoice_id="invoice-id"
    )

    assert client.call["filters"] == {
        "id": "invoice-id",
        "community_id": "community-id",
        "is_mine": True,
    }


# ---------------------------------------------------------------------------
# The projection, through the service
# ---------------------------------------------------------------------------


def test_a_missing_title_reads_as_maintenance() -> None:
    assert service._to_invoice(invoice_row(title="")).title == "Maintenance"


def test_a_null_amount_is_zero_not_none() -> None:
    """A screen that renders `null.toLocaleString()` is a screen that crashes."""
    projected = service._to_invoice(invoice_row(amount_paid=None))

    assert str(projected.amount_paid) == "0"
