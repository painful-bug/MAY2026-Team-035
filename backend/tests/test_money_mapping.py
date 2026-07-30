"""Unit tests for the money translation layer.

These cover the boundary between what the database stores and what the
dashboard renders. The database side (RLS, the RPCs, the double-billing index)
cannot be tested here -- no migration has been applied anywhere -- so every test
below is about the half that *can* be checked, and the untested half is stated
plainly in DECISIONS_NEEDED E1 rather than implied to be covered.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.formatting import bill_period
from app.domain.money_schemas import (
    CreateInvoiceRequest,
    RecordPaymentRequest,
    UpdateBillingSettingsRequest,
)
from app.domain.vocabularies import (
    invoice_status_to_wire,
    payment_method_to_storage,
    payment_method_to_wire,
)
from app.services.money_service import _amount, _to_summary


# ---------------------------------------------------------------------------
# Invoice status: two wire values over five stored ones
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("stored", "wire"),
    [
        ("draft", "Unpaid"),
        ("issued", "Unpaid"),
        # The one that matters: money is still owed, so the screen says Unpaid.
        ("partially_paid", "Unpaid"),
        ("paid", "Paid"),
        ("void", "Void"),
    ],
)
def test_invoice_status_to_wire(stored: str, wire: str) -> None:
    assert invoice_status_to_wire(stored) == wire


def test_unknown_invoice_status_reads_unpaid() -> None:
    """An unrecognised status must not read as Paid.

    Defaulting the other way would show a bill as settled on the strength of a
    typo in a status column.
    """
    assert invoice_status_to_wire("something_new") == "Unpaid"
    assert invoice_status_to_wire(None) == "Unpaid"


# ---------------------------------------------------------------------------
# Payment method: this one IS a round trip
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "stored", ["upi", "card", "netbanking", "cash", "cheque", "bank_transfer"]
)
def test_payment_method_round_trips(stored: str) -> None:
    assert payment_method_to_storage(payment_method_to_wire(stored)) == stored


@pytest.mark.parametrize(
    ("supplied", "stored"),
    [
        ("UPI", "upi"),
        ("upi", "upi"),
        # The seeded frontend values, verbatim from data/payments.js.
        ("Net Banking", "netbanking"),
        ("Credit Card", "card"),
        ("  cash  ", "cash"),
    ],
)
def test_payment_method_accepts_frontend_spellings(supplied: str, stored: str) -> None:
    assert payment_method_to_storage(supplied) == stored


def test_unknown_payment_method_is_none_not_a_guess() -> None:
    assert payment_method_to_storage("Bitcoin") is None


def test_unknown_stored_method_passes_through() -> None:
    """A method added by a later migration renders as itself rather than
    disappearing from the payment history."""
    assert payment_method_to_wire("wallet") == "wallet"
    assert payment_method_to_wire(None) is None


# ---------------------------------------------------------------------------
# Billing period formatting
# ---------------------------------------------------------------------------
def test_bill_period_matches_the_seeded_string() -> None:
    assert (
        bill_period("2026-07-01", "2026-07-31") == "July 1, 2026 - July 31, 2026"
    )


def test_bill_period_with_no_dates_is_a_one_time_charge() -> None:
    """The clubhouse charge in data/payments.js carries exactly this string."""
    assert bill_period(None, None) == "One-time charge"


def test_bill_period_with_one_date_shows_that_date() -> None:
    assert bill_period("2026-07-01", None) == "July 1, 2026"
    assert bill_period(None, "2026-07-31") == "July 31, 2026"


def test_bill_period_accepts_real_dates_and_single_days() -> None:
    assert bill_period(date(2026, 7, 1), date(2026, 7, 1)) == "July 1, 2026"


# ---------------------------------------------------------------------------
# Amount handling
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("supplied", "expected"),
    [(None, 0.0), ("4250.00", 4250.0), (4250, 4250.0), ("0.005", 0.01)],
)
def test_amount_parses_numeric_from_either_shape(
    supplied: object, expected: float
) -> None:
    """PostgREST has sent `numeric` as both a JSON number and a string across
    SDK versions, and a string reaching the frontend's reduce() concatenates."""
    assert _amount(supplied) == expected


