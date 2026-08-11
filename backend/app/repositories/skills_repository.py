"""Data access for the skill catalogue and a department's claim on it.

Every function here is an RPC call, and none of them is a ``client.table()``
read. That is not the house default -- ``departments_repository`` reads views
directly -- and the reason is that all six functions in ``0048`` are
``SECURITY DEFINER`` and ask their own authorization question. A view read
beside them would answer the same question a second way, through RLS, and the
two would drift.

The caller's **request client** is passed throughout, never the service client.
``can_manage_department`` and ``can_author_skills`` resolve the caller from
``auth.uid()``, which does not exist on the service client -- passing the wrong
one would not fail loudly, it would raise "you do not manage this department"
for somebody who does.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client


def _rows(response: Any) -> list[dict[str, Any]]:
    """Normalise an RPC result to a list.

    PostgREST returns a bare object rather than a one-element array when a
    ``returns table`` function yields exactly one row, and three of the calls
    below can do either.
    """
    data = response.data or []
    return data if isinstance(data, list) else [data]


def search_skills(
    client: Client, *, query: str | None, limit: int
) -> list[dict[str, Any]]:
    """Closest-match suggestions, already ordered by Postgres.

    An empty or absent query returns the head of the catalogue rather than
    nothing: the box is useful before the first keystroke.
    """
    try:
        response = client.rpc(
            "search_skills", {"p_query": query, "p_limit": limit}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not search skills.") from exc
    return _rows(response)


def create_skill(
    client: Client, *, name: str, category: str | None, description: str | None
) -> dict[str, Any]:
    """Add a trade, or return the one already answering to that name."""
    try:
        response = client.rpc(
            "create_skill",
            {"p_name": name, "p_category": category, "p_description": description},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not add that skill.") from exc
    rows = _rows(response)
    return rows[0] if rows else {}


def community_categories(client: Client, *, membership_id: str) -> list[dict[str, Any]]:
    """Every complaint category in the caller's community, with its trade."""
    try:
        response = client.rpc(
            "community_categories", {"p_membership_id": membership_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not read categories.") from exc
    return _rows(response)


def list_department_skills(
    client: Client, *, department_id: str
) -> list[dict[str, Any]]:
    """The skills one department claims."""
    try:
        response = client.rpc(
            "department_skill_list", {"p_department_id": department_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not read this department's skills."
        ) from exc
    return _rows(response)


def add_department_skill(
    client: Client, *, department_id: str, name: str
) -> dict[str, Any]:
    """Create-if-absent and attach, in one transaction.

    One call rather than create-then-attach from the client, because two calls
    can half-fail: a skill created and not attached is catalogue litter nobody
    asked for, and that is the failure that happens on a phone at the end of a
    long form.
    """
    try:
        response = client.rpc(
            "add_department_skill",
            {"p_department_id": department_id, "p_name": name},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not add that skill.") from exc
    rows = _rows(response)
    return rows[0] if rows else {}


def remove_department_skill(
    client: Client, *, department_id: str, skill_id: str
) -> None:
    """Detach. The skill is global and survives."""
    try:
        client.rpc(
            "remove_department_skill",
            {"p_department_id": department_id, "p_skill_id": skill_id},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not remove that skill.") from exc


def set_department_skills(
    client: Client, *, department_id: str, skill_ids: list[str]
) -> None:
    """Make the set exactly ``skill_ids``."""
    try:
        client.rpc(
            "set_department_skills",
            {"p_department_id": department_id, "p_skill_ids": skill_ids},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(exc, default_message="Could not save these skills.") from exc
