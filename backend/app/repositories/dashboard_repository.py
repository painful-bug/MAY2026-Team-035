"""Tenant-scoped dashboard reads and the SSE outbox.

This module deliberately presents one small, browser-safe projection even while
the hosted project is being migrated from its older normalized schema to the
clean baseline.  The service layer owns permission checks; every query here is
also constrained by the resolved community id.
"""

# SQL projection strings must stay on one line for PostgREST.
# ruff: noqa: E501

from __future__ import annotations

import re
from concurrent.futures import Executor
from functools import lru_cache
from typing import Any

from supabase import Client


@lru_cache(maxsize=1)
def schema_generation() -> str:
    """Detect the deployed normalized schema once per backend process."""
    # The legacy schema has visitor_access_requests; the clean baseline has
    # visitor_requests.  Keeping this detection here avoids leaking schema
    # compatibility into API handlers or the browser.
    from app.core.supabase_client import get_service_client

    try:
        get_service_client().table("visitor_access_requests").select("id").limit(1).execute()
        return "legacy"
    except Exception:  # noqa: BLE001 - a missing relation is the feature test
        return "baseline"


def list_memberships(client: Client, community_id: str) -> list[dict[str, Any]]:
    return (
        client.table("community_memberships")
        .select(
            "id,profile_id,role,status,department_id,"
            "profiles(full_name,display_email,phone_e164),"
            "unit_residencies!unit_residencies_membership_id_fkey("
            "unit_id,units(unit_code,buildings(name)))"
        )
        .eq("community_id", community_id)
        .is_("ended_at", None)
        .order("created_at")
        .execute()
        .data
        or []
    )


def list_notices(client: Client, community_id: str) -> list[dict[str, Any]]:
    query = (
        client.table("notices")
        .select("id,title,body,published_at,created_at,updated_at")
        .eq("community_id", community_id)
        .order("published_at", desc=True)
        .limit(100)
    )
    return query.execute().data or []


def list_complaints(client: Client, community_id: str, *, legacy: bool) -> list[dict[str, Any]]:
    # `raised_via` is on both branches because it is not a schema-generation
    # difference: `20260820150000_admin_raised_complaints.sql` adds it to
    # `complaints` itself, so a project that has applied that file has it whether
    # its complaint tables are the legacy shape or the baseline's. **The snapshot
    # therefore requires that migration**, the same way the resident list does --
    # see the service's `_complaints` for what the column decides.
    columns = (
        "id,category,title,description,status,priority,progress_percent,raised_by_membership_id,raised_via,created_at,updated_at,resolved_at,complaint_events(id,event_type,note,new_status,created_at)"
        if legacy
        else "id,category,title,description,status,raised_by_membership_id,raised_via,created_at,updated_at,resolved_at,complaint_events(id,event_type,payload,created_at)"
    )
    return (
        client.table("complaints").select(columns).eq("community_id", community_id)
        .order("updated_at", desc=True).limit(200).execute().data
        or []
    )


def list_visitors(client: Client, community_id: str) -> list[dict[str, Any]]:
    """Visitor requests, newest first -- from the table residents write.

    **Not schema-generation dependent, and the branch that said it was is
    gone.** Until 2026-08-23 the legacy arm read `visitor_access_requests`,
    the pre-baseline table. Residents have not written that table since
    `0032_visitor_passes.sql` moved the visitor flow onto `visitor_requests`,
    so on the hosted project the admin dashboard was reading the empty half of
    a split brain: the owner's probe of that date counted
    `visitor_access_requests` = 0 rows against `visitor_requests` = 3, and the
    three real requests were invisible to every admin (runbook §22, probes (g)
    and (h); the SSE half is `20260823160000_visitor_requests_sse.sql`).

    One source now, because there is only one true one. `purpose` is selected:
    `0032` gave `visitor_requests` that column, the resident fills it in, and
    the projection that dropped it made every card on the dashboard read
    "Guest".
    """
    columns = "id,visitor_name,visitor_phone_e164,purpose,status,requested_by_membership_id,valid_from,valid_until,checked_in_at,checked_out_at,created_at,updated_at,visitor_events(event_type,created_at)"
    return (
        client.table("visitor_requests").select(columns).eq("community_id", community_id)
        .order("created_at", desc=True).limit(200).execute().data
        or []
    )