# ---------------------------------------------------------------------------
# The invoice row, as the collections table reads it
# ---------------------------------------------------------------------------
def _row(**overrides: object) -> dict:
    row: dict = {
        "id": "inv-1",
        "invoice_number": "INV-2026-00001",
        "title": "Maintenance Fee - July 2026",
        "invoice_type": "maintenance",
        "status": "issued",
        "billing_period_start": "2026-07-01",
        "billing_period_end": "2026-07-31",
        "issued_on": "2026-07-01",
        "due_on": "2026-07-15",
        "subtotal_amount": "4250.00",
        "tax_amount": "0.00",
        "total_amount": "4250.00",
        "outstanding_amount": "4250.00",
        "amount_paid": "0.00",
        "currency_code": "INR",
        "unit_code": "B-1204",
        "tower": "B",
        "unit_id": "unit-1",
        "resident_membership_id": "mem-1",
        "resident_profile_id": "prof-1",
        "resident_name": "Priya Sharma",
        "paid_on": None,
        "payment_method": None,
        "is_overdue": False,
        "notes": None,
        "created_at": "2026-07-01T00:00:00+00:00",
        "updated_at": "2026-07-01T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_invoice_row_reproduces_the_frontend_payment_shape() -> None:
    """Every key `Maintenance.jsx` and the resident Payments page read must be
    present and hold the value they expect."""
    invoice = _to_summary(_row())
    wire = invoice.model_dump(by_alias=True)

    assert wire["title"] == "Maintenance Fee - July 2026"
    assert wire["amount"] == 4250.0
    assert wire["dueDate"] == date(2026, 7, 15)
    assert wire["status"] == "Unpaid"
    assert wire["billPeriod"] == "July 1, 2026 - July 31, 2026"
    assert wire["flat"] == "B-1204"
    assert wire["tower"] == "B"
    # `users.find(u => u.id === pay.userId)` resolves against the membership id,
    # which is what GET /residents returns as `id`.
    assert wire["userId"] == "mem-1"
    assert wire["paidOn"] is None
    assert wire["paymentMethod"] is None


def test_amount_is_a_json_number_not_a_string() -> None:
    """`payments.reduce((a, c) => a + c.amount, 0)` concatenates strings, and
    the resulting "42504250" renders as a plausible rupee total."""
    invoice = _to_summary(_row())
    assert isinstance(invoice.model_dump(by_alias=True)["amount"], float)


def test_partially_paid_invoice_still_reads_unpaid_and_keeps_its_full_amount() -> None:
    """`amount` is what the flat was billed -- the column is headed "Amount".
    The balance travels separately, which is why the totals tile is a server
    aggregate rather than a sum of this field."""
    invoice = _to_summary(
        _row(
            status="partially_paid",
            outstanding_amount="1250.00",
            amount_paid="3000.00",
        )
    )
    assert invoice.status == "Unpaid"
    assert invoice.status_detail == "partially_paid"
    assert invoice.amount == 4250.0
    assert invoice.outstanding == 1250.0
    assert invoice.amount_paid == 3000.0


def test_paid_invoice_carries_the_settling_payment() -> None:
    invoice = _to_summary(
        _row(
            status="paid",
            outstanding_amount="0.00",
            amount_paid="4250.00",
            paid_on="2026-06-10T09:30:00+00:00",
            payment_method="netbanking",
        )
    )
    assert invoice.status == "Paid"
    assert invoice.payment_method == "Net Banking"
    assert invoice.paid_on == datetime(2026, 6, 10, 9, 30, tzinfo=timezone.utc)


def test_vacant_flat_has_no_resident_rather_than_a_placeholder() -> None:
    """The dashboard already renders `user ? user.name : 'Resident'`, so null is
    a shape it handles -- and the debt belongs to the flat regardless."""
    invoice = _to_summary(
        _row(resident_membership_id=None, resident_profile_id=None, resident_name=None)
    )
    assert invoice.user_id is None
    assert invoice.resident_name is None
    assert invoice.flat == "B-1204"


def test_overdue_is_carried_from_the_view_not_recomputed() -> None:
    assert _to_summary(_row(is_overdue=True)).is_overdue is True
    assert _to_summary(_row(is_overdue=False)).is_overdue is False


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------
def test_an_invoice_needs_at_least_one_line() -> None:
    with pytest.raises(PydanticValidationError):
        CreateInvoiceRequest(title="Empty", flat="B-1204", lineItems=[])


def test_a_line_amount_must_be_positive() -> None:
    with pytest.raises(PydanticValidationError):
        CreateInvoiceRequest(
            title="Free",
            flat="B-1204",
            lineItems=[{"description": "Nothing", "unitAmount": 0}],
        )


def test_blank_flat_is_treated_as_absent() -> None:
    """The create form seeds text inputs with '', and '' is not a flat."""
    request = CreateInvoiceRequest(
        title="Charge",
        flat="   ",
        lineItems=[{"description": "Fee", "unitAmount": 100}],
    )
    assert request.flat is None


def test_a_payment_must_be_above_zero() -> None:
    with pytest.raises(PydanticValidationError):
        RecordPaymentRequest(amount=0)


def test_billing_settings_distinguish_omitted_from_null() -> None:
    """Clearing the maintenance rate stops billing runs; leaving it alone must
    not. Only key presence tells the two apart."""
    cleared = UpdateBillingSettingsRequest(defaultMaintenanceAmount=None)
    assert "default_maintenance_amount" in cleared.model_dump(exclude_unset=True)

    untouched = UpdateBillingSettingsRequest(currency="INR")
    assert "default_maintenance_amount" not in untouched.model_dump(exclude_unset=True)


def test_due_day_cannot_land_outside_february() -> None:
    with pytest.raises(PydanticValidationError):
        UpdateBillingSettingsRequest(maintenanceDueDay=30)


def test_invoice_prefix_rejects_characters_that_would_break_a_number() -> None:
    with pytest.raises(PydanticValidationError):
        UpdateBillingSettingsRequest(invoiceNumberPrefix="IN V/2026")


