"""Invoice, payment and billing-settings routes.

The money *reads* were removed after the frontend wiring audit
(``docs/FRONTEND_WIRING_AUDIT.md``): ``GET /dashboard/snapshot`` projects
``payments[]`` with invoices and payments already merged, and the Maintenance
screen computes its three tiles client-side from that.

What is left is the minimum coherent write path plus the two billing settings the
Settings screen toggles. **Neither write has a UI caller today** -- Maintenance is
read-only. They are kept rather than deleted because ``GET``/``PUT
/billing-settings`` configures late fees and maintenance amounts, and settings that
govern a billing engine with no way to issue or settle an invoice configure
nothing at all. Raised with the frontend team as agenda item 12.

**Recording a payment is admin-only, deliberately.** The resident Payments screen
has a dead ``payInvoice`` action, and it must not be wired here: this endpoint
marks money as *received* and settles the invoice, so exposing it to the payer
would let a resident clear their own dues by asserting they had paid. Resident
self-service needs a payment gateway whose webhook calls this, which is
unbuilt (F2-adjacent, and now unblocked by the baseline's ``payments.provider`` and
``idempotency_key`` columns).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status

from app.api.admin_deps import require_admin, require_csrf_unsafe
from app.api.deps import get_active_membership, get_request_client
from app.domain.schemas import MembershipContext
from app.domain.money_schemas import (
    BillingSettings,
    CreateInvoiceRequest,
    InvoiceDetail,
    RecordPaymentRequest,
    UpdateBillingSettingsRequest,
)
from app.services import money_service
from supabase import Client

router = APIRouter(
    tags=["money"],
    dependencies=[Depends(require_admin), Depends(require_csrf_unsafe)],
)


@router.post(
    "/invoices",
    response_model=InvoiceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Issue an invoice",
)
def create_invoice(
    body: CreateInvoiceRequest,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> InvoiceDetail:
    """Issue one invoice against one flat.

    The invoice, its line items and its number are written in one transaction,
    and the totals are computed from the lines -- so a header that disagrees with
    its own contents cannot be submitted.

    The flat is identified by ``unitId`` or by ``flat`` (``B-1204``), and is
    created on first reference. Returns 409 when the lines total zero or the due
    date precedes the issue date.
    """
    return money_service.create_invoice(client, membership.community_id, body)


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=InvoiceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment",
)
def record_payment(
    body: RecordPaymentRequest,
    invoice_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> InvoiceDetail:
    """Record money received against an invoice and return the settled invoice.

    **Idempotent on ``reference``.** Sending the same reference twice returns the
    payment already recorded rather than crediting the invoice again, so a
    retried gateway webhook or a double-tapped Pay button cannot settle a bill
    twice.

    Returns 409 for an amount above the outstanding balance -- an overpayment is
    refused rather than clamped, because clamping accepts money and then loses
    it. Also 409 once the invoice has been voided.
    """
    return money_service.record_payment(
        client, membership.community_id, invoice_id, body
    )


@router.get(
    "/billing-settings", response_model=BillingSettings, summary="Get billing settings"
)
def get_billing_settings(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> BillingSettings:
    """The community's billing configuration.

    ``defaultMaintenanceAmount`` is null until an admin sets one. There is no
    screen for this today and no value to migrate: the maintenance amount exists
    in the product only as a literal ``4250`` inside an approval handler
    (agenda item 12).
    """
    return money_service.get_billing_settings(client, membership.community_id)


@router.put(
    "/billing-settings",
    response_model=BillingSettings,
    summary="Update billing settings",
)
def update_billing_settings(
    body: UpdateBillingSettingsRequest,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> BillingSettings:
    """Patch the billing configuration. Omitted fields are left unchanged.

    Sending ``defaultMaintenanceAmount: null`` clears the rate and stops billing
    runs until one is set again -- distinct from omitting the field, which leaves
    it as it was.

    ``invoiceNumberPrefix`` only affects numbers issued from now on. Invoices
    already issued keep the number they were given, because a number that changes
    is not an identifier.
    """
    return money_service.update_billing_settings(client, membership.community_id, body)
