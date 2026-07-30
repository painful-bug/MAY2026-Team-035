"""Narrow community-directory queries used before a membership exists."""

from __future__ import annotations

from supabase import Client


def search_joinable_communities(
    client: Client, *, query: str, limit: int, profile_id: str
) -> list[dict]:
    """Return only the minimal projection exposed by the SQL search function."""
    response = client.rpc(
        "search_joinable_communities",
        {"p_query": query, "p_limit": limit, "p_profile_id": profile_id},
    ).execute()
    return response.data or []
