"""DTOs for the amenity catalogue, bookings, approvals, the ledger and reports.

Amounts are floats for the same reason they are in ``money_schemas``: the ledger
does ``transactions.reduce((total, t) => total + Number(t.amountPaid || 0), 0)``
(``amenityLedgerModel.js:153``) and a Pydantic ``Decimal`` would arrive as a JSON
string and concatenate. Every figure here is nevertheless computed by Postgres in
``numeric`` -- the float is the wire format, not the arithmetic.

The frontend's shapes are reproduced field for field, including the ones it stores
redundantly. ``AmenityDetail`` carries ``bookingMode`` at the top level *and*
``bookingSettings.mode``, ``cleaningBuffer`` *and*
``operatingHours.cleaningBufferMinutes``, because ``normalizeAmenityRecord``
writes both and different components read different ones. The database stores
each once; the duplication stops at the DTO.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field, field_validator

from app.domain.common_schemas import CamelModel

__all__ = [
    "OperatingHours",
    "BookingSettings",
    "PaymentSettings",
    "AvailabilitySettings",
    "MaintenanceSettings",
    "AmenitySummary",
    "AmenityDetail",
    "AmenityGuest",
    "BookingSummary",
    "ApprovalRequest",
    "LedgerEntry",
    "AuditEntry",
    "LedgerTransaction",
    "LedgerSummary",
    "ReportRow",
    "ReportKpis",
    "ReportOption",
    "ReportOptions",
    "AmenityReport",
    "SettingsInput",
    "SaveAmenityRequest",
    "AmenityStatusRequest",
    "GuestInput",
    "AdminBookingRequest",
    "ResidentBookingRequest",
    "BlockSlotRequest",
    "RejectBookingRequest",
    "CancelBookingRequest",
    "ForceCancelRequest",
    "RecordAmenityPaymentRequest",
    "RefundDepositRequest",
    "DamageDeductionRequest",
    "AddChargeRequest",
]


# ---------------------------------------------------------------------------
# The five settings groups, exactly as `DEFAULT_AMENITY_SETTINGS` shapes them.
# ---------------------------------------------------------------------------


class OperatingHours(CamelModel):
    """``HH:MM`` strings, because the settings form feeds them to
    ``<input type="time">`` -- which renders an empty field for anything it
    cannot parse, including PostgREST's ``06:00:00``."""

    opening_time: str
    closing_time: str
    slot_duration_minutes: int
    cleaning_buffer_minutes: int


class BookingSettings(CamelModel):
    """``mode`` duplicates ``AmenityDetail.bookingMode``; see the module note."""

    mode: str
    max_active_bookings_per_resident: int | None = None
    require_admin_approval: bool
    allow_private_booking: bool
    allow_recurring_booking: bool
    allow_guest_booking: bool
    allow_same_day_booking: bool
    enable_waitlist: bool
    enable_auto_approval: bool


class PaymentSettings(CamelModel):
    booking_fee: float
    security_deposit: float
    late_cancellation_charge: float
    damage_deposit: float
    refund_policy: str
    currency: str


class AvailabilitySettings(CamelModel):
    """``closedDays`` and ``maintenanceDays`` are English day names on the wire
    and ISO day numbers in the column -- see ``vocabularies.weekdays_to_wire``."""

    closed_days: list[str]
    maintenance_days: list[str]
    holiday_overrides: list[str]
    temporary_closure: bool
    minimum_booking_duration_minutes: int
    maximum_booking_duration_minutes: int
    advance_booking_window_days: int


class MaintenanceSettings(CamelModel):
    interval: str
    default_duration_minutes: int
    auto_block_slots: bool
    notes: str


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


class AmenitySummary(CamelModel):
    """One card in the catalogue grid.

    ``pendingRequests`` and ``outstandingDues`` are computed by the view rather
    than stored. The mock stores both as constants that never move -- the gym
    card claims 5 pending requests against 1 real one, and 4800 in dues against
    1600 in charges -- and a badge that disagrees with the tab it links to is
    worse than no badge.
    """

    id: str
    name: str
    description: str
    category: str
    location: str
    image: str
    status: str
    is_active: bool
    booking_mode: str
    capacity: int | None = None
    allow_private_booking: bool
    require_approval: bool
    cleaning_buffer: int
    max_bookings_per_resident: int | None = None
    opening_time: str
    closing_time: str
    # 'Shared' | 'Exclusive' | 'Hybrid' -> '6:00 AM - 10:00 PM'. A display string
    # the card renders verbatim, composed here so no caller has to.
    opening_hours: str
    pending_requests: int
    outstanding_dues: float


