"""The resident's amenity catalogue.

Closes 3.1 of ``docs/design/RESIDENT_BACKEND_DESIGN.md``: ``POST
/amenities/{id}/bookings/request`` has never been admin-guarded -- it was
written for residents and says so -- but no endpoint let a resident learn an
amenity id. The catalogue reached a client exactly once, inside
``GET /dashboard/snapshot``, behind ``require_membership_role('admin',
'manager')``. The result was a write path a resident may legitimately call with
an argument they had no legitimate way to obtain.

**What "available" means here.** Bookable *in principle* -- the amenity exists,
is active, and is not under a temporary closure. It does **not** mean free at a
particular time. That reading needs a slot query against
``amenity_bookings``, and deciding whether a slot is free is
``amenity_occurrence_guard``'s job under an advisory lock, never a read
endpoint's: a service that answered "free" would be answering about a moment
already in the past by the time the resident submitted. See ``API.md`` 10.

**Tenancy comes from the resolved membership.** The handler passes
``MembershipContext.community_id``, which ``get_active_membership`` read out of
Postgres. Nothing in the request can widen it, and ``amenities`` carries no RLS
policy of its own, so that filter is the whole tenancy boundary -- which is why
it is applied in the query rather than after the fetch.
"""

from __future__ import annotations

from typing import Any

from app.core.formatting import clock_time
from app.domain.common_schemas import Page
from app.domain.resident_amenity_schemas import BookableAmenity
from app.domain.vocabularies import booking_mode_to_wire, weekdays_to_wire
from app.repositories import resident_amenities_repository as repo
from supabase import Client


def _amount(value: object) -> float:
    """Read a Postgres ``numeric`` off the wire as a float.

    Same reasoning as ``amenities_service._amount``: PostgREST sends ``numeric``
    as a JSON number, but the SDK has surfaced it as a string on some versions,
    and a string that reaches arithmetic three frames later is a worse bug than
    a parse here.
    """
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clock(value: object) -> str:
    """``08:00:00`` -> ``08:00``, and never ``None``.

    An amenity with no opening hour recorded reads ``00:00`` rather than null so
    a client comparing times does not have to special-case absence. It is a
    weaker claim than it looks: the booking RPC, not this string, is what
    refuses a slot outside opening hours.
    """
    return clock_time(str(value) if value is not None else None) or "00:00"


def _positive_int(value: object) -> int | None:
    """Keep a limit only if it is a usable one.

    ``0`` and negatives are dropped to ``None``. A maximum duration of zero
    minutes would be read by a booking form as "no booking is long enough",
    which is a worse answer than "this amenity sets no maximum" and is never
    what the column meant.
    """
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _is_temporarily_closed(row: dict[str, Any]) -> bool:
    """Whether a temporary closure is recorded against this amenity.

    ``temporary_closure`` is unconstrained ``jsonb``. This applies exactly the
    test ``amenities_service`` already applies to the same column -- truthiness,
    so ``null``, ``{}`` and ``[]`` all read as open -- because two readers
    disagreeing about whether the pool is shut is worse than either answer.

    ``bookable_amenity`` excludes these rows already, spelling the same test in
    SQL, so this is a second pass over rows the query should have dropped. It
    stays because no migration in this project has been applied to any database
    yet: the view's predicate has never executed, this one is covered by tests,
    and the endpoint should not depend on which of the two is true. Change one
    and change the other.
    """
    return bool(row.get("temporary_closure"))


def _to_bookable(row: dict[str, Any]) -> BookableAmenity:
    return BookableAmenity(
        id=row["id"],
        name=row["name"],
        description=row.get("description") or "",
        category=row.get("category") or "Utility",
        location=row.get("location") or "",
        image=row.get("image_url") or "",
        capacity=_positive_int(row.get("capacity")),
        booking_mode=booking_mode_to_wire(row.get("booking_mode")),
        requires_approval=bool(row.get("approval_required")),
        opening_time=_clock(row.get("opening_time")),
        closing_time=_clock(row.get("closing_time")),
        slot_duration_minutes=_positive_int(row.get("slot_duration_minutes")) or 60,
        minimum_booking_duration_minutes=_positive_int(
            row.get("minimum_booking_duration_minutes")
        ),
        maximum_booking_duration_minutes=_positive_int(
            row.get("maximum_booking_duration_minutes")
        ),
        advance_booking_window_days=_positive_int(
            row.get("advance_booking_window_days")
        ),
        max_active_bookings_per_resident=_positive_int(
            row.get("max_active_bookings_per_resident")
        ),
        closed_days=weekdays_to_wire(row.get("closed_days")),
        allow_private_booking=bool(row.get("allow_private_booking")),
        allow_guest_booking=bool(row.get("allow_guest_booking")),
        allow_recurring_booking=bool(row.get("allow_recurring_booking")),
        allow_same_day_booking=bool(row.get("allow_same_day_booking")),
        booking_fee=_amount(row.get("booking_fee")),
        security_deposit=_amount(row.get("security_deposit")),
        currency_code=(row.get("currency_code") or "INR").upper(),
        refund_policy=row.get("refund_policy") or "",
    )


def list_available(client: Client, *, community_id: str) -> Page[BookableAmenity]:
    """Every amenity in the caller's community they may request a booking on.

    Unpaged by intent: ``page`` is always 1, because an amenity catalogue is a
    fixed list a client renders whole and paging it would make the common case
    two round trips for no benefit. The envelope is still ``Page`` so every
    collection on this API has one shape -- the reason ``common_schemas.Page``
    exists -- and so paging can be added later without changing the response
    type.

    **``hasMore`` is computed, not hard-coded false.** The repository reads under
    a bound, and a bound that truncates silently would make this envelope claim
    completeness it had not checked. It is true only when the view holds rows the
    query did not return, which is the signal that this endpoint has outgrown
    being unpaged -- and the one thing a client cannot work out for itself.

    ``total`` is what the view holds less what the closure test dropped -- how
    many amenities this response believes are bookable, which is the number a
    client would render a count from. The subtraction matters in exactly one
    world: the view's predicate not being in force, where the count includes
    rows this service removes. Where it is in force nothing is dropped and the
    subtraction is zero.
    """
    rows, counted = repo.list_bookable(client, community_id)
    open_rows = [row for row in rows if not _is_temporarily_closed(row)]
    items = [_to_bookable(row) for row in open_rows]
    withheld = len(rows) < counted
    return Page(
        items=items,
        total=max(counted - (len(rows) - len(items)), len(items)),
        page=1,
        page_size=len(items),
        # `len(rows)`, not `len(items)`: rows dropped by the closure test above
        # were returned by the query, not withheld by the bound, and reporting
        # them as more to fetch would send a client after rows it is never
        # meant to see.
        has_more=withheld,
    )
