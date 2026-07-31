"""Money service: invoices, payments, billing runs and the collection tiles.

Two decisions worth stating up front, because both look like details and are not.

**Nothing here adds money up.** Every total comes from a database aggregate.
Python's job is to rename fields and translate vocabularies; the moment it starts
summing amounts there are two answers to "what is outstanding" and they drift.

**The unit is the debtor.** ``userId`` on an invoice is the flat's current
occupant, resolved at read time for display. It is not a foreign key the invoice
hangs from, and it changes when somebody moves -- which is the point: a resident
who leaves does not take the flat's arrears with them.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.core.exceptions import ValidationError
from app.core.formatting import bill_period, parse_instant
from app.domain.money_schemas import (
    BillingSettings,
    CreateInvoiceRequest,
    InvoiceDetail,
    InvoiceLineItem,
    InvoiceSummary,
    PaymentSummary,
    RecordPaymentRequest,
    UpdateBillingSettingsRequest,
)
from app.domain.units import normalize_unit_code
from app.domain.vocabularies import (
    invoice_status_to_wire,
    late_fee_period_to_storage,
    payment_method_to_storage,
    payment_method_to_wire,
)
from app.repositories import money_repository as repo
from app.repositories import tenancy_repository as tenancy_repo
from supabase import Client

_VALID_INVOICE_TYPES = ("maintenance", "amenity", "penalty", "misc")
def _amount(value: object) -> float:
    """Read a Postgres ``numeric`` off the wire as a float.

    PostgREST sends ``numeric`` as a JSON number already, but the SDK has
    surfaced it as a string on some versions, and ``float("4250.00")`` is correct
    while ``4250.00 + "4250.00"`` is a TypeError three call frames away. Parsed
    once, here.
    """
    if value is None:
        return 0.0
    return round(float(value), 2)


def _as_date(value: object) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def _to_line_item(row: dict) -> InvoiceLineItem:
    return InvoiceLineItem(
        id=row["id"],
        description=row["description"],
        quantity=_amount(row.get("quantity")),
        unit_amount=_amount(row.get("unit_amount")),
        total=_amount(row.get("total_amount")),
    )


def _to_payment(row: dict) -> PaymentSummary:
    return PaymentSummary(
        id=row["id"],
        invoice_id=row["invoice_id"],
        invoice_number=row.get("invoice_number"),
        invoice_title=row.get("invoice_title"),
        amount=_amount(row.get("amount")),
        currency=row.get("currency_code") or "INR",
        method=payment_method_to_wire(row.get("payment_method")),
        status=row.get("status", "succeeded"),
        reference=row.get("provider_reference"),
        paid_at=parse_instant(row["paid_at"]),
        payer_profile_id=row.get("payer_profile_id"),
        payer_name=row.get("payer_name"),
        unit_id=row.get("unit_id"),
        flat=row.get("unit_code"),
        notes=row.get("notes"),
    )


def _to_summary(row: dict) -> InvoiceSummary:
    paid_on = row.get("paid_on")
    period_start = _as_date(row.get("billing_period_start"))
    period_end = _as_date(row.get("billing_period_end"))
    due_date = _as_date(row.get("due_on"))
    issued_on = _as_date(row.get("issued_on"))
    assert due_date is not None and issued_on is not None  # both NOT NULL

    return InvoiceSummary(
        id=row["id"],
        invoice_number=row["invoice_number"],
        title=row["title"],
        invoice_type=row.get("invoice_type", "maintenance"),
        amount=_amount(row.get("total_amount")),
        subtotal=_amount(row.get("subtotal_amount")),
        tax=_amount(row.get("tax_amount")),
        outstanding=_amount(row.get("outstanding_amount")),
        amount_paid=_amount(row.get("amount_paid")),
        currency=row.get("currency_code") or "INR",
        status=invoice_status_to_wire(row.get("status")),
        status_detail=row.get("status", "issued"),
        is_overdue=bool(row.get("is_overdue")),
        due_date=due_date,
        issued_on=issued_on,
        bill_period=bill_period(period_start, period_end),
        billing_period_start=period_start,
        billing_period_end=period_end,
        flat=row.get("unit_code"),
        tower=row.get("tower"),
        unit_id=row.get("unit_id"),
        # The membership id, matching what `GET /residents` returns as `id` --
        # so the dashboard's `users.find(u => u.id === pay.userId)` resolves.
        user_id=row.get("resident_membership_id"),
        resident_profile_id=row.get("resident_profile_id"),
        resident_name=row.get("resident_name"),
        paid_on=parse_instant(paid_on) if paid_on else None,
        payment_method=payment_method_to_wire(row.get("payment_method")),
        notes=row.get("notes"),
        created_at=parse_instant(row["created_at"]),
        updated_at=parse_instant(row["updated_at"]),
    )


def _to_detail(row: dict, lines: list[dict], payments: list[dict]) -> InvoiceDetail:
    return InvoiceDetail(
        **_to_summary(row).model_dump(),
        line_items=[_to_line_item(line) for line in lines],
        payments=[_to_payment(payment) for payment in payments],
    )


def get_invoice(client: Client, user_id: str, invoice_id: str) -> InvoiceDetail:
    """One invoice with its line items and every payment against it."""
    community_id = tenancy_repo.get_caller_community_id(client, user_id)
    row = repo.get_invoice(client, community_id, invoice_id)
    lines = repo.list_line_items(client, community_id, invoice_id)
    payments, _ = repo.list_payments(
        client, community_id, invoice_id=invoice_id, limit=100
    )
    return _to_detail(row, lines, payments)


def create_invoice(
    client: Client, user_id: str, body: CreateInvoiceRequest
) -> InvoiceDetail:
    """Issue one invoice against one flat, with its lines, atomically."""
    community_id = tenancy_repo.get_caller_community_id(client, user_id)

    if body.invoice_type not in _VALID_INVOICE_TYPES:
        raise ValidationError(
            f"invoiceType must be one of {', '.join(_VALID_INVOICE_TYPES)}.",
            code="invalid_invoice_type",
        )
    if not body.unit_id and not body.flat:
        raise ValidationError(
            "Provide either unitId or flat.", code="unit_required"
        )

    payload: dict = {
        "title": body.title.strip(),
        "invoice_type": body.invoice_type,
        "lines": [
            {
                "description": line.description.strip(),
                "quantity": line.quantity,
                "unit_amount": line.unit_amount,
            }
            for line in body.line_items
        ],
    }
    if body.unit_id:
        payload["unit_id"] = body.unit_id
    else:
        # Same normalisation as registration approval: the frontend supplies a
        # flat either as a bare number or as a full code, and both must land on
        # one canonical value (FRONTEND_MEETING_AGENDA.md item 8).
        payload["unit_code"] = normalize_unit_code(None, body.flat)
    if body.issued_on:
        payload["issued_on"] = body.issued_on.isoformat()
    if body.due_date:
        payload["due_on"] = body.due_date.isoformat()
    if body.billing_period_start:
        payload["billing_period_start"] = body.billing_period_start.isoformat()
    if body.billing_period_end:
        payload["billing_period_end"] = body.billing_period_end.isoformat()
    if body.tax_percent is not None:
        payload["tax_percent"] = body.tax_percent
    if body.notes:
        payload["notes"] = body.notes

    invoice_id = repo.issue_invoice(client, community_id, payload)
    return get_invoice(client, user_id, invoice_id)


def record_payment(
    client: Client, user_id: str, invoice_id: str, body: RecordPaymentRequest
) -> InvoiceDetail:
    """Record money received and return the invoice as it now stands.

    Returns the whole invoice rather than the payment, because the caller's next
    question is always "is it settled now" -- and answering it here saves the
    screen a second request to find out.
    """
    tenancy_repo.get_caller_community_id(client, user_id)

    method = payment_method_to_storage(body.method)
    if method is None:
        raise ValidationError(
            "method must be UPI, Credit Card, Net Banking, Cash, Cheque or "
            "Bank Transfer.",
            code="invalid_payment_method",
        )

    payload: dict = {"amount": body.amount, "payment_method": method}
    if body.reference:
        payload["provider_reference"] = body.reference.strip()
    if body.payer_profile_id:
        payload["payer_profile_id"] = body.payer_profile_id
    if body.paid_at:
        payload["paid_at"] = body.paid_at.isoformat()
    if body.notes:
        payload["notes"] = body.notes

    repo.record_payment(client, invoice_id, payload)
    return get_invoice(client, user_id, invoice_id)


def get_billing_settings(client: Client, user_id: str) -> BillingSettings:
    """The community's billing configuration.

    Reports the defaults for a community that has never saved any, rather than
    404ing -- the row is created lazily on first write, and a screen asking what
    the settings are should not have to know that.
    """
    community_id = tenancy_repo.get_caller_community_id(client, user_id)
    row = repo.fetch_billing_settings(client, community_id)
    if row is None:
        return BillingSettings(
            community_id=community_id,
            currency="INR",
            invoice_number_prefix="INV",
            default_maintenance_amount=None,
            maintenance_due_day=15,
            default_tax_percent=0.0,
            # Step-9 toggles. Both off, and both must be: a community with no
            # settings row has no maintenance amount either, and the database
            # refuses automated billing without one.
            auto_billing_enabled=False,
            auto_billing_day=1,
            late_fee_enabled=False,
            late_fee_amount=None,
            late_fee_grace_days=10,
            late_fee_period="weekly",
            updated_at=datetime.now(timezone.utc),
        )
    return _to_settings(row)


def update_billing_settings(
    client: Client, user_id: str, body: UpdateBillingSettingsRequest
) -> BillingSettings:
    """Patch the billing configuration. Omitted fields are left unchanged."""
    community_id = tenancy_repo.get_caller_community_id(client, user_id)

    supplied = body.model_dump(exclude_unset=True)
    patch: dict = {}
    if "currency" in supplied and body.currency:
        patch["currency_code"] = body.currency.upper()
    if "invoice_number_prefix" in supplied and body.invoice_number_prefix:
        patch["invoice_number_prefix"] = body.invoice_number_prefix.upper()
    # Key presence, not truthiness: sending null clears the rate, and 0 is not a
    # rate anybody means. Both differ from omitting the field.
    if "default_maintenance_amount" in supplied:
        patch["default_maintenance_amount"] = body.default_maintenance_amount
    if "maintenance_due_day" in supplied and body.maintenance_due_day:
        patch["maintenance_due_day"] = body.maintenance_due_day
    if "default_tax_percent" in supplied and body.default_tax_percent is not None:
        patch["default_tax_percent"] = body.default_tax_percent

    # Step-9 toggles. `is not None` rather than truthiness for the booleans:
    # `false` is the whole point of a switch, and `if body.auto_billing_enabled`
    # would make turning one off impossible.
    if "auto_billing_enabled" in supplied and body.auto_billing_enabled is not None:
        patch["auto_billing_enabled"] = body.auto_billing_enabled
    if "auto_billing_day" in supplied and body.auto_billing_day:
        patch["auto_billing_day"] = body.auto_billing_day
    if "late_fee_enabled" in supplied and body.late_fee_enabled is not None:
        patch["late_fee_enabled"] = body.late_fee_enabled
    # Key presence, like the maintenance amount: null clears the fine.
    if "late_fee_amount" in supplied:
        patch["late_fee_amount"] = body.late_fee_amount
    if "late_fee_grace_days" in supplied and body.late_fee_grace_days is not None:
        patch["late_fee_grace_days"] = body.late_fee_grace_days
    if "late_fee_period" in supplied and body.late_fee_period:
        period = late_fee_period_to_storage(body.late_fee_period)
        if period is None:
            raise ValidationError(
                "lateFeePeriod must be Weekly, Monthly or One-time."
            )
        patch["late_fee_period"] = period

    if patch:
        repo.update_billing_settings(client, community_id, patch)
    return get_billing_settings(client, user_id)


def _to_settings(row: dict) -> BillingSettings:
    amount = row.get("default_maintenance_amount")
    return BillingSettings(
        community_id=row["community_id"],
        currency=row.get("currency_code") or "INR",
        invoice_number_prefix=row.get("invoice_number_prefix") or "INV",
        default_maintenance_amount=_amount(amount) if amount is not None else None,
        maintenance_due_day=int(row.get("maintenance_due_day") or 15),
        default_tax_percent=_amount(row.get("default_tax_percent")),
        auto_billing_enabled=bool(row.get("auto_billing_enabled", False)),
        auto_billing_day=int(row.get("auto_billing_day") or 1),
        late_fee_enabled=bool(row.get("late_fee_enabled", False)),
        # Not `_amount`, which collapses null to 0.0: a fine of zero is one
        # somebody configured and a fine of null is one nobody has, and the
        # CHECK behind `lateFeeEnabled` distinguishes them.
        late_fee_amount=(
            None if row.get("late_fee_amount") is None
            else round(float(row["late_fee_amount"]), 2)
        ),
        late_fee_grace_days=int(row.get("late_fee_grace_days") or 0),
        late_fee_period=row.get("late_fee_period") or "weekly",
        updated_at=parse_instant(row["updated_at"]),
    )