class AmenityDetail(AmenitySummary):
    """The workspace header plus every settings group the settings tab edits."""

    booking_slot_duration: int
    operating_hours: OperatingHours
    booking_settings: BookingSettings
    payment_settings: PaymentSettings
    availability_settings: AvailabilitySettings
    maintenance_settings: MaintenanceSettings
    version: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


class AmenityGuest(CamelModel):
    id: str
    name: str
    phone: str | None = None


class BookingSummary(CamelModel):
    """One occupied day, in the shape ``amenityBookings.js`` seeds.

    ``state`` is the timeline's vocabulary ('booked' | 'blocked') and ``status``
    is the lifecycle's -- the frontend carries both and colours the timeline from
    the first. ``residentId`` is the requester's MEMBERSHIP id, which is what
    ``GET /residents`` returns as ``id``, so the dashboard's
    ``users.find(u => u.id === booking.residentId)`` resolves.

    ``status`` may read ``completed`` for a row whose stored status is
    ``approved``: a booking that has finished is completed, and storing that
    would need a scheduled job to keep it true.
    """

    id: str
    amenity_id: str
    amenity_name: str
    booking_series_id: str
    booking_group_id: str | None = None
    resident_id: str | None = None
    resident_name: str | None = None
    resident_flat: str | None = None
    tower: str | None = None
    unit_id: str | None = None
    booking_title: str
    date: date
    start_time: str
    end_time: str
    state: str
    booking_type: str
    status: str
    source: str
    requires_approval: bool
    is_private_booking: bool
    guest_count: int
    guests: list[AmenityGuest] = Field(default_factory=list)
    notes: str | None = None
    charge_override: float | None = None
    department: str | None = None
    day_count: int
    cancellation_reason: str | None = None
    cancellation_details: str | None = None
    cancelled_at: datetime | None = None
    cancelled_by_resident: bool = False
    force_cancelled: bool = False
    version: int
    created_at: datetime
    updated_at: datetime


class ApprovalRequest(BookingSummary):
    """One row in the approvals table -- one per REQUEST, not per day.

    ``dayCount`` and ``dates`` exist because one click now decides the whole
    request. A three-day booking rendered as its first day alone would tell an
    admin they are approving one day; the frontend does not read either field
    yet, which is frontend agenda item 16.

    ``outstandingDues`` is the FLAT's balance, not the person's. The frontend
    computes it per ``userId`` from the maintenance invoices; ours attach to the
    unit and have no person on them. Same label, different number --
    DECISIONS_NEEDED E18.
    """

    dates: list[date] = Field(default_factory=list)
    outstanding_dues: float = 0.0
    requested_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    rejection_reason_code: str | None = None


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


class LedgerEntry(CamelModel):
    """One refund or one damage deduction, from the append-only event stream."""

    id: str
    amount: float
    reason: str | None = None
    notes: str | None = None
    processed_by: str | None = None
    created_at: datetime


class AuditEntry(CamelModel):
    """One line of the ledger's audit timeline.

    Assembled from the booking's own lifecycle timestamps and its financial
    events, rather than from a separate audit table: two sources that must agree
    about when a refund happened are one source with a reconciliation problem.
    """

    id: str
    type: str
    label: str
    timestamp: datetime
    actor: str | None = None
    amount: float | None = None
    details: str | None = None


