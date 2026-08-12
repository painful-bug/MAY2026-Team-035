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
    }
    expected_output = {
        "status_code": 201,
        "body": {
            "id": "request-id",
            "community": {"id": "community-id", "name": "Palm Residency"},
            "status": "pending",
            "requested_relationship": "tenant",
            "requested_unit_id": "unit-id",
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
            ),
            status="pending",
            requested_relationship="tenant",
            requested_unit_id="unit-id",
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
    input_data = {"unit_id": "unit-id", "relationship": "tenant"}
    expected_output = {
        "status_code": 200,
        "body": {
            "request_id": "request-id",
            "status": "approved",
            "membership_id": "resident-membership-id",
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
