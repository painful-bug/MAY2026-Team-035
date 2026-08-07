"""The resident home aggregate.

Almost every assertion here is about a *rule*, not a field, because the fields
are other endpoints' and are tested where they live. What is only true here is
the arithmetic: which bill gets offered, whether a party of twelve counts as one
visitor or twelve, and whether the badge counts the feed or the page.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.common_schemas import Page
from app.domain.notification_schemas import NotificationFeed, NotificationItem
from app.domain.resident_complaint_schemas import ComplaintSummary
from app.domain.resident_home_schemas import Notice
from app.domain.resident_money_schemas import ResidentInvoice
from app.domain.resident_visitor_schemas import VisitorPass
from app.services import (
    notifications_service,
    resident_complaints_service,
    resident_home_service,
    resident_money_service,
    resident_visitor_passes_service,
)
from app.services import resident_snapshot_service as service

SNAPSHOT = "/api/v1/resident/snapshot"

NOW = "2026-08-04T09:00:00+00:00"


def invoice(**overrides: Any) -> ResidentInvoice:
    base: dict[str, Any] = {
        "id": "invoice-id",
        "invoice_type": "maintenance",
        "title": "August maintenance",
        "status": "Unpaid",
        "stored_status": "issued",
        "total_amount": "4250.00",
        "amount_paid": "0.00",
        "outstanding_amount": "4250.00",
        "is_overdue": False,
        "is_payable": True,
        "created_at": NOW,
    }
    base.update(overrides)
    return ResidentInvoice(**base)


def visitor_pass(**overrides: Any) -> VisitorPass:
    base: dict[str, Any] = {
        "id": "pass-id",
        "visitor_name": "Guest group",
        "purpose": "Guest",
        "guest_count": 1,
        "status": "Expected",
        "created_at": NOW,
        "is_current": True,
        "is_lapsed": False,
    }
    base.update(overrides)
    return VisitorPass(**base)


def complaint(**overrides: Any) -> ComplaintSummary:
    base: dict[str, Any] = {
        "id": "complaint-id",
        "title": "Lift is stuck",
        "category": "Maintenance",
        "status": "Pending",
        "urgency": "High",
        "location": "Block A",
        "progress": 0,
        "assignee": "",
        "created_at": NOW,
        "updated_at": NOW,
        "last_activity_at": NOW,
        "is_overdue": False,
        "is_unread": False,
        "reopened_count": 0,
        "comment_count": 0,
    }
    base.update(overrides)
    return ComplaintSummary(**base)


def notice(**overrides: Any) -> Notice:
    base: dict[str, Any] = {
        "id": "notice-id",
        "title": "Water shutdown",
        "body": "Tuesday, 10am to 2pm.",
        "category": "Maintenance",
        "urgency": "Important",
        "published_at": NOW,
    }
    base.update(overrides)
    return Notice(**base)


def event(**overrides: Any) -> NotificationItem:
    base: dict[str, Any] = {
        "id": "notification-id",
        "kind": "visitor.approval_requested",
        "title": "A visitor is at the gate",
        "body": "Ravi is asking to come up.",
        "url": "/resident/visitors",
        "is_unread": True,
        "created_at": NOW,
    }
    base.update(overrides)
    return NotificationItem(**base)


def page(items: list[Any], total: int | None = None) -> Page:
    return Page(
        items=items,
        total=len(items) if total is None else total,
        page=1,
        page_size=100,
        has_more=False,
    )


@pytest.fixture
def parts(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace the five services this one aggregates, and record their arguments."""
    captured: dict = {
        "invoices": [invoice()],
        "invoice_total": None,
        "passes": [visitor_pass()],
        "complaints": [complaint()],
        "complaint_total": 3,
        "notices": [notice()],
        "activity": [event()],
        "unread": 7,
        "calls": [],
    }

    def fake_invoices(client: Any, **kwargs: Any) -> Page:
        captured["calls"].append(("invoices", kwargs))
        return page(captured["invoices"], captured["invoice_total"])

    def fake_passes(client: Any, **kwargs: Any) -> Page:
        captured["calls"].append(("passes", kwargs))
        return page(captured["passes"])

    def fake_complaints(client: Any, **kwargs: Any) -> Page:
        captured["calls"].append(("complaints", kwargs))
        return page(captured["complaints"], captured["complaint_total"])

    def fake_notices(client: Any, **kwargs: Any) -> Page:
        captured["calls"].append(("notices", kwargs))
        return page(captured["notices"])

    def fake_feed(client: Any, **kwargs: Any) -> NotificationFeed:
        captured["calls"].append(("feed", kwargs))
        return NotificationFeed(
            items=captured["activity"],
            total=len(captured["activity"]),
            page=1,
            page_size=5,
            has_more=False,
            unread=captured["unread"],
        )

    monkeypatch.setattr(resident_money_service, "list_invoices", fake_invoices)
    monkeypatch.setattr(resident_visitor_passes_service, "list_mine", fake_passes)
    monkeypatch.setattr(resident_complaints_service, "list_mine", fake_complaints)
    monkeypatch.setattr(resident_home_service, "list_notices", fake_notices)
    monkeypatch.setattr(notifications_service, "list_feed", fake_feed)
    return captured


