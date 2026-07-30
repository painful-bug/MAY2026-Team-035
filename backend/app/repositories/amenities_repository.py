"""Data access for amenities, bookings, approvals and the booking ledger.

Reads go through the four views from migration 0016, all ``security_invoker`` so
the caller's RLS still applies. Every write goes through an RPC, for the reason
0015 gives: PostgREST has no client-side transaction, and a booking request
writes a series, its occurrences, its guests and its charges. Half of that is a
resident holding a reservation with no charge against it, or a charge against a
reservation that does not exist.

Nothing in this module computes a total. The ledger's eight summary figures and
the amenity card's outstanding-dues badge are both database aggregates.

**None of these database objects exist on the baseline yet.** ``0016_amenities.sql``
is quarantined in ``supabase/migrations/legacy-preauth/`` awaiting a rebuild, so
the endpoints in this domain pass their contract tests but would fail against a
real database. See ``legacy-preauth/README.md``.
"""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.core.pg_errors import translate
from supabase import Client

_AMENITIES = "amenity_overview"
_BOOKINGS = "amenity_booking_overview"
_LEDGER = "amenity_ledger_overview"
_LEDGER_SUMMARY = "amenity_ledger_summary"
_GUESTS = "amenity_booking_guests"
_CHARGES = "amenity_booking_charges"
_EVENTS = "amenity_financial_events"

#: Ceilings on the two reads that cannot be paged at the database. Both
#: collapse or group rows in Python, so they have to see the whole set --
#: better an explicit bound than PostgREST's default one, discovered late.
_APPROVAL_SCAN_LIMIT = 4000
_INVOICE_SCAN_LIMIT = 4000

_AMENITY_SELECT = (
    "id, community_id, name, description, category, location, image_url,"
    "capacity, booking_mode, approval_required, status, is_active, version,"
    "created_at, updated_at, opening_time, closing_time, slot_duration_minutes,"
    "cleaning_buffer_minutes, max_active_bookings_per_resident,"
    "allow_private_booking, allow_recurring_booking, allow_guest_booking,"
    "allow_same_day_booking, enable_waitlist, enable_auto_approval, booking_fee,"
    "security_deposit, late_cancellation_charge, damage_deposit, refund_policy,"
    "currency_code, closed_days, maintenance_days, holiday_overrides,"
    "temporary_closure, minimum_booking_duration_minutes,"
    "maximum_booking_duration_minutes, advance_booking_window_days,"
    "maintenance_interval, default_maintenance_duration_minutes,"
    "auto_block_maintenance_slots, maintenance_notes, pending_requests,"
    "outstanding_dues"
)

_BOOKING_SELECT = (
    "id, community_id, booking_series_id, amenity_id, amenity_name, booking_mode,"
    "booking_date, starts_at, ends_at, is_exclusive, buffer_minutes,"
    "occupant_count, status, stored_status, cancelled_at,"
    "cancellation_reason_code, cancellation_reason, cancelled_by_resident,"
    "force_cancelled, version, created_at, updated_at, title, booking_type,"
    "source, is_private, requires_approval, guest_count, notes, charge_override,"
    "department, series_status, requested_at, approved_at, rejected_at,"
    "rejection_reason, rejection_reason_code, unit_id, unit_code, tower,"
    "requested_by_membership_id, resident_profile_id, resident_name, day_count"
)

_LEDGER_SELECT = (
    "id, community_id, booking_id, booking_series_id, amenity_id, amenity_name,"
    "unit_id, unit_code, resident_profile_id, resident_name,"
    "requested_by_membership_id, booking_date, starts_at, ends_at, booking_type,"
    "title, notes, booking_status, force_cancelled, cancelled_at,"
    "cancellation_reason, approved_at, created_at, updated_at, payment_reference,"
    "deposit_amount, deposit_paid, booking_charges, additional_charges,"
    "amount_paid, refund_amount, damage_amount, total_amount,"
    "outstanding_deposit, remaining_refund, payment_status"
)


