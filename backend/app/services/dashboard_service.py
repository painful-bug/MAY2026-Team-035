"""Browser-safe dashboard projections backed by community database records."""

# The compact UI DTO mappings intentionally keep related keys together.
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import AsyncIterator
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
    result = []
    for row in rows:
        raised_by = users.get(row["raised_by_membership_id"], {})
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
            "userId": raised_by.get("id"), "flat": raised_by.get("flat", "—"),
            "date": _iso_date(row.get("created_at")), "createdAt": row.get("created_at"),
            "updatedAt": row.get("updated_at"), "resolvedAt": row.get("resolved_at"), "comments": comments,
            "history": events,
        })
    return result


def _visitors(rows: list[dict[str, Any]], users: dict[str, dict[str, Any]], *, legacy: bool) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        requester = users.get(row.get("requested_by_membership_id"), {})
        starts_at = row.get("expected_from") if legacy else row.get("valid_from")
        ends_at = row.get("expected_until") if legacy else row.get("valid_until")
        result.append({
            "id": row["id"], "name": row.get("visitor_name") or "Visitor", "phone": row.get("visitor_phone_e164") or "",
            "purpose": row.get("purpose") or "Guest", "status": _VISITOR_LABELS.get(str(row.get("status")), "Expected"),
            "userId": requester.get("id"), "requestedBy": requester.get("name", "Resident"),
            "flat": requester.get("flat", "—"), "tower": requester.get("tower", "—"),
            "date": _iso_date(starts_at or row.get("created_at")), "expectedDate": _iso_date(starts_at),
            "expectedTime": _time(starts_at), "eta": _time(starts_at), "validUntil": ends_at,
            "checkedInAt": row.get("checked_in_at"), "checkedOutAt": row.get("checked_out_at"),
            # The legacy embed key follows the hosted table name: `0032` renamed
            # the old event log to `legacy_visitor_events` when the baseline
            # claimed `visitor_events` for `visitor_requests`.
            "createdAt": row.get("created_at"),
            "events": (row.get("legacy_visitor_events") if legacy else row.get("visitor_events")) or [],
        })
    return result


def _amenities(rows: list[dict[str, Any]], *, legacy: bool) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if legacy:
            result.append({
                "id": row["id"], "name": row["name"], "description": row.get("category") or "",
                "category": row.get("category") or "Utility", "location": row.get("location") or "",
                "capacity": row.get("capacity"), "bookingMode": str(row.get("booking_mode") or "Exclusive").title(),
                "requireApproval": bool(row.get("approval_required")), "hourlyRate": row.get("hourly_rate") or 0,
                "status": str(row.get("status") or "Active").title(), "isActive": str(row.get("status", "active")).lower() == "active",
                "createdAt": row.get("created_at"), "updatedAt": row.get("updated_at"),
            })
        else:
            rules = row.get("booking_rules") or {}
            hours = row.get("amenity_operating_hours") or []
            first_hours = hours[0] if hours else {}
            result.append({
                "id": row["id"], "name": row["name"], "description": row.get("description") or "",
                "category": rules.get("category", "Utility"), "capacity": rules.get("capacity"),
                "bookingMode": rules.get("bookingMode", "Exclusive"), "requireApproval": bool(rules.get("requireApproval")),
                "openingTime": str(first_hours.get("opens_at") or ""), "closingTime": str(first_hours.get("closes_at") or ""),
                "status": "Active" if row.get("is_active") else "Inactive", "isActive": bool(row.get("is_active")),
                "createdAt": row.get("created_at"), "updatedAt": row.get("updated_at"),
            })
    return result


def _bookings(rows: list[dict[str, Any]], users: dict[str, dict[str, Any]], *, legacy: bool) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        series = row.get("series") or {}
        member_id = series.get("booked_by_membership_id") if legacy else row.get("booked_by_membership_id")
        resident = users.get(member_id, {})
        starts_at, ends_at = row.get("starts_at"), row.get("ends_at")
        result.append({
            "id": row["id"], "bookingGroupId": row.get("booking_series_id") if legacy else row["id"],
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
            "id": invoice["id"], "title": invoice.get("invoice_number") or invoice.get("invoice_type") or "Community invoice",
            "amount": float(invoice.get("total_amount") or 0), "dueDate": _iso_date(invoice.get("due_at")),
            "status": "Paid" if invoice["id"] in paid_invoice_ids or invoice.get("status") == "paid" else "Unpaid",
            "userId": owner.get("id"), "flat": owner.get("flat", "—"), "tower": owner.get("tower", "—"),
            "isMine": is_own, "billPeriod": "", "createdAt": invoice.get("created_at"),
        })
    return result


def snapshot(membership: MembershipContext) -> DashboardSnapshot:
    client = get_service_client()
    legacy = dashboard_repository.schema_generation() == "legacy"
    member_rows = dashboard_repository.list_memberships(client, membership.community_id)
    users, users_by_membership, _ = _membership_users(member_rows)
    complaints = _complaints(dashboard_repository.list_complaints(client, membership.community_id, legacy=legacy), users_by_membership, legacy=legacy)
    visitors = _visitors(dashboard_repository.list_visitors(client, membership.community_id, legacy=legacy), users_by_membership, legacy=legacy)
    amenities = _amenities(dashboard_repository.list_amenities(client, membership.community_id, legacy=legacy), legacy=legacy)
    bookings = _bookings(dashboard_repository.list_bookings(client, membership.community_id, legacy=legacy), users_by_membership, legacy=legacy)
    invoices = dashboard_repository.list_invoices(
        client, membership.community_id, legacy=legacy
    )
    payment_rows = dashboard_repository.list_payments(
        client,
        membership.community_id,
        legacy=legacy,
        invoice_ids=[row["id"] for row in invoices],
    )
    payments = _payments(
        invoices,
        payment_rows,
        users_by_membership, membership, legacy=legacy,
    )
    notices = [{"id": r["id"], "title": r["title"], "description": r.get("body") or "", "date": _iso_date(r.get("published_at") or r.get("created_at")), "createdAt": r.get("created_at")} for r in dashboard_repository.list_notices(client, membership.community_id)]
    departments = [{"id": r["id"], "name": r["name"], "description": r.get("description") or "", "status": "Active" if r.get("is_active") else "Inactive", "staff": [], "categories": []} for r in dashboard_repository.list_departments(client, membership.community_id)]
    activities = [{"id": r["id"], "text": r.get("action", "Community activity"), "time": r.get("created_at"), "type": "general"} for r in dashboard_repository.list_activity(client, membership.community_id)]
    # Join requests carry other people's name, email and phone, so only an admin
    # gets them. Everyone else gets the empty list the field defaults to.
    pending_requests = (
        dashboard_repository.list_pending_access_requests(client, membership.community_id)
        if membership.role == "admin"
        else []
    )
    # The trend chips: rows created in the trailing 7 days, counted in Postgres
    # (head-only count queries), never derived from the capped lists above.
    weekly_new = dashboard_repository.weekly_new_counts(
        client,
        membership.community_id,
        legacy=legacy,
        since_iso=(datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
    )
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
