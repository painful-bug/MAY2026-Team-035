"""Data access for the resident's invoices, bookings and payments.

Reads go through the two `0033` views; both settlements go through SECURITY
DEFINER RPCs, because each of them touches several tables that must move together
— and PostgREST has no client-side transaction.

**The ownership filter here is not the security boundary.** `0033` puts
`is_own_invoice` and `is_own_booking` behind both the policies and the RPCs. The
predicates below are the *query*, not the guard: a repository that forgot one
would return nothing it should not, and an RPC that was called with someone
else's id refuses regardless of what this module did.

**Invoices are filtered on `is_mine`, which is `is_own_invoice` itself.** Not on
`membership_id`, which is a *narrower* rule than the one the write path applies:
a bill raised against the flat rather than against a person has a null
`membership_id`, and filtering on one hides a bill the resident can pay. The
community filter beside it is the tenancy scope, since a caller with flats in two
communities is asking about the one they are signed in to.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client

_INVOICES = "resident_invoice_overview"
_BOOKINGS = "resident_booking_overview"

_INVOICE_SELECT = (
    "id, invoice_number, invoice_type, title, status, stored_status, issued_on,"
    "due_on, total_amount, amount_paid, outstanding_amount, currency_code, notes,"
    "paid_at, payment_method, instrument_label, is_overdue, is_payable, created_at"
)

_BOOKING_SELECT = (
    "id, booking_series_id, amenity_id, amenity_name, title, booking_date,"
    "starts_at, ends_at, status, stored_status, guest_count, is_private, notes,"
    "cancellation_reason, rejection_reason, total_amount, amount_paid,"
    "outstanding_amount, is_payable, is_upcoming, created_at"
)


def list_invoices(
    client: Client,
    *,
    community_id: str,
    status: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """A page of the caller's invoices, newest issue first, with the total.

    ``status`` is the *wire* word — `Unpaid` or `Paid` — because those are the two
    lists the screen has and a tab is a question about what a bill looks like, not
    about whether it can be paid. Splitting on `is_payable` instead puts every
    cancelled bill in the Paid tab, since a voided invoice is not payable and
    never was paid.
    """
    query = (
        client.table(_INVOICES)
        .select(_INVOICE_SELECT, count="exact")
        .eq("community_id", community_id)
        .eq("is_mine", True)
    )
    if status is not None:
        query = query.eq("status", status)

    response = (
        query.order("issued_on", desc=True)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def get_invoice(
    client: Client, *, community_id: str, invoice_id: str
) -> dict[str, Any] | None:
    """One invoice of the caller's, or ``None``.

    Ownership is part of the lookup rather than a check afterwards, so "not
    yours" and "not there" cannot be told apart.
    """
    rows = (
        client.table(_INVOICES)
        .select(_INVOICE_SELECT)
        .eq("id", invoice_id)
        .eq("community_id", community_id)
        .eq("is_mine", True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_bookings(
    client: Client,
    *,
    membership_id: str,
    upcoming: bool | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """A page of the caller's own amenity bookings, soonest first."""
    query = (
        client.table(_BOOKINGS)
        .select(_BOOKING_SELECT, count="exact")
        .eq("requested_by_membership_id", membership_id)
    )
    if upcoming is not None:
        query = query.eq("is_upcoming", upcoming)

    response = (
        query.order("starts_at", desc=True).range(offset, offset + limit - 1).execute()
    )
    return (response.data or []), (response.count or 0)


def get_booking(
    client: Client, *, membership_id: str, booking_id: str
) -> dict[str, Any] | None:
    rows = (
        client.table(_BOOKINGS)
        .select(_BOOKING_SELECT)
        .eq("id", booking_id)
        .eq("requested_by_membership_id", membership_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def find_invoice_payment(
    client: Client, *, invoice_id: str, key: str
) -> dict[str, Any] | None:
    """A prior attempt under this idempotency key, or ``None`` (RPC).

    Called **before the gateway**, which is the whole point of it existing
    separately from the settlement RPC's own replay branch. Raises a conflict if
    the key already settled a different invoice.
    """
    try:
        response = client.rpc(
            "find_resident_payment",
            {"p_invoice_id": invoice_id, "p_key": key},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not check the payment.") from exc
    return response.data or None


def settle_invoice(
    client: Client, *, invoice_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Record a payment outcome against an invoice (RPC). Returns the payment row.

    ``payload`` carries the outcome the simulator produced and the masked label —
    **never a card number, a CVV or an expiry.** Those are read by a pure
    function in the service and discarded there; nothing that could carry one
    reaches this call.

    What comes back is the row as stored, not an echo of what was sent, so a
    replay describes the attempt that actually settled.
    """
    try:
        response = client.rpc(
            "settle_resident_payment",
            {"p_invoice_id": invoice_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not record the payment.") from exc
    return response.data or {}


def find_booking_payment(
    client: Client, *, booking_id: str, key: str
) -> dict[str, Any] | None:
    """A prior booking-payment attempt under this key, or ``None`` (RPC)."""
    try:
        response = client.rpc(
            "find_booking_payment",
            {"p_booking_id": booking_id, "p_key": key},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not check the payment.") from exc
    return response.data or None


def settle_booking(
    client: Client, *, booking_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Settle a booking payment and confirm the booking, or neither (RPC).

    The two halves are one statement in the database for the reason `US-2.12`
    exists: a payment recorded in one transaction and a booking confirmed in
    another is precisely the failure the story describes.
    """
    try:
        response = client.rpc(
            "settle_amenity_booking_payment",
            {"p_booking_id": booking_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not record the payment.") from exc
    return response.data or {}
