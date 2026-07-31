"""Unit tests for the amenity translation layer.

These cover the boundary between what the database stores and what the amenity
subsystem renders. The database side -- the exclusion constraint, the advisory
lock in ``amenity_occurrence_guard``, the derived ``payment_status``, RLS -- cannot
be tested here, because no migration has been applied anywhere. That gap is stated
in DECISIONS_NEEDED E1 rather than papered over: the tests below are about the
half that *can* be checked from Python.

Two of them exist specifically to pin down decisions that differ from the demo,
so that changing either is a test failure rather than a silent behaviour change:
the ledger's ``availableActions`` rules, and the collapse of a multi-day request
into one approval row.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ValidationError
from app.domain.amenity_schemas import (
    AddChargeRequest,
    AdminBookingRequest,
    DamageDeductionRequest,
    RecordAmenityPaymentRequest,
    RejectBookingRequest,
    ResidentBookingRequest,
    SaveAmenityRequest,
    SettingsInput,
)
from app.domain.vocabularies import (
    amenity_status_to_wire,
    booking_mode_to_storage,
    booking_mode_to_wire,
    weekday_to_storage,
    weekday_to_wire,
    weekdays_to_storage,
    weekdays_to_wire,
)
from app.services.amenities_service import (
    _amount,
    _available_actions,
    _display_hours,
    _settings_payload,
    _timeline_state,
    _to_booking,
    _to_detail,
    _to_summary,
    _to_transaction,
    _twelve_hour,
)

_NOW = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)
_TOMORROW = (_NOW + timedelta(days=1)).date()
_YESTERDAY = (_NOW - timedelta(days=1)).date()


def _amenity_row(**overrides: object) -> dict:
    """A row of ``amenity_overview``, shaped as PostgREST returns it."""
    row = {
        "id": "amenity-gym",
        "community_id": "community-1",
        "name": "Clubhouse Gym",
        "description": "A fully equipped fitness centre.",
        "category": "Fitness",
        "location": "Clubhouse, Ground Floor",
        "image_url": "https://images.example/gym.jpg",
        "capacity": 24,
        "booking_mode": "shared",
        "approval_required": False,
        "status": "active",
        "is_active": True,
        "version": 1,
        "created_at": "2026-07-01T06:00:00+00:00",
        "updated_at": "2026-07-01T06:00:00+00:00",
        "opening_time": "06:00:00",
        "closing_time": "22:00:00",
        "slot_duration_minutes": 60,
        "cleaning_buffer_minutes": 15,
        "max_active_bookings_per_resident": 5,
        "allow_private_booking": False,
        "allow_recurring_booking": False,
        "allow_guest_booking": True,
        "allow_same_day_booking": True,
        "enable_waitlist": False,
        "enable_auto_approval": False,
        "booking_fee": "800.00",
        "security_deposit": "300.00",
        "late_cancellation_charge": "0.00",
        "damage_deposit": "0.00",
        "refund_policy": "",
        "currency_code": "INR",
        "closed_days": [],
        "maintenance_days": [],
        "holiday_overrides": [],
        "temporary_closure": False,
        "minimum_booking_duration_minutes": 60,
        "maximum_booking_duration_minutes": 180,
        "advance_booking_window_days": 30,
        "maintenance_interval": "Monthly",
        "default_maintenance_duration_minutes": 60,
        "auto_block_maintenance_slots": False,
        "maintenance_notes": "",
        "pending_requests": 1,
        "outstanding_dues": "1600.00",
    }
    row.update(overrides)
    return row


def _booking_row(**overrides: object) -> dict:
    """A row of ``amenity_booking_overview``."""
    row = {
        "id": "occurrence-1",
        "community_id": "community-1",
        "booking_series_id": "series-1",
        "amenity_id": "amenity-gym",
        "amenity_name": "Clubhouse Gym",
        "booking_mode": "shared",
        "booking_date": "2026-07-31",
        "starts_at": "07:00:00",
        "ends_at": "09:00:00",
        "is_exclusive": False,
        "buffer_minutes": 15,
        "occupant_count": 1,
        "status": "pending",
        "stored_status": "pending",
        "cancelled_at": None,
        "cancellation_reason_code": None,
        "cancellation_reason": None,
        "cancelled_by_resident": False,
        "force_cancelled": False,
        "version": 1,
        "created_at": "2026-07-30T08:15:00+00:00",
        "updated_at": "2026-07-30T08:15:00+00:00",
        "title": "Morning Fitness Session",
        "booking_type": "resident",
        "source": "resident",
        "is_private": False,
        "requires_approval": True,
        "guest_count": 0,
        "notes": None,
        "charge_override": None,
        "department": None,
        "series_status": "pending",
        "requested_at": "2026-07-30T08:15:00+00:00",
        "approved_at": None,
        "rejected_at": None,
        "rejection_reason": None,
        "rejection_reason_code": None,
        "unit_id": "unit-1",
        "unit_code": "B-1204",
        "tower": "B",
        "requested_by_membership_id": "u1",
        "resident_profile_id": "profile-1",
        "resident_name": "Aakash S.",
        "day_count": 1,
    }
    row.update(overrides)
    return row


def _ledger_row(**overrides: object) -> dict:
    """A row of ``amenity_ledger_overview``."""
    row = {
        "id": "occurrence-1",
        "community_id": "community-1",
        "booking_id": "occurrence-1",
        "booking_series_id": "series-1",
        "amenity_id": "amenity-gym",
        "amenity_name": "Clubhouse Gym",
        "unit_id": "unit-1",
        "unit_code": "B-1204",
        "resident_profile_id": "profile-1",
        "resident_name": "Aakash S.",
        "requested_by_membership_id": "u1",
        "booking_date": "2026-07-18",
        "starts_at": "07:00:00",
        "ends_at": "09:00:00",
        "booking_type": "resident",
        "title": "Resident Booking",
        "notes": "Completed without incident.",
        "booking_status": "completed",
        "force_cancelled": False,
        "cancelled_at": None,
        "cancellation_reason": None,
        "approved_at": "2026-07-17T07:45:00+00:00",
        "created_at": "2026-07-16T08:00:00+00:00",
        "updated_at": "2026-07-18T09:00:00+00:00",
        "payment_reference": "PAY-GYM-1001",
        "deposit_amount": "500.00",
        "deposit_paid": "500.00",
        "booking_charges": "1000.00",
        "additional_charges": "100.00",
        "amount_paid": "1100.00",
        "refund_amount": "0.00",
        "damage_amount": "0.00",
        "total_amount": "1100.00",
        "outstanding_deposit": "0.00",
        "remaining_refund": "500.00",
        "payment_status": "refund_pending",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Vocabularies -- the three things that actually differ
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("stored", "wire"),
    [("shared", "Shared"), ("exclusive", "Exclusive"), ("hybrid", "Hybrid")],
)
def test_booking_mode_round_trips(stored: str, wire: str) -> None:
    """A true round trip, unlike the complaint statuses: three values each way."""
    assert booking_mode_to_wire(stored) == wire
    assert booking_mode_to_storage(wire) == stored


def test_unknown_booking_mode_is_rejected_not_guessed() -> None:
    """None, so the caller can 400 rather than silently making an exclusive hall
    shared -- which would let two parties be booked into it at once."""
    assert booking_mode_to_storage("Communal") is None
    assert booking_mode_to_storage(None) is None


def test_unknown_stored_booking_mode_reads_shared() -> None:
    assert booking_mode_to_wire("something_new") == "Shared"


def test_amenity_status_reads_inactive_when_unknown() -> None:
    """Defaulting to Active would advertise a facility on the strength of a typo."""
    assert amenity_status_to_wire("active") == "Active"
    assert amenity_status_to_wire("inactive") == "Inactive"
    assert amenity_status_to_wire("retired") == "Inactive"


@pytest.mark.parametrize(
    ("number", "name"),
    [
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ],
)
def test_weekday_round_trips_on_iso_numbering(number: int, name: str) -> None:
    """ISO numbering, so `extract(isodow from d)` in SQL means the same thing."""
    assert weekday_to_wire(number) == name
    assert weekday_to_storage(name) == number


def test_weekday_accepts_a_number_as_well_as_a_name() -> None:
    """A client that has already learnt the stored form should not be forced back
    through the display form to talk to us."""
    assert weekday_to_storage(3) == 3
    assert weekday_to_storage("3") == 3


def test_weekday_rejects_out_of_range_and_nonsense() -> None:
    assert weekday_to_wire(0) is None
    assert weekday_to_wire(8) is None
    assert weekday_to_storage("Someday") is None
    assert weekday_to_storage(0) is None


def test_weekday_list_is_sorted_and_deduplicated() -> None:
    assert weekdays_to_storage(["Sunday", "Monday", "Monday"]) == [1, 7]


def test_unrecognised_days_are_dropped_not_stored() -> None:
    """A CHECK constraint rejects the whole array for one bad element, which
    would turn a typo in one checkbox into a failed save of all thirty
    settings."""
    assert weekdays_to_storage(["Monday", "Funday", "Friday"]) == [1, 5]


def test_weekday_list_survives_a_full_round_trip() -> None:
    names = ["Saturday", "Sunday"]
    assert weekdays_to_wire(weekdays_to_storage(names)) == ["Saturday", "Sunday"]


# ---------------------------------------------------------------------------
# Display strings
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("06:00", "6:00 AM"),
        ("00:00", "12:00 AM"),
        ("12:00", "12:00 PM"),
        ("18:30", "6:30 PM"),
        ("23:59", "11:59 PM"),
    ],
)
def test_twelve_hour_clock(value: str, expected: str) -> None:
    assert _twelve_hour(value) == expected


def test_opening_hours_matches_the_seeded_string() -> None:
    """``amenitiesManagementMock`` stores '6:00 AM - 10:00 PM' and the card renders
    it verbatim, so the format is not ours to choose."""
    assert _display_hours("06:00:00", "22:00:00") == "6:00 AM - 10:00 PM"
    assert _display_hours("09:00:00", "23:00:00") == "9:00 AM - 11:00 PM"


def test_postgres_time_is_truncated_for_the_time_input() -> None:
    """``<input type="time">`` shows an empty field for '06:00:00'."""
    amenity = _to_summary(_amenity_row())
    assert amenity.opening_time == "06:00"
    assert amenity.closing_time == "22:00"


# ---------------------------------------------------------------------------
# Amenity rows
# ---------------------------------------------------------------------------
def test_amenity_row_reproduces_the_card_shape() -> None:
    """Every field ``AmenityCard`` reads, under the name it reads it by."""
    amenity = _to_summary(_amenity_row())
    payload = amenity.model_dump(by_alias=True)

    for field in (
        "id",
        "name",
        "description",
        "category",
        "image",
        "status",
        "isActive",
        "bookingMode",
        "capacity",
        "openingHours",
        "pendingRequests",
        "outstandingDues",
    ):
        assert field in payload, field

    assert payload["status"] == "Active"
    assert payload["bookingMode"] == "Shared"
    assert payload["image"] == "https://images.example/gym.jpg"


def test_badges_come_from_the_view_not_from_a_stored_constant() -> None:
    """The mock stores `pendingRequests: 5` for an amenity with one pending
    request and `outstandingDues: 4800` against 1600 in charges. Both are derived
    here, so the badge cannot disagree with the tab it links to."""
    amenity = _to_summary(_amenity_row(pending_requests=3, outstanding_dues="250.50"))
    assert amenity.pending_requests == 3
    assert amenity.outstanding_dues == 250.5


def test_outstanding_dues_is_a_json_number_not_a_string() -> None:
    """The catalogue formats it with Intl.NumberFormat; a string would render as
    a plausible-looking total after concatenation."""
    payload = _to_summary(_amenity_row()).model_dump(by_alias=True)
    assert isinstance(payload["outstandingDues"], float)


def test_missing_image_is_an_empty_string_not_null() -> None:
    """The card branches on `amenity.image` and renders a placeholder icon for a
    falsy value, so '' is a supported value rather than a gap."""
    assert _to_summary(_amenity_row(image_url="")).image == ""


def test_no_capacity_means_no_limit_not_zero() -> None:
    """The Reading Lounge has no booking limit. Zero would mean an amenity nobody
    can book, which is what an inactive status is for."""
    amenity = _to_summary(
        _amenity_row(capacity=None, max_active_bookings_per_resident=None)
    )
    assert amenity.capacity is None
    assert amenity.max_bookings_per_resident is None


def test_detail_carries_both_copies_of_the_duplicated_fields() -> None:
    """``normalizeAmenityRecord`` writes bookingMode at the top level AND in
    bookingSettings, and different components read different ones. The database
    stores each once; the duplication stops at the DTO."""
    detail = _to_detail(_amenity_row())
    assert detail.booking_mode == detail.booking_settings.mode == "Shared"
    assert (
        detail.cleaning_buffer
        == detail.operating_hours.cleaning_buffer_minutes
        == 15
    )
    assert (
        detail.require_approval
        == detail.booking_settings.require_admin_approval
        is False
    )


def test_detail_renders_weekdays_as_names() -> None:
    detail = _to_detail(_amenity_row(closed_days=[1, 7], maintenance_days=[3]))
    assert detail.availability_settings.closed_days == ["Monday", "Sunday"]
    assert detail.availability_settings.maintenance_days == ["Wednesday"]


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
def test_booking_row_reproduces_the_seeded_booking_shape() -> None:
    booking = _to_booking(_booking_row())
    payload = booking.model_dump(by_alias=True)

    for field in (
        "id",
        "amenityId",
        "residentId",
        "residentName",
        "bookingTitle",
        "date",
        "startTime",
        "endTime",
        "state",
        "bookingType",
        "status",
        "notes",
        "createdAt",
        "updatedAt",
    ):
        assert field in payload, field

    assert payload["startTime"] == "07:00"
    assert payload["endTime"] == "09:00"
    assert payload["state"] == "booked"


def test_resident_id_is_the_membership_id_the_people_endpoint_returns() -> None:
    """So the dashboard's `users.find(u => u.id === booking.residentId)`
    resolves. Same rule the money endpoints follow."""
    assert _to_booking(_booking_row()).resident_id == "u1"


def test_series_id_is_emitted_as_the_booking_group_too() -> None:
    """The frontend groups multi-day requests by `bookingGroupId`. Our series id
    IS that group, so it goes out under both names -- one for the code that
    exists, one that reads correctly."""
    booking = _to_booking(_booking_row())
    assert booking.booking_group_id == booking.booking_series_id == "series-1"


def test_a_block_is_blocked_on_the_timeline_and_a_booking_is_not() -> None:
    """The timeline colours from `state`, which has four values, while the
    lifecycle has seven."""
    assert _timeline_state(_booking_row(stored_status="blocked")) == "blocked"
    assert _timeline_state(_booking_row(stored_status="pending")) == "booked"
    assert _timeline_state(_booking_row(stored_status="confirmed")) == "booked"


def test_completed_is_carried_from_the_view_not_recomputed() -> None:
    """The view derives it from the clock; recomputing here would give two
    answers that disagree for a booking finishing during the request."""
    booking = _to_booking(_booking_row(status="completed", stored_status="approved"))
    assert booking.status == "completed"


def test_a_block_has_no_resident_rather_than_a_placeholder() -> None:
    booking = _to_booking(
        _booking_row(
            requested_by_membership_id=None,
            resident_name=None,
            unit_id=None,
            unit_code=None,
            tower=None,
            stored_status="blocked",
            status="blocked",
            booking_type="maintenance-reservation",
            title="Deep clean",
            department="Cleaning",
        )
    )
    assert booking.resident_id is None
    assert booking.resident_name is None
    assert booking.resident_flat is None
    assert booking.department == "Cleaning"


def test_day_count_travels_with_every_day_of_a_request() -> None:
    """The approvals table needs it to say '3 days' -- one click now decides the
    whole request."""
    assert _to_booking(_booking_row(day_count=3)).day_count == 3


def test_guests_are_attached_by_series_not_by_day() -> None:
    """A guest list belongs to the request; a three-day booking does not have
    three copies of the same guests."""
    guests = {
        "series-1": [
            {"id": "g1", "guest_name": "Meera", "phone_e164": "+919876543210"},
            {"id": "g2", "guest_name": "Rohan", "phone_e164": None},
        ]
    }
    booking = _to_booking(_booking_row(), guests)
    assert [guest.name for guest in booking.guests] == ["Meera", "Rohan"]
    assert booking.guests[1].phone is None


def test_charge_override_distinguishes_free_from_default() -> None:
    """None means 'use the configured fee'; 0 means 'free'. Collapsing them would
    make a waived fee indistinguishable from no decision."""
    assert _to_booking(_booking_row(charge_override=None)).charge_override is None
    assert _to_booking(_booking_row(charge_override="0.00")).charge_override == 0.0


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------
def test_ledger_row_reproduces_the_transaction_shape() -> None:
    transaction = _to_transaction(_ledger_row(), [])
    payload = transaction.model_dump(by_alias=True)

    for field in (
        "id",
        "bookingId",
        "amenityId",
        "residentId",
        "residentName",
        "residentFlat",
        "bookingDate",
        "bookingType",
        "depositAmount",
        "depositPaid",
        "bookingCharges",
        "additionalCharges",
        "amountPaid",
        "paymentStatus",
        "bookingStatus",
        "paymentReference",
        "internalNotes",
        "remainingRefund",
        "totalAmount",
        "outstandingDeposit",
        "availableActions",
        "refundHistory",
        "damageHistory",
        "auditTrail",
    ):
        assert field in payload, field


def test_every_ledger_figure_is_a_number_not_a_string() -> None:
    """The ledger summary reduces over these in the browser."""
    payload = _to_transaction(_ledger_row(), []).model_dump(by_alias=True)
    for field in (
        "depositAmount",
        "depositPaid",
        "bookingCharges",
        "additionalCharges",
        "amountPaid",
        "refundAmount",
        "damageAmount",
        "totalAmount",
        "outstandingDeposit",
        "remainingRefund",
    ):
        assert isinstance(payload[field], float), field


def test_ledger_figures_come_from_the_view_not_from_python() -> None:
    """Reproduces the seeded txn-gym-1001: 1000 + 100 charged, 1100 paid."""
    transaction = _to_transaction(_ledger_row(), [])
    assert transaction.total_amount == 1100.0
    assert transaction.amount_paid == 1100.0
    assert transaction.outstanding_deposit == 0.0
    assert transaction.remaining_refund == 500.0


def test_refund_and_damage_histories_split_the_event_stream() -> None:
    events = [
        {
            "id": "e1",
            "event_type": "payment",
            "amount": "500.00",
            "reason": None,
            "notes": None,
            "actor_membership_id": "admin-1",
            "created_at": "2026-07-16T09:00:00+00:00",
        },
        {
            "id": "e2",
            "event_type": "damage_deduction",
            "amount": "200.00",
            "reason": "Broken treadmill belt",
            "notes": None,
            "actor_membership_id": "admin-1",
            "created_at": "2026-07-19T09:00:00+00:00",
        },
        {
            "id": "e3",
            "event_type": "refund",
            "amount": "300.00",
            "reason": "Deposit returned",
            "notes": None,
            "actor_membership_id": "admin-2",
            "created_at": "2026-07-20T09:00:00+00:00",
        },
    ]
    transaction = _to_transaction(_ledger_row(), events)

    assert [entry.id for entry in transaction.refund_history] == ["e3"]
    assert [entry.id for entry in transaction.damage_history] == ["e2"]
    assert transaction.damage_reason == "Broken treadmill belt"
    assert transaction.refund_processed_by == "admin-2"


def test_audit_trail_is_ordered_and_includes_the_lifecycle() -> None:
    """Assembled from the booking's own timestamps and its financial events, not
    from a second audit table that would have to agree with them."""
    events = [
        {
            "id": "e1",
            "event_type": "payment",
            "amount": "500.00",
            "reason": None,
            "notes": None,
            "actor_membership_id": "admin-1",
            "created_at": "2026-07-17T09:00:00+00:00",
        }
    ]
    trail = _to_transaction(_ledger_row(), events).audit_trail

    assert [entry.type for entry in trail] == ["created", "approved", "payment"]
    assert trail == sorted(trail, key=lambda entry: entry.timestamp)


def test_cancelled_booking_puts_a_cancellation_in_the_trail() -> None:
    trail = _to_transaction(
        _ledger_row(
            booking_status="cancelled",
            cancelled_at="2026-07-19T10:00:00+00:00",
            cancellation_reason="emergency-maintenance",
        ),
        [],
    ).audit_trail
    assert trail[-1].type == "cancelled"
    assert trail[-1].details == "emergency-maintenance"


# ---------------------------------------------------------------------------
# availableActions -- pinned, because these rules differ from nothing else and a
# button the client shows must be one the API will honour.
# ---------------------------------------------------------------------------
def test_a_completed_booking_with_a_deposit_can_be_refunded_or_charged() -> None:
    actions = _available_actions(_ledger_row())
    assert actions == ["view", "refund", "damage"]


def test_a_fully_refunded_booking_offers_neither() -> None:
    """`refunded` is financially closed: there is nothing left to return."""
    actions = _available_actions(
        _ledger_row(payment_status="refunded", remaining_refund="0.00")
    )
    assert actions == ["view"]


def test_a_pending_booking_offers_no_refund() -> None:
    """Nothing has been held yet, and the booking has not happened."""
    actions = _available_actions(
        _ledger_row(
            booking_status="pending",
            payment_status="pending",
            deposit_paid="0.00",
            remaining_refund="0.00",
            booking_date=str(_TOMORROW),
        )
    )
    assert "refund" not in actions
    assert "damage" not in actions


def test_a_future_confirmed_booking_can_be_force_cancelled() -> None:
    actions = _available_actions(
        _ledger_row(
            booking_status="confirmed",
            booking_date=str(_TOMORROW),
            payment_status="paid",
            remaining_refund="0.00",
        )
    )
    assert "force_cancel" in actions


def test_a_past_booking_cannot_be_force_cancelled() -> None:
    """There is nothing left to prevent."""
    actions = _available_actions(
        _ledger_row(
            booking_status="confirmed",
            booking_date=str(_YESTERDAY),
            payment_status="paid",
            remaining_refund="0.00",
        )
    )
    assert "force_cancel" not in actions


def test_an_already_force_cancelled_booking_cannot_be_again() -> None:
    actions = _available_actions(
        _ledger_row(
            booking_status="confirmed",
            booking_date=str(_TOMORROW),
            force_cancelled=True,
            payment_status="paid",
            remaining_refund="0.00",
        )
    )
    assert "force_cancel" not in actions


# ---------------------------------------------------------------------------
# Settings payload
# ---------------------------------------------------------------------------
def test_settings_omitted_entirely_is_not_the_same_as_settings_empty() -> None:
    """None means 'do not touch the settings row'; {} means 'a save with no
    changed fields'. The RPC branches on the difference."""
    assert _settings_payload(SaveAmenityRequest(name="Pool")) is None
    assert _settings_payload(SaveAmenityRequest(settings=SettingsInput())) == {}


