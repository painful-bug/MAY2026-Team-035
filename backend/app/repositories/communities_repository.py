"""Narrow community-directory queries used before a membership exists."""

from __future__ import annotations

from supabase import Client


def search_joinable_communities(
    client: Client, *, query: str, limit: int
) -> list[dict]:
    """Return only the minimal projection exposed by the SQL search function."""
    response = client.rpc(
        "search_joinable_communities",
        {"p_query": query, "p_limit": limit},
    ).execute()
    return response.data or []
