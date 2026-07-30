"""DTOs for invoices, payments and billing settings.

**Amounts are floats on the wire, and that is a decision rather than an
oversight.** The React app does ``amount.toLocaleString()`` and
``payments.reduce((a, c) => a + c.amount, 0)`` on this value
(``Maintenance.jsx:13``). Pydantic serialises ``Decimal`` as a JSON *string* by
default, and a string reaching that ``reduce`` would concatenate rather than add
-- "42504250" rendered as a rupee total, with nothing in the console to say so.

So the float is the display format, and every total the API reports is computed
by Postgres in ``numeric`` and read back, never summed in Python. The Maintenance
screen's tiles were the one place that rule would have been easy to break, which
is why they were a database aggregate rather than a loop over a page of rows --
the screen now computes them client-side and the endpoint is gone.

The frontend's ``payments[]`` shape is reproduced exactly -- ``title``,
``amount``, ``dueDate``, ``status``, ``billPeriod``, ``userId``, ``flat``,
``tower``, ``paidOn``, ``paymentMethod`` -- with the ids and the machine-readable
values added alongside (R23). Extra keys are ignored by the client, so the richer
fields cost nothing today.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field, field_validator

from app.domain.common_schemas import CamelModel

__all__ = [
    "InvoiceLineItem",
    "InvoiceSummary",
    "InvoiceDetail",
    "PaymentSummary",
    "LineItemInput",
    "CreateInvoiceRequest",
    "RecordPaymentRequest",
    "BillingSettings",
    "UpdateBillingSettingsRequest",
]


class InvoiceLineItem(CamelModel):
    """One charge on an invoice. ``total`` is ``quantity x unitAmount``, rounded
    in Postgres and constrained there, so it can never disagree with its own
    inputs."""

    id: str
    description: str
    quantity: float
    unit_amount: float
    total: float


class PaymentSummary(CamelModel):
    """One payment against one invoice.

    ``method`` is the display string the payment history renders (``Net
    Banking``), not the stored vocabulary (``netbanking``).
    """

    id: str
    invoice_id: str
    invoice_number: str | None = None
    invoice_title: str | None = None
    amount: float
    currency: str
    method: str | None = None
    status: str
    reference: str | None = None
    paid_at: datetime
    payer_profile_id: str | None = None
    payer_name: str | None = None
    unit_id: str | None = None
    flat: str | None = None
    notes: str | None = None


class InvoiceSummary(CamelModel):
    """One row of the maintenance collections table.

    Field-for-field compatible with the frontend's seeded ``payments[]`` entry,
    plus the identifiers behind each label.
    """

    id: str
    invoice_number: str
    # What the table renders. Stored rather than derived from type + period,
    # because "Clubhouse Event Charge" cannot be derived from either.
    title: str
    invoice_type: str
    # The full invoice value. NOT the outstanding balance -- the column is headed
    # "Amount" and means what the flat was billed. ``outstanding`` carries what is
    # still owed. ``Maintenance.jsx`` derives the screen totals from these rows.
    amount: float
    subtotal: float
    tax: float
    outstanding: float
    amount_paid: float
    currency: str

    # `Paid` | `Unpaid` | `Void`. A partially paid invoice reads `Unpaid`,
    # because money is still owed.
    status: str
    # The real lifecycle value underneath, for a client that wants the
    # distinction the two-value filter throws away.
    status_detail: str
    # Derived from the due date and the balance on every read, never stored:
    # a stored overdue flag is true only until the next midnight.
    is_overdue: bool

    due_date: date
    issued_on: date
    bill_period: str
    billing_period_start: date | None = None
    billing_period_end: date | None = None

    # Display fields the table renders as `Tower {tower} - Flat {flat}`.
    flat: str | None = None
    tower: str | None = None
    unit_id: str | None = None

    # The flat's CURRENT occupant, resolved at read time. The debt belongs to the
    # unit, not to this person -- they are who the table shows in the "Resident"
    # column, and they may be null for a vacant flat, which the frontend already
    # renders as "Resident".
    user_id: str | None = None
    resident_profile_id: str | None = None
    resident_name: str | None = None

    # From the most recent succeeded payment; both null until one exists.
    paid_on: datetime | None = None
    payment_method: str | None = None

    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class InvoiceDetail(InvoiceSummary):
    """One invoice with everything hanging off it."""

    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    payments: list[PaymentSummary] = Field(default_factory=list)


class LineItemInput(CamelModel):
    """One line on a new invoice."""

    description: str = Field(min_length=1, max_length=200)
    quantity: float = Field(default=1, gt=0, le=100_000)
    unit_amount: float = Field(gt=0, le=10_000_000)


class CreateInvoiceRequest(CamelModel):
    """Issue one invoice against one flat.

    Either ``unitId`` or ``flat`` identifies the unit; ``flat`` is the code the
    rest of the app uses (``B-1204``) and is created on first reference, because
    the product has never had a flat-creation step.
    """

    title: str = Field(min_length=1, max_length=160)
    unit_id: str | None = None
    flat: str | None = None
    invoice_type: str = "maintenance"
    line_items: list[LineItemInput] = Field(min_length=1)
    issued_on: date | None = None
    due_date: date | None = None
    billing_period_start: date | None = None
    billing_period_end: date | None = None
    tax_percent: float | None = Field(default=None, ge=0, lt=100)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("flat")
    @classmethod
    def _blank_flat_is_none(cls, value: str | None) -> str | None:
        """An empty string is the create form's "nothing entered", not a flat."""
        return value.strip() or None if value else None


