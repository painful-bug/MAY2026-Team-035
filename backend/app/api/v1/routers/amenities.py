"""Amenity catalogue, booking, approval, ledger and report routes.

The frontend's amenity subsystem is the largest in the codebase -- 114 files, a
per-amenity workspace with four tabs, and four service modules that already look
like an API client. That made it the cleanest seam of the build plan, and these
routes are shaped to it rather than to the database.

Two routes are deliberately not admin-only:

* ``POST /amenities/{id}/bookings/request`` is the resident's booking flow. It is
  here in an admin-scoped build because otherwise the approvals tab is a screen
  that can never have anything on it -- the same argument step 7 made for the
  invoice write endpoints.
* ``POST /amenity-bookings/cancel`` serves both. Which days you may cancel is
  decided by the database from your role, not by a flag in the body.

Everything else requires ADMIN.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.deps import get_current_user, get_request_client, require_role
from app.domain.amenity_schemas import (
    AddChargeRequest,
    AdminBookingRequest,
    AmenityDetail,
    AmenityReport,
    AmenityStatusRequest,
    AmenitySummary,
    ApprovalRequest,
    BlockSlotRequest,
    BookingSummary,
    CancelBookingRequest,
    DamageDeductionRequest,
    ForceCancelRequest,
    LedgerSummary,
    LedgerTransaction,
    RecordAmenityPaymentRequest,
    RefundDepositRequest,
    RejectBookingRequest,
    ResidentBookingRequest,
    SaveAmenityRequest,
)
from app.domain.common_schemas import MessageResult, Page
from app.domain.roles import Role
from app.services import amenities_service
from supabase import Client

router = APIRouter(tags=["amenities"])

_admin = Depends(require_role(Role.ADMIN))


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


@router.get(
    "/amenities",
    response_model=Page[AmenitySummary],
    summary="List amenities",
    dependencies=[_admin],
)
async def list_amenities(
    search: str | None = Query(None, max_length=100, alias="q"),
    category: str | None = Query(
        None, description="Sports | Fitness | Recreation | Events | Utility"
    ),
    status_filter: str | None = Query(
        None, alias="status", description="Active | Inactive | All"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[AmenitySummary]:
    """The catalogue grid, alphabetically.

    ``pendingRequests`` and ``outstandingDues`` are derived from the approvals
    queue and the ledger rather than stored, so the two badges on a card cannot
    disagree with the tabs they link to. The seeded data stores both as constants
    and they are already wrong there.

    Inactive amenities are included: the resident screen renders them greyed out
    rather than hiding them, so filtering them away here would change what
    residents see.
    """
    return amenities_service.list_amenities(
        client,
        principal.user_id,
        search=search,
        category=category,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/amenities",
    response_model=AmenityDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create an amenity",
    dependencies=[_admin],
)
async def create_amenity(
    body: SaveAmenityRequest,
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> AmenityDetail:
    """Create an amenity, with a full settings row from the defaults.

    Returns 409 when the community already has an amenity of that name -- one
    unique index, so two admins creating "Clubhouse Gym" at the same moment
    cannot both succeed.
    """
    return amenities_service.save_amenity(client, principal.user_id, body)


@router.get(
    "/amenities/{amenity_id}",
    response_model=AmenityDetail,
    summary="Get an amenity",
    dependencies=[_admin],
)
async def get_amenity(
    amenity_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> AmenityDetail:
    """One amenity with all five settings groups the settings tab edits."""
    return amenities_service.get_amenity(client, principal.user_id, amenity_id)


@router.patch(
    "/amenities/{amenity_id}",
    response_model=AmenityDetail,
    summary="Update an amenity",
    dependencies=[_admin],
)
async def update_amenity(
    body: SaveAmenityRequest,
    amenity_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> AmenityDetail:
    """Update the catalogue fields, the settings, or both, in one transaction.

    The settings tab saves thirty fields on one click; splitting that across two
    calls would let the second fail after the first had already been written.
    A field left out is left alone.
    """
    return amenities_service.save_amenity(
        client, principal.user_id, body, amenity_id=amenity_id
    )


@router.patch(
    "/amenities/{amenity_id}/status",
    response_model=AmenityDetail,
    summary="Activate or deactivate an amenity",
    dependencies=[_admin],
)
async def set_amenity_status(
    body: AmenityStatusRequest,
    amenity_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> AmenityDetail:
    """The availability toggle on the card.

    Its own route rather than a partial update, because the toggle sends one
    boolean and routing it through a twelve-field patch is how a toggle ends up
    blanking a description.
    """
    return amenities_service.set_amenity_status(
        client, principal.user_id, amenity_id, body.is_active
    )


@router.delete(
    "/amenities/{amenity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an amenity",
    dependencies=[_admin],
)
async def delete_amenity(
    amenity_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> Response:
    """Delete an amenity nobody has booked.

    Returns 409 once anything has been booked on it, naming the count and
    pointing at deactivation instead: the cascade would take the bookings, their
    charges and their financial events with it, including deposits residents are
    still owed.
    """
    amenities_service.delete_amenity(client, amenity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


@router.get(
    "/amenities/{amenity_id}/bookings",
    response_model=Page[BookingSummary],
    summary="List an amenity's bookings",
    dependencies=[_admin],
)
async def list_amenity_bookings(
    amenity_id: str = Path(...),
    booking_date: date | None = Query(None, alias="date"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    timeline_only: bool = Query(
        True,
        alias="timelineOnly",
        description=(
            "Drop pending, rejected and cancelled days, matching what the "
            "timeline paints. Set false for the full history."
        ),
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[BookingSummary]:
    """The day timeline.

    ``state`` is the timeline's vocabulary ('booked' | 'blocked'); ``status`` is
    the lifecycle's. The cleaning buffer is deliberately not sent as a block: the
    frontend synthesises buffers at render time from the booking's end and the
    amenity's buffer, and sending them too would give one block two sources.

    A booking whose end time has passed reads ``completed`` even though it is
    stored as ``approved`` -- that is a fact about the clock, not about the row.
    """
    return amenities_service.list_bookings(
        client,
        principal.user_id,
        amenity_id=amenity_id,
        booking_date=booking_date,
        date_from=date_from,
        date_to=date_to,
        timeline_only=timeline_only,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/amenities/{amenity_id}/bookings",
    response_model=BookingSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking on a resident's behalf",
    dependencies=[_admin],
)
async def create_admin_booking(
    body: AdminBookingRequest,
    amenity_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> BookingSummary:
    """The admin's Create Booking modal. Confirmed on creation, never pending.

    The opening-hours, closed-day and advance-window rules are **not** applied:
    an admin booking the hall outside opening hours is doing their job. The
    conflict rules still apply -- two things cannot occupy one room whoever
    booked them -- so this returns 409 when the slot is taken or full.

    ``chargeOverride`` replaces the booking fee and nothing else. A waived fee
    does not waive the deposit, which is coming back.
    """
    return amenities_service.create_admin_booking(
        client, principal.user_id, amenity_id, body
    )


@router.post(
    "/amenities/{amenity_id}/bookings/request",
    response_model=Page[BookingSummary],
    status_code=status.HTTP_201_CREATED,
    summary="Request a booking (resident)",
)
async def request_booking(
    body: ResidentBookingRequest,
    amenity_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[BookingSummary]:
    """A resident asking for one or more days of the same slot.

    The flat is read from the caller's own residency, never from the body, so a
    resident cannot book against somebody else's unit by editing the request.
    Whether it needs approval is read from the amenity's settings for the same
    reason: a client that could choose would be a client that could opt out.

    Every day is validated before any is written, so a three-day request either
    lands whole or not at all. Returns 409 for a closed day, a slot outside the
    booking window, a duration outside the amenity's limits, a full slot, or a
    conflict -- each with the message the booking form already shows.

    Returns every day created, because telling the caller about one day of three
    is how a resident is surprised by the other two.
    """
    return amenities_service.request_booking(
        client, principal.user_id, amenity_id, body
    )


@router.post(
    "/amenities/{amenity_id}/blocks",
    response_model=BookingSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Block a slot administratively",
    dependencies=[_admin],
)
async def block_slot(
    body: BlockSlotRequest,
    amenity_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> BookingSummary:
    """Reserve a slot for maintenance or an association event.

    Always exclusive, whatever the amenity's booking mode says: a hall closed for
    repairs is closed to everybody. Carries no flat and no charges.
    """
    return amenities_service.block_slot(client, principal.user_id, amenity_id, body)


@router.get(
    "/amenities/{amenity_id}/approvals",
    response_model=Page[ApprovalRequest],
    summary="List booking requests awaiting a decision",
    dependencies=[_admin],
)
async def list_approvals(
    amenity_id: str = Path(...),
    status_filter: str = Query(
        "pending",
        alias="status",
        description="pending | approved | rejected | cancelled | all",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[ApprovalRequest]:
    """The approvals tab -- **one row per request, not per day**.

    The frontend produces one row per day and approves them one at a time, so a
    three-day request appears three times and can be approved on Monday and
    rejected on Tuesday. Here one decision covers the request, and ``dayCount``
    and ``dates`` say how much it covers.

    ``outstandingDues`` is the **flat's** balance across its unpaid invoices. The
    frontend computes it per person; our invoices attach to the unit and carry no
    person, so it is the same label over a different number
    (DECISIONS_NEEDED E18).
    """
    return amenities_service.list_approvals(
        client,
        principal.user_id,
        amenity_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/amenity-bookings/{series_id}/approve",
    response_model=Page[BookingSummary],
    summary="Approve a booking request",
    dependencies=[_admin],
)
async def approve_booking(
    series_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[BookingSummary]:
    """Approve a whole request -- every day of it.

    Days the resident already withdrew keep their cancellation: approving should
    not resurrect a day somebody said they no longer wanted. Returns 409 if the
    request has already been decided.
    """
    return amenities_service.approve_booking(client, principal.user_id, series_id)


@router.post(
    "/amenity-bookings/{series_id}/reject",
    response_model=Page[BookingSummary],
    summary="Reject a booking request",
    dependencies=[_admin],
)
async def reject_booking(
    body: RejectBookingRequest,
    series_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[BookingSummary]:
    """Reject a whole request and release its slots.

    ``reasonCode`` is required and ``other`` must carry free text: a rejection
    with neither is an unanswerable support ticket, which is why the database
    refuses it as well. Returns 409 if the request has already been decided.
    """
    return amenities_service.reject_booking(
        client, principal.user_id, series_id, body
    )


@router.post(
    "/amenity-bookings/cancel",
    response_model=MessageResult,
    summary="Cancel selected booking days",
)
async def cancel_bookings(
    body: CancelBookingRequest,
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Cancel one or more days of a request.

    Serves residents and admins from one route. A resident may withdraw their own
    **future** days; an admin may cancel any. Which of the two you are is read
    from your token, so there is nothing in the body to lie about.

    All-or-nothing: if any selected day cannot be cancelled the whole call
    returns 409, rather than cancelling four of five and reporting success.
    """
    cancelled = amenities_service.cancel_bookings(client, body)
    return MessageResult(
        message=f"{cancelled} booking day(s) cancelled."
        if cancelled != 1
        else "1 booking day cancelled."
    )


