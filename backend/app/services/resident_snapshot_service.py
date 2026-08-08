"""The resident home aggregate — step 7, and the last endpoint of §6.

Closes `US-2.3`: *"as a resident I want a home screen that tells me what needs my
attention."*

**This service calls other services, not repositories.** That is the one design
decision in the file and it is deliberate. Every figure here already has an owner
— `resident_money_service` decides what `Unpaid` means, `resident_complaints_service`
decides which stored statuses render as `In Progress`, the visitor view decides
what is still current. Reaching past them into the repositories would copy each of
those rules into a second place, and the copies would be right on the day they
were written and wrong afterwards. The cost is a projection built from projections;
the benefit is that **the home screen and the screen it links to cannot disagree**,
which for a screen whose entire job is to summarise the others is the only property
that matters.

**Sequential reads, one honest timestamp.** Six reads, not one transaction, so the
dues could be a heartbeat older than the visitors. `generatedAt` is therefore the
moment the payload was assembled and not the moment any part of it was true. The
admin snapshot works the same way and for the same reason: a resident refreshing a
home screen is not asking for a consistent cut of the database.

**`activity` is the notification feed, and §5.7 says it should not be.** §5.7
reserved `member_activity` for this, reasoning that a second activity table would
mean two feeds that disagree. The reasoning holds; its premise does not. Nothing
in this project writes `member_activity` — not a trigger, not a service, not the
admin dashboard, which reads `audit_events` instead — so serving the home screen
from it would ship a feed that is empty by construction and stays empty. Meanwhile
§5.8 already made `notifications` the durable record of *"every user-visible
event"*, which is exactly what an activity strip shows. Writing those events a
second time into `member_activity` would create the very pair of disagreeing feeds
§5.7 set out to prevent. So the feed is the activity, `member_activity` stays
unused and unread, and §5.7 is corrected rather than obeyed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.resident_money_schemas import ResidentInvoice
from app.domain.resident_snapshot_schemas import (
    ComplaintDigest,
    DuesDigest,
    ResidentSnapshot,
    VisitorDigest,
)
from app.domain.resident_visitor_schemas import VisitorPass
from app.services import notifications_service
from app.services import resident_complaints_service as complaints
from app.services import resident_home_service as home
from app.services import resident_money_service as money
from app.services import resident_visitor_passes_service as visitors
from supabase import Client

#: How many unpaid bills the dues total is summed over. A resident with more than
#: this is a resident whose total is reported as partial rather than understated.
_DUES_SCAN = 100
#: The current-pass window the two guest counts are taken from. Both counts are
#: over passes that are still live, so the bound is what "still live" can grow to
#: before the numbers stop being complete.
_VISITOR_SCAN = 100
#: What the home screen renders: three notices, two complaints, three pending
#: passes, five recent events. Fetched to match, so nothing is transferred to be
#: thrown away by a client.
_NOTICES = 3
_COMPLAINTS = 5
_PENDING_PASSES = 3
_ACTIVITY = 5

#: The statuses that mean somebody is on their way but not here yet. Taken from
#: `DashboardHome.jsx`, which counts `Expected` and `Approved` together: to the
#: resident they are one thing, a guest who has not arrived.
_EXPECTED = {"Expected", "Approved"}
_CHECKED_IN = "Checked In"
_AWAITING = "Pending Approval"


def _primary_invoice(items: list[ResidentInvoice]) -> ResidentInvoice | None:
    """The bill the home screen offers to pay, per `DashboardHome.jsx`.

    The maintenance one if there is one, because that is the recurring bill a
    resident opens the app to settle; otherwise the oldest, because a bill that
    has been waiting longest is the one worth surfacing. Never the newest: that
    would quietly hide an overdue bill behind a fresh one.
    """
    payable = [item for item in items if item.is_payable]
    if not payable:
        return None

    for item in payable:
        if "maintenance" in f"{item.title} {item.invoice_type}".casefold():
            return item
    return payable[-1]


def _dues(client: Client, *, community_id: str) -> DuesDigest:
    page = money.list_invoices(
        client, community_id=community_id, view="unpaid", page_size=_DUES_SCAN
    )
    outstanding = sum(
        (item.outstanding_amount for item in page.items), start=Decimal("0")
    )
    primary = _primary_invoice(page.items)
    return DuesDigest(
        outstanding_total=outstanding,
        unpaid_count=page.total,
        currency_code=(primary.currency_code if primary else "INR"),
        is_partial_total=page.total > len(page.items),
        primary_invoice=primary,
    )


def _visitors(client: Client, *, membership_id: str) -> VisitorDigest:
    page = visitors.list_mine(
        client, membership_id=membership_id, view="current", page_size=_VISITOR_SCAN
    )

    def guests(passes: list[VisitorPass]) -> int:
        return sum(max(item.guest_count, 1) for item in passes)

    awaiting = [item for item in page.items if item.status == _AWAITING]
    return VisitorDigest(
        expected_guests=guests([i for i in page.items if i.status in _EXPECTED]),
        checked_in_guests=guests([i for i in page.items if i.status == _CHECKED_IN]),
        pending_count=len(awaiting),
        pending_approval=awaiting[:_PENDING_PASSES],
    )


def snapshot(
    client: Client, *, membership_id: str, community_id: str
) -> ResidentSnapshot:
    """Everything the resident home screen renders, in one call.

    Tenancy is the resolved membership and the community it belongs to, never a
    request parameter — §5.2, and the reason this endpoint takes no arguments at
    all. There is nothing a caller could pass that would widen it.
    """
    complaint_page = complaints.list_mine(
        client, membership_id=membership_id, page_size=_COMPLAINTS
    )
    notices = home.list_notices(client, community_id=community_id, page_size=_NOTICES)
    feed = notifications_service.list_feed(
        client, membership_id=membership_id, page_size=_ACTIVITY
    )

    return ResidentSnapshot(
        unread_notifications=feed.unread,
        dues=_dues(client, community_id=community_id),
        visitors=_visitors(client, membership_id=membership_id),
        complaints=ComplaintDigest(
            total=complaint_page.total, recent=complaint_page.items
        ),
        notices=notices.items,
        activity=feed.items,
        generated_at=datetime.now(UTC),
    )
