"""Which department owns a complaint.

**Why this is a router of its own rather than three routes bolted onto
``complaints.py``.** Its callers are the department populations -- managers and
supervisors -- and its guard has to admit them. ``complaints.py`` is guarded
``require_admin`` on the write it already has; widening that router to admit a
worker so a supervisor could reach one new route would quietly widen the
complaint edit as well.

**The router guard is coarse and is meant to be.** A supervisor holds a
``worker`` membership with the ``supervisor`` rank on their roster row -- rank
is not role, ``0035`` settled that -- so the only role filter that admits every
legitimate caller also admits every worker. Its job is to turn "signed-in
resident poking at department ids" into a 403 before any query runs. It is not
the boundary.

The boundary is in Postgres: ``is_community_admin`` on the triage queue,
``can_manage_department`` on the manager's list and the decision,
``can_supervise_department`` on the department queue and the request. Every one
of the six RPCs in ``0050`` asks its own question, so an id arriving in a URL is
never an authorization decision -- the posture ``department_hiring.py`` states.

**One asymmetry worth naming.** A supervisor may *ask* for a complaint to move
and may not move it. That is the ruling, and it is also the only shape that
works: a supervisor who could push work out of their own department could empty
it, and the department receiving it would have no say either way. The manager
who answers is the manager of the department **giving the complaint up**, never
the one receiving it -- authorizing on the destination would let the manager of
B reach into A and take A's work.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import (
    get_active_membership,
    get_request_client,
    require_membership_role,
)
from app.domain.common_schemas import MessageResult
from app.domain.complaint_routing_schemas import (
    AssignDepartmentRequest,
    DecideDepartmentChangeRequest,
    DepartmentChangeRequest,
    DepartmentComplaint,
    DepartmentOption,
    RequestDepartmentChangeRequest,
    UnassignedComplaint,
)
from app.domain.schemas import MembershipContext
from app.services import complaint_routing_service as service
from supabase import Client

#: Everyone who could conceivably hold a department complaint. Built once at
#: import time, because ``require_membership_role`` returns a new closure per
#: call and FastAPI caches dependencies by identity.
_staff_only = require_membership_role("admin", "manager", "worker", "security")

router = APIRouter(
    tags=["complaint-routing"],
    dependencies=[Depends(require_csrf_unsafe), Depends(_staff_only)],
)


@router.get(
    # **Not `/complaints/unassigned`.** `resident_complaints.py` already owns
    # `GET /complaints/{complaint_id}`, and FastAPI matches across aggregated
    # routers in registration order -- so that path resolved as a complaint
    # whose id is the word "unassigned", ran the resident's read against it, and
    # failed somewhere far from the cause. Declaring this one earlier would have
    # worked and would have made the triage queue's correctness depend on which
    # order two files are included in `app/api/v1/__init__.py`. A path that
    # cannot collide is worth more than a comment explaining the ordering.
    "/unassigned-complaints",
    response_model=list[UnassignedComplaint],
    summary="Complaints nothing could route",
)
async def unassigned_complaints(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> list[UnassignedComplaint]:
    """The admin's triage queue, oldest first.

    A complaint lands here when its category names no department **and** the
    resident either did not pick one or picked something that no longer exists.
    In practice that is the `Other` category and anything nobody has mapped yet
    -- which is exactly the ruling: *if the complaint category is left at other,
    we send it to the admin who can allot it to the department of his choosing.*

    It is also where an **ambiguous** category lands. `department_categories`
    lets one category belong to several departments, and when it does, `0050`
    routes to nothing rather than picking: a question in this queue gets a right
    answer in one click, where a guess gets a wrong one that only the department
    which *didn't* receive it could ever notice.

    Resolved complaints are excluded. One that was answered without ever being
    allotted needs nothing from anybody.
    """
    return service.unassigned_complaints(client, community_id=membership.community_id)


@router.get(
    # A sibling of `/departments`, not a child, for the same reason
    # `/unassigned-complaints` is: `GET /departments/{department_id}` exists and
    # would read "options" as a department id.
    "/department-options",
    response_model=list[DepartmentOption],
    summary="Every department, named, for a picker",
)
async def department_options(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> list[DepartmentOption]:
    """Id, name and kind of every active department in the caller's community.

    This exists because of a control that could not be drawn. `GET /departments`
    is admin-only, so a manager deciding where to move a complaint, or a
    supervisor naming where they think one belongs, had no way to learn any
    department's name -- which would have made the destination field a box you
    type a UUID into.

    Three fields, not the admin list's roster counts, categories, hours and
    skills. Widening a real read boundary so a dropdown can be drawn is the
    trade this avoids.
    """
    return service.community_departments(client, community_id=membership.community_id)


@router.patch(
    "/complaints/{complaint_id}/department",
    response_model=MessageResult,
    summary="Allot or move a complaint",
)
async def assign_department(
    body: AssignDepartmentRequest,
    complaint_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Give a complaint to a department, or move it to another one.

    **One endpoint, two acts, and which one you are performing is decided in
    Postgres by what the complaint currently holds** -- not by which route you
    called or what you claim to be:

    * the complaint has **no** department → only an **admin** may allot it;
    * the complaint **has** one → only that department's **manager** (or an
      admin, who passes `can_manage_department` everywhere) may move it out.

    Authorizing the move on the department the complaint is *leaving* is the
    load-bearing half. The obvious alternative -- checking the caller manages
    the destination -- would let the manager of B reach into A and help
    themselves to A's work.

    Re-assigning to the department that already holds it is a no-op rather than
    a 409, because a double-clicked button is not an error worth a message.
    """
    service.assign_department(
        client,
        membership_id=membership.id,
        complaint_id=complaint_id,
        department_id=body.department_id,
    )
    return MessageResult(message="Complaint assigned.")