@router.post(
    "/amenity-bookings/{occurrence_id}/force-cancel",
    response_model=BookingSummary,
    summary="Force-cancel a booking",
    dependencies=[_admin],
)
async def force_cancel_booking(
    body: ForceCancelRequest,
    occurrence_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> BookingSummary:
    """Override a booking the resident still wants.

    Distinct from an ordinary cancellation because the ledger records who did it
    and why, and because the deposit becomes refundable as a result -- which the
    ledger derives rather than being told. Returns 409 unless the booking is
    approved or confirmed.
    """
    return amenities_service.force_cancel_booking(
        client, principal.user_id, occurrence_id, body
    )


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


@router.get(
    "/amenities/{amenity_id}/ledger",
    response_model=Page[LedgerTransaction],
    summary="List an amenity's financial transactions",
    dependencies=[_admin],
)
async def list_ledger(
    amenity_id: str = Path(...),
    payment_status: str | None = Query(
        None,
        alias="paymentStatus",
        description=(
            "paid | pending | partially_paid | refund_pending | refunded | "
            "cancelled | all"
        ),
    ),
    search: str | None = Query(None, max_length=100, alias="q"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[LedgerTransaction]:
    """The ledger tab.

    Every figure is derived from the charges and the append-only event stream --
    nothing stores a balance, so no balance can drift out of agreement with the
    rows that produce it. ``paymentStatus`` is a CASE over those figures, and the
    order of its arms is its meaning: a cancelled booking still holding a
    refundable deposit is ``refund_pending``, because somebody is owed money.

    ``availableActions`` is computed from the same rules the write endpoints
    enforce, so a button the client renders is a button the API will honour.
    """
    return amenities_service.list_ledger(
        client,
        principal.user_id,
        amenity_id=amenity_id,
        payment_status=payment_status,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/amenities/{amenity_id}/ledger/summary",
    response_model=LedgerSummary,
    summary="Amenity ledger totals",
    dependencies=[_admin],
)
async def get_ledger_summary(
    amenity_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> LedgerSummary:
    """The eight cards above the ledger table.

    Aggregated by Postgres over every transaction for the amenity, so the figures
    do not change when the table is paged. An amenity nobody has booked reports
    zeros with HTTP 200, never a 404.
    """
    return amenities_service.get_ledger_summary(
        client, principal.user_id, amenity_id
    )


@router.post(
    "/amenity-bookings/{occurrence_id}/payments",
    response_model=LedgerTransaction,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment against a booking",
    dependencies=[_admin],
)
async def record_payment(
    body: RecordAmenityPaymentRequest,
    occurrence_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> LedgerTransaction:
    """Record money received against one charge -- the booking fee or the deposit.

    Idempotent on ``paymentReference``: a replayed gateway callback returns the
    event already recorded rather than double-crediting. Overpayment returns 409
    rather than being clamped, because clamping accepts money and then loses it.
    """
    return amenities_service.record_payment(
        client, principal.user_id, occurrence_id, body
    )


@router.post(
    "/amenity-bookings/{occurrence_id}/refund",
    response_model=LedgerTransaction,
    status_code=status.HTTP_201_CREATED,
    summary="Refund a booking deposit",
    dependencies=[_admin],
)
async def refund_deposit(
    body: RefundDepositRequest,
    occurrence_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> LedgerTransaction:
    """Return what is left of the deposit.

    **The amount is not a parameter.** It is the deposit paid, less damage taken,
    less anything already refunded, computed in Postgres -- a refund whose amount
    the caller chooses is a refund somebody can ask to be larger. Returns 409
    while the booking is still ahead of it, or once nothing is left.
    """
    return amenities_service.refund_deposit(
        client, principal.user_id, occurrence_id, body
    )


@router.post(
    "/amenity-bookings/{occurrence_id}/damage",
    response_model=LedgerTransaction,
    status_code=status.HTTP_201_CREATED,
    summary="Deduct damage from a booking deposit",
    dependencies=[_admin],
)
async def deduct_damage(
    body: DamageDeductionRequest,
    occurrence_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> LedgerTransaction:
    """Take damage out of the held deposit.

    Capped at what is left, and capped in Postgres rather than here: a deduction
    larger than the deposit is not a deduction, it is an invoice, and it would
    drive ``remainingRefund`` negative -- which the ledger clamps to zero, quietly
    hiding the error. Returns 409 instead. A reason is required.
    """
    return amenities_service.deduct_damage(
        client, principal.user_id, occurrence_id, body
    )


@router.post(
    "/amenity-bookings/{occurrence_id}/charges",
    response_model=LedgerTransaction,
    status_code=status.HTTP_201_CREATED,
    summary="Add a charge to a booking",
    dependencies=[_admin],
)
async def add_charge(
    body: AddChargeRequest,
    occurrence_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> LedgerTransaction:
    """Bill something after the fact -- housekeeping, or a late-cancellation fee.

    A second charge of the same kind **adds** to the first: the ledger has one
    ``additionalCharges`` figure, and housekeeping on Monday plus a broken chair
    on Tuesday is two things, not the later one.
    """
    return amenities_service.add_charge(
        client, principal.user_id, occurrence_id, body
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get(
    "/amenity-reports",
    response_model=AmenityReport,
    summary="Amenity activity report",
    dependencies=[_admin],
)
async def get_report(
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    amenity_id: str | None = Query(None, alias="amenityId"),
    booking_status: str | None = Query(None, alias="bookingStatus"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> AmenityReport:
    """The reports page.

    ``rows`` is a page, because a table renders a page. ``kpis`` is a database
    aggregate over **every** matching row, because a KPI that describes one page
    is not a KPI -- and this one is labelled "Total Revenue".

    ``options.bookingStatuses`` is the lifecycle's fixed vocabulary rather than
    the statuses that happen to be present, so the filter does not lose an option
    the moment nothing currently has that status.
    """
    return amenities_service.build_report(
        client,
        principal.user_id,
        start_date=start_date,
        end_date=end_date,
        amenity_id=amenity_id,
        booking_status=booking_status,
        page=page,
        page_size=page_size,
    )
