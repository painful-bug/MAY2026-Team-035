"""Notices, the flat, and the contact directory.

Three reads and one write, all of them things a resident does on a screen that
currently talks to a local store or, in the directory's case, to five phone
numbers typed into a component.

**No role guard on any route.** A manager living in the community has a flat, a
notice board and the same need to ring the plumber.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_active_membership, get_request_client
from app.domain.common_schemas import Page
from app.domain.resident_home_schemas import (
    AddHouseholdPhoneRequest,
    HouseholdMember,
    ManagementContact,
    Notice,
)
from app.domain.schemas import MembershipContext
from app.services import resident_home_service as service
from supabase import Client

router = APIRouter(tags=["resident-home"], dependencies=[Depends(require_csrf_unsafe)])


@router.get("/notices", response_model=Page[Notice], summary="Published notices")
def list_notices(
    category: str | None = Query(None, description="Exact category match."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> Page[Notice]:
    """The community's published notices, newest first.

    **Drafts never appear.** A notice with no `publishedAt` is one an admin is
    still writing, and it is excluded by the view *and* by the policy `0033`
    adds — two independent reasons, because half-written words reaching residents
    is not a failure worth having one guard against.

    `urgency` is `Info` | `Important` | `Urgent`, title-cased here because that is
    what the screen renders; the column stores lower case.

    There is no `POST` here. Posting a notice is an admin action and already
    exists as `POST /notices` (§12.1).
    """
    return service.list_notices(
        client,
        community_id=membership.community_id,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/me/household",
    response_model=list[HouseholdMember],
    summary="Who is registered to my flat",
)
def get_household(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> list[HouseholdMember]:
    """Everyone and every number registered to the caller's flat.

    Two kinds of row, and `source` says which. A `member` is a person with an
    account and a membership; a `contact` is a phone number somebody in the flat
    added so the gate and the office have it — it grants nothing, and its holder
    has no account.

    A caller with no residency gets an empty list, not an error: staff have a
    membership and no flat, and *nobody* is a legitimate answer.

    Not paginated. A household is not a quantity that needs a page control.
    """
    return service.get_household(client, membership_id=membership.id)


@router.post(
    "/me/household/phones",
    response_model=list[HouseholdMember],
    summary="Add a number to my flat",
)
def add_household_phone(
    body: AddHouseholdPhoneRequest,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> list[HouseholdMember]:
    """Register another phone number against the caller's own flat.

    **The flat is not in the request.** It is resolved from the caller's own
    residency inside the RPC — a unit id in a body is a unit id somebody can
    change, and the point of this endpoint is that a resident may edit their own
    flat's list without an admin and nobody else's at all.

    Adding the same number twice updates the name rather than failing: a
    correction is the likeliest reason anyone repeats it.

    Returns the whole list, because that is what the screen renders and a client
    merging one row into it can merge it wrongly.
    """
    return service.add_household_phone(client, membership_id=membership.id, body=body)


@router.get(
    "/directory/contacts",
    response_model=list[ManagementContact],
    summary="Management and emergency contacts",
)
def list_contacts(
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> list[ManagementContact]:
    """The numbers a resident should be able to ring.

    Served from `departments` (§5.6) rather than a table of its own, so it stays
    current as a side effect of admin work that already happens. `US-2.9` asks
    for a directory somebody can trust and names the failure mode as a list
    nobody updates — which is precisely what five numbers hard-coded in
    `Profile.jsx` are.

    `category` is the free text an admin typed on the department. **There is no
    emergency flag**: deciding which categories mean *emergency* by matching
    strings would be a classification invented in the backend and wrong the first
    time somebody writes "Emergencies".
    """
    return service.list_contacts(client, community_id=membership.community_id)
