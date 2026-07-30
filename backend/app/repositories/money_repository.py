"""Data access for invoices, payments and billing settings.

Reads go through the three views from migration 0015, all declared
``security_invoker`` so RLS still applies to the caller. Every write goes through
an RPC: issuing an invoice touches three tables and a counter, recording a
payment touches three and recomputes a balance, and PostgREST has no client-side
transaction -- so doing either here would leave an invoice whose header disagreed
with its own lines the first time the second call failed.

No total is ever computed in this module. ``fetch_collection_summary`` reads a
database aggregate rather than summing rows, because summing floats in Python
produces a figure that is wrong in a way nobody notices.
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.core.pg_errors import translate
from supabase import Client

_INVOICES = "invoice_overview"
_PAYMENTS = "payment_overview"
_SUMMARY = "collection_summary"
_LINE_ITEMS = "invoice_line_items"
_SETTINGS = "community_billing_settings"

_INVOICE_SELECT = (
    "id, community_id, unit_id, invoice_number, invoice_type, title, status,"
    "billing_period_start, billing_period_end, issued_on, due_on,"
    "subtotal_amount, tax_amount, total_amount, outstanding_amount, amount_paid,"
    "currency_code, notes, created_at, updated_at, unit_code, tower,"
    "resident_membership_id, resident_profile_id, resident_name,"
    "paid_on, payment_method, is_overdue"
)

_PAYMENT_SELECT = (
    "id, community_id, invoice_id, amount, currency_code, payment_method,"
    "provider_reference, status, paid_at, notes, created_at, invoice_number,"
    "invoice_title, unit_id, unit_code, payer_profile_id, payer_name,"
    "received_by_membership_id"
)


def _safe_search(value: str) -> str:
    """Strip the characters that would change what the query means.

    ``%`` and ``_`` are wildcards to ``ilike``; ``,`` ``(`` ``)`` are PostgREST's
    own filter delimiters. An unescaped one silently widens the query rather than
    failing, which on a money screen means showing an admin somebody else's
    invoice.
    """
    return (
        value.replace("%", "").replace("_", "")
        .replace(",", " ").replace("(", " ").replace(")", " ")
        .strip()
        .lower()
    )


def list_invoices(
    client: Client,
    community_id: str,
    *,
    search: str | None,
    statuses: tuple[str, ...] | None,
    unit_id: str | None,
    invoice_type: str | None,
    overdue_only: bool,
    issued_from: str | None,
    issued_to: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """Page through the community's invoices.

    The search is one ``ilike`` against the view's precomputed ``search_text``,
    which spans the invoice title, its number, the flat code and the current
    resident's name -- the dashboard searches resident name *and* flat in a
    single box (``Maintenance.jsx:23``), which is a join PostgREST cannot filter
    across.
    """
    query = (
        client.table(_INVOICES)
        .select(_INVOICE_SELECT, count="exact")
        .eq("community_id", community_id)
    )

    if statuses:
        query = query.in_("status", list(statuses))
    if unit_id:
        query = query.eq("unit_id", unit_id)
    if invoice_type:
        query = query.eq("invoice_type", invoice_type)
    if overdue_only:
        query = query.eq("is_overdue", True)
    if issued_from:
        query = query.gte("issued_on", issued_from)
    if issued_to:
        query = query.lte("issued_on", issued_to)
    if search:
        safe = _safe_search(search)
        if safe:
            query = query.ilike("search_text", f"%{safe}%")

    response = (
        query.order("due_on", desc=True)
        .order("invoice_number", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def get_invoice(client: Client, community_id: str, invoice_id: str) -> dict:
    """Fetch one invoice, or raise."""
    response = (
        client.table(_INVOICES)
        .select(_INVOICE_SELECT)
        .eq("community_id", community_id)
        .eq("id", invoice_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Invoice not found.")
    return rows[0]


def list_line_items(client: Client, community_id: str, invoice_id: str) -> list[dict]:
    """The charges making up one invoice, in the order they were entered."""
    response = (
        client.table(_LINE_ITEMS)
        .select("id, description, quantity, unit_amount, total_amount, sort_order")
        .eq("community_id", community_id)
        .eq("invoice_id", invoice_id)
        .order("sort_order")
        .execute()
    )
    return response.data or []


def list_payments(
    client: Client,
    community_id: str,
    *,
    invoice_id: str | None = None,
    search: str | None = None,
    method: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """Page through recorded payments -- the collection log."""
    query = (
        client.table(_PAYMENTS)
        .select(_PAYMENT_SELECT, count="exact")
        .eq("community_id", community_id)
    )

    if invoice_id:
        query = query.eq("invoice_id", invoice_id)
    if method:
        query = query.eq("payment_method", method)
    if search:
        safe = _safe_search(search)
        if safe:
            query = query.ilike("search_text", f"%{safe}%")

    response = (
        query.order("paid_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def fetch_collection_summary(client: Client, community_id: str) -> dict | None:
    """The community's collection totals, aggregated by Postgres.

    Returns None for a community with no invoices at all -- the view groups by
    community, so a founding community has no row rather than a row of zeros. The
    service turns that into zeros, because the dashboard must render something
    (FRONTEND_MEETING_AGENDA.md item 7).
    """
    response = (
        client.table(_SUMMARY)
        .select(
            "total_collected, total_outstanding, total_billed, paid_count,"
            "unpaid_count, invoice_count, overdue_count, overdue_amount, currency_code"
        )
        .eq("community_id", community_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def fetch_billing_settings(client: Client, community_id: str) -> dict | None:
    """The community's billing configuration, or None before it has one."""
    response = (
        client.table(_SETTINGS)
        .select(
            "community_id, currency_code, invoice_number_prefix,"
            "default_maintenance_amount, maintenance_due_day, default_tax_percent,"
            "auto_billing_enabled, auto_billing_day, late_fee_enabled,"
            "late_fee_amount, late_fee_grace_days, late_fee_period,"
            "updated_at"
        )
        .eq("community_id", community_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def issue_invoice(client: Client, community_id: str, payload: dict) -> str:
    """Create an invoice with its line items and number (RPC)."""
    try:
        response = client.rpc(
            "issue_invoice",
            {"p_community_id": community_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not issue the invoice.") from exc

    invoice_id = response.data
    if isinstance(invoice_id, list):
        invoice_id = invoice_id[0] if invoice_id else None
    if not invoice_id:
        raise NotFoundError("Invoice was not created.")
    return str(invoice_id)


def record_payment(client: Client, invoice_id: str, payload: dict) -> str:
    """Record a payment and settle the invoice against it (RPC).

    Idempotent on ``provider_reference``: a repeat call with the same reference
    returns the id of the payment already recorded, so this is safe to retry.
    """
    try:
        response = client.rpc(
            "record_payment",
            {"p_invoice_id": invoice_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not record the payment.") from exc

    payment_id = response.data
    if isinstance(payment_id, list):
        payment_id = payment_id[0] if payment_id else None
    if not payment_id:
        raise NotFoundError("Payment was not recorded.")
    return str(payment_id)


def run_maintenance_billing(
    client: Client, community_id: str, payload: dict
) -> dict:
    """Issue one maintenance invoice per occupied flat for a period (RPC)."""
    try:
        response = client.rpc(
            "run_maintenance_billing",
            {"p_community_id": community_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not run the billing.") from exc

    rows = response.data
    if isinstance(rows, list):
        rows = rows[0] if rows else None
    return rows or {"invoiced": 0, "skipped": 0, "total_amount": 0}


def void_invoice(client: Client, invoice_id: str, reason: str | None) -> None:
    """Cancel an invoice (RPC). Refuses once a payment has succeeded on it."""
    try:
        client.rpc(
            "void_invoice", {"p_invoice_id": invoice_id, "p_reason": reason}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not void the invoice.") from exc


def update_billing_settings(client: Client, community_id: str, patch: dict) -> None:
    """Patch the billing configuration (RPC), creating the row on first use."""
    try:
        client.rpc(
            "update_billing_settings",
            {"p_community_id": community_id, "p_patch": patch},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not update the billing settings."
        ) from exc


def get_payment(client: Client, community_id: str, payment_id: str) -> dict:
    """Fetch one recorded payment, or raise."""
    response = (
        client.table(_PAYMENTS)
        .select(_PAYMENT_SELECT)
        .eq("community_id", community_id)
        .eq("id", payment_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Payment not found.")
    return rows[0]
