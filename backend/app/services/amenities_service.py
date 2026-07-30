"""Amenity service: the catalogue, bookings, approvals, the ledger and reports.

Three decisions worth stating up front.

**Nothing here adds money up.** Every ledger figure and every summary card comes
from a database aggregate, computed in ``numeric``. Python renames fields and
translates vocabularies; the moment it starts summing amounts there are two
answers to "what deposits are we holding" and they drift.

**Nothing here decides whether a slot is free.** That is
``amenity_occurrence_guard`` in migration 0016, which takes an advisory lock
before it looks. A service-layer availability check would be the classic
check-then-act race: two residents booking the last place both read a free
amenity and both write.

**Approval belongs to the request, not the day.** ``list_approvals`` returns one
row per booking series, carrying the first day plus ``dayCount`` and ``dates``.
The frontend approves one day at a time because it has no series to approve --
see the 0016 header.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.core.exceptions import ValidationError
from app.core.formatting import clock_time
from app.domain.amenity_schemas import (
    AddChargeRequest,
    AdminBookingRequest,
    AmenityDetail,
    AmenityGuest,
    AmenityReport,
    AmenitySummary,
    ApprovalRequest,
    AuditEntry,
    AvailabilitySettings,
    BlockSlotRequest,
    BookingSettings,
    BookingSummary,
    CancelBookingRequest,
    DamageDeductionRequest,
    ForceCancelRequest,
    LedgerEntry,
    LedgerSummary,
    LedgerTransaction,
    MaintenanceSettings,
    OperatingHours,
    PaymentSettings,
    RecordAmenityPaymentRequest,
    RefundDepositRequest,
    RejectBookingRequest,
    ReportKpis,
    ReportOption,
    ReportOptions,
    ReportRow,
    ResidentBookingRequest,
    SaveAmenityRequest,
)
from app.domain.common_schemas import Page
from app.domain.vocabularies import (
    amenity_status_to_wire,
    booking_mode_to_storage,
    booking_mode_to_wire,
    weekdays_to_storage,
    weekdays_to_wire,
)
from app.repositories import amenities_repository as repo
from app.repositories import tenancy_repository as dash_repo
from supabase import Client

_CATEGORIES = ("Sports", "Fitness", "Recreation", "Events", "Utility")
_MAINTENANCE_INTERVALS = ("Weekly", "Monthly", "Quarterly", "As Needed")
_BOOKING_TYPES = (
    "resident",
    "private-event",
    "society-event",
    "maintenance-reservation",
)
_CHARGE_TYPES = ("booking", "deposit", "additional", "late_cancellation")
_APPROVAL_FILTERS = {
    "pending": ("pending",),
    "approved": ("approved", "confirmed"),
    "rejected": ("rejected",),
    "cancelled": ("cancelled",),
    "all": ("pending", "approved", "confirmed", "rejected", "cancelled"),
}
# Statuses the ledger treats as money still in play, for `availableActions`.
_REFUNDABLE_STATUSES = ("completed", "cancelled")
_FORCE_CANCELLABLE_STATUSES = ("approved", "confirmed")


def _community(client: Client, user_id: str) -> str:
    """The community the caller belongs to.

    Resolved here rather than in the router, matching every other service: the
    router layer has no repository call in it anywhere else and this is not the
    place to introduce the first one.
    """
    return dash_repo.get_caller_community_id(client, user_id)


def _amount(value: object) -> float:
    """Read a Postgres ``numeric`` off the wire as a float.

    PostgREST sends ``numeric`` as a JSON number, but the SDK has surfaced it as
    a string on some versions -- and ``float("500.00")`` is correct while
    ``500.00 + "500.00"`` is a TypeError three call frames away. Parsed once,
    here.
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


def _clock(value: object) -> str:
    """``08:00:00`` -> ``08:00``. Never None: the timeline positions a block by
    parsing this string, and a missing one would collapse the block to zero
    width rather than fail visibly."""
    return clock_time(str(value) if value is not None else None) or "00:00"


def _display_hours(opening: object, closing: object) -> str:
    """``06:00``, ``22:00`` -> ``6:00 AM - 10:00 PM``.

    Composed here rather than in the view because it is a display string, and
    the schema is not where display belongs -- the same rule 0015 followed for
    the flat/tower split, in the opposite direction.
    """
    start = _twelve_hour(_clock(opening))
    end = _twelve_hour(_clock(closing))
    if not start or not end:
        return ""
    return f"{start} - {end}"


def _twelve_hour(value: str) -> str:
    """``18:30`` -> ``6:30 PM``. Built by hand rather than with ``%-I``, which is
    a glibc extension that raises on Windows -- the same reason
    ``formatting.long_date`` avoids ``%-d``."""
    try:
        hours, minutes = (int(part) for part in value.split(":")[:2])
    except (TypeError, ValueError):
        return ""
    period = "PM" if hours >= 12 else "AM"
    display = hours % 12 or 12
    return f"{display}:{minutes:02d} {period}"


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


