"""Database access for resident access-request workflows."""

from __future__ import annotations

from supabase import Client

_TABLE = "access_requests"
_SELECT = (
    "id,community_id,requested_unit_id,requested_building_text,requested_unit_text,"
    "requested_relationship,status,"
    "applicant_name,applicant_email,applicant_phone_e164,created_at,reviewed_at,"
    "rejection_reason,communities(name,community_type)"
)


def insert(client: Client, payload: dict) -> dict:
    response = client.table(_TABLE).insert(payload).execute()
    return response.data[0]


def get(client: Client, request_id: str) -> dict | None:
    rows = (
        client.table(_TABLE)
        .select(_SELECT)
        .eq("id", request_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def find_pending(client: Client, *, profile_id: str, community_id: str) -> dict | None:
    rows = (
        client.table(_TABLE)
        .select(_SELECT)
        .eq("applicant_profile_id", profile_id)
        .eq("community_id", community_id)
        .eq("status", "pending")
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_for_profile(client: Client, profile_id: str) -> list[dict]:
    return (
        client.table(_TABLE)
        .select(_SELECT)
        .eq("applicant_profile_id", profile_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


def list_for_community(
    client: Client, *, community_id: str, status: str, limit: int
) -> list[dict]:
    query = (
        client.table(_TABLE)
        .select(_SELECT)
        .eq("community_id", community_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("status", status)
    return query.execute().data or []


def withdraw(client: Client, *, request_id: str, profile_id: str) -> dict | None:
    rows = (
        client.table(_TABLE)
        .update({"status": "withdrawn"})
        .eq("id", request_id)
        .eq("applicant_profile_id", profile_id)
        .eq("status", "pending")
        .select(_SELECT)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def approve(
    client: Client,
    *,
    request_id: str,
    reviewer_profile_id: str,
    unit_id: str | None,
    relationship: str | None,
    unit_code: str | None = None,
    building_code: str | None = None,
) -> dict:
    payload = {
        "p_request_id": request_id,
        "p_reviewer_profile_id": reviewer_profile_id,
        "p_unit_id": unit_id,
        "p_relationship": relationship,
    }
    # Sent only when present, so a backend deployed before the hand-applied
    # residence-claim migration still matches the old 4-argument RPC shape.
    if unit_code is not None:
        payload["p_unit_code"] = unit_code
    if building_code is not None:
        payload["p_building_code"] = building_code
    response = client.rpc("approve_access_request", payload).execute()
    return response.data[0] if isinstance(response.data, list) else response.data


def reject(
    client: Client, *, request_id: str, reviewer_profile_id: str, reason: str
) -> dict:
    response = client.rpc(
        "reject_access_request",
        {
            "p_request_id": request_id,
            "p_reviewer_profile_id": reviewer_profile_id,
            "p_reason": reason,
        },
    ).execute()
    return response.data[0] if isinstance(response.data, list) else response.data


def blacklist(
    client: Client, *, request_id: str, reviewer_profile_id: str, reason: str
) -> dict:
    response = client.rpc(
        "blacklist_access_request",
        {"p_request_id": request_id, "p_reviewer_profile_id": reviewer_profile_id, "p_reason": reason},
    ).execute()
    return response.data[0] if isinstance(response.data, list) else response.data
