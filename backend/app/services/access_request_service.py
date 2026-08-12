"""Resident join-request lifecycle and community-admin decisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.pg_errors import custom_error
from app.core.supabase_client import get_service_client
from app.domain.schemas import (
    AccessRequestCommunity,
    AccessRequestListResponse,
    AccessRequestResponse,
    ApproveAccessRequest,
    BlacklistAccessRequest,
    CreateAccessRequest,
    Principal,
    RejectAccessRequest,
)
from app.repositories import access_requests_repository, profiles_repository


def _normal_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().replace(" ", "").replace("-", "")
    if (
        not normalized.startswith("+")
        or not normalized[1:].isdigit()
        or not 8 <= len(normalized) <= 20
    ):
        raise ValidationError(
            "Phone number must use E.164 format.", code="validation_failed"
        )
    return normalized


def _summary(row: dict) -> AccessRequestResponse:
    community = row.get("communities") or {}
    if isinstance(community, list):
        community = community[0] if community else {}
    return AccessRequestResponse(
        id=row["id"],
        community=AccessRequestCommunity(
            id=row["community_id"], name=community.get("name", "Community")
        ),
        status=row["status"],
        requested_relationship=row["requested_relationship"],
        requested_unit_id=row.get("requested_unit_id"),
        applicant_name=row.get("applicant_name"),
        applicant_email=row.get("applicant_email"),
        applicant_phone_e164=row.get("applicant_phone_e164"),
        created_at=row.get("created_at"),
        reviewed_at=row.get("reviewed_at"),
        rejection_reason=row.get("rejection_reason"),
    )


def _require_active_admin(*, profile_id: str, community_id: str) -> dict:
    rows = (
        get_service_client()
        .table("community_memberships")
        .select("id, community_id")
        .eq("profile_id", profile_id)
        .eq("community_id", community_id)
        .eq("role", "admin")
        .eq("status", "active")
        .is_("ended_at", None)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise AuthorizationError(
            "You do not administer this community.", code="community_role_required"
        )
    return rows[0]


def create(request: CreateAccessRequest, principal: Principal) -> AccessRequestResponse:
    # Google OAuth has already authenticated the account.  The join request is
    # bound to that authenticated identity, not to Supabase's optional email
    # confirmation claim (which is not consistently present in Google JWTs).
    if not principal.email:
        raise ValidationError(
            "Your sign-in account must provide an email address.",
            code="identity_email_missing",
        )
    service = get_service_client()
    try:
        profile = profiles_repository.get_profile(service, principal.user_id)
    except NotFoundError:
        profile = profiles_repository.upsert_profile(
            service,
            user_id=principal.user_id,
            full_name=None,
            phone=None,
            email=principal.email,
        )
    community_rows = (
        service.table("communities")
        .select("id, name, status")
        .eq("id", request.community_id)
        .eq("status", "active")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not community_rows:
        raise NotFoundError("Community not found.", code="community_not_found")

    # The separate-account rule, at the point the person is standing in.
    #
    # The database refuses the membership this request would eventually create
    # (`20260812113000_professional_membership_symmetry`), so without this the
    # request is filed, sits in a queue for days, and fails in an
    # administrator's hands -- who can neither see the applicant's professional
    # registration nor do anything about it but reject. The applicant learns
    # nothing. Same code and same wording as the refusal downstream, so the two
    # cannot drift into two different explanations of one rule.
    professional = (
        service.table("service_providers")
        .select("id")
        .eq("profile_id", principal.user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if professional:
        raise ConflictError(
            "This account is registered as a service professional. Use a "
            "separate account to join a community as a resident.",
            code="professional_account_separate",
        )

    existing_membership = (
        service.table("community_memberships")
        .select("id")
        .eq("profile_id", principal.user_id)
        .eq("community_id", request.community_id)
        .eq("status", "active")
        .is_("ended_at", None)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing_membership:
        raise ConflictError(
            "You already belong to this community.", code="membership_already_active"
        )

    blocked = (
        service.table("blacklisted_residents")
        .select("id")
        .eq("community_id", request.community_id)
        .eq("profile_id", principal.user_id)
        .is_("revoked_at", None)
        .limit(1)
        .execute()
        .data
        or []
    )
    if blocked:
        raise NotFoundError("Community not found.", code="community_not_found")

    existing = access_requests_repository.find_pending(
        service, profile_id=principal.user_id, community_id=request.community_id
    )
    if existing:
        raise ConflictError(
            "A request to join this community is already pending.",
            code="access_request_pending",
        )

    recent_rejection = next(
        (
            row for row in access_requests_repository.list_for_profile(service, principal.user_id)
            if row.get("community_id") == request.community_id and row.get("status") == "rejected"
            and row.get("reviewed_at")
            and datetime.fromisoformat(str(row["reviewed_at"]).replace("Z", "+00:00")) > datetime.now(UTC) - timedelta(hours=24)
        ),
        None,
    )
    if recent_rejection:
        raise ConflictError(
            "Your previous application was rejected. You can apply again after 24 hours.",
            code="access_request_rejected_cooldown",
        )

    if request.requested_unit_id:
        units = (
            service.table("units")
            .select("id")
            .eq("id", request.requested_unit_id)
            .eq("community_id", request.community_id)
            .eq("status", "active")
            .limit(1)
            .execute()
            .data
            or []
        )
        if not units:
            raise ValidationError(
                "The selected unit does not belong to this community.",
                code="invalid_requested_unit",
            )

    payload = {
        "community_id": request.community_id,
        "requested_unit_id": request.requested_unit_id,
        "applicant_profile_id": principal.user_id,
        "applicant_name": profile.full_name or principal.email,
        "applicant_email": principal.email.strip().casefold(),
        "applicant_phone_e164": _normal_phone(request.phone or profile.phone),
        "requested_relationship": request.requested_relationship,
        "status": "pending",
    }
    try:
        row = access_requests_repository.insert(service, payload)
    except Exception as exc:  # pragma: no cover - provider-specific duplicate error
        duplicate = access_requests_repository.find_pending(
            service, profile_id=principal.user_id, community_id=request.community_id
        )
        if duplicate:
            raise ConflictError(
                "A request to join this community is already pending.",
                code="access_request_pending",
            ) from exc
        raise
    row["communities"] = {"name": community_rows[0]["name"]}
    return _summary(row)


def mine(principal: Principal) -> AccessRequestListResponse:
    rows = access_requests_repository.list_for_profile(
        get_service_client(), principal.user_id
    )
    return AccessRequestListResponse(items=[_summary(row) for row in rows])


def withdraw(request_id: str, principal: Principal) -> AccessRequestResponse:
    row = access_requests_repository.withdraw(
        get_service_client(), request_id=request_id, profile_id=principal.user_id
    )
    if row is None:
        raise ConflictError(
            "This access request cannot be withdrawn.",
            code="access_request_not_pending",
        )
    return _summary(row)


def list_for_admin(
    principal: Principal, *, status: str, limit: int
) -> AccessRequestListResponse:
    service = get_service_client()
    memberships = (
        service.table("community_memberships")
        .select("community_id")
        .eq("profile_id", principal.user_id)
        .eq("role", "admin")
        .eq("status", "active")
        .is_("ended_at", None)
        .order("is_default_community", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not memberships:
        raise AuthorizationError(
            "Administrator access is required.", code="community_role_required"
        )
    rows = access_requests_repository.list_for_community(
        service,
        community_id=memberships[0]["community_id"],
        status=status,
        limit=min(max(limit, 1), 100),
    )
    return AccessRequestListResponse(items=[_summary(row) for row in rows])


def approve(request_id: str, body: ApproveAccessRequest, principal: Principal) -> dict:
    service = get_service_client()
    request = access_requests_repository.get(service, request_id)
    if request is None:
        raise NotFoundError(
            "Access request not found.", code="access_request_not_found"
        )
    _require_active_admin(
        profile_id=principal.user_id, community_id=request["community_id"]
    )
    try:
        return access_requests_repository.approve(
            service,
            request_id=request_id,
            reviewer_profile_id=principal.user_id,
            unit_id=body.unit_id,
            relationship=body.relationship,
        )
    except Exception as exc:  # provider error text is unstable
        # Our own SQLSTATEs carry a message written for the caller, and one of
        # them now says something this fallback cannot: the applicant is a
        # registered service professional, so the membership trigger refuses
        # the resident row this approval would create. An administrator told
        # only "this access request cannot be approved" would go looking at the
        # request, where there is nothing wrong.
        refusal = custom_error(exc) or ConflictError(
            "This access request cannot be approved.",
            code="access_request_not_pending",
        )
        raise refusal from exc


def reject(request_id: str, body: RejectAccessRequest, principal: Principal) -> dict:
    service = get_service_client()
    request = access_requests_repository.get(service, request_id)
    if request is None:
        raise NotFoundError(
            "Access request not found.", code="access_request_not_found"
        )
    _require_active_admin(
        profile_id=principal.user_id, community_id=request["community_id"]
    )
    try:
        return access_requests_repository.reject(
            service,
            request_id=request_id,
            reviewer_profile_id=principal.user_id,
            reason=body.reason.strip(),
        )
    except Exception as exc:  # pragma: no cover - provider error text is unstable
        raise ConflictError(
            "This access request cannot be rejected.",
            code="access_request_not_pending",
        ) from exc


def blacklist(request_id: str, body: BlacklistAccessRequest, principal: Principal) -> dict:
    service = get_service_client()
    request = access_requests_repository.get(service, request_id)
    if request is None:
        raise NotFoundError("Access request not found.", code="access_request_not_found")
    _require_active_admin(profile_id=principal.user_id, community_id=request["community_id"])
    try:
        return access_requests_repository.blacklist(
            service, request_id=request_id, reviewer_profile_id=principal.user_id, reason=body.reason.strip()
        )
    except Exception as exc:  # pragma: no cover - provider error is intentionally hidden
        raise ConflictError("This access request cannot be blacklisted.", code="access_request_not_pending") from exc