def list_amenities(client: Client, community_id: str, *, legacy: bool) -> list[dict[str, Any]]:
    # `description`, `image_url`, `opening_time` and `closing_time` are real
    # columns on the legacy arm too -- `0023` added them (lines 49-89). Leaving
    # them out of the select is what made the catalogue unable to show a photo
    # or an opening hour (issue #48 D2).
    columns = (
        "id,name,description,category,location,image_url,opening_time,closing_time,capacity,booking_mode,approval_required,hourly_rate,status,created_at,updated_at"
        if legacy
        else "id,name,description,booking_rules,is_active,created_at,updated_at,amenity_operating_hours(weekday,opens_at,closes_at)"
    )
    return (
        client.table("amenities").select(columns).eq("community_id", community_id)
        .order("name").execute().data
        or []
    )


def list_bookings(client: Client, community_id: str) -> list[dict[str, Any]]:
    """Amenity bookings, newest first -- from the table residents write.

    The other half of the split brain `list_visitors` documents. The legacy arm
    read `legacy_amenity_booking_series` / `legacy_amenity_booking_occurrences`,
    the names `0023_amenities_on_baseline.sql` parked the pre-baseline tables
    under when it claimed the booking namespace for `amenity_bookings`. `0023`
    also moved the booking RPCs onto `amenity_bookings`, so nothing has written
    a series row since -- hosted holds 0 of them -- and the two tables were
    still what the dashboard asked for. The `legacy` parameter is gone with the
    branch: there was never a second source, only a second name for an empty
    one.
    """
    return (
        client.table("amenity_bookings")
        .select("id,amenity_id,booked_by_membership_id,starts_at,ends_at,status,created_at,updated_at")
        .eq("community_id", community_id).order("starts_at", desc=True).limit(500)
        .execute().data
        or []
    )


def weekly_new_counts(
    client: Client,
    community_id: str,
    *,
    since_iso: str,
    executor: Executor | None = None,
) -> dict[str, int]:
    """Rows created since `since_iso`, one integer per dashboard trend chip.

    Four head-only counts (`count="exact", head=True`): PostgREST returns the
    `Content-Range` total and no rows, so this costs four index scans rather
    than four page fetches. Keys are the wire names `DashboardSnapshot.weeklyNew`
    promises the frontend.

    With an `executor` the four counts are submitted to it and run
    concurrently (the snapshot passes its own bounded pool, so the counts join
    the batch instead of adding four round trips after it); without one they
    run in sequence. Either way the call returns the completed dict, and a
    failing count raises its own exception -- `Future.result()` re-raises.
    """

    def _count(table: str, extra: dict[str, str] | None = None) -> int:
        query = (
            client.table(table)
            .select("id", count="exact", head=True)
            .eq("community_id", community_id)
            .gte("created_at", since_iso)
        )
        for column, value in (extra or {}).items():
            query = query.eq(column, value)
        return int(query.execute().count or 0)

    jobs: dict[str, tuple[str, dict[str, str] | None]] = {
        # Memberships are soft-ended, so "started in the window" is a row
        # created in the window that is still an active resident membership.
        "residents": (
            "community_memberships", {"role": "resident", "status": "active"}
        ),
        "complaints": ("complaints", None),
        # The two tables residents write, on every schema generation -- see
        # `list_visitors` and `list_bookings`. Counting the pre-baseline names
        # here made both chips read `+0 this week` on a hosted project where
        # requests were arriving.
        "visitorRequests": ("visitor_requests", None),
        "bookings": ("amenity_bookings", None),
    }
    if executor is not None:
        futures = {
            key: executor.submit(_count, table, extra)
            for key, (table, extra) in jobs.items()
        }
        return {key: future.result() for key, future in futures.items()}
    return {key: _count(table, extra) for key, (table, extra) in jobs.items()}


def list_invoices(client: Client, community_id: str, *, legacy: bool) -> list[dict[str, Any]]:
    columns = (
        "id,liable_unit_id,status,due_at,total_amount,invoice_number,invoice_type,created_at,updated_at,invoice_line_items(description,total_amount)"
        if legacy
        else "id,membership_id,status,due_at,total_amount,created_at,updated_at,invoice_line_items(description,amount)"
    )
    return (
        client.table("invoices").select(columns).eq("community_id", community_id)
        .order("due_at", desc=True).limit(300).execute().data
        or []
    )


