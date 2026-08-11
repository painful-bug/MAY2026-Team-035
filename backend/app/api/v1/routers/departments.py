"""Department and staff routes.

**These reads survived the wiring audit, unlike every other read we built.** The
shared ``GET /dashboard/snapshot`` does project ``departments[]``, but it builds
each one as ``{"staff": [], "categories": []}`` -- literally empty lists
(``dashboard_service.py:203``). ``Departments.jsx`` (1 095 lines) and
``DepartmentDetail.jsx`` (713 lines) are built around staff rosters, so the
snapshot cannot feed them and these endpoints are the only source. See
``docs/FRONTEND_WIRING_AUDIT.md``.

Complaints belonging to a department are *not* served here. That used to point at
``GET /api/v1/complaints?departmentId=...``, which the audit removed; the queue now
comes from the snapshot's ``complaints[]``, which carries ``departmentId``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import (
    require_admin,
    require_admin_or_manager,
    require_csrf_unsafe,
)
from app.api.deps import get_current_user, get_request_client
from app.domain.common_schemas import MessageResult, Page
from app.domain.department_schemas import (
    CreateDepartmentRequest,
    DepartmentDetail,
    ReplaceStaffRequest,
    StaffMember,
    StaffMemberInput,
    UpdateDepartmentRequest,
    UpdateStaffMemberRequest,
)
from app.services import departments_service
from supabase import Client

# **The router guard is the looser of the two, and every admin-only route says
# so explicitly.** It was `require_admin` for the whole router until the manager
# portal needed to read its own department — the one read here a manager has any
# business making, and the only one that had no frontend caller at all.
#
# Widening the router and narrowing eight routes, rather than the reverse, is
# the arrangement FastAPI actually allows: router dependencies cannot be removed
# per route. The risk it introduces is a new route added here without
# `require_admin` and silently reachable by a manager, so
# `tests/api/test_departments.py::test_api_186` asserts the whole table: a
# manager is refused on all eight and allowed on the read.
router = APIRouter(
    tags=["departments"],
    dependencies=[Depends(require_admin_or_manager), Depends(require_csrf_unsafe)],
)

#: Spelled once, applied to every route except the detail read.
ADMIN_ONLY = [Depends(require_admin)]


@router.get(
    "/departments",
    response_model=Page[DepartmentDetail],
    summary="List departments",
    dependencies=ADMIN_ONLY,
)
async def list_departments(
    search: str | None = Query(
        None,
        max_length=100,
        alias="q",
        description=(
            "Matches name, description, head, contact email, category names and "
            "staff names -- the same fields the dashboard's search box covers."
        ),
    ),
    status_filter: str | None = Query(
        None, alias="status", description="Active | Inactive. Omit for both."
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> Page[DepartmentDetail]:
    """Departments with their staff, category claims and complaint counts.

    ``activeComplaintCount`` and ``overdueComplaintCount`` are computed from the
    complaints actually routed to the department, so they agree with the
    complaints list rather than being re-derived per screen.
    """
    return departments_service.list_departments(
        client,
        principal.user_id,
        search=search,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/departments",
    response_model=DepartmentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a department",
    dependencies=ADMIN_ONLY,
)
async def create_department(
    body: CreateDepartmentRequest,
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> DepartmentDetail:
    """Create a department together with its categories, roster and head.

    All four in one transaction. ``categories`` are names: any that do not exist
    yet are created, because one of the two create screens is a free-text box.

    Returns 409 when the community already has a department with that name.
    """
    return departments_service.create_department(client, principal.user_id, body)


@router.get(
    "/departments/{department_id}",
    response_model=DepartmentDetail,
    summary="Get a department",
)
async def get_department(
    department_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> DepartmentDetail:
    """One department with its active roster and each member's open workload."""
    return departments_service.get_department(client, principal.user_id, department_id)


