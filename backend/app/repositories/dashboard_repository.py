"""Tenant-scoped dashboard reads and the SSE outbox.

This module deliberately presents one small, browser-safe projection even while
the hosted project is being migrated from its older normalized schema to the
clean baseline.  The service layer owns permission checks; every query here is
also constrained by the resolved community id.
"""

# SQL projection strings must stay on one line for PostgREST.
# ruff: noqa: E501

from __future__ import annotations

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
    columns = (
        "id,category,title,description,status,priority,progress_percent,raised_by_membership_id,created_at,updated_at,resolved_at,complaint_events(id,event_type,note,new_status,created_at)"
        if legacy
        else "id,category,title,description,status,raised_by_membership_id,created_at,updated_at,resolved_at,complaint_events(id,event_type,payload,created_at)"
    )
    return (
        client.table("complaints").select(columns).eq("community_id", community_id)
        .order("updated_at", desc=True).limit(200).execute().data
        or []
    )


def list_visitors(client: Client, community_id: str, *, legacy: bool) -> list[dict[str, Any]]:
    if legacy:
        columns = "id,visitor_name,visitor_phone_e164,purpose,status,requested_by_membership_id,unit_id,expected_from,expected_until,checked_in_at,checked_out_at,created_at,updated_at,visitor_events(event_type,note,occurred_at)"
        table = "visitor_access_requests"
    else:
        columns = "id,visitor_name,visitor_phone_e164,status,requested_by_membership_id,valid_from,valid_until,checked_in_at,checked_out_at,created_at,updated_at,visitor_events(event_type,created_at)"
        table = "visitor_requests"
    return (
        client.table(table).select(columns).eq("community_id", community_id)
        .order("created_at", desc=True).limit(200).execute().data
        or []
    )


def list_amenities(client: Client, community_id: str, *, legacy: bool) -> list[dict[str, Any]]:
    columns = (
        "id,name,category,location,capacity,booking_mode,approval_required,hourly_rate,status,created_at,updated_at"
        if legacy
        else "id,name,description,booking_rules,is_active,created_at,updated_at,amenity_operating_hours(weekday,opens_at,closes_at)"
    )
    return (
        client.table("amenities").select(columns).eq("community_id", community_id)
        .order("name").execute().data
        or []
    )


def list_bookings(client: Client, community_id: str, *, legacy: bool) -> list[dict[str, Any]]:
    if legacy:
        series = (
            client.table("amenity_booking_series")
            .select("id,amenity_id,booked_by_membership_id,status")
            .eq("community_id", community_id).execute().data
            or []
        )
        series_by_id = {row["id"]: row for row in series}
        rows = (
            client.table("amenity_booking_occurrences")
            .select("id,booking_series_id,amenity_id,starts_at,ends_at,status,cancellation_reason,created_at,updated_at")
            .order("starts_at", desc=True).limit(500).execute().data
            or []
        )
        return [
            {**row, "series": series_by_id[row["booking_series_id"]]}
            for row in rows if row.get("booking_series_id") in series_by_id
        ]
    return (
        client.table("amenity_bookings")
        .select("id,amenity_id,booked_by_membership_id,starts_at,ends_at,status,created_at,updated_at")
        .eq("community_id", community_id).order("starts_at", desc=True).limit(500)
        .execute().data
        or []
    )


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
            "category": payload["category"],
            "location": payload["location"] or None,
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
            "booking_rules": {
                "category": payload["category"],
                "location": payload["location"],
                "capacity": payload["capacity"],
                "bookingMode": payload["booking_mode"],
                "requireApproval": payload["approval_required"],
                "hourlyRate": payload["hourly_rate"],
            },
        }
    return client.table("amenities").insert(row).execute().data[0]


def update_amenity(
    client: Client, *, amenity_id: str, community_id: str, payload: dict[str, Any], legacy: bool
) -> dict[str, Any] | None:
    if legacy:
        row = {
            "name": payload["name"], "category": payload["category"],
            "location": payload["location"] or None, "capacity": payload["capacity"],
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


def publish(client: Client, *, community_id: str, topic: str, payload: dict[str, Any] | None = None) -> None:
    client.table("sse_events").insert(
        {"community_id": community_id, "topic": topic, "payload": payload or {}}
    ).execute()


def read_events(client: Client, *, community_id: str, after_id: int) -> list[dict[str, Any]]:
    return (
        client.table("sse_events").select("id,topic,payload,created_at")
        .eq("community_id", community_id).gt("id", after_id).order("id").limit(100)
        .execute().data
        or []
    )
