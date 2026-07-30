"""Departments service: the roster, the category claims, and the counts.

The one shape decision worth stating up front: a department is returned with its
staff embedded, not behind a second request. The department screen renders staff
count, head and the roster on the same card, so splitting them would make every
list render N+1 requests from a client we are not allowed to change.
"""

from __future__ import annotations

from app.core.exceptions import ValidationError
from app.core.formatting import clock_time, parse_instant
from app.domain.common_schemas import Page
from app.domain.department_schemas import (
    ComplaintCategorySummary,
    CreateDepartmentRequest,
    DepartmentDetail,
    DepartmentSummary,
    OperatingHours,
    StaffMember,
    StaffMemberInput,
    UpdateDepartmentRequest,
    UpdateStaffMemberRequest,
)
from app.domain.vocabularies import (
    department_status_to_storage,
    department_status_to_wire,
)
from app.repositories import admin_overview_repository as dash_repo
from app.repositories import departments_repository as repo
from supabase import Client

_VALID_KINDS = ("service", "security")
_VALID_SHIFTS = ("Day", "Evening", "Night")
_VALID_STAFF_STATUSES = ("active", "inactive")


def _to_staff(row: dict) -> StaffMember:
    return StaffMember(
        id=row["id"],
        name=row["display_name"],
        phone=row.get("phone_e164"),
        role=row.get("job_title"),
        rank=row.get("rank", "member"),
        shift=row.get("shift"),
        status=row.get("status", "active"),
        membership_id=row.get("membership_id"),
        active_assignment_count=row.get("active_assignment_count") or 0,
    )


def _to_summary(row: dict) -> DepartmentSummary:
    return DepartmentSummary(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        # The view returns both arrays ordered by category name, so the two line
        # up positionally as well as by content (R23).
        categories=list(row.get("category_names") or []),
        category_ids=[str(value) for value in (row.get("category_ids") or [])],
        head=row.get("head_name"),
        head_staff_id=row.get("head_staff_id"),
        email=row.get("contact_email"),
        phone=row.get("contact_phone_e164"),
        operating_hours=OperatingHours(
            start=clock_time(row.get("opens_at")),
            end=clock_time(row.get("closes_at")),
        ),
        sla_hours=row.get("sla_hours"),
        kind=row.get("kind", "service"),
        status=department_status_to_wire(row.get("status")),
        staff_count=row.get("staff_count") or 0,
        active_complaint_count=row.get("active_complaint_count") or 0,
        resolved_complaint_count=row.get("resolved_complaint_count") or 0,
        overdue_complaint_count=row.get("overdue_complaint_count") or 0,
        created_at=parse_instant(row["created_at"]),
        updated_at=parse_instant(row["updated_at"]),
    )


def _to_detail(row: dict, staff: list[dict]) -> DepartmentDetail:
    return DepartmentDetail(
        **_to_summary(row).model_dump(),
        staff=[_to_staff(member) for member in staff],
    )


def _staff_payload(members: list[StaffMemberInput]) -> list[dict]:
    """Flatten staff DTOs into the jsonb the RPC reconciles against."""
    payload = []
    for member in members:
        item: dict = {"name": member.name.strip()}
        if member.id:
            item["id"] = member.id
        # Only keys that were actually supplied: the RPC treats key presence as
        # "change this", so sending `phone: null` for an untouched field would
        # wipe a number the caller never mentioned.
        supplied = member.model_dump(exclude_unset=True)
        for wire_key, payload_key in (
            ("phone", "phone"),
            ("role", "role"),
            ("shift", "shift"),
            ("status", "status"),
        ):
            if wire_key in supplied:
                item[payload_key] = supplied[wire_key]
        payload.append(item)
    return payload


def _validate_kind(kind: str | None) -> None:
    if kind is not None and kind not in _VALID_KINDS:
        raise ValidationError(
            f"kind must be one of {', '.join(_VALID_KINDS)}.", code="invalid_kind"
        )


def _validate_shift(shift: str | None) -> None:
    if shift is not None and shift not in _VALID_SHIFTS:
        raise ValidationError(
            f"shift must be one of {', '.join(_VALID_SHIFTS)}.", code="invalid_shift"
        )


def _validate_staff_status(status: str | None) -> None:
    if status is not None and status not in _VALID_STAFF_STATUSES:
        raise ValidationError(
            f"status must be one of {', '.join(_VALID_STAFF_STATUSES)}.",
            code="invalid_status",
        )