@router.patch(
    "/departments/{department_id}",
    response_model=DepartmentDetail,
    summary="Update a department",
    dependencies=ADMIN_ONLY,
)
async def update_department(
    body: UpdateDepartmentRequest,
    department_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> DepartmentDetail:
    """Patch a department. Omitted fields are left unchanged.

    Two fields have collection semantics: sending ``categories`` replaces the
    claim set, and sending ``staff`` replaces the roster. Omitting either leaves
    it alone.

    Setting ``status`` to ``Inactive`` is the deactivation the dashboard offers
    instead of deletion, and is **not** blocked by open complaints -- that guard
    belongs to `DELETE` alone, or an admin with an unresolvable department would
    have no action left.
    """
    return departments_service.update_department(
        client, principal.user_id, department_id, body
    )


@router.delete(
    "/departments/{department_id}",
    response_model=MessageResult,
    summary="Delete a department",
    dependencies=ADMIN_ONLY,
)
async def delete_department(
    department_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Permanently remove a department, its category claims and its roster.

    **This one really is a delete**, unlike removing a resident. Complaint
    records survive with their department reference cleared, which is what the
    confirmation dialog promises.

    Returns 409 while the department owns any open complaint; the count is taken
    inside the deleting transaction, so a complaint raised mid-check cannot slip
    through. Deactivate instead.
    """
    departments_service.delete_department(client, principal.user_id, department_id)
    return MessageResult(message="Department deleted.")


@router.put(
    "/departments/{department_id}/staff",
    response_model=list[StaffMember],
    summary="Replace a department's roster",
    dependencies=ADMIN_ONLY,
)
async def replace_staff(
    body: ReplaceStaffRequest,
    department_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> list[StaffMember]:
    """Reconcile the whole roster in one transaction.

    Entries carrying an ``id`` are updated in place, entries without one are
    added, and active members the payload omits are **deactivated, not deleted**
    -- a complaint's ``assignee`` records staff by name, so removing the row
    would turn a past assignment into an unattributable string.

    PUT rather than POST because this replaces a collection: sending the same
    roster twice leaves the same result.
    """
    return departments_service.replace_staff(
        client, principal.user_id, department_id, body.staff
    )


@router.post(
    "/departments/{department_id}/staff",
    response_model=StaffMember,
    status_code=status.HTTP_201_CREATED,
    summary="Add a staff member",
    dependencies=ADMIN_ONLY,
)
async def add_staff_member(
    body: StaffMemberInput,
    department_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> StaffMember:
    """Add one person to a roster.

    A staff member needs no account: name is the only required field, matching
    what the department form actually collects.
    """
    return departments_service.add_staff_member(
        client, principal.user_id, department_id, body
    )


@router.patch(
    "/departments/{department_id}/staff/{staff_id}",
    response_model=StaffMember,
    summary="Update a staff member",
    dependencies=ADMIN_ONLY,
)
async def update_staff_member(
    body: UpdateStaffMemberRequest,
    department_id: str = Path(...),
    staff_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> StaffMember:
    """Patch one roster entry.

    Promotion to head is not done here: ``PATCH /departments/{id}`` with a
    ``head`` name is the only path, because promoting one person has to demote
    the incumbent in the same transaction.
    """
    return departments_service.update_staff_member(
        client, principal.user_id, department_id, staff_id, body
    )


@router.delete(
    "/departments/{department_id}/staff/{staff_id}",
    response_model=MessageResult,
    summary="Remove a staff member",
    dependencies=ADMIN_ONLY,
)
async def remove_staff_member(
    department_id: str = Path(...),
    staff_id: str = Path(...),
    principal=Depends(get_current_user),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Take a member off the active roster.

    **Not a delete.** The row is marked inactive so past assignments recorded
    against their name stay explainable. Removing the head also frees the head
    slot in the same statement.
    """
    departments_service.remove_staff_member(
        client, principal.user_id, department_id, staff_id
    )
    return MessageResult(message="Staff member removed.")
