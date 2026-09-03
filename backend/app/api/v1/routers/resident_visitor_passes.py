"""The resident's visitor passes.

There is no admin counterpart to this router, and no `routers/visitors.py`: the
visitor surface has never had a backend at all. The gate's half — presenting a
pass, checking a guest in, raising an approval request when somebody arrives
unannounced — belongs to security software that does not exist in this
repository. Both halves are named here so the gap is a stated boundary rather
than something a reader has to infer from six routes that stop short.

**Every route is the caller's own pass.** No role check beyond an active
membership: a resident, a manager and an admin all have visitors, and the passes
they see are the ones they raised.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.admin_deps import require_csrf_unsafe
from app.api.deps import get_active_membership, get_request_client
from app.domain.common_schemas import Page
from app.domain.resident_visitor_schemas import (
    CreateVisitorPassRequest,
    VisitorPass,
    VisitorPassCreated,
)
from app.domain.schemas import MembershipContext
from app.services import resident_visitor_passes_service as service
from supabase import Client

router = APIRouter(tags=["visitors"], dependencies=[Depends(require_csrf_unsafe)])


@router.get(
    "/visitor-passes",
    response_model=Page[VisitorPass],
    summary="List my visitor passes",
)
def list_my_visitor_passes(
    view: str | None = Query(
        None,
        description="`current` | `history`. Omitted returns both.",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> Page[VisitorPass]:
    """The caller's own passes, newest first.

    `current` is a pass still ahead of them — open, and not past its window.
    `history` is everything else. The split is computed in
    `visitor_pass_overview` rather than from a status list here, so it cannot
    drift from the transitions the RPC allows.

    **No security code and no pass token on any row.** They are returned once, by
    `POST /visitor-passes`, and the view this reads does not carry the columns
    they were hashed into.
    """
    return service.list_mine(
        client,
        membership_id=membership.id,
        view=view,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/visitor-passes",
    response_model=VisitorPassCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Pre-approve a visitor",
)
def create_visitor_pass(
    body: CreateVisitorPassRequest,
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> VisitorPassCreated:
    """Mint a pass for an expected visitor. **Requires an active membership.**

    **`securityCode` and `passToken` appear in this response and nowhere else.**
    Both are stored as SHA-256 hashes; the plaintext is generated in the API,
    never sent to the database, and cannot be recovered by any endpoint. A
    resident who loses the code issues a new pass — the same trade the invite
    flow already makes, and the correct one for something that opens a gate.

    **The validity window is not accepted from the client.** It runs from
    `expectedAt` (or now) for the community's `visitorCodeTtlMinutes` — the
    settings value that has been written since `0018` and read by nothing until
    this endpoint. A resident who could choose the window could mint a pass valid
    for a year.

    The status is `Expected`, not `Approved`: a pre-approved visitor has been
    announced, not approved by anybody. `Approved` is what answering a gate
    request produces, and a gate log needs to keep those apart.
    """
    return service.create_pass(client, membership_id=membership.id, body=body)


@router.get(
    "/visitor-passes/{pass_id}",
    response_model=VisitorPass,
    summary="One of my visitor passes",
)
def get_visitor_pass(
    pass_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> VisitorPass:
    """One pass — the QR screen's read.

    A pass belonging to someone else is a `404`, identical to one that does not
    exist. **The QR payload is not reconstructible from this response**: the
    token it embeds was returned once at creation, so a client that did not keep
    it cannot rebuild the code from a later read.
    """
    return service.get_mine(
        client, membership_id=membership.id, pass_id=pass_id
    )


@router.post(
    "/visitor-passes/{pass_id}/approve",
    response_model=VisitorPass,
    summary="Approve a gate request",
)
def approve_visitor_pass(
    pass_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> VisitorPass:
    """Let in a visitor who arrived unannounced.

    Only from `Pending Approval` — the state the **gate** puts a pass in when
    somebody turns up asking for a flat. No endpoint in this repository creates
    one; the security app does, and it does not exist yet. This route is built
    now because it answers `visitor.approval_requested`, which is `US-2.1`'s
    recorded pain point, and a reply is the wrong thing to build after the
    notification that prompts it.

    Notifies the community's `security` role, and its admins so that a community
    with nobody on security is not told nothing at all.
    """
    return service.decide(
        client,
        membership_id=membership.id,
        pass_id=pass_id,
        decision="approve",
    )


@router.post(
    "/visitor-passes/{pass_id}/reject",
    response_model=VisitorPass,
    summary="Reject a gate request",
)
def reject_visitor_pass(
    pass_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> VisitorPass:
    """Turn away a visitor who arrived unannounced. Same states as `/approve`."""
    return service.decide(
        client,
        membership_id=membership.id,
        pass_id=pass_id,
        decision="reject",
    )


@router.post(
    "/visitor-passes/{pass_id}/cancel",
    response_model=VisitorPass,
    summary="Cancel a visitor pass",
)
def cancel_visitor_pass(
    pass_id: str = Path(...),
    membership: MembershipContext = Depends(get_active_membership),
    client: Client = Depends(get_request_client),
) -> VisitorPass:
    """Withdraw a pass that has not been used.

    **A pass whose guest is already inside cannot be cancelled** — `409`,
    `pass_already_used`. Once someone is through the gate, *cancel* is a
    physical-world operation and no database write performs it; a pass that
    flipped back would leave a record disagreeing with what happened, and the
    record is all anyone will have later. `PO`, 2026-08-04.

    The refusal is in the RPC rather than here, so it holds for every future
    caller and not only for this route.
    """
    return service.decide(
        client,
        membership_id=membership.id,
        pass_id=pass_id,
        decision="cancel",
    )