def test_only_the_fields_the_caller_sent_are_translated() -> None:
    """A field left out is left alone. `exclude_unset`, not `exclude_none`."""
    payload = _settings_payload(
        SaveAmenityRequest(settings=SettingsInput(booking_fee=1200))
    )
    assert payload == {"booking_fee": 1200}


def test_a_null_booking_limit_is_sent_rather_than_dropped() -> None:
    """Null means 'no limit', which is a value. Dropping it would make clearing
    the limit impossible."""
    payload = _settings_payload(
        SaveAmenityRequest(
            settings=SettingsInput.model_validate(
                {"maxActiveBookingsPerResident": None}
            )
        )
    )
    assert payload == {"max_active_bookings_per_resident": None}


def test_settings_translate_to_the_column_names_the_migration_uses() -> None:
    payload = _settings_payload(
        SaveAmenityRequest(
            settings=SettingsInput(
                currency="USD",
                interval="Weekly",
                default_duration_minutes=90,
                auto_block_slots=True,
                notes="Filters replaced monthly.",
                closed_days=["Sunday"],
                holiday_overrides=[date(2026, 8, 15)],
            )
        )
    )
    assert payload["currency_code"] == "USD"
    assert payload["maintenance_interval"] == "Weekly"
    assert payload["default_maintenance_duration_minutes"] == 90
    assert payload["auto_block_maintenance_slots"] is True
    assert payload["maintenance_notes"] == "Filters replaced monthly."
    assert payload["closed_days"] == [7]
    assert payload["holiday_overrides"] == ["2026-08-15"]


