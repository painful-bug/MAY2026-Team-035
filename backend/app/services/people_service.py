"""People service: residents, admins and registration review."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.core import tokens
from app.core.formatting import long_date, parse_instant
from app.core.logging import get_logger
from app.domain.common_schemas import Page
from app.domain.people_schemas import (
    AdminSummary,
    ApprovedRegistration,
    RegistrationRequestSummary,
    UpdateResidentRequest,
)
from app.domain.roles import display_role
from app.repositories import dashboard_repository as dash_repo
from app.repositories import people_repository as repo
from supabase import Client

_logger = get_logger(__name__)


def _tower_of(unit_code: str | None) -> str | None:
    """Derive the tower from a flat code ('C-505' -> 'C').

    The frontend renders tower and flat as separate fields but only the full
    code is stored, because storing both invites them to disagree -- which is
    exactly the bug in ``createPendingRequestsSlice`` (see app/domain/units.py).
    """
    if not unit_code or "-" not in unit_code:
        return None
    return unit_code.split("-", 1)[0] or None


def list_admins(client: Client, user_id: str) -> Page[AdminSummary]:
    """All admins of the caller's community."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    rows = repo.list_admins(client, community_id)

    codes = sorted(
        {
            code
            for row in rows
            if (code := (row.get("profiles") or {}).get("apartment_id"))
        }
    )
    code_to_id = dash_repo.map_unit_codes_to_ids(client, community_id, codes)

    items = []
    for row in rows:
        profile = row.get("profiles") or {}
        flat = profile.get("apartment_id")
        items.append(
            AdminSummary(
                id=row["id"],
                profile_id=row["profile_id"],
                name=profile.get("full_name"),
                email=profile.get("email"),
                phone=profile.get("phone"),
                role=row["role"],
                display_role=display_role(row["role"]),
                designation=row.get("designation"),
                flat=flat,
                # 'Admin Office' is a real value the frontend uses for admins who
                # have no flat. It resolves to no unit id, which is correct.
                unit_id=code_to_id.get(flat) if flat else None,
                status=row.get("status", "active"),
                joined_at=parse_instant(row["joined_at"]),
            )
        )

    return Page[AdminSummary](
        items=items,
        total=len(items),
        page=1,
        page_size=len(items),
        has_more=False,
    )


def update_resident(
    client: Client, user_id: str, membership_id: str, body: UpdateResidentRequest
) -> None:
    """Patch a resident's editable fields.

    Spans two tables (``profiles`` and ``community_memberships``) but is NOT an
    RPC, unlike approve/deactivate. The difference is what a partial failure
    costs: here it leaves some fields updated and others not, which the admin can
    see and simply retry. There is no invariant between the two writes. Approving
    a request, by contrast, would leave a request marked approved with no
    invitation -- unrecoverable from the UI.
    """
    community_id = dash_repo.get_caller_community_id(client, user_id)
    # Existence + tenancy check before writing: the RLS policy would reject a
    # cross-community write anyway, but silently, as "0 rows updated".
    member = repo.get_membership(client, community_id, membership_id)

    supplied = body.model_dump(exclude_unset=True)
    profile_fields = {
        key: supplied[key] for key in ("name", "email", "phone") if key in supplied
    }
    # The column is `full_name`; the wire field is `name`.
    if "name" in profile_fields:
        profile_fields["full_name"] = profile_fields.pop("name")

    repo.update_profile_fields(client, member["profile_id"], profile_fields)

    if "designation" in supplied:
        repo.update_membership_fields(
            client,
            community_id,
            membership_id,
            {"designation": supplied["designation"]},
        )


def remove_resident(client: Client, user_id: str, membership_id: str) -> None:
    """Deactivate a resident. Not a delete -- see migration 0012."""
    dash_repo.get_caller_community_id(client, user_id)
    repo.deactivate_membership(client, membership_id)


def list_registration_requests(
    client: Client,
    user_id: str,
    *,
    status: str = "pending",
    page: int = 1,
    page_size: int = 20,
) -> Page[RegistrationRequestSummary]:
    """Page through registration requests."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    offset = (page - 1) * page_size

    rows, total = repo.list_registration_requests(
        client, community_id, status=status, offset=offset, limit=page_size
    )

    items = [
        RegistrationRequestSummary(
            id=row["id"],
            name=row["full_name"],
            email=row.get("email"),
            phone=row["phone"],
            flat=row["requested_unit_code"],
            tower=_tower_of(row["requested_unit_code"]),
            status=row["status"],
            date=long_date(parse_instant(row["created_at"])),
            submitted_at=parse_instant(row["created_at"]),
        )
        for row in rows
    ]

    return Page[RegistrationRequestSummary](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(items) < total,
    )


def approve_registration(
    client: Client, user_id: str, request_id: str
) -> ApprovedRegistration:
    """Approve a request: mark it reviewed and mint an invitation, atomically.

    The plaintext link and code are returned **once** and never stored.
    """
    community_id = dash_repo.get_caller_community_id(client, user_id)
    reviewer = repo.get_membership_id_for_profile(client, community_id, user_id)

    token = tokens.generate_token()
    code = tokens.generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=get_settings().invite_ttl_hours
    )

    result = repo.approve_registration_request(
        client,
        request_id=request_id,
        token_hash=tokens.hash_secret(token),
        code_hash=tokens.hash_secret(code),
        expires_at=expires_at,
        reviewer_membership_id=reviewer,
        created_by=user_id,
    )

    link = f"{get_settings().frontend_base_url.rstrip('/')}/join/{token}"
    _logger.info("Registration request %s approved for flat %s", request_id,
                 result.get("unit_code"))

    return ApprovedRegistration(
        request_id=request_id,
        invitation_id=result["invitation_id"],
        link=link,
        code=code,
        phone=result["phone"],
        flat=result["unit_code"],
        name=result.get("full_name"),
        expires_at=expires_at,
    )


def reject_registration(
    client: Client, user_id: str, request_id: str, reason: str | None
) -> None:
    """Reject a pending request."""
    community_id = dash_repo.get_caller_community_id(client, user_id)
    reviewer = repo.get_membership_id_for_profile(client, community_id, user_id)
    repo.reject_registration_request(
        client, request_id=request_id, reason=reason, reviewer_membership_id=reviewer
    )