class LedgerTransaction(CamelModel):
    """One row of the ledger table, reconstructed from charges and events.

    Every figure is derived. ``remainingRefund`` is deposit paid minus damage
    taken minus refunds already made; ``paymentStatus`` is a CASE over those,
    with the order of its arms being its meaning -- a cancelled booking still
    holding a refundable deposit is ``refund_pending``, not ``cancelled``,
    because somebody is owed money.
    """

    id: str
    booking_id: str
    amenity_id: str
    amenity_name: str
    resident_id: str | None = None
    resident_name: str | None = None
    resident_flat: str | None = None
    booking_date: date
    booking_type: str
    deposit_amount: float
    deposit_paid: float
    booking_charges: float
    additional_charges: float
    amount_paid: float
    refund_amount: float
    damage_amount: float
    total_amount: float
    outstanding_deposit: float
    remaining_refund: float
    payment_status: str
    booking_status: str
    payment_reference: str | None = None
    internal_notes: str | None = None
    refund_date: datetime | None = None
    refund_reason: str | None = None
    refund_processed_by: str | None = None
    damage_reason: str | None = None
    force_cancelled: bool = False
    force_cancel_reason: str | None = None
    force_cancelled_by: str | None = None
    force_cancelled_at: datetime | None = None
    refund_history: list[LedgerEntry] = Field(default_factory=list)
    damage_history: list[LedgerEntry] = Field(default_factory=list)
    cancellation_history: list[AuditEntry] = Field(default_factory=list)
    audit_trail: list[AuditEntry] = Field(default_factory=list)
    # 'view' | 'refund' | 'damage' | 'force_cancel'. Computed server-side from
    # the same rules `amenityLedgerModel.getAvailableActions` uses, so a button
    # the client renders is a button the API will honour.
    available_actions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class LedgerSummary(CamelModel):
    """The eight cards above the ledger table, aggregated by Postgres."""

    total_bookings: int
    total_revenue: float
    pending_deposits: float
    refund_pending: int
    refund_completed: float
    damage_deductions: float
    outstanding_refunds: float
    completed_transactions: int


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class ReportRow(CamelModel):
    id: str
    booking_id: str
    amenity_id: str
    amenity_name: str
    resident_name: str
    resident_flat: str | None = None
    booking_date: date
    booking_status: str
    payment_status: str | None = None
    amount_paid: float


class ReportKpis(CamelModel):
    total_amenities: int
    total_active_bookings: int
    pending_approvals: int
    total_revenue: float
    active_amenities: int
    bookings_this_month: int


class ReportOption(CamelModel):
    value: str
    label: str


class ReportOptions(CamelModel):
    amenities: list[ReportOption]
    booking_statuses: list[str]


class AmenityReport(CamelModel):
    """``calculateAmenityReports`` returns exactly this, computed in the browser
    over the whole dataset. Computed here instead, for the reason agenda item 11
    gives about the money tiles: a client-side aggregate reports on the page it
    is holding, not on the community."""

    rows: list[ReportRow]
    kpis: ReportKpis
    options: ReportOptions


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class SettingsInput(CamelModel):
    """Every field optional: the catalogue form sends none of these and the
    settings tab sends all of them, and both have to work. A field left out is
    left alone, which is not the same as a field sent as null."""

    opening_time: str | None = None
    closing_time: str | None = None
    slot_duration_minutes: int | None = Field(None, ge=5, le=1440)
    cleaning_buffer_minutes: int | None = Field(None, ge=0, le=480)
    max_active_bookings_per_resident: int | None = Field(None, ge=1, le=100)
    require_admin_approval: bool | None = None
    allow_private_booking: bool | None = None
    allow_recurring_booking: bool | None = None
    allow_guest_booking: bool | None = None
    allow_same_day_booking: bool | None = None
    enable_waitlist: bool | None = None
    enable_auto_approval: bool | None = None
    booking_fee: float | None = Field(None, ge=0)
    security_deposit: float | None = Field(None, ge=0)
    late_cancellation_charge: float | None = Field(None, ge=0)
    damage_deposit: float | None = Field(None, ge=0)
    refund_policy: str | None = Field(None, max_length=2000)
    currency: str | None = Field(None, min_length=3, max_length=3)
    closed_days: list[str] | None = None
    maintenance_days: list[str] | None = None
    holiday_overrides: list[date] | None = None
    temporary_closure: bool | None = None
    minimum_booking_duration_minutes: int | None = Field(None, ge=5, le=1440)
    maximum_booking_duration_minutes: int | None = Field(None, ge=5, le=1440)
    advance_booking_window_days: int | None = Field(None, ge=0, le=365)
    interval: str | None = None
    default_duration_minutes: int | None = Field(None, ge=5, le=1440)
    auto_block_slots: bool | None = None
    notes: str | None = Field(None, max_length=2000)


