"""Departments service: the roster, the category claims, and the counts.

The one shape decision worth stating up front: a department is returned with its
staff embedded, not behind a second request. The department screen renders staff
count, head and the roster on the same card, so splitting them would make every
list render N+1 requests from a client we are not allowed to change.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.core.exceptions import ValidationError
from app.core.formatting import clock_time, parse_instant
from app.core.ttl_cache import TTLCache
from app.domain.common_schemas import Page
from app.domain.department_schemas import (
    CreateDepartmentRequest,
    DepartmentDetail,
    DepartmentSummary,
    OperatingHours,
    StaffMember,
    StaffMemberInput,
    UpdateDepartmentRequest,
)
from app.domain.vocabularies import (
    department_status_to_storage,
    department_status_to_wire,
)
from app.repositories import departments_repository as repo
from app.services import skills_service
from supabase import Client

_VALID_KINDS = ("service", "security")

# The department list -- name, roster, category and skill claims, counts -- is
# a community-scoped reference read requested repeatedly by the same admin
# screen (poll, re-render, a second tab). Keyed by every input that changes the
# rows, not community_id alone: a cache that ignored `search`/`status`/`page`
# would answer a filtered request with an unrelated cached page. 60 seconds,
# matching every other cache added in this pass -- see
# ``app.core.ttl_cache`` for why that number and why per-process is accepted.
_LIST_CACHE: TTLCache[Page[DepartmentDetail]] = TTLCache(ttl_seconds=60, max_entries=256)


def reset_cache() -> None:
    """Empty the department list cache. For tests only."""
    _LIST_CACHE.clear()


def invalidate_department_cache(community_id: str) -> None:
    """Drop every cached listing page/filter for one community.

    Called after any write that changes a row the list renders: the roster
    embedded in each ``DepartmentDetail``, a department's own fields, or the
    category/skill claims shown alongside it. The key is a tuple
    ``(community_id, ...)``, so every cached page and filter for this
    community is cleared at once rather than only the one combination the
    writer happened to read last.
    """
    _LIST_CACHE.invalidate_where(lambda key: key[0] == community_id)


# Widened to match `staff_assignments_shift_check` as 0035 corrects it. Before
# that they were disjoint on three of five words: this tuple accepted `Day`,
# which the CHECK rejected, and the CHECK accepted `Morning` and `Full Day`,
# which this rejected. Only `Evening` and `Night` could be saved at all.
_VALID_SHIFTS = ("Day", "Evening", "Night", "Full Day", "Rotating")
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
        service_provider_id=row.get("service_provider_id"),
        supervised_work_order_count=row.get("supervised_work_order_count") or 0,
        open_commitment_count=row.get("open_commitment_count") or 0,
        departure_status=row.get("departure_status"),
        departure_effective_at=row.get("departure_effective_at"),
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
        # Same positional pairing, from the same view (0048). Empty for a
        # department that has chosen no skills, which is every department until
        # somebody picks some -- they are never inherited from categories.
        skills=list(row.get("skill_names") or []),
        skill_ids=[str(value) for value in (row.get("skill_ids") or [])],
        head=row.get("head_name"),
        head_staff_id=row.get("head_staff_id"),
        email=row.get("contact_email"),
        phone=row.get("contact_phone_e164"),
        operating_hours=OperatingHours(
            start=clock_time(row.get("opens_at")),
            end=clock_time(row.get("closes_at")),
        ),
        sla_hours=row.get("sla_hours"),
        kind=row.get("kind") or "service",
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
    community_id: str,
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

    Cached for 60 seconds per ``(community_id, search, status, page,
    page_size)`` -- the exact combination a re-render or a poll repeats
    verbatim, and never one a differently-filtered request can collide with.
    """
    storage_status = _storage_status(status)
    cache_key = (community_id, search, storage_status, page, page_size)

    def _load() -> Page[DepartmentDetail]:
        offset = (page - 1) * page_size

        rows, total = repo.list_departments(
            client,
            community_id,
            search=search,
            status=storage_status,
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

    return _LIST_CACHE.get_or_load(cache_key, _load)


def get_department(
    client: Client, community_id: str, department_id: str
) -> DepartmentDetail:
    """One department with its active roster, and whether this caller may hire.

    ``canHire`` is only filled in here. The list leaves it ``None`` because the
    answer is per department and per caller, so a list of twelve would be twelve
    extra round trips for a screen with no control that needs one.

    The three reads are independent, so they run concurrently (the pattern
    ``dashboard_service.snapshot`` set). ``row_f.result()`` is taken first: a
    missing department raises its ``NotFoundError`` from there, exactly as the
    sequential version did.
    """
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="department") as pool:
        row_f = pool.submit(repo.get_department, client, community_id, department_id)
        staff_f = pool.submit(repo.list_staff, client, community_id, [department_id])
        can_hire_f = pool.submit(repo.can_hire, client, department_id)
        row = row_f.result()
        staff = staff_f.result()
        can_hire = can_hire_f.result()
    detail = _to_detail(row, staff)
    detail.can_hire = can_hire
    return detail


def create_department(
    client: Client, community_id: str, body: CreateDepartmentRequest
) -> DepartmentDetail:
    """Create a department, its category claims and its roster, atomically."""
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
    # Always invalidated, not only when `categories` was non-empty: `payload`
    # always carries the key (see the comment above), and the RPC may have
    # just created new category rows this community's cached
    # `community_categories` read does not know about yet.
    invalidate_department_cache(community_id)
    skills_service.invalidate_categories_cache(community_id)
    row = repo.get_department(client, community_id, department_id)
    staff = repo.list_staff(client, community_id, [department_id])
    return _to_detail(row, staff)


def update_department(
    client: Client, community_id: str, department_id: str, body: UpdateDepartmentRequest
) -> DepartmentDetail:
    """Apply a partial update and return the department as it now stands."""
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
        invalidate_department_cache(community_id)
        if "categories" in patch:
            skills_service.invalidate_categories_cache(community_id)
    else:
        # Nothing to write, but the caller still deserves a 404 rather than a
        # cheerful echo if the department does not exist.
        repo.get_department(client, community_id, department_id)

    row = repo.get_department(client, community_id, department_id)
    staff = repo.list_staff(client, community_id, [department_id])
    return _to_detail(row, staff)


def delete_department(client: Client, community_id: str, department_id: str) -> None:
    """Delete a department. Refuses (409) while it owns open complaints.

    ``community_id`` is only needed to invalidate this community's cached
    listing and category counts -- the delete RPC still enforces its own
    rules from the caller's proven membership, exactly as before this cache
    existed.
    """
    repo.delete_department(client, department_id)
    invalidate_department_cache(community_id)
    # A deleted department's category claims go with it, which moves the
    # `departmentCount` the categories read reports.
    skills_service.invalidate_categories_cache(community_id)