def _storage_status(value: str | None) -> str | None:
    """Map ``Active``/``Inactive`` to the stored vocabulary, or reject."""
    if value is None:
        return None
    stored = department_status_to_storage(value)
    if stored is None:
        raise ValidationError(
            "status must be 'Active' or 'Inactive'.", code="invalid_status"
        )
    return stored


def list_departments(
    client: Client,
    user_id: str,
    *,
    search: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[DepartmentDetail]:
    """Page through the community's departments, each with its roster.

    The roster is included rather than left to a follow-up request because the
    frontend's edit modal is seeded straight from the list row
    (``Departments.jsx:69``). One extra query per page, not one per department:
    ``list_staff`` takes every id on the page at once.
    """
    community_id = dash_repo.get_caller_community_id(client, user_id)
    offset = (page - 1) * page_size

    rows, total = repo.list_departments(
        client,
        community_id,
        search=search,
        status=_storage_status(status),
        offset=offset,
        limit=page_size,
    )

    staff_rows = repo.list_staff(client, community_id, [row["id"] for row in rows])
    by_department: dict[str, list[dict]] = {}
    for member in staff_rows:
        by_department.setdefault(member["department_id"], []).append(member)

    items = [_to_detail(row, by_department.get(row["id"], [])) for row in rows]
    return Page[DepartmentDetail](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(items) < total,
    )


def get_department(
    client: Client, user_id: str, department_id: str
) -> DepartmentDetail:
    """One department with its active roster."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    row = repo.get_department(client, community_id, department_id)
    staff = repo.list_staff(client, community_id, [department_id])
    return _to_detail(row, staff)


def create_department(
    client: Client, user_id: str, body: CreateDepartmentRequest
) -> DepartmentDetail:
    """Create a department, its category claims and its roster, atomically."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    _validate_kind(body.kind)
    for member in body.staff:
        _validate_shift(member.shift)
        _validate_staff_status(member.status)

    payload: dict = {"name": body.name.strip()}
    supplied = body.model_dump(exclude_unset=True)

    if "description" in supplied:
        payload["description"] = body.description
    if "email" in supplied:
        payload["contact_email"] = body.email
    if "phone" in supplied:
        payload["contact_phone_e164"] = body.phone
    if "sla_hours" in supplied:
        payload["sla_hours"] = body.sla_hours
    if "kind" in supplied and body.kind:
        payload["kind"] = body.kind
    if "status" in supplied:
        payload["status"] = _storage_status(body.status)
    if "head" in supplied:
        payload["head"] = body.head
    if body.operating_hours is not None:
        payload["opens_at"] = body.operating_hours.start
        payload["closes_at"] = body.operating_hours.end
    # Always sent, even when empty: creating a department with no categories is a
    # real choice, and the RPC distinguishes an empty list from an absent key.
    payload["categories"] = [name.strip() for name in body.categories if name.strip()]
    if body.staff:
        payload["staff"] = _staff_payload(body.staff)

    department_id = repo.create_department(client, community_id, payload)
    row = repo.get_department(client, community_id, department_id)
    staff = repo.list_staff(client, community_id, [department_id])
    return _to_detail(row, staff)


def update_department(
    client: Client, user_id: str, department_id: str, body: UpdateDepartmentRequest
) -> DepartmentDetail:
    """Apply a partial update and return the department as it now stands."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    _validate_kind(body.kind)
    for member in body.staff or []:
        _validate_shift(member.shift)
        _validate_staff_status(member.status)

    supplied = body.model_dump(exclude_unset=True)
    patch: dict = {}

    if "name" in supplied and body.name:
        patch["name"] = body.name.strip()
    if "description" in supplied:
        patch["description"] = body.description
    if "email" in supplied:
        patch["contact_email"] = body.email
    if "phone" in supplied:
        patch["contact_phone_e164"] = body.phone
    if "sla_hours" in supplied:
        patch["sla_hours"] = body.sla_hours
    if "kind" in supplied and body.kind:
        patch["kind"] = body.kind
    if "status" in supplied:
        patch["status"] = _storage_status(body.status)
    if "head" in supplied:
        patch["head"] = body.head
    if "operating_hours" in supplied and body.operating_hours is not None:
        patch["opens_at"] = body.operating_hours.start
        patch["closes_at"] = body.operating_hours.end
    if "categories" in supplied and body.categories is not None:
        patch["categories"] = [name.strip() for name in body.categories if name.strip()]
    if "staff" in supplied and body.staff is not None:
        patch["staff"] = _staff_payload(body.staff)

    if patch:
        repo.update_department(client, department_id, patch)
    else:
        # Nothing to write, but the caller still deserves a 404 rather than a
        # cheerful echo if the department does not exist.
        repo.get_department(client, community_id, department_id)

    row = repo.get_department(client, community_id, department_id)
    staff = repo.list_staff(client, community_id, [department_id])
    return _to_detail(row, staff)


def delete_department(client: Client, user_id: str, department_id: str) -> None:
    """Delete a department. Refuses (409) while it owns open complaints."""
    dash_repo.get_caller_community_id(client, user_id)
    repo.delete_department(client, department_id)


def replace_staff(
    client: Client, user_id: str, department_id: str, members: list[StaffMemberInput]
) -> list[StaffMember]:
    """Replace a department's roster wholesale, as the department form submits it."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    for member in members:
        _validate_shift(member.shift)
        _validate_staff_status(member.status)

    repo.update_department(client, department_id, {"staff": _staff_payload(members)})
    return [
        _to_staff(row) for row in repo.list_staff(client, community_id, [department_id])
    ]


def add_staff_member(
    client: Client, user_id: str, department_id: str, member: StaffMemberInput
) -> StaffMember:
    """Add one person to a roster."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    _validate_shift(member.shift)
    _validate_staff_status(member.status)
    # Existence and tenancy first: RLS would reject a cross-community insert, but
    # as a policy failure, which reads as a permission error rather than "no such
    # department".
    repo.get_department(client, community_id, department_id)

    staff_id = repo.insert_staff_member(
        client,
        community_id,
        department_id,
        {
            "display_name": member.name.strip(),
            "phone_e164": (member.phone or "").strip() or None,
            "job_title": (member.role or "").strip() or None,
            "shift": member.shift,
            "status": member.status or "active",
        },
    )
    return _to_staff(repo.get_staff_member(client, community_id, staff_id))


def update_staff_member(
    client: Client,
    user_id: str,
    department_id: str,
    staff_id: str,
    body: UpdateStaffMemberRequest,
) -> StaffMember:
    """Patch one roster entry.

    ``rank`` is deliberately not patchable here: a department has at most one
    head, and naming it through ``PATCH /departments/{id}`` with a ``head`` field
    is the single path that demotes the incumbent in the same transaction.
    """
    community_id = dash_repo.get_caller_community_id(client, user_id)
    _validate_shift(body.shift)
    _validate_staff_status(body.status)

    existing = repo.get_staff_member(client, community_id, staff_id)
    if existing.get("department_id") != department_id:
        raise ValidationError(
            "That staff member belongs to a different department.",
            code="wrong_department",
        )

    supplied = body.model_dump(exclude_unset=True)
    fields: dict = {}
    if "name" in supplied and body.name:
        fields["display_name"] = body.name.strip()
    if "phone" in supplied:
        fields["phone_e164"] = (body.phone or "").strip() or None
    if "role" in supplied:
        fields["job_title"] = (body.role or "").strip() or None
    if "shift" in supplied:
        fields["shift"] = body.shift
    if "status" in supplied and body.status:
        fields["status"] = body.status

    repo.update_staff_member(client, community_id, staff_id, fields)
    return _to_staff(repo.get_staff_member(client, community_id, staff_id))


def remove_staff_member(
    client: Client, user_id: str, department_id: str, staff_id: str
) -> None:
    """Take a member off the active roster. Deactivation, not deletion (A7)."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    existing = repo.get_staff_member(client, community_id, staff_id)
    if existing.get("department_id") != department_id:
        raise ValidationError(
            "That staff member belongs to a different department.",
            code="wrong_department",
        )
    repo.remove_staff_member(client, staff_id)


def list_categories(client: Client, user_id: str) -> Page[ComplaintCategorySummary]:
    """The community's complaint categories and who claims each one."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    rows = repo.list_categories(client, community_id)

    items = [
        ComplaintCategorySummary(
            id=row["id"],
            name=row["name"],
            sla_hours=row.get("sla_hours"),
            status=row.get("status", "active"),
            department_ids=row.get("department_ids") or [],
        )
        for row in rows
    ]
    return Page[ComplaintCategorySummary](
        items=items,
        total=len(items),
        page=1,
        page_size=len(items),
        has_more=False,
    )
