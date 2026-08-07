"""Data access for the resident amenity catalogue.

Reads ``bookable_amenity`` (migration ``0029``), **not** ``amenity_overview``.
Two views over one table, each owned by the surface that reads it.

``amenity_overview`` is the admin card's projection: two lateral aggregates per
row, one counting bookings by status and one summing charges against payments to
produce ``outstanding_dues``. A resident is shown neither -- see
``resident_amenity_schemas`` for why -- so reading it would compute both and
discard them. The cost is the smaller half of the argument. The larger half is
that sharing it would leave the resident response one column away from an admin
field: the next column added there for the admin card would be in scope here the
moment it was added, by someone with no reason to think about residents at all.

``bookable_amenity`` already applies the row filter -- active, not temporarily
closed -- so this module does not repeat it, with one exception noted on
``list_bookable``. What is left here is tenancy, ordering and a bound.

No RPC and no write path. This module is read-only by construction; the resident
booking write already exists in ``amenities_repository`` and goes through the
occurrence guard.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

_BOOKABLE_AMENITY = "bookable_amenity"

#: A community's amenity catalogue is tens of rows -- a bound that exists so a
#: pathological community cannot page the whole view into memory, not a
#: pagination scheme. If a real deployment ever approaches this, the endpoint
#: needs proper paging rather than a bigger number.
#:
#: The bound is asked for **alongside an exact count**, so reaching it is
#: visible rather than silent: the caller can see that more rows exist than were
#: returned. A bound that truncates without saying so is the same failure as a
#: page that reports ``hasMore: false`` while holding data back, and this file
#: is the only place that knows the truncation happened.
_CATALOGUE_SCAN_LIMIT = 500

_BOOKABLE_SELECT = (
    "id, name, description, category, location, image_url, capacity,"
    "booking_mode, approval_required, opening_time, closing_time,"
    "slot_duration_minutes, minimum_booking_duration_minutes,"
    "maximum_booking_duration_minutes, advance_booking_window_days,"
    "max_active_bookings_per_resident, closed_days, allow_private_booking,"
    "allow_guest_booking, allow_recurring_booking, allow_same_day_booking,"
    "booking_fee, security_deposit, currency_code, refund_policy,"
    "temporary_closure"
)


def list_bookable(
    client: Client, community_id: str
) -> tuple[list[dict[str, Any]], int]:
    """The community's bookable amenities ordered by name, and how many exist.

    ``community_id`` is the only predicate applied here. It is not a convenience:
    ``amenities`` carries no RLS policy of its own, so the view's
    ``security_invoker`` inherits nothing, and this filter -- taken from the
    membership ``get_active_membership`` resolved out of Postgres -- is the whole
    tenancy boundary.

    The second half of the return value is the count **before** the bound, which
    is the only reason the count is asked for: everywhere it matters these two
    numbers are equal, and the endpoint exists to notice the day they are not.
    ``count="exact"`` is the same instrument ``notifications_repository`` uses
    for the same purpose -- there to page a feed, here to prove a page is whole.

    ``temporary_closure`` is selected even though the view has already excluded
    every row where it is truthy, because the service tests it again in Python.
    That duplication is deliberate and is explained in ``0029``: no migration in
    this project has been applied to any database yet, so the view's predicate
    has never executed, while the service's has tests behind it.
    """
    response = (
        client.table(_BOOKABLE_AMENITY)
        .select(_BOOKABLE_SELECT, count="exact")
        .eq("community_id", community_id)
        .order("name")
        .limit(_CATALOGUE_SCAN_LIMIT)
        .execute()
    )
    rows = response.data or []
    # `count` is null when PostgREST was not asked for one, or on an SDK that
    # does not surface it. Falling back to the rows in hand keeps the endpoint
    # honest in the only direction it can be: it claims completeness, which is
    # what it claimed before the count existed.
    return rows, (response.count if response.count is not None else len(rows))
