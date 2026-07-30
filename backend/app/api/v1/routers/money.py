"""Invoice, payment and billing-settings routes.

The admin dashboard's Maintenance screen is **read-only** -- it lists invoices
and shows three tiles, and there is no way to bill anybody from it. The write
endpoints here exist anyway, because a collections screen over a system that
cannot issue an invoice reports on an empty table forever. Raised with the
frontend team as agenda item 12.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.deps import get_current_user, get_request_client, require_role
from app.domain.common_schemas import Page
from app.domain.money_schemas import (
    BillingSettings,
    CollectionSummaryDetail,
    CreateInvoiceRequest,
    InvoiceDetail,
    InvoiceSummary,
    MaintenanceRunRequest,
    MaintenanceRunResult,
    PaymentSummary,
    RecordPaymentRequest,
    UpdateBillingSettingsRequest,
    VoidInvoiceRequest,
)
from app.domain.roles import Role
from app.services import money_service
from supabase import Client

router = APIRouter(tags=["money"], dependencies=[Depends(require_role(Role.ADMIN))])


@router.get("/invoices", response_model=Page[InvoiceSummary], summary="List invoices")
async def list_invoices(
    search: str | None = Query(
        None,
        max_length=100,
        alias="q",
        description=(
            "Matches the invoice title, its number, the flat code and the "
            "current resident's name -- the fields the collections search box "
            "covers."
        ),
    ),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Paid | Unpaid | Void | All. A partially paid invoice is Unpaid.",
    ),
    unit_id: str | None = Query(None, alias="unitId"),
    invoice_type: str | None = Query(
        None, alias="invoiceType", description="maintenance | amenity | penalty | misc"
    ),
    overdue_only: bool = Query(False, alias="overdueOnly"),
    issued_from: date | None = Query(None, alias="issuedFrom"),
    issued_to: date | None = Query(None, alias="issuedTo"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[InvoiceSummary]:
    """The maintenance collections table, newest due date first.

    ``amount`` is what the flat was billed, not what it still owes -- the column
    is headed "Amount". ``outstanding`` carries the balance, and
    ``GET /invoices/summary`` is the authority on the totals: deriving them by
    summing this page gives the total of a page, not of the community.
    """
    return money_service.list_invoices(
        client,
        principal.user_id,
        search=search,
        status=status_filter,
        unit_id=unit_id,
        invoice_type=invoice_type,
        overdue_only=overdue_only,
        issued_from=issued_from,
        issued_to=issued_to,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/invoices/summary",
    response_model=CollectionSummaryDetail,
    summary="Collection totals",
)
async def get_collection_summary(
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> CollectionSummaryDetail:
    """The three tiles at the top of the Maintenance screen.

    Aggregated by Postgres over every invoice in the community, so the figures do
    not change when the list is paged. ``totalOutstanding`` sums the outstanding
    *balances*, so a partially paid invoice contributes only what is still owed.

    A community with no invoices reports zeros with HTTP 200, never a 404.
    """
    return money_service.get_collection_summary(client, principal.user_id)


@router.post(
    "/invoices",
    response_model=InvoiceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Issue an invoice",
)
async def create_invoice(
    body: CreateInvoiceRequest,
    principal=Depends(get_current_user),
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
    return money_service.create_invoice(client, principal.user_id, body)


@router.get(
    "/invoices/{invoice_id}", response_model=InvoiceDetail, summary="Get an invoice"
)
async def get_invoice(
    invoice_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> InvoiceDetail:
    """One invoice with its line items and every payment recorded against it."""
    return money_service.get_invoice(client, principal.user_id, invoice_id)


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=InvoiceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment",
)
async def record_payment(
    body: RecordPaymentRequest,
    invoice_id: str = Path(...),
    principal=Depends(get_current_user),
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
        client, principal.user_id, invoice_id, body
    )


@router.post(
    "/invoices/{invoice_id}/void",
    response_model=InvoiceDetail,
    summary="Void an invoice",
)
async def void_invoice(
    body: VoidInvoiceRequest,
    invoice_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> InvoiceDetail:
    """Cancel an invoice.

    **There is no DELETE for money.** The invoice, its lines and its number stay
    in place and are marked void -- an invoice number that vanishes is a gap
    somebody has to account for later.

    Returns 409 once any payment has succeeded against it: cancelling a bill
    somebody has already paid would strand their money against nothing.
    """
    return money_service.void_invoice(
        client, principal.user_id, invoice_id, body.reason
    )


@router.post(
    "/maintenance-runs",
    response_model=MaintenanceRunResult,
    status_code=status.HTTP_201_CREATED,
    summary="Run maintenance billing",
)
async def run_maintenance_billing(
    body: MaintenanceRunRequest,
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MaintenanceRunResult:
    """Issue one maintenance invoice per **occupied** flat for a billing period.

    **Safe to repeat.** A second run for the same period reports every flat as
    skipped and bills nobody; the guard is a partial unique index, so it holds
    even if two admins click at the same moment.

    The amount comes from ``billingSettings.defaultMaintenanceAmount`` unless
    overridden here. With neither set the call returns **409** rather than
    falling back to a number nobody chose -- the frontend's hardcoded 4250 is a
    demo value and adopting it would bill a real community by accident.

    Vacant flats are not billed, because nothing in the product records who owns
    an empty one (DECISIONS_NEEDED A14).
    """
    return money_service.run_maintenance_billing(client, principal.user_id, body)


@router.get("/payments", response_model=Page[PaymentSummary], summary="List payments")
async def list_payments(
    search: str | None = Query(None, max_length=100, alias="q"),
    method: str | None = Query(
        None,
        description="UPI | Credit Card | Net Banking | Cash | Cheque | Bank Transfer",
    ),
    invoice_id: str | None = Query(None, alias="invoiceId"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[PaymentSummary]:
    """The collection log the Maintenance screen's subtitle promises.

    Every payment received, newest first, across all invoices -- which is a
    different question from "what does this flat owe" and needs its own list.
    """
    return money_service.list_payments(
        client,
        principal.user_id,
        search=search,
        method=method,
        invoice_id=invoice_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/billing-settings", response_model=BillingSettings, summary="Get billing settings"
)
async def get_billing_settings(
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> BillingSettings:
    """The community's billing configuration.

    ``defaultMaintenanceAmount`` is null until an admin sets one. There is no
    screen for this today and no value to migrate: the maintenance amount exists
    in the product only as a literal ``4250`` inside an approval handler
    (agenda item 12).
    """
    return money_service.get_billing_settings(client, principal.user_id)


@router.put(
    "/billing-settings",
    response_model=BillingSettings,
    summary="Update billing settings",
)
async def update_billing_settings(
    body: UpdateBillingSettingsRequest,
    principal=Depends(get_current_user),
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
    return money_service.update_billing_settings(client, principal.user_id, body)
