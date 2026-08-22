"""The three leadership rulings of 2026-08-21, at the seams the API owns.

    RULING 1  Leadership is invite-only and never from the marketplace pool.
    RULING 2  Leadership is exclusive to one community.
    RULING 3  Removal severs access completely.

**What these tests can and cannot prove.** Rulings 1 and 2 are enforced by
triggers and RPCs in ``20260821140000_leadership_exclusivity.sql``, and no test
in this suite runs Postgres. So the database half is asserted statically in
``tests/test_leadership_exclusivity_migration.py``, and what is asserted *here*
is the half the Python owns and is the half that has actually broken before:

* that the two new SQLSTATEs reach a caller as a 409 carrying a code they can
  branch on, rather than as an opaque 500 (``pg_errors`` is exercised for real,
  not stubbed -- the fakes raise what ``translate`` produces from a genuine
  ``HBMKT``/``HBLED``);
* that a refused claim does not cost anybody their session. That is not a
  hypothetical: ``_claim_staff_invitations`` swallows exceptions on purpose, so
  a claim that raises abandons *every* invitation in the loop silently, and the
  only way to tell the two designs apart from outside is that the refused
  person still gets a session and the department still sees the invitation;
* that ruling 3's snapshot read asks for active engagements only, so an account
  with an ended posting in one community and a live one in another sees exactly
  one.

Ruling 3's other surfaces -- the mailbox, the calendar, the feed -- are RLS and
are unreachable from here by construction. They are enumerated with their
verification queries in the migration's section 10.

**Added 2026-08-21, same day:** the refused invitee is now told why
(``20260821170000_blocked_invitee_notice.sql``). The write is SQL and is pinned
in ``tests/test_blocked_invitee_notice_migration.py``; what the API owns is the
*read* -- that the person-scoped, community-less, link-less row the claim files
comes back out of ``GET /notifications`` as the sentence the product owner
approved, rather than as a fallback title over an invented link.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_request_client
from app.core import pg_errors
from app.domain.schemas import Principal, Profile
from app.repositories import profiles_repository
from app.services import auth_service, hiring_service, service_providers_service
from app.services import worker_service

DEPARTMENT = "/api/v1/departments/department-id"
INVITATIONS = f"{DEPARTMENT}/staff-invitations"
PROVIDERS = "/api/v1/service-providers"
SNAPSHOT = "/api/v1/worker/snapshot"

PROFILE_ID = "leader-profile-id"

#: The sentences the migration raises, verbatim enough to be recognisable.
MARKETPLACE_REFUSAL = (
    "That address belongs to a registered service professional. A manager or "
    "supervisor is never hired out of the marketplace -- invite somebody who "
    "is not a registered provider."
)
ELSEWHERE_REFUSAL = (
    "That person already manages or supervises another community. Leadership "
    "is held in one community at a time, so they would have to leave that "
    "posting before taking this one."
)
REGISTRATION_REFUSAL = (
    "You manage or supervise a community, and leadership is not part of the "
    "marketplace. A manager or supervisor is placed by an administrator, never "
    "matched by distance and trade, so there is no professional profile for "
    "you to register."
)


class FakePostgrestError(Exception):
    """The shape ``pg_errors._extract_code`` reads a SQLSTATE out of.

    ``postgrest.exceptions.APIError`` carries ``.code`` and ``.message``, and
    ``translate`` reads exactly those two. Building the refusal *through*
    ``translate`` rather than raising a ``ConflictError`` directly is the point
    of these tests: the thing most likely to be wrong is the mapping, and a
    hand-raised ``ConflictError`` would assert the mapping by assuming it.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def refusal(code: str, message: str) -> Exception:
    return pg_errors.translate(
        FakePostgrestError(code, message),
        default_message="Could not create that invitation.",
    )


