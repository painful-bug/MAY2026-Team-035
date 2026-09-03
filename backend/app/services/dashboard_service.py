"""Browser-safe dashboard projections backed by community database records."""

# The compact UI DTO mappings intentionally keep related keys together.
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.exceptions import NotFoundError
from app.core.realtime import hub
from app.core.supabase_client import get_service_client
from app.domain.schemas import DashboardSnapshot, MembershipContext
from app.domain.vocabularies import complaint_status_to_wire
from app.repositories import dashboard_repository

_ROLE_LABELS = {
    "admin": "Admin", "manager": "SecurityManager", "security": "Security",
    "worker": "Worker", "resident": "Resident",
}
_VISITOR_LABELS = {
    "expected": "Expected", "pending_approval": "Pending Approval", "approved": "Approved",
    "denied": "Rejected", "checked_in": "Checked In", "checked_out": "Checked Out",
    "expired": "Expired", "cancelled": "Cancelled",
}
# Moved into `domain/vocabularies.py` when the resident complaint surface needed
# the same map. Two copies of one vocabulary is how the admin and resident views
# of a complaint end up disagreeing about what `closed` is called.


def _iso_date(value: str | None) -> str:
    return value[:10] if value else ""


def _time(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return ""


def _membership_users(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    users: list[dict[str, Any]] = []
    by_membership: dict[str, dict[str, Any]] = {}
    profile_to_membership: dict[str, str] = {}
    for row in rows:
        profile = row.get("profiles") or {}
        residencies = row.get("unit_residencies") or []
        unit = (residencies[0].get("units") or {}) if residencies else {}
        building = unit.get("buildings") or {}
        user = {
            "id": row["profile_id"], "membershipId": row["id"],
            "name": profile.get("full_name") or profile.get("display_email") or "Community member",
            "email": profile.get("display_email") or "", "phone": profile.get("phone_e164") or "",
            "role": _ROLE_LABELS.get(str(row.get("role", "resident")).lower(), "Resident"),
            "status": "Active" if row.get("status") == "active" else str(row.get("status", "Pending")).title(),
            "flat": unit.get("unit_code") or "—", "tower": building.get("name") or "—",
            "apartmentId": unit.get("id") or (residencies[0].get("unit_id") if residencies else None),
            "departmentId": row.get("department_id"),
        }
        users.append(user)
        by_membership[row["id"]] = user
        profile_to_membership[row["profile_id"]] = row["id"]
    return users, by_membership, profile_to_membership


def _complaints(rows: list[dict[str, Any]], users: dict[str, dict[str, Any]], *, legacy: bool) -> list[dict[str, Any]]:
    """The admin queue's complaint rows.

    ``raisedVia`` and the flat it suppresses are one decision, not two. Every
    row's ``flat`` is read from **the raiser's membership**, which was a complete
    description of a complaint for as long as only residents could raise one. It
    stopped being one when the admin portal gained
    ``POST /complaints/admin-raise``: a complaint about the lobby is owned by the
    admin's own membership, so the unchanged projection would print that admin's
    home flat beside it -- a number that is true of the person and false of the
    problem, and false in the direction that sends somebody to the wrong door.

    ``raised_via = 'admin'`` is exactly the set of complaints attached to no
    home, so it is what blanks the flat. ``—`` rather than ``""`` because that is
    already this projection's word for *no unit* -- ``_membership_users`` writes
    it for every member without a residency -- and a second spelling of the same
    absence is how one table ends up rendering two.
    """
    result = []
    for row in rows:
        raised_by = users.get(row["raised_by_membership_id"], {})
        # Defaults to `resident` for a row written before the column existed,
        # which is what every such row is: until `20260820150000` there was no
        # other way to raise a complaint.
        raised_via = str(row.get("raised_via") or "resident")
        events = row.get("complaint_events") or []
        comments = []
        for event in events:
            payload = event.get("payload") or {}
            note = event.get("note") or payload.get("note")
            if note:
                comments.append({"id": event["id"], "author": "Community team", "text": note, "createdAt": event.get("created_at")})
        result.append({
            "id": row["id"], "title": row["title"], "description": row.get("description") or "",
            "category": row.get("category") or "General", "status": complaint_status_to_wire(row.get("status")),
            "progress": int(row.get("progress_percent") or (100 if row.get("status") in {"resolved", "closed"} else 0)),
            "urgency": str(row.get("priority") or "Medium").title(), "raisedBy": raised_by.get("name", "Resident"),
            "userId": raised_by.get("id"), "raisedVia": raised_via,
            "flat": "—" if raised_via == "admin" else raised_by.get("flat", "—"),
            "date": _iso_date(row.get("created_at")), "createdAt": row.get("created_at"),
            "updatedAt": row.get("updated_at"), "resolvedAt": row.get("resolved_at"), "comments": comments,
            "history": events,
        })
    return result


def _visitors(rows: list[dict[str, Any]], users: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Wire shape for one visitor card. Every key below is frozen -- the admin
    and resident screens read them by name.

    The `legacy` parameter is gone because its source table is: both schema
    generations now read `visitor_requests` (see
    `dashboard_repository.list_visitors`), so the pre-baseline column names
    `expected_from` / `expected_until` and the `legacy_visitor_events` embed
    have nothing left to read. `valid_from` / `valid_until` / `visitor_events`
    are the columns of the table residents write.
    """
    result = []
    for row in rows:
        requester = users.get(row.get("requested_by_membership_id"), {})
        starts_at = row.get("valid_from")
        ends_at = row.get("valid_until")
        result.append({
            "id": row["id"], "name": row.get("visitor_name") or "Visitor", "phone": row.get("visitor_phone_e164") or "",
            "purpose": row.get("purpose") or "Guest", "status": _VISITOR_LABELS.get(str(row.get("status")), "Expected"),
            "userId": requester.get("id"), "requestedBy": requester.get("name", "Resident"),
            "flat": requester.get("flat", "—"), "tower": requester.get("tower", "—"),
            "date": _iso_date(starts_at or row.get("created_at")), "expectedDate": _iso_date(starts_at),
            "expectedTime": _time(starts_at), "eta": _time(starts_at), "validUntil": ends_at,
            "checkedInAt": row.get("checked_in_at"), "checkedOutAt": row.get("checked_out_at"),
            "createdAt": row.get("created_at"),
            "events": row.get("visitor_events") or [],
        })
    return result


def _amenities(rows: list[dict[str, Any]], *, legacy: bool) -> list[dict[str, Any]]:
    """Wire shape for the catalogue card. Frozen keys, as `_visitors`.

    `image`, `openingTime` and `closingTime` are on both arms and both read the
    real `amenities` columns `0023` added -- that migration alters the table
    unconditionally, so neither arm is short of them. The non-legacy arm keeps
    `booking_rules` and `amenity_operating_hours` behind them as fallbacks, for
    rows an older build wrote before those columns were reached for.
    `description` on the legacy arm is the real column too -- it used to repeat
    `category`, so every card described itself as "Fitness" (issue #48 D2).
    """
    result = []
    for row in rows:
        if legacy:
            result.append({
                # `description` is the amenity's own column and nothing else.
                # Falling back to `category` is the issue #48 D2 defect itself
                # -- it is what made every card describe itself as "Fitness".
                "id": row["id"], "name": row["name"], "description": row.get("description") or "",
                "category": row.get("category") or "Utility", "location": row.get("location") or "",
                "image": row.get("image_url") or "",
                "capacity": row.get("capacity"), "bookingMode": str(row.get("booking_mode") or "Exclusive").title(),
                "requireApproval": bool(row.get("approval_required")), "hourlyRate": row.get("hourly_rate") or 0,
                "openingTime": str(row.get("opening_time") or ""), "closingTime": str(row.get("closing_time") or ""),
                # `sync_amenity_status` (`0023`) keeps `status` and `is_active`
                # in lockstep, so the real column is read first and the status
                # string is the answer for a row written before that trigger.
                "status": str(row.get("status") or "Active").title(), "isActive": bool(row.get("is_active", str(row.get("status", "active")).lower() == "active")),
                "createdAt": row.get("created_at"), "updatedAt": row.get("updated_at"),
            })
        else:
            rules = row.get("booking_rules") or {}
            hours = row.get("amenity_operating_hours") or []
            first_hours = hours[0] if hours else {}
            result.append({
                "id": row["id"], "name": row["name"], "description": row.get("description") or "",
                # The real columns lead and the jsonb is the fallback: `0023`
                # alters `public.amenities` unconditionally, so this arm has
                # `category`, `image_url` and the hours too -- but a row written
                # by an older build only ever put them in `booking_rules`.
                "category": row.get("category") or rules.get("category", "Utility"),
                "location": row.get("location") or rules.get("location", ""),
                "image": row.get("image_url") or rules.get("image") or "",
                "capacity": row.get("capacity") if row.get("capacity") is not None else rules.get("capacity"),
                "bookingMode": str(row.get("booking_mode") or rules.get("bookingMode", "Exclusive")).title(),
                "requireApproval": bool(row.get("approval_required", rules.get("requireApproval"))),
                # `amenity_operating_hours` stays a source, third: it is a real
                # table on this arm and the per-weekday answer when there is one.
                "openingTime": str(row.get("opening_time") or first_hours.get("opens_at") or rules.get("openingTime") or ""),
                "closingTime": str(row.get("closing_time") or first_hours.get("closes_at") or rules.get("closingTime") or ""),
                "status": "Active" if row.get("is_active") else "Inactive", "isActive": bool(row.get("is_active")),
                "createdAt": row.get("created_at"), "updatedAt": row.get("updated_at"),
            })
    return result


def _bookings(rows: list[dict[str, Any]], users: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Wire shape for one booking row. Frozen keys, as `_visitors`.

    `legacy` is gone with the series tables it read: `amenity_bookings` is one
    row per booking with no series above it, so `bookingGroupId` is the row's
    own id and the booker is on the row. `cancellationReason` stays in the
    payload and stays `None` -- `amenity_bookings` has no such column, the key
    is part of the contract, and a cancelled booking carries its reason in the
    amenity screens' own read rather than here.
    """
    result = []
    for row in rows:
        resident = users.get(row.get("booked_by_membership_id"), {})
        starts_at, ends_at = row.get("starts_at"), row.get("ends_at")
        result.append({
            "id": row["id"], "bookingGroupId": row["id"],
            "amenityId": row["amenity_id"], "residentId": resident.get("id"), "residentName": resident.get("name", "Resident"),
            "residentFlat": resident.get("flat", "—"), "date": _iso_date(starts_at), "startTime": _time(starts_at), "endTime": _time(ends_at),
            "status": str(row.get("status") or "requested").lower(), "state": "booked",
            "cancellationReason": row.get("cancellation_reason"), "createdAt": row.get("created_at"), "updatedAt": row.get("updated_at"),
        })
    return result


def _payments(invoices: list[dict[str, Any]], payments: list[dict[str, Any]], users: dict[str, dict[str, Any]], membership: MembershipContext, *, legacy: bool) -> list[dict[str, Any]]:
    paid_invoice_ids = {p.get("invoice_id") for p in payments if str(p.get("status")) in {"succeeded", "paid"}}
    unit_ids = {
        user.get("apartmentId")
        for user in users.values()
        if user.get("membershipId") == membership.id
    }
    result = []
    for invoice in invoices:
        owner = users.get(invoice.get("membership_id"), {}) if not legacy else {}
        is_own = invoice.get("membership_id") == membership.id if not legacy else invoice.get("liable_unit_id") in unit_ids
        result.append({
            "id": invoice["id"], "title": invoice.get("title") or invoice.get("invoice_number") or invoice.get("invoice_type") or "Community invoice",
            "amount": float(invoice.get("total_amount") or 0), "dueDate": _iso_date(invoice.get("due_at")),
            "status": "Paid" if invoice["id"] in paid_invoice_ids or invoice.get("status") == "paid" else "Unpaid",
            "userId": owner.get("id"), "flat": owner.get("flat", "—"), "tower": owner.get("tower", "—"),
            "isMine": is_own, "billPeriod": "", "createdAt": invoice.get("created_at"),
        })
    return result


def snapshot(membership: MembershipContext) -> DashboardSnapshot:
    """Assemble the snapshot from concurrent repository reads.

    Every read is one synchronous PostgREST round trip, and none depends on
    another's result -- they all key off the community id and the legacy flag,
    both known before the first request -- so sequentially the wall time was
    the *sum* of ~15 network RTTs. The reads now share a bounded thread pool
    and the wall time is roughly the slowest read.

    Sharing the singleton service client across the workers is safe here:
    `client.table()` builds a fresh request builder per call (no per-query
    state lives on the client), the underlying `httpx.Client` is documented
    thread-safe, and the one lazily-initialised attribute (`client.postgrest`)
    is forced on this thread by the `schema_generation()` probe before any
    worker starts. Nothing in this path calls `.auth()` or otherwise mutates
    the shared client.

    Error semantics are unchanged: `Future.result()` re-raises the read's own
    exception, so a failing read still fails the whole snapshot with the same
    exception type -- never a partial payload.
    """
    client = get_service_client()
    legacy = dashboard_repository.schema_generation() == "legacy"
    community_id = membership.community_id

    def _invoices_then_payments() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        # The one genuine dependency: the legacy payments read filters by the
        # invoice ids it just fetched. Chained inside a single task, so the
        # pair costs two round trips in one worker, concurrent with the rest.
        invoices = dashboard_repository.list_invoices(client, community_id, legacy=False)
        payment_rows = dashboard_repository.list_payments(
            client, community_id, legacy=False,
            invoice_ids=[row["id"] for row in invoices],
        )
        return invoices, payment_rows

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="snapshot") as pool:
        member_rows_f = pool.submit(dashboard_repository.list_memberships, client, community_id)
        complaints_f = pool.submit(dashboard_repository.list_complaints, client, community_id, legacy=legacy)
        # Visitors and bookings take no `legacy`: both generations read the
        # tables residents actually write (`visitor_requests`,
        # `amenity_bookings`). Amenities still do -- the two schemas keep that
        # one on the same table under different columns.
        visitors_f = pool.submit(dashboard_repository.list_visitors, client, community_id)
        amenities_f = pool.submit(dashboard_repository.list_amenities, client, community_id, legacy=legacy)
        bookings_f = pool.submit(dashboard_repository.list_bookings, client, community_id)
        money_f = pool.submit(_invoices_then_payments)
        notices_f = pool.submit(dashboard_repository.list_notices, client, community_id)
        departments_f = pool.submit(dashboard_repository.list_departments, client, community_id)
        activities_f = pool.submit(dashboard_repository.list_activity, client, community_id)
        # Join requests carry other people's name, email and phone, so only an
        # admin gets them. Everyone else gets the empty list the field defaults
        # to.
        pending_f = (
            pool.submit(dashboard_repository.list_pending_access_requests, client, community_id)
            if membership.role == "admin"
            else None
        )
        # The trend chips: rows created in the trailing 7 days, counted in
        # Postgres (head-only count queries), never derived from the capped
        # lists above. Handing the pool down folds the four counts into the
        # same concurrent batch; the call returns once they are all in.
        weekly_new = dashboard_repository.weekly_new_counts(
            client,
            community_id,
            since_iso=(datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
            executor=pool,
        )

        member_rows = member_rows_f.result()
        users, users_by_membership, _ = _membership_users(member_rows)
        complaints = _complaints(complaints_f.result(), users_by_membership, legacy=legacy)
        visitors = _visitors(visitors_f.result(), users_by_membership)
        amenities = _amenities(amenities_f.result(), legacy=legacy)
        bookings = _bookings(bookings_f.result(), users_by_membership)
        invoices, payment_rows = money_f.result()
        payments = _payments(
            invoices,
            payment_rows,
            users_by_membership, membership, legacy=False,
        )
        notices = [{"id": r["id"], "title": r["title"], "description": r.get("body") or "", "date": _iso_date(r.get("published_at") or r.get("created_at")), "createdAt": r.get("created_at")} for r in notices_f.result()]
        departments = [{"id": r["id"], "name": r["name"], "description": r.get("description") or "", "status": "Active" if r.get("is_active") else "Inactive", "staff": [], "categories": []} for r in departments_f.result()]
        activities = [{"id": r["id"], "text": r.get("action", "Community activity"), "time": r.get("created_at"), "type": "general"} for r in activities_f.result()]
        pending_requests = pending_f.result() if pending_f is not None else []
    if membership.role == "resident":
        current_profile_id = users_by_membership.get(membership.id, {}).get("id")
        complaints = [row for row in complaints if row.get("userId") == current_profile_id]
        visitors = [row for row in visitors if row.get("userId") == current_profile_id]
        payments = [row for row in payments if row.get("isMine")]
    return DashboardSnapshot(users=users, complaints=complaints, visitors=visitors, amenities=amenities, bookings=bookings, payments=payments, notices=notices, departments=departments, activities=activities, pendingRequests=pending_requests, weeklyNew=weekly_new)


def save_amenity(
    membership: MembershipContext, *, amenity_id: str | None, payload: dict[str, Any]
) -> dict[str, Any]:
    client = get_service_client()
    legacy = dashboard_repository.schema_generation() == "legacy"
    if amenity_id:
        saved = dashboard_repository.update_amenity(
            client, amenity_id=amenity_id, community_id=membership.community_id,
            payload=payload, legacy=legacy,
        )
        if not saved:
            raise NotFoundError("Amenity not found.")
    else:
        saved = dashboard_repository.create_amenity(
            client, community_id=membership.community_id, payload=payload, legacy=legacy
        )
    # Same audience the `0028` triggers now give `dashboard.refresh`: the frame
    # means "re-read the admin snapshot", which is not a thing a resident can
    # do. Left community-wide it would be the one leak the migration missed.
    dashboard_repository.publish(
        client,
        community_id=membership.community_id,
        topic="dashboard.refresh",
        audience_roles=["admin", "manager"],
    )
    return saved


def remove_amenity(membership: MembershipContext, amenity_id: str) -> None:
    if not dashboard_repository.delete_amenity(
        get_service_client(), amenity_id=amenity_id, community_id=membership.community_id
    ):
        raise NotFoundError("Amenity not found.")


async def event_stream(
    membership: MembershipContext, last_event_id: int
) -> AsyncIterator[str]:
    """Yield audience-scoped SSE frames and heartbeat comments.

    Delegates to the process-wide outbox poller in `app.core.realtime`. The
    authorization check is here and only here: a subscriber is bound to the
    community, the membership and the role on its verified membership, so a
    client cannot widen its own stream by replaying someone else's
    `Last-Event-ID`.

    This is the only place the three identity values are read off the
    membership, which is why the hub takes them as explicit arguments rather
    than the whole `MembershipContext` -- `app.core` stays free of the domain
    layer, and the mapping is visible on one line.
    """
    async for frame in hub.subscribe(
        membership.community_id,
        membership_id=membership.id,
        role=membership.role,
        last_event_id=max(last_event_id, 0),
    ):
        yield frame
