"""Creating a manager or supervisor, and admitting them at sign-in.

This surface has no acceptance step, no token and nothing delivered, so the
usual assurances are absent: nothing bounces when the address is wrong, and
nobody confirms. What is left to test divides in two.

**The API half** — that a rank outside `manager|supervisor` never reaches the
database, that the email travels unmodified because it is the matching key
rather than a delivery address, and that claimed invitations stay in the list.

**The seam half** (`api_215` onward) — the more important one. A claim writes a
membership for somebody who had none, keyed on an email. Three properties keep
that from being a way in for the wrong person, and all three are assertions
about what the *Python* does rather than what the RPC returns:

* the email comes from `verified_identity`, never from the profile row or
  anything a client sent;
* the claim is attempted on **every** session read (`api_336`). It was attempted
  only when the caller held no membership until 2026-08-21, and that guard was a
  gap rather than an optimisation: a person who already belonged to a community
  never reached the claim, so their pending invitation was neither applied nor
  refused — it waited, invisibly, while the department that sent it saw
  `pending` forever;
* a failure inside it does not fail the session.

The RPC itself is Postgres and is stubbed here, so none of these tests prove a
membership is created correctly. They prove the API never offers a path to the
wrong one.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.schemas import Principal, Profile
from app.repositories import profiles_repository
from app.services import auth_service, hiring_service

DEPARTMENT = "/api/v1/departments/department-id"
INVITATIONS = f"{DEPARTMENT}/staff-invitations"


def invitation_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "invitation-id",
        "department_id": "department-id",
        "invitee_email": "manager@example.com",
        "invitee_name": "Priya Nair",
        "invitee_phone_e164": "+919876543210",
        "rank": "manager",
        "job_title": "Department manager",
        "status": "pending",
        "claimed_at": None,
        "created_at": "2026-08-11T09:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def invitations(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    captured: dict = {"rows": [invitation_row()], "calls": []}

    def fake_list(
        client: Any, *, department_id: str, status: str | None
    ) -> list[dict[str, Any]]:
        captured["listed"] = {"department_id": department_id, "status": status}
        return captured["rows"]

    def fake_invite(client: Any, **kwargs: Any) -> str:
        captured["calls"].append("invite")
        captured["invited"] = kwargs
        return "invitation-id"

    def fake_revoke(client: Any, *, invitation_id: str) -> None:
        captured["calls"].append("revoke")
        captured["revoked"] = invitation_id

    def fake_update(client: Any, **kwargs: Any) -> None:
        captured["calls"].append("update")
        captured["updated"] = kwargs

    repo = hiring_service.repo
    monkeypatch.setattr(repo, "list_staff_invitations", fake_list)
    monkeypatch.setattr(repo, "invite_staff_member", fake_invite)
    monkeypatch.setattr(repo, "revoke_staff_invitation", fake_revoke)
    monkeypatch.setattr(repo, "update_staff_invitation", fake_update)
    yield captured


def test_api_210_the_email_reaches_the_database_unmodified(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """The address is the matching key, not a delivery address.

    Whoever signs in with it is admitted to this department. Any normalisation
    the API did on the way in would have to be repeated exactly at sign-in, in a
    different language, against a different value -- so the API does none, and
    the RPC's `lower(btrim(...))` is the single place it happens.
    """
    admin_api_client.post(
        INVITATIONS,
        json={
            "email": "Manager@Example.COM",
            "name": "Priya Nair",
            "rank": "manager",
        },
        headers=csrf_headers,
    )
    assert invitations["invited"]["email"] == "Manager@Example.COM"
    assert invitations["invited"]["department_id"] == "department-id"


def test_api_211_the_response_is_read_back_not_echoed(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """What comes back is what will be matched against, not what was typed.

    The RPC lowercases and trims. Echoing the request would show an
    administrator `Manager@Example.COM` while the database waits for
    `manager@example.com` -- and on this endpoint that difference is the entire
    feature, because nothing else will ever tell them which one is real.
    """
    response = admin_api_client.post(
        INVITATIONS,
        json={
            "email": "Manager@Example.COM",
            "name": "Priya Nair",
            "rank": "manager",
        },
        headers=csrf_headers,
    )
    assert response.status_code == 201
    assert response.json()["email"] == "manager@example.com"


def test_api_212_member_is_not_an_invitable_rank(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """`member` is reached only by hiring a registered service provider.

    Allowing it here would rebuild the typed-in technician the department form
    just removed, by a different door.
    """
    response = admin_api_client.post(
        INVITATIONS,
        json={"email": "x@example.com", "name": "X", "rank": "member"},
        headers=csrf_headers,
    )
    assert response.status_code == 422
    assert invitations["calls"] == []


def test_api_213_claimed_invitations_stay_in_the_list(
    admin_api_client: TestClient, invitations: dict
) -> None:
    """An administrator needs to know the manager they created has arrived.

    A list that dropped each person at the moment they signed in would look
    identical whether somebody was still expected or had been working a month --
    and "still pending after two weeks" is the only signal a mistyped address
    ever produces.
    """
    invitations["rows"] = [
        invitation_row(),
        invitation_row(
            id="claimed-id",
            invitee_email="supervisor@example.com",
            rank="supervisor",
            status="claimed",
            claimed_at="2026-08-12T08:00:00Z",
        ),
    ]
    body = admin_api_client.get(INVITATIONS).json()
    assert [row["status"] for row in body] == ["pending", "claimed"]
    assert body[1]["claimedAt"] is not None


def test_api_214_a_resident_cannot_provision_leadership(
    resident_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """This endpoint mints a membership for somebody who has none.

    It is the single most consequential write on the department surface, and
    the router guard is the first of the two things standing in front of it.
    """
    response = resident_api_client.post(
        INVITATIONS,
        json={"email": "x@example.com", "name": "X", "rank": "manager"},
        headers=csrf_headers,
    )
    assert response.status_code == 403
    assert invitations["calls"] == []


def test_api_241_a_mistyped_address_can_be_corrected(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """The correction is the whole answer to this surface's one failure mode.

    Nothing is mailed, so a wrong address produces no bounce -- only an
    invitation that never gets claimed. This is what an administrator does once
    the pending list has made that visible.
    """
    response = admin_api_client.patch(
        f"{INVITATIONS}/invitation-id",
        json={"email": "correct@example.com"},
        headers=csrf_headers,
    )
    assert response.status_code == 200
    assert invitations["updated"]["email"] == "correct@example.com"
    assert invitations["updated"]["invitation_id"] == "invitation-id"


def test_api_242_an_omitted_field_is_left_alone_not_cleared(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """`None` reaches the RPC, which reads it as "leave alone".

    This is the difference between a PATCH and a PUT and it matters here for a
    concrete reason: the form that fixes an email is the same form that carries
    the job title, and a caller sending only the field they changed must not
    silently blank the rest. The nulls are sent rather than omitted so that the
    Python and the SQL agree on what absence means.
    """
    admin_api_client.patch(
        f"{INVITATIONS}/invitation-id",
        json={"email": "correct@example.com"},
        headers=csrf_headers,
    )
    updated = invitations["updated"]
    assert updated["name"] is None
    assert updated["rank"] is None
    assert updated["phone"] is None
    assert updated["job_title"] is None


def test_api_243_the_correction_is_read_back_not_echoed(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """Same reason as `api_211`, and more pointed.

    The purpose of this call is to answer "is the address right now?". Echoing
    the request would answer "is the address what I just typed?", which the
    administrator already knows.
    """
    invitations["rows"] = [invitation_row(invitee_email="correct@example.com")]
    response = admin_api_client.patch(
        f"{INVITATIONS}/invitation-id",
        json={"email": "Correct@Example.COM"},
        headers=csrf_headers,
    )
    assert response.json()["email"] == "correct@example.com"


def test_api_244_the_department_cannot_be_moved(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """A department in the body would be an authorization hole, not a field.

    `can_manage_department` is checked against the invitation's *current*
    department, so honouring a new one would let the manager of department A
    mint staff into department B. Pydantic's default `extra='ignore'` means a
    client sending it is not refused -- it is simply not listened to, which is
    the safe half of that default and worth pinning down.
    """
    admin_api_client.patch(
        f"{INVITATIONS}/invitation-id",
        json={"email": "x@example.com", "departmentId": "somebody-elses"},
        headers=csrf_headers,
    )
    assert "department_id" not in invitations["updated"]


def test_api_245_a_resident_cannot_correct_an_invitation(
    resident_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """Editing the address is editing who gets admitted.

    It carries exactly the consequence of creating the invitation, so it is
    guarded exactly the same -- the router refuses before the RPC is reached.
    """
    response = resident_api_client.patch(
        f"{INVITATIONS}/invitation-id",
        json={"email": "attacker@example.com"},
        headers=csrf_headers,
    )
    assert response.status_code == 403
    assert invitations["calls"] == []


# ---------------------------------------------------------------------------
# The claim seam
# ---------------------------------------------------------------------------


@pytest.fixture
def seam(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """Stub everything `_claim_staff_invitations` touches, recording the call."""
    captured: dict = {"claimed_with": None, "claim_result": [{"membership_id": "m"}]}

    class _RPC:
        def __init__(self, name: str, params: dict) -> None:
            self.name, self.params = name, params

        def execute(self) -> Any:
            captured["claimed_with"] = self.params
            result = captured["claim_result"]
            if isinstance(result, Exception):
                raise result
            return type("R", (), {"data": result})()

    class _Service:
        def rpc(self, name: str, params: dict) -> _RPC:
            return _RPC(name, params)

    monkeypatch.setattr(auth_service, "get_service_client", lambda: _Service())
    monkeypatch.setattr(
        auth_service,
        "verified_identity",
        lambda token: Principal(
            user_id="profile-id",
            email="verified@example.com",
            email_verified=True,
            full_name="Priya Nair",
        ),
    )
    yield captured


def signed_in_profile(**overrides: Any) -> Profile:
    """A profile shaped the way `get_session_context` actually holds one.

    Built through `profiles_repository._to_profile`, the one mapper both
    branches of the session read go through, rather than hand-assembled -- so
    the column names (`display_email`, `phone_e164`) and the model field names
    (`email`, `phone`) stay each other's problem and not this file's.

    These three tests used to pass a bare `dict` here. That is what let the
    claim read `profile.get("email")` on a Pydantic model for three commits
    without a single failure: the seam under test was the only caller that ever
    sent a dict, and it was a test.
    """
    row: dict[str, Any] = {
        "id": "profile-id",
        "full_name": "Priya Nair",
        "phone_e164": "+919876543210",
        "display_email": "verified@example.com",
        "is_active": True,
    }
    row.update(overrides)
    return profiles_repository._to_profile(row)


def test_api_215_the_claim_uses_the_verified_email_not_the_profile_row(
    seam: dict,
) -> None:
    """The email IS the authorization, so it must come from GoTrue.

    `profiles.display_email` is an ordinary table. Trusting it would make a row
    a credential -- anything able to write that column could admit itself to any
    department that had been provisioned for that address.
    """
    claimed = auth_service._claim_staff_invitations(
        signed_in_profile(display_email="attacker-controlled@example.com"),
        Principal(
            user_id="profile-id",
            email="verified@example.com",
            email_verified=True,
            full_name="Priya Nair",
        ),
        "access-token",
    )
    assert claimed is True
    assert seam["claimed_with"] == {
        "p_profile_id": "profile-id",
        "p_email": "verified@example.com",
    }


def test_api_216_a_failed_claim_does_not_fail_the_session(seam: dict) -> None:
    """Claiming is an enhancement to a session that is already valid.

    Somebody provisioned who meets a database error should land on the account
    page and be admitted on their next sign-in -- not be refused a session they
    are entitled to, which is what raising here would do to every request they
    make.
    """
    seam["claim_result"] = RuntimeError("connection reset")
    claimed = auth_service._claim_staff_invitations(
        signed_in_profile(),
        Principal(
            user_id="profile-id",
            email="verified@example.com",
            email_verified=True,
            full_name="Priya Nair",
        ),
        "access-token",
    )
    assert claimed is False


def test_api_217_nothing_to_claim_reports_nothing(seam: dict) -> None:
    """An empty result must not read as a claim.

    `get_session_context` re-reads memberships only when this returns True. A
    truthy empty list would make every membership-less sign-in run the
    membership query twice, forever.
    """
    seam["claim_result"] = []
    assert (
        auth_service._claim_staff_invitations(
            signed_in_profile(),
            Principal(
                user_id="profile-id",
                email="verified@example.com",
                email_verified=True,
                full_name="Priya Nair",
            ),
            "access-token",
        )
        is False
    )


# ---------------------------------------------------------------------------
# The whole session read, with the objects the session read actually holds
# ---------------------------------------------------------------------------


class _Rows:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _SessionQuery:
    """The slice of the PostgREST builder `get_session_context` uses.

    ``rows`` is a callable, not a list: the membership table has to answer
    differently before and after the claim, which is the behaviour the whole
    re-read exists for.
    """

    def __init__(self, rows: Any) -> None:
        self._rows = rows

    def select(self, *_: Any, **__: Any) -> _SessionQuery:
        return self

    def eq(self, *_: Any) -> _SessionQuery:
        return self

    def is_(self, *_: Any) -> _SessionQuery:
        return self

    def in_(self, *_: Any) -> _SessionQuery:
        return self

    def order(self, *_: Any, **__: Any) -> _SessionQuery:
        return self

    def limit(self, *_: Any) -> _SessionQuery:
        return self

    def execute(self) -> _Rows:
        return _Rows(list(self._rows()))


class _SessionService:
    """A service client where the claim RPC is what creates the membership."""

    MEMBERSHIP: dict[str, Any] = {
        "id": "membership-id",
        "community_id": "community-id",
        "role": "manager",
        "department_id": "department-id",
        "is_default_community": True,
    }

    def __init__(self) -> None:
        self.claimed_with: dict[str, Any] | None = None
        self.tables: list[str] = []

    def _rows_for(self, name: str) -> list[dict[str, Any]]:
        if name == "community_memberships":
            return [self.MEMBERSHIP] if self.claimed_with else []
        if name == "departments":
            return [{"kind": "service"}]
        return []

    def table(self, name: str) -> _SessionQuery:
        self.tables.append(name)
        return _SessionQuery(lambda: self._rows_for(name))

    def rpc(self, name: str, params: dict[str, Any]) -> Any:
        service = self

        class _RPC:
            def execute(self) -> _Rows:
                service.claimed_with = params
                return _Rows([{"membership_id": "membership-id"}])

        return _RPC()


def test_api_261_the_provisioned_manager_is_admitted_by_the_session_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The claim, called the way production calls it -- with a `Profile`.

    `api_215`-`api_217` hand `_claim_staff_invitations` its argument directly,
    so they were free to invent its shape, and they invented a dict. The only
    real caller is `get_session_context`, which holds whatever
    `profiles_repository` returns, and that has always been the `Profile` model.
    Reading it with `.get()` therefore raised `AttributeError` *before* the
    deliberate swallow inside the claim -- so the failure did not degrade to "no
    claim this time", it took down `GET /api/v1/auth/session` with a 500 for
    every signed-in user, on every request, whatever their intent.

    Nothing above this line would have noticed: no test called
    `get_session_context` at all. This one does, and asserts the outcome the
    claim exists to produce -- a manager who has never signed in before lands in
    their portal on their first sign-in.
    """
    service = _SessionService()
    monkeypatch.setattr(auth_service, "get_service_client", lambda: service)
    monkeypatch.setattr(
        auth_service,
        "verified_identity",
        lambda _token: Principal(
            user_id="profile-id",
            email="verified@example.com",
            email_verified=True,
            full_name="Priya Nair",
        ),
    )
    profile = signed_in_profile()
    monkeypatch.setattr(
        auth_service.profiles_repository,
        "get_profile",
        lambda _client, _user_id: profile,
    )

    context = auth_service.get_session_context(
        object(),  # type: ignore[arg-type]  # the repository read is stubbed
        Principal(
            user_id="profile-id",
            email="verified@example.com",
            email_verified=True,
            full_name="Priya Nair",
        ),
        "access-token",
    )

    assert service.claimed_with == {
        "p_profile_id": "profile-id",
        "p_email": "verified@example.com",
    }
    assert context.identity == profile
    assert context.membership is not None
    assert context.membership.id == "membership-id"
    assert context.portal == "manager"
    assert context.onboarding_eligible is False
    # The re-read is the point: membership, claim, membership.
    assert service.tables.count("community_memberships") == 2


