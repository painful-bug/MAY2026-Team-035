"""Resident access-request and administrator-decision API cases."""

import pytest
from fastapi.testclient import TestClient

from app.domain.schemas import AccessRequestCommunity, AccessRequestResponse


def test_api_005_resident_creates_access_request(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import access_requests as access_router

    endpoint = "POST /api/v1/access-requests"
    input_data = {
        "community_id": "community-id",
        "requested_unit_id": "unit-id",
        "requested_relationship": "tenant",
        "phone": "+919876543210",
        "requested_building_text": "C",
        "requested_unit_text": "505",
    }
    expected_output = {
        "status_code": 201,
        "body": {
            "id": "request-id",
            "community": {
                "id": "community-id",
                "name": "Palm Residency",
                "community_type": "apartment",
            },
            "status": "pending",
            "requested_relationship": "tenant",
            "requested_unit_id": "unit-id",
            "requested_building_text": "C",
            "requested_unit_text": "505",
            "applicant_name": "Test Resident",
            "applicant_email": "resident@example.com",
            "applicant_phone_e164": "+919876543210",
            "created_at": None,
            "reviewed_at": None,
            "rejection_reason": None,
        },
    }
    captured_input: dict[str, object] = {}

    def create_request(request: object, principal: object) -> AccessRequestResponse:
        captured_input.update(request.model_dump(mode="json"))
        assert principal.user_id == "resident-profile-id"
        return AccessRequestResponse(
            id="request-id",
            community=AccessRequestCommunity(
                id="community-id",
                name="Palm Residency",
                community_type="apartment",
            ),
            status="pending",
            requested_relationship="tenant",
            requested_unit_id="unit-id",
            requested_building_text="C",
            requested_unit_text="505",
            applicant_name="Test Resident",
            applicant_email="resident@example.com",
            applicant_phone_e164="+919876543210",
        )

    monkeypatch.setattr(access_router.access_request_service, "create", create_request)

    response = resident_api_client.post(
        "/api/v1/access-requests",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/access-requests"
    assert captured_input == input_data
    assert actual_output == expected_output


def test_api_006_admin_approves_access_request(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import access_requests as access_router

    endpoint = "POST /api/v1/admin/access-requests/request-id/approve"
    input_data = {
        "unit_id": "unit-id",
        "relationship": "tenant",
        "unit_code": "C-505",
        "building_code": "C",
    }
    expected_output = {
        "status_code": 200,
        "body": {
            "request_id": "request-id",
            "status": "approved",
            "membership_id": "resident-membership-id",
            "unit_id": "unit-id",
        },
    }
    captured_input: dict[str, object] = {}

    def approve_request(
        request_id: str,
        body: object,
        principal: object,
    ) -> dict[str, str]:
        captured_input.update(body.model_dump(mode="json"))
        assert request_id == "request-id"
        assert principal.user_id == "admin-profile-id"
        return expected_output["body"]

    monkeypatch.setattr(
        access_router.access_request_service,
        "approve",
        approve_request,
    )

    response = admin_api_client.post(
        "/api/v1/admin/access-requests/request-id/approve",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint.endswith("/request-id/approve")
    assert captured_input == input_data
    assert actual_output == expected_output


# ---------------------------------------------------------------------------
# The separate-account rule, met from the administrator's side
#
# `20260812113000_professional_membership_symmetry` refuses a resident
# membership on an account that holds a `service_providers` registration, and
# the approval RPC is one of the two places that refusal lands. It lands on the
# *administrator*, who did nothing wrong and cannot see the applicant's other
# identity -- so what the API says here is the whole of what they get.
# ---------------------------------------------------------------------------


class _RefusedApprovalError(Exception):
    """A postgrest APIError carrying the trigger's SQLSTATE and message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _AdminMembershipQuery:
    """Just enough of the postgrest builder for `_require_active_admin`."""

    data = [{"id": "admin-membership-id", "community_id": "community-id"}]

    def select(self, _: str) -> "_AdminMembershipQuery":
        return self

    def eq(self, _: str, __: object) -> "_AdminMembershipQuery":
        return self

    def is_(self, _: str, __: object) -> "_AdminMembershipQuery":
        return self

    def limit(self, _: int) -> "_AdminMembershipQuery":
        return self

    def execute(self) -> "_AdminMembershipQuery":
        return self


class _ServiceClient:
    def table(self, _: str) -> _AdminMembershipQuery:
        return _AdminMembershipQuery()


def _approval_refused_with(
    monkeypatch: pytest.MonkeyPatch, exc: Exception
) -> None:
    from app.services import access_request_service

    monkeypatch.setattr(access_request_service, "get_service_client", _ServiceClient)
    monkeypatch.setattr(
        access_request_service.access_requests_repository,
        "get",
        lambda _client, _request_id: {
            "id": "request-id",
            "community_id": "community-id",
        },
    )

    def refuse(*_args: object, **_kwargs: object) -> dict:
        raise exc

    monkeypatch.setattr(
        access_request_service.access_requests_repository, "approve", refuse
    )


def test_api_258_approving_a_registered_professional_says_which_rule_refused(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The trigger's own message reaches the administrator, with its own code.

    Before this the approval path answered every database failure with "this
    access request cannot be approved" and the code
    ``access_request_not_pending``, which sends an administrator to look at a
    request that is pending and perfectly fine. The applicant is a registered
    service professional and needs a second account; nothing in the old answer
    could say so.
    """
    _approval_refused_with(
        monkeypatch,
        _RefusedApprovalError(
            "HBSEP",
            "This account is registered as a service professional. Use a "
            "separate account to join a community as a resident, manager or "
            "administrator.",
        ),
    )

    response = admin_api_client.post(
        "/api/v1/admin/access-requests/request-id/approve",
        json={"unit_id": "unit-id", "relationship": "tenant"},
        headers=csrf_headers,
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "professional_account_separate"
    assert "separate account" in body["message"]


def test_api_259_an_unrecognised_approval_failure_keeps_the_generic_answer(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Postgres' own text can quote a row value, so only our codes pass through."""
    _approval_refused_with(
        monkeypatch,
        _RefusedApprovalError("23505", 'duplicate key value violates "secret_idx"'),
    )

    response = admin_api_client.post(
        "/api/v1/admin/access-requests/request-id/approve",
        json={"unit_id": "unit-id", "relationship": "tenant"},
        headers=csrf_headers,
    )

    body = response.json()["error"]
    assert response.status_code == 409
    assert body["code"] == "access_request_not_pending"
    assert "secret_idx" not in body["message"]


class _TableQuery:
    """A postgrest builder that answers with whatever its table was given."""

    def __init__(self, rows: list[dict]) -> None:
        self.data = rows

    def select(self, _: str) -> "_TableQuery":
        return self

    def eq(self, _: str, __: object) -> "_TableQuery":
        return self

    def is_(self, _: str, __: object) -> "_TableQuery":
        return self

    def limit(self, _: int) -> "_TableQuery":
        return self

    def order(self, _: str, **__: object) -> "_TableQuery":
        return self

    def execute(self) -> "_TableQuery":
        return self


class _TablesClient:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self._tables = tables
        self.seen: list[str] = []

    def table(self, name: str) -> _TableQuery:
        self.seen.append(name)
        return _TableQuery(self._tables.get(name, []))


def test_api_260_a_registered_professional_cannot_file_a_join_request(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refused where the person is, not days later in an administrator's hands.

    The membership this request would create is refused by the database, so
    filing it can only ever end one way. Before this the applicant was told
    "pending", waited, and the failure landed on an administrator who can see
    neither the professional registration nor a reason.
    """
    from app.services import access_request_service

    client = _TablesClient(
        {
            "communities": [
                {"id": "community-id", "name": "Palm Residency", "status": "active"}
            ],
            "service_providers": [{"id": "provider-id"}],
        }
    )
    monkeypatch.setattr(access_request_service, "get_service_client", lambda: client)
    monkeypatch.setattr(
        access_request_service.profiles_repository,
        "get_profile",
        lambda _client, _user_id: type(
            "Profile", (), {"full_name": "Ravi Kumar", "phone": None}
        )(),
    )

    response = resident_api_client.post(
        "/api/v1/access-requests",
        json={"community_id": "community-id", "requested_relationship": "tenant"},
        headers=csrf_headers,
    )

    body = response.json()["error"]
    assert response.status_code == 409
    assert body["code"] == "professional_account_separate"
    assert "separate account" in body["message"]
    # Refused before the request row is even considered.
    assert "access_requests" not in client.seen


# ---------------------------------------------------------------------------
# Residence claim on the join flow (2026-08-27 rulings)
#
# Approval now requires a unit: `unit_id`, or a tower/flat text pair the RPC
# finds-or-creates. The service refuses an empty approval before the RPC is
# ever called, and canonicalises the pair with `normalize_unit_code` so the
# documented C-C-505 double-prefix hazard cannot reach the database.
# ---------------------------------------------------------------------------


def _real_approve_service(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Run the real service.approve against stubs; capture the repo call."""
    from app.services import access_request_service

    monkeypatch.setattr(access_request_service, "get_service_client", _ServiceClient)
    monkeypatch.setattr(
        access_request_service.access_requests_repository,
        "get",
        lambda _client, _request_id: {
            "id": "request-id",
            "community_id": "community-id",
        },
    )
    captured_input: dict[str, object] = {}

    def approve(_client: object, **kwargs: object) -> dict:
        captured_input.update(kwargs)
        return {
            "request_id": "request-id",
            "status": "approved",
            "membership_id": "resident-membership-id",
            "unit_id": "created-unit-id",
        }

    monkeypatch.setattr(
        access_request_service.access_requests_repository, "approve", approve
    )
    return captured_input


def test_api_261_approving_without_any_unit_is_refused_before_the_rpc(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = "POST /api/v1/admin/access-requests/request-id/approve"
    input_data: dict[str, object] = {}
    expected_output = {"status_code": 422, "code": "approval_requires_unit"}
    captured_input = _real_approve_service(monkeypatch)

    response = admin_api_client.post(
        "/api/v1/admin/access-requests/request-id/approve",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert endpoint.endswith("/request-id/approve")
    assert actual_output == expected_output
    # The refusal happened in the service, not the database.
    assert captured_input == {}


def test_api_262_blank_unit_text_counts_as_no_unit(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace is not a residence."""
    captured_input = _real_approve_service(monkeypatch)

    response = admin_api_client.post(
        "/api/v1/admin/access-requests/request-id/approve",
        json={"unit_code": "   ", "building_code": "C"},
        headers=csrf_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "approval_requires_unit"
    assert captured_input == {}


def test_api_263_approval_canonicalises_the_tower_flat_pair(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """('C', 'C-505') reaches the repository as 'C-505', never 'C-C-505'."""
    endpoint = "POST /api/v1/admin/access-requests/request-id/approve"
    input_data = {"unit_code": "C-505", "building_code": "C"}
    expected_output = {
        "status_code": 200,
        "body": {
            "request_id": "request-id",
            "status": "approved",
            "membership_id": "resident-membership-id",
            "unit_id": "created-unit-id",
        },
    }
    captured_input = _real_approve_service(monkeypatch)

    response = admin_api_client.post(
        "/api/v1/admin/access-requests/request-id/approve",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {"status_code": response.status_code, "body": response.json()}

    assert endpoint.endswith("/request-id/approve")
    assert actual_output == expected_output
    assert captured_input == {
        "request_id": "request-id",
        "reviewer_profile_id": "admin-profile-id",
        "unit_id": None,
        "relationship": None,
        "unit_code": "C-505",
        "building_code": "C",
    }


def test_api_264_reject_and_blacklist_answer_with_the_typed_decision_shape(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All three decisions share one response model; the RPCs that return only
    `{request_id, status}` still serialise the optional fields as null."""
    from app.api.v1.routers import access_requests as access_router

    expected_output = {
        "status_code": 200,
        "body": {
            "request_id": "request-id",
            "status": "rejected",
            "membership_id": None,
            "unit_id": None,
        },
    }

    for action, status in (("reject", "rejected"), ("blacklist", "blacklisted")):
        monkeypatch.setattr(
            access_router.access_request_service,
            action,
            lambda _rid, _body, _principal, status=status: {
                "request_id": "request-id",
                "status": status,
            },
        )
        response = admin_api_client.post(
            f"/api/v1/admin/access-requests/request-id/{action}",
            json={"reason": "Not a resident of this community."},
            headers=csrf_headers,
        )
        expected_output["body"]["status"] = status
        actual_output = {"status_code": response.status_code, "body": response.json()}
        assert actual_output == expected_output