def sent(captured: dict, name: str) -> dict[str, Any]:
    matches = [kwargs for call, kwargs in captured["calls"] if call == name]
    assert len(matches) == 1, f"expected one {name} call, saw {len(matches)}"
    return matches[0]


# ---------------------------------------------------------------------------
# The guards
# ---------------------------------------------------------------------------


def test_the_snapshot_requires_a_session(api_client: TestClient) -> None:
    assert api_client.get(SNAPSHOT).status_code == 401


def test_staff_get_their_own_home_too(
    admin_api_client: TestClient, parts: dict
) -> None:
    """No role guard. An admin who lives in the community owes maintenance and
    receives visitors like anybody else, and what comes back is theirs."""
    assert admin_api_client.get(SNAPSHOT).status_code == 200


def test_tenancy_comes_from_the_membership_and_nowhere_else(
    resident_api_client: TestClient, parts: dict
) -> None:
    """§5.2. The endpoint takes no parameters, so there is nothing a caller could
    send that would widen what comes back -- and a query string that looks like
    one is ignored rather than honoured."""
    resident_api_client.get(f"{SNAPSHOT}?communityId=somebody-elses")

    assert sent(parts, "invoices")["community_id"] == "community-id"
    assert sent(parts, "passes")["membership_id"] == "resident-membership-id"


# ---------------------------------------------------------------------------
# Dues
# ---------------------------------------------------------------------------


def test_only_unpaid_bills_are_scanned(
    resident_api_client: TestClient, parts: dict
) -> None:
    assert resident_api_client.get(SNAPSHOT).status_code == 200
    assert sent(parts, "invoices")["view"] == "unpaid"


def test_the_outstanding_total_is_the_sum_of_what_is_owed(
    resident_api_client: TestClient, parts: dict
) -> None:
    parts["invoices"] = [
        invoice(id="a", outstanding_amount="4250.00"),
        invoice(
            id="b",
            title="Water",
            invoice_type="utility",
            outstanding_amount="75.50",
        ),
    ]

    dues = resident_api_client.get(SNAPSHOT).json()["dues"]

    assert dues["outstandingTotal"] == "4325.50"
    assert dues["unpaidCount"] == 2


def test_the_maintenance_bill_is_the_one_offered(
    resident_api_client: TestClient, parts: dict
) -> None:
    """`DashboardHome.jsx` looks for it by name: it is the recurring bill a
    resident opens the app to settle."""
    parts["invoices"] = [
        invoice(id="water", title="Water charges", invoice_type="utility"),
        invoice(id="maint", title="August maintenance"),
    ]

    dues = resident_api_client.get(SNAPSHOT).json()["dues"]

    assert dues["primaryInvoice"]["id"] == "maint"


def test_without_a_maintenance_bill_the_oldest_is_offered(
    resident_api_client: TestClient, parts: dict
) -> None:
    """Newest-first, so the last row is the oldest. Offering the newest would
    quietly hide an overdue bill behind a fresh one."""
    parts["invoices"] = [
        invoice(id="new", title="Water charges", invoice_type="utility"),
        invoice(id="old", title="Clubhouse damage", invoice_type="penalty"),
    ]

    dues = resident_api_client.get(SNAPSHOT).json()["dues"]

    assert dues["primaryInvoice"]["id"] == "old"


