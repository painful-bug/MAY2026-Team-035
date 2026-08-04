"""The resident home aggregate.

`RESIDENT_BACKEND_DESIGN.md` §5.1 and step 7 of §9. This is a **projection of
other endpoints, not a source of truth**: every model below is either reused
verbatim from the endpoint that owns it — `ResidentInvoice`, `VisitorPass`,
`ComplaintSummary`, `Notice`, `NotificationItem` — or is a count derived from
one. Nothing here has a shape of its own that could drift from the screen a
resident taps through to.

That is the whole reason this file is short. A home screen that renders a bill in
its own bespoke shape is a home screen that will eventually show a different
amount than the Payments page, and the resident will believe the smaller one.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.domain.common_schemas import CamelModel
from app.domain.notification_schemas import NotificationItem
from app.domain.resident_complaint_schemas import ComplaintSummary
from app.domain.resident_home_schemas import Notice
from app.domain.resident_money_schemas import ResidentInvoice
from app.domain.resident_visitor_schemas import VisitorPass


class DuesDigest(CamelModel):
    """What the caller owes, and the one bill the home screen offers to settle.

    ``primaryInvoice`` follows `DashboardHome.jsx`: the maintenance bill if there
    is one, otherwise the oldest unpaid bill. It is a whole `ResidentInvoice`
    rather than a title and an amount, so the Pay button on the home screen and
    the Pay button on the Payments page are drawn from the same `isPayable`.

    ``isPartialTotal`` is the honest half of ``outstandingTotal``. The sum is over
    the bills actually read, and a resident holding more unpaid bills than one
    page can carry would otherwise be shown a total that is quietly too small.
    A flag the client can act on beats a number that is wrong without saying so.
    """

    outstanding_total: Decimal = Decimal("0")
    unpaid_count: int = 0
    currency_code: str = "INR"
    is_partial_total: bool = False
    primary_invoice: ResidentInvoice | None = None


class VisitorDigest(CamelModel):
    """Who is expected, who is already inside, and who is waiting on an answer.

    Both counts are **guests, not passes**, because that is what the shipped
    screen counts: `DashboardHome.jsx` reduces over `guestCount`. One pass for a
    party of twelve is twelve people at the gate, and a card reading "1" in front
    of a resident expecting a dozen is a card that has misunderstood the question.

    ``pendingApproval`` carries whole passes because the home screen approves and
    rejects from the card, without navigating.
    """

    expected_guests: int = 0
    checked_in_guests: int = 0
    pending_count: int = 0
    pending_approval: list[VisitorPass] = []


class ComplaintDigest(CamelModel):
    """The caller's most recent complaints, and how many they have raised.

    No open/closed split. The home screen renders the newest two with their
    status words and counts nothing, and a number nobody asked for is a number
    that has to be kept correct for the rest of the project's life.
    """

    total: int = 0
    recent: list[ComplaintSummary] = []


class ResidentSnapshot(CamelModel):
    """One read for the resident home screen.

    Deliberately **not** `/dashboard/snapshot` with a role branch (§5.1). An
    admin wants counts across the community and a resident wants *their* dues,
    *their* visitors, *their* complaints; a single payload whose shape depends on
    a runtime role is one `if` away from leaking a community-wide count into a
    resident's response.

    ``activity`` is the caller's notification feed rather than a second event
    log — see the service for why, and for the disagreement with §5.7 that
    choice records.
    """

    #: The badge. Counted across the whole feed, never across the page below.
    unread_notifications: int = 0
    dues: DuesDigest = DuesDigest()
    visitors: VisitorDigest = VisitorDigest()
    complaints: ComplaintDigest = ComplaintDigest()
    notices: list[Notice] = []
    activity: list[NotificationItem] = []
    #: When the server assembled this. The parts are read in sequence rather than
    #: inside one transaction, so this is the only timestamp the payload can
    #: honestly claim.
    generated_at: datetime