class SaveAmenityRequest(CamelModel):
    """Create or update. On create ``name`` is required; on update every field is
    optional, so the status toggle and the settings tab can share one endpoint
    without the toggle blanking a description."""

    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    category: str | None = None
    location: str | None = Field(None, max_length=200)
    image: str | None = Field(None, max_length=1000)
    capacity: int | None = Field(None, ge=1, le=100000)
    booking_mode: str | None = None
    require_approval: bool | None = None
    is_active: bool | None = None
    settings: SettingsInput | None = None

    @field_validator("name", "description", "location", "image", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        """An empty string from a cleared form field means "unchanged", not
        "set to empty" -- except for description, location and image, where the
        service passes '' through deliberately. Only whitespace is stripped."""
        if isinstance(value, str):
            return value.strip()
        return value


class AmenityStatusRequest(CamelModel):
    is_active: bool


class GuestInput(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=20)


class AdminBookingRequest(CamelModel):
    """The admin's Create Booking modal. ``membershipId`` names the resident; the
    flat is resolved from their residency rather than sent, so the ledger charges
    a unit that actually exists."""

    membership_id: str
    booking_title: str | None = Field(None, max_length=200)
    booking_type: str = "resident"
    date: date
    start_time: str
    end_time: str
    is_private_booking: bool = False
    guest_count: int = Field(0, ge=0, le=1000)
    guests: list[GuestInput] = Field(default_factory=list)
    notes: str | None = Field(None, max_length=2000)
    # None means "use the amenity's configured fee"; 0 means "free". They are
    # different answers and the API keeps them different.
    charge_override: float | None = Field(None, ge=0)


class ResidentBookingRequest(CamelModel):
    """A resident asking for one or more days of the same slot.

    Exists in an admin-scoped build because the approvals tab is otherwise a
    screen that can never have anything on it -- the same argument step 7 made
    for the invoice write endpoints.

    The flat is NOT a parameter: it is read from the caller's own residency, so a
    resident cannot book against somebody else's unit by editing a request.
    """

    booking_title: str | None = Field(None, max_length=200)
    dates: list[date] = Field(min_length=1, max_length=30)
    start_time: str
    end_time: str
    is_private_booking: bool = False
    guest_count: int = Field(0, ge=0, le=1000)
    guests: list[GuestInput] = Field(default_factory=list)
    notes: str | None = Field(None, max_length=2000)


class BlockSlotRequest(CamelModel):
    """An administrative reservation. Always exclusive: a hall closed for repairs
    is closed to everybody, whatever its booking mode says."""

    reason: str = Field(min_length=1, max_length=200)
    date: date
    start_time: str
    end_time: str
    department: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=2000)


class RejectBookingRequest(CamelModel):
    """``reasonCode`` is one of ``BOOKING_REJECTION_REASONS``; ``reason`` carries
    the free text that ``other`` requires. A rejection with neither is an
    unanswerable support ticket, so the database refuses it too."""

    reason_code: str = Field(min_length=1, max_length=60)
    reason: str | None = Field(None, max_length=1000)
    notify_resident: bool = True


class CancelBookingRequest(CamelModel):
    """Cancel selected days of a request. A resident may withdraw their own
    future days; an admin may cancel any. Which of the two you are is read from
    the token, not from this body."""

    occurrence_ids: list[str] = Field(min_length=1, max_length=60)
    reason_code: str | None = Field(None, max_length=60)
    reason: str | None = Field(None, max_length=1000)


class ForceCancelRequest(CamelModel):
    reason_code: str = Field(min_length=1, max_length=60)
    reason: str | None = Field(None, max_length=1000)


class RecordAmenityPaymentRequest(CamelModel):
    """``paymentReference`` makes this idempotent: a replayed gateway callback
    returns the event already recorded rather than double-crediting."""

    amount: float = Field(gt=0)
    charge_type: str = "booking"
    method: str | None = Field(None, max_length=40)
    payment_reference: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=1000)


class RefundDepositRequest(CamelModel):
    """No amount. It is what is left of the deposit after damage, computed
    server-side -- a refund whose amount is a request parameter is a refund
    somebody can ask to be larger."""

    reason: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=1000)


class DamageDeductionRequest(CamelModel):
    amount: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    notes: str | None = Field(None, max_length=1000)


class AddChargeRequest(CamelModel):
    """An extra charge after the fact -- housekeeping billed after an event, or a
    late-cancellation fee. A second charge of the same kind ADDS to the first."""

    amount: float = Field(gt=0)
    charge_type: str = "additional"
    description: str | None = Field(None, max_length=500)