def test_a_maximum_shorter_than_the_minimum_is_refused() -> None:
    with pytest.raises(ValidationError):
        _settings_payload(
            SaveAmenityRequest(
                settings=SettingsInput(
                    minimum_booking_duration_minutes=120,
                    maximum_booking_duration_minutes=60,
                )
            )
        )


def test_closing_before_opening_is_refused() -> None:
    """Otherwise the amenity has no bookable minute and every booking fails with
    a confusing message instead of this one."""
    with pytest.raises(ValidationError):
        _settings_payload(
            SaveAmenityRequest(
                settings=SettingsInput(opening_time="22:00", closing_time="06:00")
            )
        )


def test_an_unknown_maintenance_interval_is_refused() -> None:
    with pytest.raises(ValidationError):
        _settings_payload(
            SaveAmenityRequest(settings=SettingsInput(interval="Fortnightly"))
        )


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------
def test_a_resident_request_needs_at_least_one_date() -> None:
    with pytest.raises(PydanticValidationError):
        ResidentBookingRequest(dates=[], start_time="07:00", end_time="09:00")


def test_a_resident_request_carries_no_flat() -> None:
    """The flat is read from the caller's own residency, so a resident cannot
    book against somebody else's unit by editing the request."""
    assert "unit_id" not in ResidentBookingRequest.model_fields
    assert "flat" not in ResidentBookingRequest.model_fields
    assert "membership_id" not in ResidentBookingRequest.model_fields


