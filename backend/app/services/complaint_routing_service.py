"""Which department owns a complaint: the queues, the allot, and the transfer.

Thin, like every service over a definer RPC. ``is_community_admin``,
``can_manage_department`` and ``can_supervise_department`` ask the
authorization questions in Postgres, so there is nothing for this layer to
re-decide -- what it owns is the shape of the answer and the one piece of
validation that is cheaper here than a round trip.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationError
from app.domain.complaint_routing_schemas import (
    DecideDepartmentChangeRequest,
    DepartmentChangeRequest,
    DepartmentComplaint,
    DepartmentOption,
    RequestDepartmentChangeRequest,
    UnassignedComplaint,
)
from app.repositories import complaint_routing_repository as repo
from supabase import Client

#: The two answers a manager may give. Checked here as well as in the RPC so a
#: typo comes back as a 422 naming both words, rather than as a database error
#: the client has to guess at.
_DECISIONS = ("accept", "reject")


def _text(value: Any) -> str | None:
    return str(value) if value is not None else None


def department_complaints(
    client: Client, *, department_id: str, status: str | None
) -> list[DepartmentComplaint]:
    """One department's queue, for its manager and its supervisors."""
    return [
        DepartmentComplaint(
            id=str(row["id"]),
            title=str(row.get("title") or ""),
            description=_text(row.get("description")),
            category=_text(row.get("category")),
            status=str(row.get("status") or ""),
            priority=_text(row.get("priority")),
            location=_text(row.get("location")),
            created_at=row.get("created_at"),
            due_at=row.get("due_at"),
            resolved_at=row.get("resolved_at"),
            raised_by=_text(row.get("raised_by")),
            unit_code=_text(row.get("unit_code")),
            open_request_id=_text(row.get("open_request_id")),
        )
        for row in repo.department_complaints(
            client, department_id=department_id, status=status
        )
    ]


def unassigned_complaints(
    client: Client, *, community_id: str
) -> list[UnassignedComplaint]:
    """The admin's triage queue."""
    return [
        UnassignedComplaint(
            id=str(row["id"]),
            title=str(row.get("title") or ""),
            description=_text(row.get("description")),
            category=_text(row.get("category")),
            status=str(row.get("status") or ""),
            priority=_text(row.get("priority")),
            created_at=row.get("created_at"),
            raised_by=_text(row.get("raised_by")),
            unit_code=_text(row.get("unit_code")),
        )
        for row in repo.unassigned_complaints(client, community_id=community_id)
    ]


def community_departments(
    client: Client, *, community_id: str
) -> list[DepartmentOption]:
    """Every active department, named, for a destination picker."""
    return [
        DepartmentOption(
            id=str(row["id"]),
            name=str(row.get("name") or ""),
            kind=_text(row.get("kind")),
        )
        for row in repo.community_departments(client, community_id=community_id)
    ]


def department_change_requests(
    client: Client, *, department_id: str
) -> list[DepartmentChangeRequest]:
    """Open transfer requests waiting on this department's manager."""
    return [
        DepartmentChangeRequest(
            id=str(row["id"]),
            complaint_id=str(row["complaint_id"]),
            complaint_title=_text(row.get("complaint_title")),
            to_department_id=_text(row.get("to_department_id")),
            to_department_name=_text(row.get("to_department_name")),
            requested_by=_text(row.get("requested_by")),
            reason=_text(row.get("reason")),
            created_at=row.get("created_at"),
        )
        for row in repo.department_change_requests(
            client, department_id=department_id
        )
    ]


def assign_department(
    client: Client, *, membership_id: str, complaint_id: str, department_id: str
) -> None:
    """Allot an unrouted complaint, or move a routed one out."""
    repo.assign_department(
        client,
        membership_id=membership_id,
        complaint_id=complaint_id,
        department_id=department_id,
    )


def request_department_change(
    client: Client,
    *,
    membership_id: str,
    complaint_id: str,
    body: RequestDepartmentChangeRequest,
) -> str:
    """A supervisor asking their manager to move a complaint."""
    return repo.request_department_change(
        client,
        membership_id=membership_id,
        complaint_id=complaint_id,
        to_department_id=body.to_department_id,
        reason=body.reason,
    )


def decide_department_change(
    client: Client,
    *,
    membership_id: str,
    request_id: str,
    body: DecideDepartmentChangeRequest,
) -> None:
    """The manager's answer, and the move if they accepted."""
    decision = (body.decision or "").strip().lower()
    if decision not in _DECISIONS:
        raise ValidationError(
            f"Unknown decision: {body.decision}. Use accept or reject.",
            code="unknown_decision",
        )
    repo.decide_department_change(
        client,
        membership_id=membership_id,
        request_id=request_id,
        decision=decision,
        to_department_id=body.to_department_id,
    )