def list_payments(
    client: Client,
    community_id: str,
    *,
    legacy: bool,
    invoice_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    columns = "id,invoice_id,amount,status,method,paid_at,created_at" if legacy else "id,invoice_id,amount,status,provider,provider_reference,created_at"
    query = client.table("payments").select(columns)
    if legacy:
        if not invoice_ids:
            return []
        query = query.in_("invoice_id", invoice_ids)
    else:
        query = query.eq("community_id", community_id)
    return query.order("created_at", desc=True).limit(300).execute().data or []


def list_departments(client: Client, community_id: str) -> list[dict[str, Any]]:
    return (
        client.table("departments")
        .select("id,name,description,is_active,manager_membership_id,created_at,updated_at")
        .eq("community_id", community_id).order("name").execute().data
        or []
    )


def list_activity(client: Client, community_id: str) -> list[dict[str, Any]]:
    try:
        return (
            client.table("audit_events").select("id,action,created_at")
            .eq("community_id", community_id).order("created_at", desc=True).limit(50)
            .execute().data
            or []
        )
    except Exception:  # noqa: BLE001 - activity is non-critical dashboard context
        return []


def create_amenity(
    client: Client, *, community_id: str, payload: dict[str, Any], legacy: bool
) -> dict[str, Any]:
    if legacy:
        row = {
            "community_id": community_id,
            "name": payload["name"],
            # Written at last: the column has existed since `0023` and the form
            # has always collected a description, but the legacy arm dropped it
            # between the two (issue #48 D2).
            "description": payload["description"] or None,
            "category": payload["category"],
            "location": payload["location"] or None,
            "image_url": payload.get("image"),
            "opening_time": payload.get("opening_time"),
            "closing_time": payload.get("closing_time"),
            "capacity": payload["capacity"],
            "booking_mode": payload["booking_mode"].lower(),
            "approval_required": payload["approval_required"],
            "hourly_rate": payload["hourly_rate"],
            "status": "active" if payload["is_active"] else "inactive",
        }
    else:
        row = {
            "community_id": community_id,
            "name": payload["name"],
            "description": payload["description"],
            "is_active": payload["is_active"],
            # The image and the hours ride in the jsonb on this arm: it has no
            # `image_url`/`opening_time` columns and adding them would be a
            # migration. Dead in every real environment -- see `list_amenities`.
            "booking_rules": {
                "category": payload["category"],
                "location": payload["location"],
                "capacity": payload["capacity"],
                "bookingMode": payload["booking_mode"],
                "requireApproval": payload["approval_required"],
                "hourlyRate": payload["hourly_rate"],
                "image": payload.get("image"),
                "openingTime": payload.get("opening_time"),
                "closingTime": payload.get("closing_time"),
            },
        }
    return client.table("amenities").insert(row).execute().data[0]


def update_amenity(
    client: Client, *, amenity_id: str, community_id: str, payload: dict[str, Any], legacy: bool
) -> dict[str, Any] | None:
    if legacy:
        row = {
            "name": payload["name"], "description": payload["description"] or None,
            "category": payload["category"],
            "location": payload["location"] or None, "capacity": payload["capacity"],
            "image_url": payload.get("image"),
            "opening_time": payload.get("opening_time"),
            "closing_time": payload.get("closing_time"),
            "booking_mode": payload["booking_mode"].lower(),
            "approval_required": payload["approval_required"], "hourly_rate": payload["hourly_rate"],
            "status": "active" if payload["is_active"] else "inactive",
        }
    else:
        row = {
            "name": payload["name"], "description": payload["description"],
            "is_active": payload["is_active"],
            "booking_rules": {
                "category": payload["category"], "location": payload["location"],
                "capacity": payload["capacity"], "bookingMode": payload["booking_mode"],
                "requireApproval": payload["approval_required"], "hourlyRate": payload["hourly_rate"],
                "image": payload.get("image"), "openingTime": payload.get("opening_time"),
                "closingTime": payload.get("closing_time"),
            },
        }
    rows = (
        client.table("amenities").update(row).eq("id", amenity_id)
        .eq("community_id", community_id).select("id").execute().data
        or []
    )
    return rows[0] if rows else None


def delete_amenity(client: Client, *, amenity_id: str, community_id: str) -> bool:
    rows = (
        client.table("amenities").delete().eq("id", amenity_id)
        .eq("community_id", community_id).select("id").execute().data
        or []
    )
    return bool(rows)


def publish(
    client: Client,
    *,
    community_id: str,
    topic: str,
    payload: dict[str, Any] | None = None,
    audience_roles: list[str] | None = None,
) -> None:
    """Write one outbox row.

    `audience_roles` is the only audience this path offers, and omitting it
    means community-wide. Member-addressed events are not published from Python
    at all -- they come from the trigger on `notifications`, so that live
    delivery is a property of writing a notification rather than a step someone
    can forget (see the resident design 5.10).
    """
    row: dict[str, Any] = {
        "community_id": community_id,
        "topic": topic,
        "payload": payload or {},
    }
    if audience_roles:
        row["audience"] = "role"
        row["audience_roles"] = audience_roles
    client.table("sse_events").insert(row).execute()


_EVENT_COLUMNS = "id,topic,payload,audience,audience_roles,recipient_membership_id"

# PostgREST filter values are not parameterised, so anything interpolated into
# one is checked against a whitelist first. Both values come from a membership
# row the caller already resolved out of Postgres, which is why these patterns
# can be this narrow: `membership_role` is an enum of lowercase words and the
# id is a uuid primary key. A value that fails is not escaped, it is dropped --
# the filter widens, and `_Subscriber.accepts` still decides.
_ROLE_RE = re.compile(r"^[a-z_]{1,32}$")
_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


def _audience_filter(membership_id: str | None, role: str | None) -> str:
    """The `or=` narrowing clause for one subscriber's audience (`0028`)."""
    clauses = ["audience.eq.community"]
    if role and _ROLE_RE.match(role):
        clauses.append(f"and(audience.eq.role,audience_roles.cs.{{{role}}})")
    if membership_id and _UUID_RE.match(membership_id):
        clauses.append(
            f"and(audience.eq.member,recipient_membership_id.eq.{membership_id})"
        )
    return ",".join(clauses)


def read_events(
    client: Client,
    *,
    community_id: str,
    after_id: int,
    membership_id: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    """One subscriber's missed events, for the reconnect backfill.

    Narrowed by audience in Postgres rather than after the fact, because the
    100-row cap is applied by the query: a burst of `{admin,manager}` refresh
    rows must not be able to fill the page and push a resident's own events off
    the end of it. `app.core.realtime` re-checks every row it gets back.
    """
    return (
        client.table("sse_events").select(_EVENT_COLUMNS)
        .eq("community_id", community_id).gt("id", after_id)
        .or_(_audience_filter(membership_id, role))
        .order("id").limit(100)
        .execute().data
        or []
    )


def read_events_since(client: Client, *, after_id: int, limit: int = 500) -> list[dict[str, Any]]:
    """Every community's events past `after_id`, for the shared SSE poller.

    Deliberately not community-scoped, and deliberately not audience-scoped
    either: one process-wide poller reads the outbox once per tick and
    `app.core.realtime` routes rows to subscribers by `community_id` and then
    by audience, so the query cost stays flat as viewers are added. Filtering
    here would mean one query per distinct audience, which is the per-viewer
    cost this poller exists to remove.
    """
    return (
        client.table("sse_events").select("community_id," + _EVENT_COLUMNS)
        .gt("id", after_id).order("id").limit(limit)
        .execute().data
        or []
    )


def latest_event_id(client: Client) -> int:
    """High-water mark, used to start a stream at 'now' rather than replay."""
    rows = (
        client.table("sse_events").select("id").order("id", desc=True).limit(1)
        .execute().data
        or []
    )
    return int(rows[0]["id"]) if rows else 0


def list_pending_access_requests(client: Client, community_id: str) -> list[dict[str, Any]]:
    """Pending join requests, newest first -- the admin sidebar badge's source."""
    return (
        client.table("pending_access_request_overview")
        .select(
            "id,applicant_name,applicant_email,applicant_phone_e164,"
            "requested_relationship,status,created_at,requested_unit_code,community_name"
        )
        .eq("community_id", community_id).order("created_at", desc=True).limit(200)
        .execute().data
        or []
    )