def test_an_admin_booking_names_the_resident_but_not_the_flat() -> None:
    """The flat is resolved from their residency, so the ledger charges a unit
    that exists."""
    assert "membership_id" in AdminBookingRequest.model_fields
    assert "unit_id" not in AdminBookingRequest.model_fields


def test_a_payment_must_be_above_zero() -> None:
    with pytest.raises(PydanticValidationError):
        RecordAmenityPaymentRequest(amount=0)


def test_a_damage_deduction_needs_a_reason() -> None:
    with pytest.raises(PydanticValidationError):
        DamageDeductionRequest(amount=250, reason="")


def test_a_rejection_needs_a_reason_code() -> None:
    with pytest.raises(PydanticValidationError):
        RejectBookingRequest(reason_code="")


def test_a_refund_request_cannot_name_its_own_amount() -> None:
    """A refund whose amount is a request parameter is a refund somebody can ask
    to be larger. It is computed from the deposit in Postgres."""
    from app.domain.amenity_schemas import RefundDepositRequest

    assert "amount" not in RefundDepositRequest.model_fields


def test_an_added_charge_must_be_positive() -> None:
    with pytest.raises(PydanticValidationError):
        AddChargeRequest(amount=-100)


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 0.0),
        (0, 0.0),
        ("1600.00", 1600.0),
        (1600.0, 1600.0),
        ("0.50", 0.5),
        ("1234.567", 1234.57),
    ],
)
def test_amount_parses_numeric_from_either_shape(
    raw: object, expected: float
) -> None:
    """PostgREST sends `numeric` as a JSON number, but the SDK has surfaced it as
    a string on some versions."""
    assert _amount(raw) == expected
