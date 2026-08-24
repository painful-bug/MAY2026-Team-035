"""The resident's bills and bookings, and paying either one.

There is already a money router — `routers/money.py` — and this is deliberately
not it. §5.5: an admin *records* a payment that happened somewhere else, with an
arbitrary amount, an arbitrary method and possibly a backdated date. A resident
*initiates* one against their own bill, for the full balance, through whatever
gateway exists. Merging them would produce one endpoint where half the fields are
forbidden depending on who is calling.

**Every payment here goes through a simulator, and every row it writes says so.**
`provider = 'simulator'` is written on each one, so no ledger entry ever claims
to be something it is not — which is the only way anybody will be able to
separate the money that moved from the money that did not, on the day a real
gateway arrives.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_active_membership, get_request_client
from app.domain.common_schemas import Page
from app.domain.resident_money_schemas import (
    PayBookingRequest,
    PayInvoiceRequest,
    PaymentOutcome,
    ResidentBooking,
    ResidentInvoice,
)
from app.domain.schemas import MembershipContext
from app.services import resident_money_service as service
from supabase import Client

router = APIRouter(tags=["resident-money"], dependencies=[Depends(require_csrf_unsafe)])


@router.get(
    "/invoices/mine",
    response_model=Page[ResidentInvoice],
    summary="List my invoices",
)
async def list_my_invoices(
    view: str | None = Query(
        None, description="`unpaid` | `paid`. Omitted returns both."
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> Page[ResidentInvoice]:
    """The caller's own bills, newest first. **Requires an active membership.**

    `status` is the screen's word: `partially_paid`, `issued` and `overdue` all
    read as `Unpaid`, because that is what they are to the person who owes the
    money. `storedStatus` carries the real one.

    `isPayable` is computed in the database and is the same rule the settlement
    RPC enforces — a Pay button drawn from anything else is a button that fails.
    It is **not** what `view` splits on: a cancelled bill is not payable and was
    never paid, so the tabs split on `status`, which is the word the screen shows.

    Bills raised against the flat rather than against a person are included, since
    they are the caller's to pay. Drafts are not: an unissued bill is not yet a
    bill.
    """
    return service.list_invoices(
        client,
        community_id=membership.community_id,
        view=view,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/invoices/{invoice_id}/pay",
    response_model=PaymentOutcome,
    summary="Pay one of my invoices",
)
async def pay_invoice(
    body: PayInvoiceRequest,
    invoice_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> PaymentOutcome:
    """Settle a bill through the simulated gateway.

    **A declined payment is a `200`, not an error.** The request was well-formed,
    authorized, processed and produced a durable record; the *payment* failed.
    Branch on `status`, which is `succeeded` or `failed`, and read `failureCode`
    for the reason. HTTP `4xx` still means what it always meant — `404` for
    somebody else's invoice, `409` for one already settled, `422` for a body that
    does not add up.

    **`amount` must equal the outstanding balance**, and it is checked against the
    balance the database computes rather than accepted as an instruction. A
    partial payment is a policy question nobody has answered.

    **`idempotencyKey` is required. One key per press of Pay** — a double-tap or
    a retried request returns the payment that was already recorded, described
    from the stored row rather than re-judged, which is what stops a resident
    paying twice. **A new key for a new attempt**, once a decline has been shown;
    reusing it would replay that decline forever and a corrected card would never
    work. Reusing one across two different bills is a `409`, not a silent
    success against the wrong invoice.

    Card numbers, CVVs and expiry dates are read by a pure function and
    discarded. Nothing but a masked label is stored, logged or returned.
    """
    return service.pay_invoice(
        client,
        community_id=membership.community_id,
        invoice_id=invoice_id,
        body=body,
    )


@router.get(
    "/amenity-bookings/mine",
    response_model=Page[ResidentBooking],
    summary="List my amenity bookings",
)
async def list_my_bookings(
    view: str | None = Query(
        None, description="`upcoming` | `past`. Omitted returns both."
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> Page[ResidentBooking]:
    """The caller's own bookings, with what is still owed on each.

    `amenity_booking_charges` was admin-only until `0033`, so a resident could be
    charged for a booking and had no endpoint that would tell them so. They can
    now see their own, and nobody else's.

    `status` is the lowercase machine value — `pending`, `approved`, `rejected`,
    `cancelled`, `completed`, `no_show` — the same vocabulary the admin amenity
    endpoints emit. Unlike the invoice list above, `storedStatus` is not a
    second, truer answer here: it agrees with `status` on every row except that
    it keeps the enum's own `requested` for the pending state.
    """
    return service.list_bookings(
        client,
        membership_id=membership.id,
        view=view,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/amenity-bookings/{booking_id}/pay",
    response_model=PaymentOutcome,
    summary="Pay for one of my bookings",
)
async def pay_booking(
    body: PayBookingRequest,
    booking_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> PaymentOutcome:
    """Pay for an amenity booking, and confirm it in the same transaction.

    **This is the endpoint `US-2.12` asks for.** The story is *"a successful
    payment always yields a confirmed booking"*, and the pain point behind it —
    *"payments can fail even after money has been deducted"* — is not a gateway
    defect. It is a payment recorded in one transaction and a booking confirmed
    in another, with a crash in between. Here they are one statement.

    On a decline the booking is left **exactly** as it was, and the resident is
    told. A failed payment must not leave a half-confirmed booking somebody
    believes they hold.

    Same request shape, same `200`-on-decline rule and same idempotency
    obligation as paying an invoice.
    """
    return service.pay_booking(
        client,
        membership_id=membership.id,
        booking_id=booking_id,
        body=body,
    )