def invitation_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "invitation-id",
        "department_id": "department-id",
        "invitee_email": "priya@example.com",
        "invitee_name": "Priya Nair",
        "invitee_phone_e164": None,
        "rank": "supervisor",
        "job_title": None,
        "status": "pending",
        "claimed_at": None,
        "created_at": "2026-08-21T09:00:00Z",
        "blocked_reason": None,
        "blocked_at": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def invitations(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """The invitation repository, with a refusal a test can arm."""
    captured: dict = {"rows": [invitation_row()], "invite_raises": None, "calls": []}

    def fake_list(
        client: Any, *, department_id: str, status: str | None
    ) -> list[dict[str, Any]]:
        return captured["rows"]

    def fake_invite(client: Any, **kwargs: Any) -> str:
        captured["calls"].append(("invite", kwargs))
        if captured["invite_raises"] is not None:
            raise captured["invite_raises"]
        return "invitation-id"

    repo = hiring_service.repo
    monkeypatch.setattr(repo, "list_staff_invitations", fake_list)
    monkeypatch.setattr(repo, "invite_staff_member", fake_invite)
    yield captured


# ---------------------------------------------------------------------------
# Ruling 1 and 2 at invite time
# ---------------------------------------------------------------------------


def test_api_270_a_registered_provider_cannot_be_invited_as_leadership(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """Ruling 1, refused where somebody is watching.

    The trigger on ``staff_assignments`` would refuse this eventually -- at the
    claim, days later, with nobody at a screen. Refusing at the invitation is
    what turns "the manager we created never arrived" into a sentence the
    administrator reads while their hand is still on the mouse.
    """
    invitations["invite_raises"] = refusal("HBMKT", MARKETPLACE_REFUSAL)

    response = admin_api_client.post(
        INVITATIONS,
        json={"email": "ravi@example.com", "name": "Ravi Kumar", "rank": "supervisor"},
        headers=csrf_headers,
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "leadership_marketplace_conflict"
    assert "marketplace" in body["message"]


def test_api_271_a_second_leadership_invitation_is_refused(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """Ruling 2, and a different code from ruling 1 on purpose.

    Both are 409s. A client that must offer "hire them at technician rank
    instead" for one and "wait until they leave the other society" for the
    other cannot tell them apart from a status, and branching on the message
    text is what the custom SQLSTATEs exist to avoid.
    """
    invitations["invite_raises"] = refusal("HBLED", ELSEWHERE_REFUSAL)

    response = admin_api_client.post(
        INVITATIONS,
        json={"email": "priya@example.com", "name": "Priya Nair", "rank": "manager"},
        headers=csrf_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "leadership_already_held"


def test_api_272_the_two_refusals_do_not_collapse_into_one_code(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """The property the two tests above only imply when read together."""
    codes = []
    for sqlstate, message in (
        ("HBMKT", MARKETPLACE_REFUSAL),
        ("HBLED", ELSEWHERE_REFUSAL),
        ("HB409", "That person already belongs to this community."),
    ):
        invitations["invite_raises"] = refusal(sqlstate, message)
        response = admin_api_client.post(
            INVITATIONS,
            json={"email": "x@example.com", "name": "X", "rank": "supervisor"},
            headers=csrf_headers,
        )
        assert response.status_code == 409
        codes.append(response.json()["error"]["code"])

    assert len(set(codes)) == 3


def test_api_273_an_invitation_after_the_previous_posting_ended_is_created(
    admin_api_client: TestClient,
    invitations: dict,
    csrf_headers: dict[str, str],
) -> None:
    """Ruling 2 bounds *active* leadership, not leadership ever held.

    "Being invited to a different community AFTER the previous leadership
    engagement has fully ended is legitimate and must keep working" is half the
    ruling, and it is the half a guard written as "has this person ever led"
    would break. Nothing is armed here, so the RPC accepts -- which is what an
    ended posting looks like from this side of the wire.
    """
    response = admin_api_client.post(
        INVITATIONS,
        json={"email": "priya@example.com", "name": "Priya Nair", "rank": "supervisor"},
        headers=csrf_headers,
    )

    assert response.status_code == 201
    assert response.json()["email"] == "priya@example.com"
    assert response.json()["blockedReason"] is None


def test_api_274_a_blocked_invitation_says_why_in_the_pending_list(
    admin_api_client: TestClient, invitations: dict
) -> None:
    """The claim has no screen, so the pending list is where the answer lands.

    Without this the row reads "waiting for first sign-in", which after a
    blocked claim is false: they signed in and were turned away. The status
    stays ``pending`` deliberately -- the situation is not terminal, and both
    existing verbs (correct the address, withdraw) still apply.
    """
    invitations["rows"] = [
        invitation_row(
            blocked_reason=(
                "They signed in, but already manage or supervise another "
                "community."
            ),
            blocked_at="2026-08-21T10:00:00Z",
        )
    ]

    body = admin_api_client.get(INVITATIONS).json()

    assert body[0]["status"] == "pending"
    assert "already manage or supervise" in body[0]["blockedReason"]
    assert body[0]["blockedAt"] is not None


# ---------------------------------------------------------------------------
# Ruling 1 at registration time
# ---------------------------------------------------------------------------


def test_api_275_a_supervisor_is_refused_a_marketplace_profile(
    worker_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    csrf_headers: dict[str, str],
) -> None:
    """The mirror of ``api_270``, from the other side of ruling 1.

    A supervisor holds a ``worker`` membership -- rank is not role -- so
    ``register_service_provider``'s older separate-account check deliberately
    lets them through: it refuses residents, managers and administrators.
    ``HBMKT`` is the refusal written for them, and the message says why there is
    nothing here for them rather than merely that they may not.
    """

    def fake_register(client: Any, **kwargs: Any) -> str:
        raise pg_errors.translate(
            FakePostgrestError("HBMKT", REGISTRATION_REFUSAL),
            default_message="Could not register the service provider.",
        )

    monkeypatch.setattr(
        service_providers_service.repo, "register_profile", fake_register
    )

    response = worker_api_client.post(
        PROVIDERS,
        json={
            "displayName": "Priya Nair",
            "latitude": 12.9,
            "longitude": 77.6,
            "skillIds": ["skill-id"],
        },
        headers=csrf_headers,
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "leadership_marketplace_conflict"
    # The form renders `error.message` straight through
    # (`RegisterProvider.jsx` 199-202), so the sentence has to be one.
    assert body["message"] == REGISTRATION_REFUSAL


# ---------------------------------------------------------------------------
# The claim seam: refused, and the session survives
# ---------------------------------------------------------------------------


class _Rows:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: Any) -> None:
        self._rows = rows

    def select(self, *_: Any, **__: Any) -> "_Query":
        return self

    def eq(self, *_: Any) -> "_Query":
        return self

    def is_(self, *_: Any) -> "_Query":
        return self

    def in_(self, *_: Any) -> "_Query":
        return self

    def order(self, *_: Any, **__: Any) -> "_Query":
        return self

    def limit(self, *_: Any) -> "_Query":
        return self

    def execute(self) -> _Rows:
        return _Rows(list(self._rows()))


class _BlockedClaimService:
    """A database where the claim is refused the way the migration refuses it.

    The RPC **returns zero rows**. It does not raise, and that is the whole
    design under test: ``_claim_staff_invitations`` swallows exceptions, so a
    refusal spelled as an exception would be indistinguishable from a database
    outage and would take every other pending invitation down with it.
    """

    def __init__(self, *, provider_rows: list[dict[str, Any]]) -> None:
        self.claimed_with: dict[str, Any] | None = None
        self.tables: list[str] = []
        self._provider_rows = provider_rows

    def _rows_for(self, name: str) -> list[dict[str, Any]]:
        if name == "service_providers":
            return self._provider_rows
        return []

    def table(self, name: str) -> _Query:
        self.tables.append(name)
        return _Query(lambda: self._rows_for(name))

    def rpc(self, name: str, params: dict[str, Any]) -> Any:
        service = self

        class _RPC:
            def execute(self) -> _Rows:
                service.claimed_with = params
                return _Rows([])

        return _RPC()


def signed_in_profile(**overrides: Any) -> Profile:
    row: dict[str, Any] = {
        "id": PROFILE_ID,
        "full_name": "Ravi Kumar",
        "phone_e164": None,
        "display_email": "ravi@example.com",
        "is_active": True,
    }
    row.update(overrides)
    return profiles_repository._to_profile(row)


def principal() -> Principal:
    return Principal(
        user_id=PROFILE_ID,
        email="ravi@example.com",
        email_verified=True,
        full_name="Ravi Kumar",
    )


@pytest.fixture
def blocked_claim(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    service = _BlockedClaimService(provider_rows=[{"id": "provider-id"}])
    monkeypatch.setattr(auth_service, "get_service_client", lambda: service)
    monkeypatch.setattr(auth_service, "verified_identity", lambda _t: principal())
    profile = signed_in_profile()
    monkeypatch.setattr(
        auth_service.profiles_repository, "get_profile", lambda _c, _u: profile
    )
    yield service


def test_api_276_a_refused_claim_does_not_cost_the_session(
    blocked_claim: _BlockedClaimService,
) -> None:
    """The claim-time design, asserted as an outcome rather than a mechanism.

    A registered provider whose email was invited as a supervisor signs in. The
    invitation must not take effect -- and the sign-in must still work. Under
    the rejected design (raise inside ``claim_staff_invitations``) the RPC would
    throw, ``_claim_staff_invitations`` would swallow it, and the observable
    result here would be identical *except* that any other legitimate
    invitation in the same loop would also have been abandoned. So what is
    pinned is what the API can see: the claim was attempted, nothing was
    claimed, and the caller ends up in the portal their provider row entitles
    them to rather than on an error page.
    """
    context = auth_service.get_session_context(
        object(),  # type: ignore[arg-type]  # the profile read is stubbed
        principal(),
        "access-token",
    )

    assert blocked_claim.claimed_with == {
        "p_profile_id": PROFILE_ID,
        "p_email": "ravi@example.com",
    }
    assert context.membership is None
    # The provider fallback in `get_session_context`: registered, hired
    # nowhere. Not an error, and not the leadership portal the invitation was
    # trying to hand them.
    assert context.portal == "worker"
    assert context.onboarding_eligible is False


def test_api_277_nothing_claimed_is_not_reported_as_a_claim(
    blocked_claim: _BlockedClaimService,
) -> None:
    """An empty result must stay falsy through the blocked path too.

    ``get_session_context`` re-reads memberships only when the claim reports
    success. A blocked claim that reported ``True`` would make every sign-in by
    a refused invitee run the membership query twice, forever, and would look
    like a claim that keeps not sticking.
    """
    assert (
        auth_service._claim_staff_invitations(
            signed_in_profile(), principal(), "access-token"
        )
        is False
    )


def test_api_278_a_claim_that_raises_still_leaves_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backstop behind the design, kept honest.

    The trigger is the guarantee and the in-function skip is the courtesy. If a
    path is ever found that reaches the trigger, the RPC *will* raise -- and the
    person must still get a session, because being refused an invitation is not
    the same as being refused an account.
    """

    class _Raising:
        def table(self, name: str) -> _Query:
            return _Query(list)

        def rpc(self, name: str, params: dict[str, Any]) -> Any:
            class _RPC:
                def execute(self) -> _Rows:
                    raise RuntimeError("HBMKT: a provider may not hold leadership")

            return _RPC()

    monkeypatch.setattr(auth_service, "get_service_client", lambda: _Raising())
    monkeypatch.setattr(auth_service, "verified_identity", lambda _t: principal())
    profile = signed_in_profile()
    monkeypatch.setattr(
        auth_service.profiles_repository, "get_profile", lambda _c, _u: profile
    )

    context = auth_service.get_session_context(
        object(),  # type: ignore[arg-type]
        principal(),
        "access-token",
    )

    assert context.identity == profile
    assert context.onboarding_eligible is True


def test_api_279_a_reinvitation_after_the_old_posting_ended_is_claimed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of ruling 2, at the claim.

    Somebody whose supervision of community A has fully ended holds no active
    membership, so the session read reaches the claim -- which is exactly the
    path a *first* sign-in takes, and that is the point: an ended posting leaves
    the person indistinguishable from somebody who has never led anywhere, and
    community B's invitation lands normally.
    """

    class _AdmittingService:
        MEMBERSHIP = {
            "id": "membership-b",
            "community_id": "community-b",
            "role": "worker",
            "department_id": "department-b",
            "is_default_community": True,
        }

        def __init__(self) -> None:
            self.claimed_with: dict[str, Any] | None = None

        def table(self, name: str) -> _Query:
            def rows() -> list[dict[str, Any]]:
                if name == "community_memberships":
                    # The ended community-A membership is invisible to this
                    # read: `_active_memberships` filters `status = active` and
                    # `ended_at is null`. So before the claim there is nothing.
                    return [self.MEMBERSHIP] if self.claimed_with else []
                return []

            return _Query(rows)

        def rpc(self, name: str, params: dict[str, Any]) -> Any:
            service = self

            class _RPC:
                def execute(self) -> _Rows:
                    service.claimed_with = params
                    return _Rows([{"membership_id": "membership-b"}])

            return _RPC()

    service = _AdmittingService()
    monkeypatch.setattr(auth_service, "get_service_client", lambda: service)
    monkeypatch.setattr(auth_service, "verified_identity", lambda _t: principal())
    profile = signed_in_profile()
    monkeypatch.setattr(
        auth_service.profiles_repository, "get_profile", lambda _c, _u: profile
    )

    context = auth_service.get_session_context(
        object(),  # type: ignore[arg-type]
        principal(),
        "access-token",
    )

    assert service.claimed_with is not None
    assert context.membership is not None
    assert context.membership.community_id == "community-b"


# ---------------------------------------------------------------------------
# Ruling 3: ended in A, active in B
# ---------------------------------------------------------------------------


def engagement_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "staff_assignment_id": "staff-b",
        "community_id": "community-b",
        "community_name": "Blue Waters",
        "community_city": "Kochi",
        "department_id": "department-b",
        "department_name": "Electrical",
        "department_kind": "service",
        "membership_id": "membership-b",
        "membership_role": "worker",
        "rank": "supervisor",
        "job_title": "Supervisor",
        "shift": None,
        "status": "active",
        "started_at": "2026-08-20",
        "ended_at": None,
    }
    base.update(overrides)
    return base


def test_api_280_the_snapshot_shows_only_the_community_that_still_employs_them(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 3 on the one surface the BFF composes rather than the database.

    Every other ruling-3 read is RLS. ``communities[]`` is not: it is assembled
    in Python from ``list_engagements_for_profile``, and it is what the
    supervisor's Complaints screen picks a department out of
    (``WorkerDashboard/Complaints.jsx`` 29-37). A single ended community-A row
    leaking into it would put community A's complaint queue on the screen of
    somebody who was removed from community A -- and the endpoint behind that
    queue is guarded by ``can_supervise_department``, so it would 403 rather
    than leak, which is a broken screen instead of a breach but is still not
    the answer.

    Two assertions, and the second is the load-bearing one: the *request* is
    for active engagements only, so the filter is the repository's rather than
    a coincidence of the fixture.
    """
    asked: dict[str, Any] = {}

    def fake_staff_engagements(
        client: Any, *, profile_id: str, active_only: bool
    ) -> list[dict[str, Any]]:
        asked["profile_id"] = profile_id
        asked["active_only"] = active_only
        # The repository has already dropped the ended community-A row; this is
        # what it returns for a supervisor removed from A and invited into B.
        return [engagement_row()]

    def no_provider(client: Any, *, profile_id: str) -> dict[str, Any] | None:
        return None

    monkeypatch.setattr(
        worker_service.service_providers_service.repo, "get_by_profile", no_provider
    )
    monkeypatch.setattr(
        worker_service.hiring_service.repo,
        "list_engagements_for_profile",
        fake_staff_engagements,
    )
    monkeypatch.setattr(worker_service, "get_service_client", lambda: object())

    api_client.app.dependency_overrides[get_current_user] = lambda: principal()
    api_client.app.dependency_overrides[get_request_client] = lambda: object()

    body = api_client.get(SNAPSHOT).json()

    assert asked == {"profile_id": PROFILE_ID, "active_only": True}
    assert [row["communityId"] for row in body["communities"]] == ["community-b"]
    assert body["communities"][0]["rank"] == "supervisor"
    # No marketplace profile, and that is not an error for leadership.
    assert body["provider"] is None


# ---------------------------------------------------------------------------
# The invitee is told -- 2026-08-21, the product owner's follow-up
# ---------------------------------------------------------------------------

FEED = "/api/v1/notifications"

#: The kind `claim_staff_invitations` writes for the *invitee*. Deliberately not
#: the department's `staff_invitation.blocked`: same event, opposite voice.
INVITEE_KIND = "staff_invitation.not_applied"

#: The approved wording, with the community's name substituted. Pinned against
#: the SQL that produces it in `tests/test_blocked_invitee_notice_migration.py`;
#: reproduced here so these tests read as what the person actually sees.
PROVIDER_NOTICE = (
    "Your invitation to join Blue Waters couldn't be applied. This account is "
    "registered as a marketplace service professional, and department "
    "leadership can't be combined with a provider profile. Ask the community to "
    "invite a different email address."
)
ELSEWHERE_NOTICE = (
    "Your invitation to join Blue Waters couldn't be applied because you already "
    "manage or supervise another community. Leadership is held in one community "
    "at a time — once your current engagement ends, the invitation can be "
    "applied on your next sign-in."
)


def notice_row(body: str) -> dict[str, Any]:
    """One `notification_overview` row as the claim files it.

    `community_id` is null and so is `recipient_membership_id`: `notify_profile`
    addresses the person and no community, which is what keeps the row readable
    after every membership change. There is no `url` key at all -- see
    `test_api_283`.
    """
    return {
        "id": "notice-id",
        "kind": INVITEE_KIND,
        "payload": {
            "title": "Your invitation couldn't be applied",
            "body": body,
            "invitationId": "invitation-id",
            "communityId": "community-a",
            "communityName": "Blue Waters",
        },
        "community_id": None,
        "read_at": None,
        "is_unread": True,
        "created_at": "2026-08-21T10:00:00Z",
    }


@pytest.fixture
def invitee_feed(monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    """The notification feed, staged with whatever a test puts in `rows`."""
    from app.repositories import notifications_repository

    captured: dict = {"rows": []}

    def fake_list_feed(
        client: Any, *, profile_id: str, unread_only: bool, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        captured["profile_id"] = profile_id
        return captured["rows"], len(captured["rows"])

    monkeypatch.setattr(notifications_repository, "list_feed", fake_list_feed)
    monkeypatch.setattr(
        notifications_repository, "unread_count", lambda client, *, profile_id: 1
    )
    yield captured


@pytest.mark.parametrize(
    ("case", "expected"),
    (("marketplace", PROVIDER_NOTICE), ("elsewhere", ELSEWHERE_NOTICE)),
)
def test_api_281_the_refused_invitee_reads_the_reason_in_their_own_feed(
    worker_api_client: TestClient,
    invitee_feed: dict,
    case: str,
    expected: str,
) -> None:
    """The gap this closes, from the only side that could see it.

    Before 2026-08-21 the department was told three times -- `blockedReason` on
    the invitation, `blockedAt`, and a `staff_invitation.blocked` notification --
    and the invitee was told nothing. They signed in, the invitation did not
    take, and the session read returned exactly what it returns for somebody
    nobody has ever invited (`api_276`). That contract is unchanged and must
    stay unchanged; the answer arrives out of band, here.
    """
    invitee_feed["rows"] = [notice_row(expected)]

    response = worker_api_client.get(FEED)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["kind"] == INVITEE_KIND
    assert item["body"] == expected
    # The whole approved sentence is one string. A renderer that split it across
    # title and body would make the wording depend on which surface reassembled
    # it -- and the lock-screen line uses the same two fields.
    assert item["title"] == "Your invitation couldn't be applied"


def test_api_282_the_notice_is_readable_with_no_community_behind_it(
    worker_api_client: TestClient, invitee_feed: dict
) -> None:
    """Person-scoped, and that is not incidental.

    A registered provider hired nowhere holds no membership at all, and a
    sitting leader holds one in a *different* community. `notify_member` would
    have filed this under whichever community was to hand, and ruling 3's own
    feed policy (`membership_is_live`) would then hide it the day that
    membership ended -- deleting the explanation for a refusal caused by that
    very posting.
    """
    invitee_feed["rows"] = [notice_row(ELSEWHERE_NOTICE)]

    body = worker_api_client.get(FEED).json()

    assert invitee_feed["profile_id"] == "worker-profile-id"
    assert body["items"][0]["body"] == ELSEWHERE_NOTICE
    assert body["unread"] == 1


def test_api_283_the_notice_offers_no_link_and_none_is_invented(
    worker_api_client: TestClient, invitee_feed: dict
) -> None:
    """There is no screen for this, and a guessed one would be worse than none.

    The invitee is not a member of that community and never becomes one; no
    portal lists invitations addressed to you, and the two refused populations
    land in different portals anyway. `notifications_service._FALLBACK_URLS`
    exists for four hiring kinds whose payloads carry the id a route needs, and
    its docstring is the rule being relied on here -- "a link that goes to the
    wrong screen is one the reader believes". `NotificationBell.openItem` marks
    an empty-url row read and navigates nowhere, which is the intended click.
    """
    from app.services import notifications_service

    invitee_feed["rows"] = [notice_row(PROVIDER_NOTICE)]

    assert worker_api_client.get(FEED).json()["items"][0]["url"] == ""
    assert INVITEE_KIND not in notifications_service._FALLBACK_URLS


def test_api_284_an_unrecognised_kind_still_renders_as_a_row(
    worker_api_client: TestClient, invitee_feed: dict
) -> None:
    """The property that let this ship without touching the reader.

    `render` reads `title`, `body` and `url` and nothing else, so a kind no
    Python file has heard of renders from its own payload. The fallback table is
    for writers that supplied no title; this writer supplies one, which is why
    `staff_invitation.not_applied` needed no entry -- exactly as the
    department's `staff_invitation.blocked` needed none.
    """
    from app.services import notifications_service

    assert INVITEE_KIND not in notifications_service._FALLBACK_TITLES

    row = notice_row(PROVIDER_NOTICE)
    row["payload"].pop("title")
    invitee_feed["rows"] = [row]

    item = worker_api_client.get(FEED).json()["items"][0]

    # A dull generic line rather than a blank one, and the approved sentence is
    # still underneath it.
    assert item["title"] == notifications_service._GENERIC_TITLE
    assert item["body"] == PROVIDER_NOTICE