def _safe_search(value: str) -> str:
    """Strip the characters that would change what the query means.

    ``%`` and ``_`` are ``ilike`` wildcards; ``,`` ``(`` ``)`` are PostgREST's
    own filter delimiters. An unescaped one widens the query silently rather than
    failing -- which on the approvals tab means showing an admin a request from
    another amenity and letting them decide it.
    """
    return (
        value.replace("%", "").replace("_", "")
        .replace(",", " ").replace("(", " ").replace(")", " ")
        .strip()
        .lower()
    )


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


def list_amenities(
    client: Client,
    community_id: str,
    *,
    search: str | None,
    category: str | None,
    status: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """Page through the community's amenities, newest configuration last."""
    query = (
        client.table(_AMENITIES)
        .select(_AMENITY_SELECT, count="exact")
        .eq("community_id", community_id)
    )

    if category:
        query = query.eq("category", category)
    if status:
        query = query.eq("status", status)
    if search:
        safe = _safe_search(search)
        if safe:
            query = query.ilike("search_text", f"%{safe}%")

    response = (
        query.order("name").range(offset, offset + limit - 1).execute()
    )
    return (response.data or []), (response.count or 0)


def get_amenity(client: Client, community_id: str, amenity_id: str) -> dict:
    """Fetch one amenity with every settings column, or raise."""
    response = (
        client.table(_AMENITIES)
        .select(_AMENITY_SELECT)
        .eq("community_id", community_id)
        .eq("id", amenity_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Amenity not found.")
    return rows[0]


def save_amenity(
    client: Client, community_id: str, amenity_id: str | None, payload: dict
) -> str:
    """Create or update an amenity and its settings in one transaction (RPC)."""
    try:
        response = client.rpc(
            "save_amenity",
            {
                "p_community_id": community_id,
                "p_amenity_id": amenity_id,
                "p_payload": payload,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not save the amenity.") from exc

    result = response.data
    if isinstance(result, list):
        result = result[0] if result else None
    if not result:
        raise NotFoundError("Amenity was not saved.")
    return str(result)


def delete_amenity(client: Client, amenity_id: str) -> None:
    """Delete an amenity (RPC). Refused once anything has been booked on it."""
    try:
        client.rpc("delete_amenity", {"p_amenity_id": amenity_id}).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not delete the amenity.") from exc


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


def list_bookings(
    client: Client,
    community_id: str,
    *,
    amenity_id: str | None = None,
    booking_date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    statuses: tuple[str, ...] | None = None,
    membership_id: str | None = None,
    series_id: str | None = None,
    timeline_only: bool = False,
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """Page through occupied days.

    ``timeline_only`` drops the statuses the timeline does not paint -- pending,
    rejected and cancelled -- matching ``isTimelineVisibleBooking``. It is a
    separate flag rather than a default because the approvals tab and the ledger
    both want exactly the rows it would hide.
    """
    query = (
        client.table(_BOOKINGS)
        .select(_BOOKING_SELECT, count="exact")
        .eq("community_id", community_id)
    )

    if amenity_id:
        query = query.eq("amenity_id", amenity_id)
    if booking_date:
        query = query.eq("booking_date", booking_date)
    if date_from:
        query = query.gte("booking_date", date_from)
    if date_to:
        query = query.lte("booking_date", date_to)
    if series_id:
        query = query.eq("booking_series_id", series_id)
    if membership_id:
        query = query.eq("requested_by_membership_id", membership_id)
    if statuses:
        query = query.in_("stored_status", list(statuses))
    if timeline_only:
        query = query.in_("stored_status", ["approved", "confirmed", "blocked"])
    if search:
        safe = _safe_search(search)
        if safe:
            query = query.ilike("search_text", f"%{safe}%")

    response = (
        query.order("booking_date", desc=True)
        .order("starts_at")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def get_booking(client: Client, community_id: str, occurrence_id: str) -> dict:
    """Fetch one occupied day, or raise."""
    response = (
        client.table(_BOOKINGS)
        .select(_BOOKING_SELECT)
        .eq("community_id", community_id)
        .eq("id", occurrence_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Booking not found.")
    return rows[0]


def list_series_first_days(
    client: Client,
    community_id: str,
    *,
    amenity_id: str,
    statuses: tuple[str, ...],
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """The approvals tab: one row per REQUEST, carrying its first day.

    Ordered by request time rather than by date, because the queue an admin works
    through is chronological in when it was asked, not in when it is for.
    """
    query = (
        client.table(_BOOKINGS)
        .select(_BOOKING_SELECT, count="exact")
        .eq("community_id", community_id)
        .eq("amenity_id", amenity_id)
        .eq("source", "resident")
        .in_("series_status", list(statuses))
    )

    response = (
        query.order("requested_at", desc=True)
        .order("booking_date")
        # Bounded rather than unbounded, because collapsing has to see every day
        # of every request before it can page: the row count is days, not
        # requests. 4000 days is several years of approvals for one amenity, and
        # an explicit ceiling is better than discovering PostgREST's default one
        # the day a queue crosses it.
        .limit(_APPROVAL_SCAN_LIMIT)
        .execute()
    )
    rows = response.data or []

    # Collapse to one row per series, keeping the earliest day. Done here rather
    # than in SQL because PostgREST cannot express DISTINCT ON, and a view that
    # pre-collapsed would have to choose an ordering for every caller.
    seen: dict[str, dict] = {}
    for row in rows:
        series_id = row.get("booking_series_id")
        if series_id and series_id not in seen:
            seen[series_id] = row
    collapsed = list(seen.values())
    return collapsed[offset : offset + limit], len(collapsed)


def sum_outstanding_by_unit(
    client: Client, community_id: str, unit_ids: list[str]
) -> dict[str, float]:
    """What each flat still owes on its invoices, for a page of approvals.

    One query for every flat on the page rather than one per flat. The balances
    themselves are already final -- each is maintained by ``record_payment`` and
    constrained by a CHECK -- so grouping them here is not the same as computing
    a total in Python.
    """
    if not unit_ids:
        return {}

    response = (
        client.table("invoice_overview")
        .select("unit_id, outstanding_amount")
        .eq("community_id", community_id)
        .in_("unit_id", unit_ids)
        .in_("status", ["draft", "issued", "partially_paid"])
        .limit(_INVOICE_SCAN_LIMIT)
        .execute()
    )

    totals: dict[str, float] = {}
    for row in response.data or []:
        unit_id = row.get("unit_id")
        if not unit_id:
            continue
        totals[unit_id] = totals.get(unit_id, 0.0) + float(
            row.get("outstanding_amount") or 0
        )
    return {unit_id: round(total, 2) for unit_id, total in totals.items()}


def list_series_dates(
    client: Client, community_id: str, series_ids: list[str]
) -> dict[str, list[str]]:
    """Every live day of each request, so an approval row can say "3 days".

    One query for the whole page rather than one per row: the approvals tab shows
    twenty requests, and twenty round trips to render a date list is how a list
    endpoint becomes the slowest screen in the product.
    """
    if not series_ids:
        return {}

    response = (
        client.table(_BOOKINGS)
        .select("booking_series_id, booking_date")
        .eq("community_id", community_id)
        .in_("booking_series_id", series_ids)
        .not_.in_("stored_status", ["rejected", "cancelled"])
        .order("booking_date")
        .execute()
    )

    grouped: dict[str, list[str]] = {}
    for row in response.data or []:
        grouped.setdefault(row["booking_series_id"], []).append(row["booking_date"])
    return grouped


def list_guests(
    client: Client, community_id: str, series_ids: list[str]
) -> dict[str, list[dict]]:
    """Guests for a page of bookings, grouped by request. One query, same reason."""
    if not series_ids:
        return {}

    response = (
        client.table(_GUESTS)
        .select("id, booking_series_id, guest_name, phone_e164")
        .eq("community_id", community_id)
        .in_("booking_series_id", series_ids)
        .order("created_at")
        .execute()
    )

    grouped: dict[str, list[dict]] = {}
    for row in response.data or []:
        grouped.setdefault(row["booking_series_id"], []).append(row)
    return grouped


def request_booking(client: Client, amenity_id: str, payload: dict) -> str:
    """A resident's booking request: series, occurrences, guests, charges (RPC)."""
    try:
        response = client.rpc(
            "request_amenity_booking",
            {"p_amenity_id": amenity_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not create the booking.") from exc
    return _one_id(response.data, "Booking was not created.")


def create_admin_booking(client: Client, amenity_id: str, payload: dict) -> str:
    """An admin booking on a resident's behalf, confirmed on creation (RPC)."""
    try:
        response = client.rpc(
            "create_admin_amenity_booking",
            {"p_amenity_id": amenity_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not create the booking.") from exc
    return _one_id(response.data, "Booking was not created.")


def block_slot(client: Client, amenity_id: str, payload: dict) -> str:
    """Reserve a slot administratively (RPC)."""
    try:
        response = client.rpc(
            "block_amenity_slot",
            {"p_amenity_id": amenity_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not block the slot.") from exc
    return _one_id(response.data, "Slot was not blocked.")


def approve_booking(client: Client, series_id: str) -> str:
    """Approve a whole request -- every day of it (RPC)."""
    try:
        response = client.rpc(
            "approve_amenity_booking", {"p_series_id": series_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not approve the request.") from exc
    return _one_id(response.data, "Request was not approved.")


def reject_booking(client: Client, series_id: str, payload: dict) -> str:
    """Reject a whole request and free its slots (RPC)."""
    try:
        response = client.rpc(
            "reject_amenity_booking",
            {"p_series_id": series_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not reject the request.") from exc
    return _one_id(response.data, "Request was not rejected.")


def cancel_occurrences(client: Client, payload: dict) -> int:
    """Cancel selected days (RPC). Returns how many were cancelled."""
    try:
        response = client.rpc(
            "cancel_amenity_occurrences", {"p_payload": payload}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not cancel the booking.") from exc

    result = response.data
    if isinstance(result, list):
        result = result[0] if result else 0
    return int(result or 0)


def force_cancel_booking(client: Client, occurrence_id: str, payload: dict) -> str:
    """Override a booking the resident still wants (RPC)."""
    try:
        response = client.rpc(
            "force_cancel_amenity_booking",
            {"p_occurrence_id": occurrence_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not cancel the booking.") from exc
    return _one_id(response.data, "Booking was not cancelled.")


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


def list_ledger(
    client: Client,
    community_id: str,
    *,
    amenity_id: str | None = None,
    payment_status: str | None = None,
    booking_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """Page through the ledger, newest booking first."""
    query = (
        client.table(_LEDGER)
        .select(_LEDGER_SELECT, count="exact")
        .eq("community_id", community_id)
    )

    if amenity_id:
        query = query.eq("amenity_id", amenity_id)
    if payment_status:
        query = query.eq("payment_status", payment_status)
    if booking_status:
        query = query.eq("booking_status", booking_status)
    if date_from:
        query = query.gte("booking_date", date_from)
    if date_to:
        query = query.lte("booking_date", date_to)
    if search:
        safe = _safe_search(search)
        if safe:
            query = query.ilike("resident_name", f"%{safe}%")

    response = (
        query.order("booking_date", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return (response.data or []), (response.count or 0)


def get_ledger_row(client: Client, community_id: str, occurrence_id: str) -> dict:
    """Fetch one ledger row, or raise."""
    response = (
        client.table(_LEDGER)
        .select(_LEDGER_SELECT)
        .eq("community_id", community_id)
        .eq("id", occurrence_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise NotFoundError("Booking not found.")
    return rows[0]


def fetch_report_totals(client: Client, community_id: str, payload: dict) -> dict:
    """The reports page's six KPIs, aggregated by Postgres (RPC).

    An RPC rather than a view because the filters have to apply BEFORE the
    aggregate, and rather than a Python sum because summing a page of rows gives
    the revenue of the page.
    """
    try:
        response = client.rpc(
            "amenity_report_totals",
            {"p_community_id": community_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not build the report.") from exc

    rows = response.data
    if isinstance(rows, list):
        rows = rows[0] if rows else None
    return rows or {}


def fetch_ledger_summary(
    client: Client, community_id: str, amenity_id: str
) -> dict | None:
    """The eight cards above the ledger table.

    Returns None for an amenity nobody has booked -- the view groups by amenity,
    so there is no row rather than a row of zeros. The service turns that into
    zeros, because the tab has to render something.
    """
    response = (
        client.table(_LEDGER_SUMMARY)
        .select(
            "total_bookings, total_revenue, pending_deposits, refund_pending,"
            "refund_completed, damage_deductions, outstanding_refunds,"
            "completed_transactions"
        )
        .eq("community_id", community_id)
        .eq("amenity_id", amenity_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def list_financial_events(
    client: Client, community_id: str, occurrence_ids: list[str]
) -> dict[str, list[dict]]:
    """Every refund, deduction and payment for a page of ledger rows.

    Two queries -- charges, then their events -- rather than one per row. The
    ledger renders refund history, damage history and an audit timeline for every
    transaction it lists, which is three lists per row and would be three round
    trips per row done naively.
    """
    if not occurrence_ids:
        return {}

    charges = (
        client.table(_CHARGES)
        .select("id, booking_occurrence_id, charge_type")
        .eq("community_id", community_id)
        .in_("booking_occurrence_id", occurrence_ids)
        .execute()
    )
    charge_rows = charges.data or []
    if not charge_rows:
        return {}

    by_charge = {row["id"]: row for row in charge_rows}
    events = (
        client.table(_EVENTS)
        .select(
            "id, booking_charge_id, actor_membership_id, event_type, amount,"
            "payment_reference, reason, notes, created_at"
        )
        .eq("community_id", community_id)
        .in_("booking_charge_id", list(by_charge))
        .order("created_at")
        .execute()
    )

    grouped: dict[str, list[dict]] = {}
    for event in events.data or []:
        charge = by_charge.get(event["booking_charge_id"])
        if not charge:
            continue
        enriched = dict(event, charge_type=charge["charge_type"])
        grouped.setdefault(charge["booking_occurrence_id"], []).append(enriched)
    return grouped


def record_payment(client: Client, occurrence_id: str, payload: dict) -> str:
    """Record money received against one charge (RPC). Idempotent on reference."""
    try:
        response = client.rpc(
            "record_amenity_payment",
            {"p_occurrence_id": occurrence_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not record the payment.") from exc
    return _one_id(response.data, "Payment was not recorded.")


def refund_deposit(client: Client, occurrence_id: str, payload: dict) -> str:
    """Return what is left of the deposit (RPC). The amount is computed there."""
    try:
        response = client.rpc(
            "refund_amenity_deposit",
            {"p_occurrence_id": occurrence_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not process the refund.") from exc
    return _one_id(response.data, "Refund was not processed.")


def deduct_damage(client: Client, occurrence_id: str, payload: dict) -> str:
    """Take damage out of the held deposit (RPC). Capped at what is left."""
    try:
        response = client.rpc(
            "deduct_amenity_damage",
            {"p_occurrence_id": occurrence_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not record the damage deduction."
        ) from exc
    return _one_id(response.data, "Damage deduction was not recorded.")


def add_charge(client: Client, occurrence_id: str, payload: dict) -> str:
    """Add an extra charge after the fact (RPC)."""
    try:
        response = client.rpc(
            "add_amenity_charge",
            {"p_occurrence_id": occurrence_id, "p_payload": payload},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not add the charge.") from exc
    return _one_id(response.data, "Charge was not added.")


def _one_id(data: object, missing_message: str) -> str:
    """PostgREST returns a scalar RPC result bare or wrapped in a list depending
    on the function's return type. Both shapes arrive here."""
    result = data
    if isinstance(result, list):
        result = result[0] if result else None
    if not result:
        raise NotFoundError(missing_message)
    return str(result)
