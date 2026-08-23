"""What a resident owes, and what they send to settle it.

**The instrument models are the reason this file needs reading before it is
edited.** `card.number`, `card.cvv` and the expiry are the only fields in this
API that must not survive the request that carried them. They are `SecretStr`,
so an accidental `repr()` in a log line or a traceback prints `**********` rather
than a card number; they are read by `payment_simulator.simulate`, which is pure
and returns a masked label; and nothing downstream of that function is given
them. §11.3.

**A decline is a `200`.** `PaymentOutcome` carries `status`, and the client
branches on it. A declined card is not a failed API call: the request was
well-formed, authorized, processed and produced a durable record — the *payment*
failed. Returning a `402` would put an ordinary business outcome in the same
branch as "your session expired", and would leave a payment id to be dug out of
an error envelope with nowhere to put one. §11.5.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, SecretStr, StringConstraints

from app.domain.common_schemas import CamelModel


def _text(limit: int) -> object:
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=limit)]


class ResidentInvoice(CamelModel):
    """One of the caller's bills.

    ``status`` is the screen's word, not the enum's. `Payments.jsx` splits on
    `Unpaid` and `Paid` and has no third branch, so `partially_paid`, `issued`
    and `overdue` all read as `Unpaid` — which is what they are to the person who
    owes the money. ``storedStatus`` carries the real one for anything that needs
    it.
    """

    id: str
    invoice_number: str | None = None
    invoice_type: str = "maintenance"
    title: str
    #: `Unpaid` | `Paid` | `Cancelled`.
    status: str
    stored_status: str
    issued_on: date | None = None
    due_on: date | None = None
    total_amount: Decimal
    amount_paid: Decimal
    outstanding_amount: Decimal
    currency_code: str = "INR"
    notes: str = ""
    paid_at: datetime | None = None
    payment_method: str | None = None
    #: The masked receipt line of whatever settled it — `•••• 4242`, `UPI`.
    instrument_label: str | None = None
    is_overdue: bool
    #: The precondition the settlement RPC enforces, computed once in the
    #: database. A Pay button drawn from a different rule than the write path
    #: applies is a Pay button that fails.
    is_payable: bool
    created_at: datetime


class ResidentBooking(CamelModel):
    """One of the caller's amenity bookings, and what is still owed on it.

    ``status`` is the lowercase machine value, the same vocabulary the admin
    amenity endpoints emit -- one word per state across the whole app. It used
    to be the view's Title-case display string ('Pending', 'No Show'), which
    made this the one booking endpoint whose status could not be compared
    against any other's (issue #48 D4).

    ``storedStatus`` therefore now AGREES with ``status`` on every row, with the
    single exception that it keeps the enum's own name for the pending state --
    ``requested`` where the wire says ``pending``. The key stays because the
    wire keys are frozen and because that one distinction is still real; no
    caller needs it to tell the states apart any more.
    """

    id: str
    booking_series_id: str
    amenity_id: str
    amenity_name: str
    title: str | None = None
    booking_date: date | None = None
    starts_at: datetime
    ends_at: datetime
    #: `pending` | `approved` | `rejected` | `cancelled` | `completed` | `no_show`.
    status: str
    #: The stored enum: as above, but `requested` for `pending`.
    stored_status: str
    guest_count: int = 0
    is_private: bool = False
    notes: str = ""
    cancellation_reason: str = ""
    rejection_reason: str = ""
    total_amount: Decimal
    amount_paid: Decimal
    outstanding_amount: Decimal
    is_payable: bool
    is_upcoming: bool
    created_at: datetime


class CardInstrument(CamelModel):
    """Card details, held only long enough to be judged.

    Every field here is discarded inside `simulate(...)`. Nothing on this model
    reaches the database, a log, an error payload or `payment_events`.

    Only the published test numbers are accepted (§11.3). A simulated gateway
    that took any Luhn-valid number is one that will eventually be handed a real
    card by somebody being helpful, and at that moment this becomes an
    application holding a live PAN with none of the obligations that implies.
    """

    number: SecretStr
    cvv: SecretStr
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2000, le=2100)


class UpiInstrument(CamelModel):
    """A UPI handle.

    ``vpa`` is optional because the shipped screen does not collect one:
    `Payments.jsx` renders UPI as the only enabled method and its Confirm button
    sends no instrument at all. Omitted, the payment succeeds and the receipt
    line reads `UPI` — the honest record of what was known.

    A VPA whose local part starts `failure` or `fail` always declines. That is
    the UPI half of the expiry-date demonstration; without it the failure path is
    unreachable from the only payment screen that exists.
    """

    vpa: _text(120) = ""  # type: ignore[valid-type]


class PayInvoiceRequest(CamelModel):
    """A resident's attempt to settle one bill.

    ``amount`` is required and is checked against the balance **the database
    computes**, not accepted as an instruction. It is in the request so a client
    working from a stale screen can be told so, rather than so it can choose what
    to pay: a partial payment is a policy question nobody has answered, and
    accepting one silently would leave a resident believing they had paid.

    ``idempotencyKey`` is required, and the rule for minting it is the part that
    cannot be enforced from this side (§11.4):

    * **One key per press of Pay.** A double-tap, a dropped connection, a retried
      request — same key, same payment returned, and the caller cannot tell
      whether it settled now or a moment ago. This is what stops a resident
      paying twice.
    * **A new key for a new attempt.** Once the client has *shown* someone a
      decline, the next press is a different attempt. Reusing the key there would
      replay the old failure forever, and a corrected card would never work.

    The key identifies an attempt, not an invoice. Backwards, it produces either a
    double charge or an unpayable bill.
    """

    amount: Decimal = Field(gt=0)
    idempotency_key: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=8, max_length=120)
    ]
    method: Literal["upi", "card"] = "upi"
    card: CardInstrument | None = None
    upi: UpiInstrument | None = None


class PayBookingRequest(PayInvoiceRequest):
    """Identical to paying an invoice, and deliberately not a separate shape.

    One simulator, one settlement contract, two callers. `US-2.12` is about the
    transaction that follows — a successful payment must always leave a confirmed
    booking — and that lives in `settle_amenity_booking_payment`, not here.
    """


class PaymentOutcome(CamelModel):
    """The result of an attempt. **`200` whether it succeeded or not.**

    ``failureCode`` is a stable identifier, never a sentence: `card_expired`,
    `insufficient_funds`, `payment_declined`. The wording a resident reads is the
    client's to choose and to translate.
    """

    payment_id: str
    #: `succeeded` | `failed`.
    status: str
    failure_code: str | None = None
    instrument_label: str
    amount: Decimal
    #: Where the thing being paid for ended up — the invoice's wire status, or
    #: the booking's. Returned so a client need not re-read to know whether the
    #: screen it is on has changed.
    settled_status: str