def _to_summary(row: dict) -> AmenitySummary:
    return AmenitySummary(
        id=row["id"],
        name=row["name"],
        description=row.get("description") or "",
        category=row.get("category") or "Utility",
        location=row.get("location") or "",
        image=row.get("image_url") or "",
        status=amenity_status_to_wire(row.get("status")),
        is_active=bool(row.get("is_active")),
        booking_mode=booking_mode_to_wire(row.get("booking_mode")),
        capacity=row.get("capacity"),
        allow_private_booking=bool(row.get("allow_private_booking")),
        require_approval=bool(row.get("approval_required")),
        cleaning_buffer=int(row.get("cleaning_buffer_minutes") or 0),
        max_bookings_per_resident=row.get("max_active_bookings_per_resident"),
        opening_time=_clock(row.get("opening_time")),
        closing_time=_clock(row.get("closing_time")),
        opening_hours=_display_hours(row.get("opening_time"), row.get("closing_time")),
        pending_requests=int(row.get("pending_requests") or 0),
        outstanding_dues=_amount(row.get("outstanding_dues")),
    )


def _to_detail(row: dict) -> AmenityDetail:
    summary = _to_summary(row)
    return AmenityDetail(
        **summary.model_dump(),
        booking_slot_duration=int(row.get("slot_duration_minutes") or 60),
        operating_hours=OperatingHours(
            opening_time=summary.opening_time,
            closing_time=summary.closing_time,
            slot_duration_minutes=int(row.get("slot_duration_minutes") or 60),
            cleaning_buffer_minutes=summary.cleaning_buffer,
        ),
        booking_settings=BookingSettings(
            mode=summary.booking_mode,
            max_active_bookings_per_resident=summary.max_bookings_per_resident,
            require_admin_approval=summary.require_approval,
            allow_private_booking=summary.allow_private_booking,
            allow_recurring_booking=bool(row.get("allow_recurring_booking")),
            allow_guest_booking=bool(row.get("allow_guest_booking")),
            allow_same_day_booking=bool(row.get("allow_same_day_booking")),
            enable_waitlist=bool(row.get("enable_waitlist")),
            enable_auto_approval=bool(row.get("enable_auto_approval")),
        ),
        payment_settings=PaymentSettings(
            booking_fee=_amount(row.get("booking_fee")),
            security_deposit=_amount(row.get("security_deposit")),
            late_cancellation_charge=_amount(row.get("late_cancellation_charge")),
            damage_deposit=_amount(row.get("damage_deposit")),
            refund_policy=row.get("refund_policy") or "",
            currency=row.get("currency_code") or "INR",
        ),
        availability_settings=AvailabilitySettings(
            closed_days=weekdays_to_wire(row.get("closed_days")),
            maintenance_days=weekdays_to_wire(row.get("maintenance_days")),
            holiday_overrides=[
                str(day) for day in (row.get("holiday_overrides") or [])
            ],
            temporary_closure=bool(row.get("temporary_closure")),
            minimum_booking_duration_minutes=int(
                row.get("minimum_booking_duration_minutes") or 60
            ),
            maximum_booking_duration_minutes=int(
                row.get("maximum_booking_duration_minutes") or 180
            ),
            advance_booking_window_days=int(
                row.get("advance_booking_window_days") or 30
            ),
        ),
        maintenance_settings=MaintenanceSettings(
            interval=row.get("maintenance_interval") or "Monthly",
            default_duration_minutes=int(
                row.get("default_maintenance_duration_minutes") or 60
            ),
            auto_block_slots=bool(row.get("auto_block_maintenance_slots")),
            notes=row.get("maintenance_notes") or "",
        ),
        version=int(row.get("version") or 1),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_amenities(
    client: Client,
    user_id: str,
    *,
    search: str | None = None,
    category: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 24,
) -> Page[AmenitySummary]:
    """The catalogue grid."""
    community_id = _community(client, user_id)
    stored_status = None
    if status and status.lower() not in ("all", ""):
        if status.lower() not in ("active", "inactive"):
            raise ValidationError("Status must be Active, Inactive or All.")
        stored_status = status.lower()

    offset = (page - 1) * page_size
    rows, total = repo.list_amenities(
        client,
        community_id,
        search=search,
        category=category,
        status=stored_status,
        offset=offset,
        limit=page_size,
    )
    return Page(
        items=[_to_summary(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(rows) < total,
    )


def get_amenity(client: Client, user_id: str, amenity_id: str) -> AmenityDetail:
    """One amenity with every settings group."""
    community_id = _community(client, user_id)
    return _to_detail(repo.get_amenity(client, community_id, amenity_id))


def _settings_payload(request: SaveAmenityRequest) -> dict | None:
    """Translate the five settings groups into the column names 0016 uses.

    Only keys the caller actually sent are included. ``exclude_unset`` rather
    than ``exclude_none`` because null is a meaningful value for
    ``maxActiveBookingsPerResident`` -- it means "no limit" -- and dropping it
    would make clearing the limit impossible.
    """
    if request.settings is None:
        return None

    sent = request.settings.model_dump(exclude_unset=True)
    if not sent:
        return {}

    mapping = {
        "opening_time": "opening_time",
        "closing_time": "closing_time",
        "slot_duration_minutes": "slot_duration_minutes",
        "cleaning_buffer_minutes": "cleaning_buffer_minutes",
        "max_active_bookings_per_resident": "max_active_bookings_per_resident",
        "allow_private_booking": "allow_private_booking",
        "allow_recurring_booking": "allow_recurring_booking",
        "allow_guest_booking": "allow_guest_booking",
        "allow_same_day_booking": "allow_same_day_booking",
        "enable_waitlist": "enable_waitlist",
        "enable_auto_approval": "enable_auto_approval",
        "booking_fee": "booking_fee",
        "security_deposit": "security_deposit",
        "late_cancellation_charge": "late_cancellation_charge",
        "damage_deposit": "damage_deposit",
        "refund_policy": "refund_policy",
        "currency": "currency_code",
        "temporary_closure": "temporary_closure",
        "minimum_booking_duration_minutes": "minimum_booking_duration_minutes",
        "maximum_booking_duration_minutes": "maximum_booking_duration_minutes",
        "advance_booking_window_days": "advance_booking_window_days",
        "interval": "maintenance_interval",
        "default_duration_minutes": "default_maintenance_duration_minutes",
        "auto_block_slots": "auto_block_maintenance_slots",
        "notes": "maintenance_notes",
    }

    payload: dict = {}
    for field, column in mapping.items():
        if field in sent:
            payload[column] = sent[field]

    if "closed_days" in sent:
        payload["closed_days"] = weekdays_to_storage(sent["closed_days"])
    if "maintenance_days" in sent:
        payload["maintenance_days"] = weekdays_to_storage(sent["maintenance_days"])
    if "holiday_overrides" in sent:
        payload["holiday_overrides"] = [
            str(day) for day in (sent["holiday_overrides"] or [])
        ]

    interval = payload.get("maintenance_interval")
    if interval is not None and interval not in _MAINTENANCE_INTERVALS:
        raise ValidationError(
            "Maintenance interval must be one of: "
            + ", ".join(_MAINTENANCE_INTERVALS)
            + "."
        )

    minimum = payload.get("minimum_booking_duration_minutes")
    maximum = payload.get("maximum_booking_duration_minutes")
    if minimum is not None and maximum is not None and maximum < minimum:
        raise ValidationError(
            "The maximum booking duration cannot be shorter than the minimum."
        )

    opening = payload.get("opening_time")
    closing = payload.get("closing_time")
    if opening and closing and _clock(closing) <= _clock(opening):
        raise ValidationError("The closing time must be later than the opening time.")

    return payload


def save_amenity(
    client: Client,
    user_id: str,
    request: SaveAmenityRequest,
    *,
    amenity_id: str | None = None,
) -> AmenityDetail:
    """Create or update an amenity and its settings in one call."""
    community_id = _community(client, user_id)
    if amenity_id is None and not request.name:
        raise ValidationError("An amenity needs a name.")

    if request.category is not None and request.category not in _CATEGORIES:
        raise ValidationError(
            "Category must be one of: " + ", ".join(_CATEGORIES) + "."
        )

    mode = None
    if request.booking_mode is not None:
        mode = booking_mode_to_storage(request.booking_mode)
        if mode is None:
            raise ValidationError(
                "Booking mode must be Shared, Exclusive or Hybrid."
            )

    payload: dict = {}
    if request.name is not None:
        payload["name"] = request.name
    if request.description is not None:
        payload["description"] = request.description
    if request.category is not None:
        payload["category"] = request.category
    if request.location is not None:
        payload["location"] = request.location
    if request.image is not None:
        payload["image_url"] = request.image
    if request.capacity is not None or "capacity" in request.model_fields_set:
        payload["capacity"] = (
            str(request.capacity) if request.capacity is not None else ""
        )
    if mode is not None:
        payload["booking_mode"] = mode
    if request.require_approval is not None:
        payload["approval_required"] = request.require_approval
    if request.is_active is not None:
        payload["is_active"] = request.is_active

    settings = _settings_payload(request)
    if settings is not None:
        payload["settings"] = settings

    saved_id = repo.save_amenity(client, community_id, amenity_id, payload)
    return _to_detail(repo.get_amenity(client, community_id, saved_id))


def set_amenity_status(
    client: Client, user_id: str, amenity_id: str, is_active: bool
) -> AmenityDetail:
    """Flip the card's availability toggle."""
    community_id = _community(client, user_id)
    repo.set_amenity_status(client, amenity_id, is_active)
    return _to_detail(repo.get_amenity(client, community_id, amenity_id))


def delete_amenity(client: Client, amenity_id: str) -> None:
    """Delete an amenity. Refused once anything has been booked on it -- the
    cascade would take the bookings, their charges and their financial events
    with it, including deposits somebody is still owed."""
    repo.delete_amenity(client, amenity_id)


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


def _timeline_state(row: dict) -> str:
    """The timeline's four-value vocabulary, from the lifecycle's seven.

    The cleaning buffer is deliberately not a state here: the frontend synthesises
    buffer blocks at render time from the booking's end and the amenity's buffer
    (``amenityTimeline.createCleaningBuffers``), and duplicating that on the wire
    would give the timeline two sources for the same block.
    """
    return "blocked" if row.get("stored_status") == "blocked" else "booked"


def _to_booking(
    row: dict, guests: dict[str, list[dict]] | None = None
) -> BookingSummary:
    series_id = row["booking_series_id"]
    guest_rows = (guests or {}).get(series_id, [])
    return BookingSummary(
        id=row["id"],
        amenity_id=row["amenity_id"],
        amenity_name=row.get("amenity_name") or "",
        booking_series_id=series_id,
        # The frontend groups multi-day requests by `bookingGroupId`. Our series
        # id IS that group, so it is emitted under both names -- one for the
        # code that already exists, one for the code that reads correctly.
        booking_group_id=series_id,
        resident_id=row.get("requested_by_membership_id"),
        resident_name=row.get("resident_name"),
        resident_flat=row.get("unit_code"),
        tower=row.get("tower"),
        unit_id=row.get("unit_id"),
        booking_title=row.get("title") or "Resident Booking",
        date=_as_date(row.get("booking_date")) or date.today(),
        start_time=_clock(row.get("starts_at")),
        end_time=_clock(row.get("ends_at")),
        state=_timeline_state(row),
        booking_type=row.get("booking_type") or "resident",
        status=row.get("status") or "pending",
        source=row.get("source") or "resident",
        requires_approval=bool(row.get("requires_approval")),
        is_private_booking=bool(row.get("is_private")),
        guest_count=int(row.get("guest_count") or 0),
        guests=[
            AmenityGuest(
                id=guest["id"],
                name=guest.get("guest_name") or "",
                phone=guest.get("phone_e164"),
            )
            for guest in guest_rows
        ],
        notes=row.get("notes"),
        charge_override=(
            _amount(row.get("charge_override"))
            if row.get("charge_override") is not None
            else None
        ),
        department=row.get("department"),
        day_count=int(row.get("day_count") or 1),
        cancellation_reason=row.get("cancellation_reason_code"),
        cancellation_details=row.get("cancellation_reason"),
        cancelled_at=row.get("cancelled_at"),
        cancelled_by_resident=bool(row.get("cancelled_by_resident")),
        force_cancelled=bool(row.get("force_cancelled")),
        version=int(row.get("version") or 1),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_bookings(
    client: Client,
    user_id: str,
    *,
    amenity_id: str | None = None,
    booking_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    membership_id: str | None = None,
    timeline_only: bool = False,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Page[BookingSummary]:
    """Occupied days, for the timeline and for a resident's own list."""
    community_id = _community(client, user_id)
    offset = (page - 1) * page_size
    rows, total = repo.list_bookings(
        client,
        community_id,
        amenity_id=amenity_id,
        booking_date=str(booking_date) if booking_date else None,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
        membership_id=membership_id,
        timeline_only=timeline_only,
        search=search,
        offset=offset,
        limit=page_size,
    )
    guests = repo.list_guests(
        client, community_id, [row["booking_series_id"] for row in rows]
    )
    return Page(
        items=[_to_booking(row, guests) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(rows) < total,
    )


def list_approvals(
    client: Client,
    user_id: str,
    amenity_id: str,
    *,
    status: str = "pending",
    page: int = 1,
    page_size: int = 20,
) -> Page[ApprovalRequest]:
    """The approvals tab: one row per REQUEST.

    ``outstandingDues`` is the FLAT's outstanding balance. The frontend computes
    it per person, from the maintenance invoices filtered on ``userId``; our
    invoices attach to the unit and carry no person. Same label, different
    number -- DECISIONS_NEEDED E18.
    """
    community_id = _community(client, user_id)
    statuses = _APPROVAL_FILTERS.get(status.lower())
    if statuses is None:
        raise ValidationError(
            "Status must be one of: " + ", ".join(sorted(_APPROVAL_FILTERS)) + "."
        )

    offset = (page - 1) * page_size
    rows, total = repo.list_series_first_days(
        client,
        community_id,
        amenity_id=amenity_id,
        statuses=statuses,
        offset=offset,
        limit=page_size,
    )

    series_ids = [row["booking_series_id"] for row in rows]
    guests = repo.list_guests(client, community_id, series_ids)
    dates = repo.list_series_dates(client, community_id, series_ids)
    dues = _outstanding_by_unit(client, community_id, rows)

    items = []
    for row in rows:
        booking = _to_booking(row, guests)
        day_list = [
            parsed
            for parsed in (
                _as_date(value) for value in dates.get(row["booking_series_id"], [])
            )
            if parsed is not None
        ]
        items.append(
            ApprovalRequest(
                **booking.model_dump(),
                dates=day_list,
                outstanding_dues=dues.get(row.get("unit_id") or "", 0.0),
                requested_at=row["requested_at"],
                approved_at=row.get("approved_at"),
                rejected_at=row.get("rejected_at"),
                rejection_reason=row.get("rejection_reason"),
                rejection_reason_code=row.get("rejection_reason_code"),
            )
        )

    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(rows) < total,
    )


def _outstanding_by_unit(
    client: Client, community_id: str, rows: list[dict]
) -> dict[str, float]:
    """What each flat on this page of approvals still owes on its invoices.

    One query for the whole page. Each balance is already final -- maintained by
    ``record_payment`` and constrained by a CHECK -- so grouping them is not the
    same as computing a total in Python.
    """
    unit_ids = sorted({row["unit_id"] for row in rows if row.get("unit_id")})
    return repo.sum_outstanding_by_unit(client, community_id, unit_ids)


def request_booking(
    client: Client,
    user_id: str,
    amenity_id: str,
    request: ResidentBookingRequest,
) -> Page[BookingSummary]:
    """A resident asking for one or more days of the same slot.

    Returns every day created, because a multi-day request produces several
    bookings and telling the caller about one of them is how a resident ends up
    surprised by the other two.
    """
    community_id = _community(client, user_id)
    _assert_time_range(request.start_time, request.end_time)

    payload = {
        "title": request.booking_title,
        "dates": [str(day) for day in sorted(set(request.dates))],
        "starts_at": request.start_time,
        "ends_at": request.end_time,
        "is_private": request.is_private_booking,
        "guest_count": request.guest_count,
        "notes": request.notes,
        "guests": [
            {"name": guest.name, "phone": guest.phone} for guest in request.guests
        ],
    }
    series_id = repo.request_booking(client, amenity_id, payload)
    return _series_page(client, community_id, series_id)


def create_admin_booking(
    client: Client,
    user_id: str,
    amenity_id: str,
    request: AdminBookingRequest,
) -> BookingSummary:
    """An admin booking on a resident's behalf. Confirmed on creation."""
    community_id = _community(client, user_id)
    _assert_time_range(request.start_time, request.end_time)
    if request.booking_type not in _BOOKING_TYPES:
        raise ValidationError(
            "Booking type must be one of: " + ", ".join(_BOOKING_TYPES) + "."
        )

    payload = {
        "membership_id": request.membership_id,
        "title": request.booking_title,
        "booking_type": request.booking_type,
        "booking_date": str(request.date),
        "starts_at": request.start_time,
        "ends_at": request.end_time,
        "is_private": request.is_private_booking,
        "guest_count": request.guest_count,
        "notes": request.notes,
        "charge_override": (
            str(request.charge_override)
            if request.charge_override is not None
            else None
        ),
        "guests": [
            {"name": guest.name, "phone": guest.phone} for guest in request.guests
        ],
    }
    series_id = repo.create_admin_booking(client, amenity_id, payload)
    return _first_of_series(client, community_id, series_id)


def block_slot(
    client: Client, user_id: str, amenity_id: str, request: BlockSlotRequest
) -> BookingSummary:
    """Reserve a slot administratively. Always exclusive."""
    community_id = _community(client, user_id)
    _assert_time_range(request.start_time, request.end_time)

    payload = {
        "reason": request.reason,
        "booking_date": str(request.date),
        "starts_at": request.start_time,
        "ends_at": request.end_time,
        "department": request.department,
        "notes": request.notes,
    }
    series_id = repo.block_slot(client, amenity_id, payload)
    return _first_of_series(client, community_id, series_id)


def approve_booking(
    client: Client, user_id: str, series_id: str
) -> Page[BookingSummary]:
    """Approve a whole request. Every day of it, in one decision."""
    community_id = _community(client, user_id)
    repo.approve_booking(client, series_id)
    return _series_page(client, community_id, series_id)


def reject_booking(
    client: Client, user_id: str, series_id: str, request: RejectBookingRequest
) -> Page[BookingSummary]:
    """Reject a whole request and free its slots."""
    community_id = _community(client, user_id)
    if request.reason_code == "other" and not (request.reason or "").strip():
        raise ValidationError("Add the rejection reason.")

    repo.reject_booking(
        client,
        series_id,
        {
            "reason_code": request.reason_code,
            "reason": request.reason,
            "notify_resident": request.notify_resident,
        },
    )
    return _series_page(client, community_id, series_id)


def cancel_bookings(client: Client, request: CancelBookingRequest) -> int:
    """Cancel selected days. Returns how many were cancelled.

    Whether the caller may cancel somebody else's booking is decided by the
    database from their role, not by anything in this request -- so there is no
    parameter here to lie about.
    """
    if request.reason_code == "other" and not (request.reason or "").strip():
        raise ValidationError("Add details for the cancellation reason.")

    return repo.cancel_occurrences(
        client,
        {
            "occurrence_ids": request.occurrence_ids,
            "reason_code": request.reason_code,
            "reason": request.reason,
        },
    )


def force_cancel_booking(
    client: Client, user_id: str, occurrence_id: str, request: ForceCancelRequest
) -> BookingSummary:
    """Override a booking the resident still wants. The ledger records who."""
    community_id = _community(client, user_id)
    repo.force_cancel_booking(
        client,
        occurrence_id,
        {"reason_code": request.reason_code, "reason": request.reason},
    )
    row = repo.get_booking(client, community_id, occurrence_id)
    guests = repo.list_guests(client, community_id, [row["booking_series_id"]])
    return _to_booking(row, guests)


def _assert_time_range(start: str, end: str) -> None:
    """The one validation that stays in Python: it needs no database round trip
    and its message is the same one the booking form already shows."""
    if _clock(start) >= _clock(end):
        raise ValidationError("End time must be later than start time.")


def _series_page(
    client: Client, community_id: str, series_id: str
) -> Page[BookingSummary]:
    rows, total = repo.list_bookings(
        client, community_id, series_id=series_id, offset=0, limit=60
    )
    guests = repo.list_guests(client, community_id, [series_id])
    return Page(
        items=[_to_booking(row, guests) for row in rows],
        total=total,
        page=1,
        page_size=max(total, 1),
        has_more=False,
    )


def _first_of_series(
    client: Client, community_id: str, series_id: str
) -> BookingSummary:
    page = _series_page(client, community_id, series_id)
    if not page.items:
        raise ValidationError("The booking was created but could not be read back.")
    return page.items[0]


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


def _available_actions(row: dict) -> list[str]:
    """The same rules as ``amenityLedgerModel.getAvailableActions``.

    Computed server-side so that a button the client renders is a button the API
    will honour: the refund and damage RPCs apply these conditions themselves,
    and a client that disagreed would show an action that always 409s.
    """
    actions = ["view"]
    status = row.get("booking_status")
    remaining = _amount(row.get("remaining_refund"))
    payment_status = row.get("payment_status")

    financially_closed = payment_status in ("refunded", "cancelled")
    if remaining > 0 and not financially_closed and status in _REFUNDABLE_STATUSES:
        actions.extend(("refund", "damage"))

    booking_date = _as_date(row.get("booking_date"))
    if (
        status in _FORCE_CANCELLABLE_STATUSES
        and booking_date is not None
        and booking_date > datetime.now(timezone.utc).date()
        and not row.get("force_cancelled")
    ):
        actions.append("force_cancel")

    return actions


def _to_ledger_entry(event: dict) -> LedgerEntry:
    return LedgerEntry(
        id=event["id"],
        amount=_amount(event.get("amount")),
        reason=event.get("reason"),
        notes=event.get("notes"),
        processed_by=event.get("actor_membership_id"),
        created_at=event["created_at"],
    )


def _audit_trail(row: dict, events: list[dict]) -> list[AuditEntry]:
    """The ledger's timeline, assembled from the booking's own timestamps and its
    financial events.

    Not read from a separate audit table, because two tables that must agree
    about when a refund happened are one table and a reconciliation problem. The
    events are already append-only.
    """
    entries: list[AuditEntry] = [
        AuditEntry(
            id=f"audit-created-{row['id']}",
            type="created",
            label="Created",
            timestamp=row["created_at"],
            actor=None,
        )
    ]

    if row.get("approved_at"):
        entries.append(
            AuditEntry(
                id=f"audit-approved-{row['id']}",
                type="approved",
                label="Approved",
                timestamp=row["approved_at"],
                actor=None,
            )
        )

    labels = {
        "payment": "Payment recorded",
        "refund": "Refunded",
        "damage_deduction": "Damage deduction recorded",
        "waiver": "Charge waived",
    }
    for event in events:
        entries.append(
            AuditEntry(
                id=event["id"],
                type=(
                    "damage"
                    if event["event_type"] == "damage_deduction"
                    else event["event_type"]
                ),
                label=labels.get(event["event_type"], event["event_type"]),
                timestamp=event["created_at"],
                actor=event.get("actor_membership_id"),
                amount=_amount(event.get("amount")),
                details=event.get("reason"),
            )
        )

    if row.get("cancelled_at"):
        entries.append(
            AuditEntry(
                id=f"audit-cancelled-{row['id']}",
                type="cancelled",
                label="Cancelled",
                timestamp=row["cancelled_at"],
                actor=None,
                details=row.get("cancellation_reason"),
            )
        )

    return sorted(entries, key=lambda entry: entry.timestamp)


def _to_transaction(row: dict, events: list[dict]) -> LedgerTransaction:
    refunds = [event for event in events if event["event_type"] == "refund"]
    damages = [event for event in events if event["event_type"] == "damage_deduction"]
    last_refund = refunds[-1] if refunds else None
    last_damage = damages[-1] if damages else None

    cancellations = (
        [
            AuditEntry(
                id=f"cancellation-{row['id']}",
                type="cancelled",
                label="Cancelled",
                timestamp=row["cancelled_at"],
                actor=None,
                details=row.get("cancellation_reason"),
            )
        ]
        if row.get("cancelled_at")
        else []
    )

    return LedgerTransaction(
        id=row["id"],
        booking_id=row["booking_id"],
        amenity_id=row["amenity_id"],
        amenity_name=row.get("amenity_name") or "",
        resident_id=row.get("requested_by_membership_id"),
        resident_name=row.get("resident_name"),
        resident_flat=row.get("unit_code"),
        booking_date=_as_date(row.get("booking_date")) or date.today(),
        booking_type=row.get("booking_type") or "resident",
        deposit_amount=_amount(row.get("deposit_amount")),
        deposit_paid=_amount(row.get("deposit_paid")),
        booking_charges=_amount(row.get("booking_charges")),
        additional_charges=_amount(row.get("additional_charges")),
        amount_paid=_amount(row.get("amount_paid")),
        refund_amount=_amount(row.get("refund_amount")),
        damage_amount=_amount(row.get("damage_amount")),
        total_amount=_amount(row.get("total_amount")),
        outstanding_deposit=_amount(row.get("outstanding_deposit")),
        remaining_refund=_amount(row.get("remaining_refund")),
        payment_status=row.get("payment_status") or "pending",
        booking_status=row.get("booking_status") or "pending",
        payment_reference=row.get("payment_reference"),
        internal_notes=row.get("notes"),
        refund_date=last_refund["created_at"] if last_refund else None,
        refund_reason=last_refund.get("reason") if last_refund else None,
        refund_processed_by=(
            last_refund.get("actor_membership_id") if last_refund else None
        ),
        damage_reason=last_damage.get("reason") if last_damage else None,
        force_cancelled=bool(row.get("force_cancelled")),
        force_cancel_reason=(
            row.get("cancellation_reason") if row.get("force_cancelled") else None
        ),
        force_cancelled_by=None,
        force_cancelled_at=(
            row.get("cancelled_at") if row.get("force_cancelled") else None
        ),
        refund_history=[_to_ledger_entry(event) for event in refunds],
        damage_history=[_to_ledger_entry(event) for event in damages],
        cancellation_history=cancellations,
        audit_trail=_audit_trail(row, events),
        available_actions=_available_actions(row),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_ledger(
    client: Client,
    user_id: str,
    *,
    amenity_id: str | None = None,
    payment_status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[LedgerTransaction]:
    """The ledger table."""
    community_id = _community(client, user_id)
    status = None
    if payment_status and payment_status.lower() not in ("all", ""):
        status = payment_status.lower()

    offset = (page - 1) * page_size
    rows, total = repo.list_ledger(
        client,
        community_id,
        amenity_id=amenity_id,
        payment_status=status,
        search=search,
        offset=offset,
        limit=page_size,
    )
    events = repo.list_financial_events(
        client, community_id, [row["id"] for row in rows]
    )
    return Page(
        items=[_to_transaction(row, events.get(row["id"], [])) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(rows) < total,
    )


def get_ledger_summary(
    client: Client, user_id: str, amenity_id: str
) -> LedgerSummary:
    """The eight cards above the ledger table. Zeros for an unbooked amenity."""
    community_id = _community(client, user_id)
    row = repo.fetch_ledger_summary(client, community_id, amenity_id) or {}
    return LedgerSummary(
        total_bookings=int(row.get("total_bookings") or 0),
        total_revenue=_amount(row.get("total_revenue")),
        pending_deposits=_amount(row.get("pending_deposits")),
        refund_pending=int(row.get("refund_pending") or 0),
        refund_completed=_amount(row.get("refund_completed")),
        damage_deductions=_amount(row.get("damage_deductions")),
        outstanding_refunds=_amount(row.get("outstanding_refunds")),
        completed_transactions=int(row.get("completed_transactions") or 0),
    )


def record_payment(
    client: Client,
    user_id: str,
    occurrence_id: str,
    request: RecordAmenityPaymentRequest,
) -> LedgerTransaction:
    """Record money received. Refused if it exceeds what the charge still owes."""
    community_id = _community(client, user_id)
    if request.charge_type not in _CHARGE_TYPES:
        raise ValidationError(
            "Charge type must be one of: " + ", ".join(_CHARGE_TYPES) + "."
        )

    repo.record_payment(
        client,
        occurrence_id,
        {
            "amount": request.amount,
            "charge_type": request.charge_type,
            "method": request.method,
            "payment_reference": request.payment_reference,
            "notes": request.notes,
        },
    )
    return _read_transaction(client, community_id, occurrence_id)


def refund_deposit(
    client: Client,
    user_id: str,
    occurrence_id: str,
    request: RefundDepositRequest,
) -> LedgerTransaction:
    """Return what is left of the deposit. The amount is computed in Postgres."""
    community_id = _community(client, user_id)
    repo.refund_deposit(
        client,
        occurrence_id,
        {"reason": request.reason, "notes": request.notes},
    )
    return _read_transaction(client, community_id, occurrence_id)


def deduct_damage(
    client: Client,
    user_id: str,
    occurrence_id: str,
    request: DamageDeductionRequest,
) -> LedgerTransaction:
    """Take damage out of the held deposit. Capped there, not here."""
    community_id = _community(client, user_id)
    repo.deduct_damage(
        client,
        occurrence_id,
        {
            "amount": request.amount,
            "reason": request.reason,
            "notes": request.notes,
        },
    )
    return _read_transaction(client, community_id, occurrence_id)


def add_charge(
    client: Client, user_id: str, occurrence_id: str, request: AddChargeRequest
) -> LedgerTransaction:
    """Add an extra charge after the fact."""
    community_id = _community(client, user_id)
    if request.charge_type not in ("additional", "late_cancellation"):
        raise ValidationError(
            "Only additional and late-cancellation charges can be added."
        )

    repo.add_charge(
        client,
        occurrence_id,
        {
            "amount": request.amount,
            "charge_type": request.charge_type,
            "description": request.description,
        },
    )
    return _read_transaction(client, community_id, occurrence_id)


def _read_transaction(
    client: Client, community_id: str, occurrence_id: str
) -> LedgerTransaction:
    """Read the row back after a write, so the caller sees the derived figures.

    Every one of them -- ``remainingRefund``, ``paymentStatus``,
    ``availableActions`` -- is a function of the events just written, and none of
    them is stored. Returning the request echoed back would be returning what the
    client already knew.
    """
    row = repo.get_ledger_row(client, community_id, occurrence_id)
    events = repo.list_financial_events(client, community_id, [occurrence_id])
    return _to_transaction(row, events.get(occurrence_id, []))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def build_report(
    client: Client,
    user_id: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    amenity_id: str | None = None,
    booking_status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> AmenityReport:
    """``calculateAmenityReports``, with the KPIs computed over the whole set.

    The split matters. ``rows`` is a PAGE, because a table renders a page.
    ``kpis`` is an RPC aggregate over every matching row, because a KPI that
    describes one page is not a KPI -- it is the same failure as the money tiles
    (agenda item 11), and it is worse here because the number is labelled "Total
    Revenue".
    """
    community_id = _community(client, user_id)
    filters = {
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
        "amenity_id": amenity_id,
        "booking_status": booking_status,
    }

    offset = (page - 1) * page_size
    rows, _total = repo.list_ledger(
        client,
        community_id,
        amenity_id=amenity_id,
        offset=offset,
        limit=page_size,
        date_from=str(start_date) if start_date else None,
        date_to=str(end_date) if end_date else None,
        booking_status=booking_status,
    )
    totals = repo.fetch_report_totals(client, community_id, filters)
    catalogue, _ = repo.list_amenities(
        client, community_id, search=None, category=None, status=None,
        offset=0, limit=200,
    )
    amenities = [_to_summary(row) for row in catalogue]

    return AmenityReport(
        rows=[
            ReportRow(
                id=row["id"],
                booking_id=row["booking_id"],
                amenity_id=row["amenity_id"],
                amenity_name=row.get("amenity_name") or "Unknown Amenity",
                # 'Administration' is the frontend's own fallback for a row with
                # no resident -- an administrative block. Kept verbatim.
                resident_name=row.get("resident_name") or "Administration",
                resident_flat=row.get("unit_code"),
                booking_date=_as_date(row.get("booking_date")) or date.today(),
                booking_status=row.get("booking_status") or "pending",
                payment_status=row.get("payment_status"),
                amount_paid=_amount(row.get("amount_paid")),
            )
            for row in rows
        ],
        kpis=ReportKpis(
            total_amenities=int(totals.get("total_amenities") or 0),
            total_active_bookings=int(totals.get("total_active_bookings") or 0),
            pending_approvals=int(totals.get("pending_approvals") or 0),
            total_revenue=_amount(totals.get("total_revenue")),
            active_amenities=int(totals.get("active_amenities") or 0),
            bookings_this_month=int(totals.get("bookings_this_month") or 0),
        ),
        options=ReportOptions(
            amenities=[
                ReportOption(value=item.id, label=item.name) for item in amenities
            ],
            # The lifecycle's fixed vocabulary rather than the statuses that
            # happen to be present: a filter whose options shrink as the data
            # changes is a filter that cannot be used to find an empty result.
            booking_statuses=[
                "pending",
                "approved",
                "confirmed",
                "completed",
                "cancelled",
                "rejected",
                "blocked",
            ],
        ),
    )