def test_an_unpayable_bill_is_never_offered(
    resident_api_client: TestClient, parts: dict
) -> None:
    """The home screen's Pay button and the Payments page's Pay button are drawn
    from one column, so a bill the write path would refuse is never put behind
    one."""
    parts["invoices"] = [invoice(is_payable=False)]

    dues = resident_api_client.get(SNAPSHOT).json()["dues"]

    assert dues["primaryInvoice"] is None


def test_a_total_that_could_not_be_summed_in_full_says_so(
    resident_api_client: TestClient, parts: dict
) -> None:
    """A number that is quietly too small is worse than a number with a caveat:
    the resident pays what they are shown and believes they are square."""
    parts["invoice_total"] = 400

    dues = resident_api_client.get(SNAPSHOT).json()["dues"]

    assert dues["isPartialTotal"] is True
    assert dues["unpaidCount"] == 400


def test_a_resident_with_nothing_owing_gets_zero_not_null(
    resident_api_client: TestClient, parts: dict
) -> None:
    """A screen that renders `null.toLocaleString()` is a screen that crashes."""
    parts["invoices"] = []

    dues = resident_api_client.get(SNAPSHOT).json()["dues"]

    assert dues["outstandingTotal"] == "0"
    assert dues["primaryInvoice"] is None
    assert dues["isPartialTotal"] is False


# ---------------------------------------------------------------------------
# Visitors
# ---------------------------------------------------------------------------


def test_the_counts_are_guests_and_not_passes(
    resident_api_client: TestClient, parts: dict
) -> None:
    """One pass for a party of twelve is twelve people at the gate. A card
    reading "1" in front of a resident expecting a dozen has misunderstood the
    question -- and `DashboardHome.jsx` reduces over `guestCount` for exactly
    this reason."""
    parts["passes"] = [visitor_pass(guest_count=12)]

    visitors = resident_api_client.get(SNAPSHOT).json()["visitors"]

    assert visitors["expectedGuests"] == 12


def test_approved_and_expected_are_counted_together(
    resident_api_client: TestClient, parts: dict
) -> None:
    """To the resident they are one thing: a guest who has not arrived yet."""
    parts["passes"] = [
        visitor_pass(id="a", status="Expected", guest_count=2),
        visitor_pass(id="b", status="Approved", guest_count=3),
    ]

    visitors = resident_api_client.get(SNAPSHOT).json()["visitors"]

    assert visitors["expectedGuests"] == 5


def test_a_guest_already_inside_is_not_still_expected(
    resident_api_client: TestClient, parts: dict
) -> None:
    parts["passes"] = [
        visitor_pass(id="a", status="Expected", guest_count=2),
        visitor_pass(id="b", status="Checked In", guest_count=4),
    ]

    visitors = resident_api_client.get(SNAPSHOT).json()["visitors"]

    assert visitors["expectedGuests"] == 2
    assert visitors["checkedInGuests"] == 4


def test_passes_awaiting_an_answer_come_back_whole(
    resident_api_client: TestClient, parts: dict
) -> None:
    """The home screen approves and rejects from the card without navigating, so
    a title and a count would not be enough to act on."""
    parts["passes"] = [visitor_pass(id="waiting", status="Pending Approval")]

    visitors = resident_api_client.get(SNAPSHOT).json()["visitors"]

    assert visitors["pendingCount"] == 1
    assert visitors["pendingApproval"][0]["id"] == "waiting"


def test_only_three_pending_passes_are_carried_but_all_are_counted(
    resident_api_client: TestClient, parts: dict
) -> None:
    """The screen renders three. The count is what tells a resident there are
    more, which is the number they act on."""
    parts["passes"] = [
        visitor_pass(id=f"p{n}", status="Pending Approval") for n in range(5)
    ]

    visitors = resident_api_client.get(SNAPSHOT).json()["visitors"]

    assert len(visitors["pendingApproval"]) == 3
    assert visitors["pendingCount"] == 5


