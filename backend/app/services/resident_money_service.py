"""The resident's money: their bills, their bookings, and settling either one.

Closes §5.5, §6 (Money) and §11 of ``docs/design/RESIDENT_BACKEND_DESIGN.md``,
and step 6 of its build order.

**This module is the seam.** `payment_simulator.simulate` decides an outcome and
the RPC records one; neither knows about the other. Swapping the simulator for a
real gateway is an edit to :func:`_settle` and to one module — the router is
unchanged, the RPC is unchanged, and every business path downstream has already
been exercised, because the simulator can produce on demand the outcomes a real
provider only produces by accident.

**The card details stop here.** They arrive as ``SecretStr``, are unwrapped for
exactly one call into a pure function, and the only thing that survives is a
masked label. Nothing below :func:`_outcome_payload` has ever seen a number.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.common_schemas import Page
from app.domain.resident_money_schemas import (
    PayBookingRequest,
    PayInvoiceRequest,
    PaymentOutcome,
    ResidentBooking,
    ResidentInvoice,
)
from app.domain.vocabularies import booking_status_to_wire
from app.repositories import resident_money_repository as repo
from app.services.payment_simulator import SimulatedOutcome, simulate
from supabase import Client


def _text(value: object) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _money(value: object) -> Decimal:
    return Decimal(str(value or 0))


def _to_invoice(row: dict[str, Any]) -> ResidentInvoice:
    return ResidentInvoice(
        id=row["id"],
        invoice_number=row.get("invoice_number"),
        invoice_type=_text(row.get("invoice_type")) or "maintenance",
        title=_text(row.get("title")) or "Maintenance",
        status=_text(row.get("status")) or "Unpaid",
        stored_status=_text(row.get("stored_status")),
        issued_on=row.get("issued_on"),
        due_on=row.get("due_on"),
        total_amount=_money(row.get("total_amount")),
        amount_paid=_money(row.get("amount_paid")),
        outstanding_amount=_money(row.get("outstanding_amount")),
        currency_code=_text(row.get("currency_code")) or "INR",
        notes=_text(row.get("notes")),
        paid_at=row.get("paid_at"),
        payment_method=row.get("payment_method"),
        instrument_label=row.get("instrument_label"),
        is_overdue=bool(row.get("is_overdue")),
        is_payable=bool(row.get("is_payable")),
        created_at=row["created_at"],
    )


def _to_booking(row: dict[str, Any]) -> ResidentBooking:
    return ResidentBooking(
        id=row["id"],
        booking_series_id=row.get("booking_series_id") or row["id"],
        amenity_id=row["amenity_id"],
        amenity_name=_text(row.get("amenity_name")),
        title=row.get("title"),
        booking_date=row.get("booking_date"),
        starts_at=row["starts_at"],
        ends_at=row["ends_at"],
        # The lowercase machine value, from the stored enum where the view gives
        # us one and from its own display string otherwise. `resident_booking_
        # overview.status` is Title-case ('Pending', 'No Show') and passing it
        # through made this the one booking endpoint whose status could not be
        # compared against any other's (issue #48 D4).
        status=booking_status_to_wire(
            row.get("stored_status") or row.get("status")
        ),
        stored_status=_text(row.get("stored_status")),
        guest_count=int(row.get("guest_count") or 0),
        is_private=bool(row.get("is_private")),
        notes=_text(row.get("notes")),
        cancellation_reason=_text(row.get("cancellation_reason")),
        rejection_reason=_text(row.get("rejection_reason")),
        total_amount=_money(row.get("total_amount")),
        amount_paid=_money(row.get("amount_paid")),
        outstanding_amount=_money(row.get("outstanding_amount")),
        is_payable=bool(row.get("is_payable")),
        is_upcoming=bool(row.get("is_upcoming")),
        created_at=row["created_at"],
    )


def list_invoices(
    client: Client,
    *,
    community_id: str,
    view: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[ResidentInvoice]:
    """One page of the caller's bills, newest first.

    ``view`` is ``unpaid`` or ``paid``, matching the screen's two lists. Anything
    else — including nothing — returns both, for the same reason the visitor tab
    selector does: a third value is a client that did not mean to constrain
    anything, not a request worth refusing.

    It maps to the **wire status**, not to `is_payable`. Those two agree on every
    invoice a resident normally has and disagree on the ones that matter: a
    cancelled bill is not payable and was never paid, so a Paid tab defined as
    "not payable" is a tab with somebody's voided ₹12,000 in it. A tab is a
    question about what a bill *is*.
    """
    wanted = (view or "").strip().casefold()
    status: str | None = None
    if wanted == "unpaid":
        status = "Unpaid"
    elif wanted == "paid":
        status = "Paid"

    offset = max(page - 1, 0) * page_size
    rows, total = repo.list_invoices(
        client,
        community_id=community_id,
        status=status,
        offset=offset,
        limit=page_size,
    )
    items = [_to_invoice(row) for row in rows]
    return Page(
        items=items,
        total=total,
        page=max(page, 1),
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


def list_bookings(
    client: Client,
    *,
    membership_id: str,
    view: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[ResidentBooking]:
    """One page of the caller's own amenity bookings.

    ``view`` is ``upcoming`` or ``past``, filtered on a column the database
    computes from the booking's own start time.
    """
    wanted = (view or "").strip().casefold()
    upcoming: bool | None = None
    if wanted == "upcoming":
        upcoming = True
    elif wanted == "past":
        upcoming = False

    offset = max(page - 1, 0) * page_size
    rows, total = repo.list_bookings(
        client,
        membership_id=membership_id,
        upcoming=upcoming,
        offset=offset,
        limit=page_size,
    )
    items = [_to_booking(row) for row in rows]
    return Page(
        items=items,
        total=total,
        page=max(page, 1),
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


def _run_simulator(body: PayInvoiceRequest) -> SimulatedOutcome:
    """Judge the instrument. **The only place a card number is unwrapped.**

    ``get_secret_value()`` appears twice in this codebase and both are on this
    line. That is deliberate: the value is passed straight into a pure function
    with no I/O, and what comes back carries a mask rather than a number.
    """
    if body.method == "card":
        if body.card is None:
            raise ValidationError(
                "Card details are required to pay by card.", code="card_required"
            )
        return simulate(
            method="card",
            card_number=body.card.number.get_secret_value(),
            card_cvv=body.card.cvv.get_secret_value(),
            expiry_month=body.card.expiry_month,
            expiry_year=body.card.expiry_year,
        )
    return simulate(method="upi", vpa=body.upi.vpa if body.upi else "")


def _outcome_payload(
    body: PayInvoiceRequest, outcome: SimulatedOutcome
) -> dict[str, Any]:
    """What the database is told. Every field here is safe to appear in a log."""
    return {
        "amount": str(body.amount),
        "idempotency_key": body.idempotency_key,
        "payment_method": body.method,
        "instrument_label": outcome.instrument_label,
        "status": outcome.status,
        "failure_code": outcome.failure_code,
    }


def _recorded(row: dict[str, Any], *, settled_status: str) -> PaymentOutcome:
    """Describe an attempt **from the row that recorded it**, never from the request.

    On a fresh settlement the two agree. On a replay they do not: the stored row
    belongs to the first attempt, and reporting the new simulation over it would
    answer a retry with a verdict the database never accepted — a body reading
    ``failed`` beside a ``settledStatus`` of ``Paid``.
    """
    return PaymentOutcome(
        payment_id=str(row.get("payment_id") or ""),
        status=_text(row.get("status")) or "failed",
        failure_code=row.get("failure_code"),
        instrument_label=_text(row.get("instrument_label")) or "payment",
        amount=_money(row.get("amount")),
        settled_status=settled_status,
    )


def pay_invoice(
    client: Client, *, community_id: str, invoice_id: str, body: PayInvoiceRequest
) -> PaymentOutcome:
    """Settle one of the caller's bills through the simulated gateway.

    **A decline is a `200`.** The request was well-formed, authorized, processed
    and produced a durable record; the payment failed, which is a business
    outcome and not an API error. The client branches on ``status`` (§11.5).

    The read at the front is what turns somebody else's invoice into a `404`
    rather than an authorization error from three layers down — and the read at
    the end is what makes ``settledStatus`` the state the database reached rather
    than the one this function assumed.

    **The replay check comes before the gateway call, not after it.** With a pure
    simulator the ordering is invisible. With a real provider behind the same
    seam — which is the entire claim this module makes — charging first and
    checking for a duplicate afterwards takes money twice on every double-tap.
    The settlement RPC checks again for the two requests that arrive at once.
    """
    own = repo.get_invoice(client, community_id=community_id, invoice_id=invoice_id)
    if own is None:
        raise NotFoundError("Invoice not found.", code="invoice_not_found")

    replayed = repo.find_invoice_payment(
        client, invoice_id=invoice_id, key=body.idempotency_key
    )
    if replayed:
        return _recorded(replayed, settled_status=_text(own.get("status")) or "Unpaid")

    outcome = _run_simulator(body)
    recorded = repo.settle_invoice(
        client, invoice_id=invoice_id, payload=_outcome_payload(body, outcome)
    )
    settled = repo.get_invoice(
        client, community_id=community_id, invoice_id=invoice_id
    )

    return _recorded(
        recorded, settled_status=_text((settled or {}).get("status")) or "Unpaid"
    )


def pay_booking(
    client: Client, *, membership_id: str, booking_id: str, body: PayBookingRequest
) -> PaymentOutcome:
    """Pay for one of the caller's amenity bookings.

    **This is the endpoint `US-2.12` is about**, and the story is not about the
    gateway: *"a successful payment always yields a confirmed booking"* fails when
    the payment is one transaction and the confirmation is another. Both happen
    inside `settle_amenity_booking_payment`, or neither does.

    On a decline the booking is left exactly as it was. That half is the one that
    gets forgotten, and it is the one the resident notices — a half-confirmed
    booking they believe they hold.
    """
    own = repo.get_booking(client, membership_id=membership_id, booking_id=booking_id)
    if own is None:
        raise NotFoundError("Booking not found.", code="booking_not_found")

    replayed = repo.find_booking_payment(
        client, booking_id=booking_id, key=body.idempotency_key
    )
    if replayed:
        return _recorded(replayed, settled_status=_text(own.get("status")) or "Pending")

    outcome = _run_simulator(body)
    recorded = repo.settle_booking(
        client, booking_id=booking_id, payload=_outcome_payload(body, outcome)
    )
    settled = repo.get_booking(
        client, membership_id=membership_id, booking_id=booking_id
    )

    return _recorded(
        recorded, settled_status=_text((settled or {}).get("status")) or "Pending"
    )