def test_api_336_a_sitting_member_still_gets_their_invitation_processed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The claim-pass gap, closed. Product ruling 8, 2026-08-21.

    `_claim_staff_invitations` sat inside `if not rows:` — the branch that had
    already established the caller holds no membership. So the whole population
    that *does* hold one never reached it: a resident invited to supervise a
    department, a worker on one community's roster invited to manage another, a
    supervisor being promoted. Their invitation was neither claimed nor refused.
    It stayed `pending` and the department that sent it kept seeing `pending`,
    with nothing anywhere reporting a problem.

    Since `20260821140000`/`20260821170000` the refusal half matters as much as
    the claim half: an invitation that *cannot* be applied is marked `blocked`
    and both the department and the invitee are told — and that announcement was
    reachable only by people with no membership.

    What is asserted is the call, not the outcome, because the outcome is the
    RPC's and the RPC is Postgres. The caller here holds a membership from the
    first read and the claim is attempted anyway.
    """

    class _SittingMember:
        MEMBERSHIP: dict[str, Any] = {
            "id": "membership-id",
            "community_id": "community-id",
            "role": "resident",
            "department_id": None,
            "is_default_community": True,
        }

        def __init__(self) -> None:
            self.claimed_with: dict[str, Any] | None = None

        def table(self, name: str) -> _SessionQuery:
            def rows() -> list[dict[str, Any]]:
                if name == "community_memberships":
                    return [self.MEMBERSHIP]
                return []

            return _SessionQuery(rows)

        def rpc(self, name: str, params: dict[str, Any]) -> Any:
            service = self

            class _RPC:
                def execute(self) -> _Rows:
                    service.claimed_with = params
                    # Nothing claimed: the ordinary case for somebody with no
                    # invitation waiting, and the one that must not trigger a
                    # second membership read.
                    return _Rows([])

            return _RPC()

    service = _SittingMember()
    monkeypatch.setattr(auth_service, "get_service_client", lambda: service)
    monkeypatch.setattr(
        auth_service,
        "verified_identity",
        lambda _token: Principal(
            user_id="profile-id",
            email="verified@example.com",
            email_verified=True,
            full_name="Priya Nair",
        ),
    )
    profile = signed_in_profile()
    monkeypatch.setattr(
        auth_service.profiles_repository,
        "get_profile",
        lambda _client, _user_id: profile,
    )

    context = auth_service.get_session_context(
        object(),  # type: ignore[arg-type]  # the repository read is stubbed
        Principal(
            user_id="profile-id",
            email="verified@example.com",
            email_verified=True,
            full_name="Priya Nair",
        ),
        "access-token",
    )

    assert service.claimed_with == {
        "p_profile_id": "profile-id",
        "p_email": "verified@example.com",
    }
    # And the session they already had is untouched by the extra pass.
    assert context.membership is not None
    assert context.membership.id == "membership-id"
    assert context.onboarding_eligible is False