def test_a_visitor_awaiting_approval_is_not_counted_as_expected(
    resident_api_client: TestClient, parts: dict
) -> None:
    """They are at the gate and have not been let in. Counting them among the
    expected would tell a resident somebody is on their way when in fact
    somebody is waiting on them."""
    parts["passes"] = [visitor_pass(status="Pending Approval", guest_count=3)]

    visitors = resident_api_client.get(SNAPSHOT).json()["visitors"]

    assert visitors["expectedGuests"] == 0
    assert visitors["checkedInGuests"] == 0


def test_only_current_passes_are_read(
    resident_api_client: TestClient, parts: dict
) -> None:
    """History is a tab, not a home-screen count. A guest who left last month is
    not somebody the resident needs to know about now."""
    resident_api_client.get(SNAPSHOT)

    assert sent(parts, "passes")["view"] == "current"


# ---------------------------------------------------------------------------
# Complaints, notices, activity
# ---------------------------------------------------------------------------


def test_the_complaint_total_is_the_callers_own_count(
    resident_api_client: TestClient, parts: dict
) -> None:
    body = resident_api_client.get(SNAPSHOT).json()

    assert body["complaints"]["total"] == 3
    assert body["complaints"]["recent"][0]["id"] == "complaint-id"


def test_notices_are_the_communitys_and_the_rest_is_the_callers(
    resident_api_client: TestClient, parts: dict
) -> None:
    """The one part of this payload that is not personal. A notice board is a
    community fact, and it is scoped by community rather than by membership."""
    resident_api_client.get(SNAPSHOT)

    assert sent(parts, "notices")["community_id"] == "community-id"


def test_the_badge_counts_the_feed_and_not_the_page(
    resident_api_client: TestClient, parts: dict
) -> None:
    """A badge drawn from the returned events would read "1" for a resident with
    seven unread notifications, and would be wrong the moment anybody scrolled."""
    parts["activity"] = [event()]
    parts["unread"] = 7

    body = resident_api_client.get(SNAPSHOT).json()

    assert body["unreadNotifications"] == 7
    assert len(body["activity"]) == 1


def test_the_activity_strip_is_the_notification_feed(
    resident_api_client: TestClient, parts: dict
) -> None:
    """Not `member_activity`, which §5.7 reserved for it and which nothing in
    this project writes. §5.8 already made `notifications` the durable record of
    every user-visible event; a second log would be the pair of disagreeing feeds
    §5.7 set out to prevent."""
    body = resident_api_client.get(SNAPSHOT).json()

    assert body["activity"][0]["kind"] == "visitor.approval_requested"
    assert body["activity"][0]["url"] == "/resident/visitors"


def test_the_payload_says_when_it_was_assembled(
    resident_api_client: TestClient, parts: dict
) -> None:
    """Six reads in sequence, not one transaction, so this is the only timestamp
    the response can honestly claim."""
    assert resident_api_client.get(SNAPSHOT).json()["generatedAt"]


def test_an_empty_community_is_an_empty_snapshot_not_an_error(
    resident_api_client: TestClient, parts: dict
) -> None:
    """A resident who moved in this morning has nothing anywhere, and every list
    is empty rather than absent -- a client that has to test for both is a client
    that will crash on one."""
    parts.update(
        invoices=[], passes=[], complaints=[], complaint_total=0, notices=[],
        activity=[], unread=0,
    )

    body = resident_api_client.get(SNAPSHOT).json()

    assert body["notices"] == []
    assert body["activity"] == []
    assert body["visitors"]["pendingApproval"] == []
    assert body["complaints"]["recent"] == []


# ---------------------------------------------------------------------------
# The projection, directly
# ---------------------------------------------------------------------------


def test_a_pass_with_no_guest_count_still_counts_one_person(
    resident_api_client: TestClient, parts: dict
) -> None:
    """`guestCount` of zero is a data problem, not an empty party. Counting it as
    nobody would make a visitor vanish from the card drawn to announce them."""
    parts["passes"] = [visitor_pass(guest_count=0)]

    visitors = resident_api_client.get(SNAPSHOT).json()["visitors"]

    assert visitors["expectedGuests"] == 1


def test_no_payable_bill_means_nothing_to_offer() -> None:
    assert service._primary_invoice([]) is None