@router.post(
    "/complaints/{complaint_id}/department-requests",
    response_model=MessageResult,
    status_code=status.HTTP_201_CREATED,
    summary="Ask for a complaint to be moved",
)
async def request_department_change(
    body: RequestDepartmentChangeRequest,
    complaint_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """A supervisor saying this complaint is not their department's.

    `toDepartmentId` is **optional on purpose**. A supervisor who knows a lift
    complaint is not plumbing usually does not know whose it is, and requiring a
    destination would either silence them or make them guess. Accepted with
    nothing named, the complaint returns to the admin's triage queue.

    Returns 409 when the complaint has not been assigned to any department yet
    -- there is nothing to move it out of and no manager whose inbox this would
    land in -- and 409 on a second open request for the same complaint. Two
    supervisors disagreeing about where a complaint belongs is a conversation,
    not two rows racing a manager's inbox.
    """
    service.request_department_change(
        client,
        membership_id=membership.id,
        complaint_id=complaint_id,
        body=body,
    )
    return MessageResult(message="Request raised.")


@router.patch(
    "/complaints/{complaint_id}/department-requests/{request_id}",
    response_model=MessageResult,
    summary="Answer a move request",
)
async def decide_department_change(
    body: DecideDepartmentChangeRequest,
    complaint_id: str = Path(...),
    request_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """The manager's answer: `accept` or `reject`.

    The manager may name a different destination than the supervisor suggested
    -- they know the society better and they are the one being asked. Accepting
    with **no** destination sends the complaint back to the admin's triage
    queue, which is what "not ours, and I don't know whose either" honestly
    means; inventing a department for it would be worse than admitting that.

    The supervisor who asked is notified either way. A request that is silently
    rejected is a request they raise again next week.
    """
    service.decide_department_change(
        client,
        membership_id=membership.id,
        request_id=request_id,
        body=body,
    )
    return MessageResult(message="Request answered.")


@router.get(
    "/departments/{department_id}/complaints",
    response_model=list[DepartmentComplaint],
    summary="This department's complaints",
)
async def department_complaints(
    department_id: str = Path(...),
    complaint_status: str | None = Query(default=None, alias="status"),
    client: Client = Depends(get_request_client),
) -> list[DepartmentComplaint]:
    """The department's queue, newest first, for its manager and supervisors.

    Both roles read the same list because they act on the same complaints: the
    supervisor triages and requests a move, the manager answers the request and
    can move it themselves. Splitting it into two endpoints would have meant two
    projections that must agree about what a complaint looks like.

    Each row carries `openRequestId` when a transfer has already been asked for,
    so the screen can draw the button correctly without a second read -- and so a
    supervisor cannot file the same request twice before the unique index tells
    them.
    """
    return service.department_complaints(
        client, department_id=department_id, status=complaint_status
    )


@router.get(
    "/departments/{department_id}/complaint-department-requests",
    response_model=list[DepartmentChangeRequest],
    summary="Move requests waiting on this manager",
)
async def department_change_requests(
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> list[DepartmentChangeRequest]:
    """Open "this isn't ours" requests, for the manager who must answer them.

    Manager-only, where the list above is manager-and-supervisor: a supervisor
    can see the requests they raised in the complaint list's `openRequestId`,
    and the queue itself is an inbox, which is a manager's.
    """
    return service.department_change_requests(client, department_id=department_id)