class RecordPaymentRequest(CamelModel):
    """Record money received against an invoice.

    ``reference`` makes the call **idempotent**: sending the same reference twice
    returns the payment already recorded rather than crediting the invoice twice.
    A gateway that retries its webhook, or a resident who double-taps Pay, must
    not settle a bill two times.
    """

    amount: float = Field(gt=0, le=10_000_000)
    method: str = "Cash"
    reference: str | None = Field(default=None, max_length=120)
    payer_profile_id: str | None = None
    paid_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)


class BillingSettings(CamelModel):
    """The community's billing configuration.

    ``defaultMaintenanceAmount`` is null until an admin sets it. It has no home
    in the frontend or the ERD -- the amount exists today only as a literal
    ``4250`` inside an approval handler -- so there is nothing to migrate from
    and nothing to default to.
    """

    community_id: str
    currency: str
    invoice_number_prefix: str
    default_maintenance_amount: float | None = None
    maintenance_due_day: int
    default_tax_percent: float
    # Build step 9. The Settings screen's two billing switches, stored here rather
    # than in `community_settings` because money already had a home -- see the
    # 0017 header. `autoBillingEnabled` cannot be true while
    # `defaultMaintenanceAmount` is null, and `lateFeeEnabled` cannot be true
    # without an amount above zero: the database refuses both.
    #
    # **Nothing charges a late fee, and nothing runs billing on a schedule.**
    # `POST /maintenance-runs` is manual and ignores `autoBillingEnabled` on
    # purpose -- an admin pressing the button has said what they want more
    # recently than a toggle did.
    auto_billing_enabled: bool = False
    auto_billing_day: int = 1
    late_fee_enabled: bool = False
    late_fee_amount: float | None = None
    late_fee_grace_days: int = 10
    late_fee_period: str = "weekly"
    updated_at: datetime


class UpdateBillingSettingsRequest(CamelModel):
    """Patch the billing configuration. Omitted fields are left unchanged.

    ``defaultMaintenanceAmount`` distinguishes omitted from null: sending null
    clears the rate, which stops billing runs until one is set again.
    """

    currency: str | None = Field(default=None, min_length=3, max_length=3)
    invoice_number_prefix: str | None = Field(
        default=None, min_length=1, max_length=12, pattern=r"^[A-Za-z0-9-]+$"
    )
    default_maintenance_amount: float | None = Field(default=None, ge=0, le=10_000_000)
    # Capped at 28 so a due day never lands outside February.
    maintenance_due_day: int | None = Field(default=None, ge=1, le=28)
    default_tax_percent: float | None = Field(default=None, ge=0, lt=100)
    # Build step 9. Switching either flag on without the number it needs is a
    # `409`, not a silent no-op: the toggle would otherwise spring back on the
    # next read, which is the bug the current frontend already has.
    auto_billing_enabled: bool | None = None
    auto_billing_day: int | None = Field(default=None, ge=1, le=28)
    late_fee_enabled: bool | None = None
    # Nullable to clear, like `defaultMaintenanceAmount`. Clearing it while
    # `lateFeeEnabled` is true is a `409`.
    late_fee_amount: float | None = Field(default=None, ge=0, le=1_000_000)
    late_fee_grace_days: int | None = Field(default=None, ge=0, le=90)
    late_fee_period: str | None = Field(default=None, max_length=16)
