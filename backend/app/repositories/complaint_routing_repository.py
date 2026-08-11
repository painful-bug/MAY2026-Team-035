"""Data access for which department owns a complaint.

Every function here is an RPC in ``complaint_department_routing``, and the
reason is the same one ``skills_repository`` gives: all six are ``SECURITY DEFINER`` and ask their own
authorization question, so a table or view read beside them would answer the
same question a second way through RLS and the two would drift.

The **request client** is passed throughout, never the service client.
``can_manage_department``, ``can_supervise_department`` and
``is_community_admin`` all resolve the caller from ``auth.uid()``, which does
not exist on the service client -- so passing the wrong one would not fail
loudly, it would refuse somebody who is in fact allowed.
"""

from __future__ import annotations

from typing import Any

from app.core.pg_errors import translate
from supabase import Client


def _rows(response: Any) -> list[dict[str, Any]]:
    """Normalise an RPC result to a list.

    PostgREST returns a bare object rather than a one-element array when a
    ``returns table`` function yields exactly one row, and a department with one
    complaint is not a rare case.
    """
    data = response.data or []
    return data if isinstance(data, list) else [data]


def department_complaints(
    client: Client, *, department_id: str, status: str | None
) -> list[dict[str, Any]]:
    """One department's queue, for its manager and its supervisors."""
    try:
        response = client.rpc(
            "department_complaints",
            {"p_department_id": department_id, "p_status": status},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not read this department's complaints."
        ) from exc
    return _rows(response)


def unassigned_complaints(
    client: Client, *, community_id: str
) -> list[dict[str, Any]]:
    """The admin's triage queue: complaints nothing could route."""
    try:
        response = client.rpc(
            "unassigned_complaints", {"p_community_id": community_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not read the triage queue."
        ) from exc
    return _rows(response)


def community_departments(
    client: Client, *, community_id: str
) -> list[dict[str, Any]]:
    """Id, name and kind of every active department, for a picker."""
    try:
        response = client.rpc(
            "community_departments", {"p_community_id": community_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not read the department list."
        ) from exc
    return _rows(response)


def department_change_requests(
    client: Client, *, department_id: str
) -> list[dict[str, Any]]:
    """Open transfer requests waiting on this department's manager."""
    try:
        response = client.rpc(
            "department_change_requests", {"p_department_id": department_id}
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not read the change requests."
        ) from exc
    return _rows(response)


def assign_department(
    client: Client, *, membership_id: str, complaint_id: str, department_id: str
) -> None:
    """Allot or move a complaint. Which one it is, Postgres decides."""
    try:
        client.rpc(
            "assign_complaint_department",
            {
                "p_membership_id": membership_id,
                "p_complaint_id": complaint_id,
                "p_department_id": department_id,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not assign that complaint."
        ) from exc


def request_department_change(
    client: Client,
    *,
    membership_id: str,
    complaint_id: str,
    to_department_id: str | None,
    reason: str | None,
) -> str:
    """A supervisor asking their manager to move a complaint. Returns its id."""
    try:
        response = client.rpc(
            "request_complaint_department_change",
            {
                "p_membership_id": membership_id,
                "p_complaint_id": complaint_id,
                "p_to_department_id": to_department_id,
                "p_reason": reason,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not raise that request."
        ) from exc
    return str(response.data or "")


def decide_department_change(
    client: Client,
    *,
    membership_id: str,
    request_id: str,
    decision: str,
    to_department_id: str | None,
) -> None:
    """The manager's answer, and the move if they accepted."""
    try:
        client.rpc(
            "decide_complaint_department_change",
            {
                "p_membership_id": membership_id,
                "p_request_id": request_id,
                "p_decision": decision,
                "p_to_department_id": to_department_id,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise translate(
            exc, default_message="Could not answer that request."
        ) from exc
