"""The dashboard live-update path: frame format, fan-out, and tenant isolation.

Nothing here touches Supabase. The hub's only contact with the database is two
repository functions, so the tests substitute those and drive the rest for real
-- including the asyncio queues, so the concurrency being asserted is the
concurrency that ships.
"""

from __future__ import annotations

import asyncio
import json

from app.core import realtime
from app.core.realtime import Event, RealtimeHub, _Subscriber

ALPHA = "11111111-1111-1111-1111-111111111111"
BETA = "22222222-2222-2222-2222-222222222222"

# Membership ids. A subscriber is a membership, not a person: the same human on
# two communities is two subscribers with two ids.
ADMIN_M = "aaaaaaaa-0000-0000-0000-000000000001"
RESIDENT_M = "bbbbbbbb-0000-0000-0000-000000000002"
OTHER_M = "cccccccc-0000-0000-0000-000000000003"


def sub(community=ALPHA, membership_id=ADMIN_M, role="admin"):
    """A subscriber with an identity, which is now the only kind there is."""
    return _Subscriber(community_id=community, membership_id=membership_id, role=role)


def run(coro):
    """Drive one coroutine to completion.

    The project has no async test plugin and its dependencies are locked, so
    rather than add `pytest-asyncio` these tests own their event loop. Each
    gets a fresh one, which also keeps `asyncio.Queue` construction inside a
    running loop -- required on 3.10, harmless on the 3.14 the team deploys.
    """
    return asyncio.run(coro())


# ---------------------------------------------------------------------------
# Frame rendering
# ---------------------------------------------------------------------------


def test_frame_data_is_json_not_a_python_repr():
    """The regression that made every payload unparseable in the browser.

    The previous implementation interpolated the dict directly, emitting
    `{'table': 'complaints'}` -- single-quoted, so `JSON.parse` threw on it.
    """
    frame = Event(id=7, topic="access_request.created", payload={"table": "x"}).frame()
    data = [line for line in frame.splitlines() if line.startswith("data: ")][0]
    body = data[len("data: ") :]

    assert "'" not in body
    assert json.loads(body) == {"table": "x"}


def test_frame_carries_id_and_topic_for_reconnect_and_dispatch():
    frame = Event(id=42, topic="access_request.decided", payload={}).frame()

    assert frame.startswith("id: 42\n")
    assert "event: access_request.decided\n" in frame
    assert frame.endswith("\n\n")


def test_a_payload_containing_a_newline_cannot_split_the_frame():
    """A raw newline in the data field would end the event early and
    desynchronise everything after it. json.dumps escapes it."""
    frame = Event(id=1, topic="t", payload={"note": "line one\nline two"}).frame()

    # Exactly one blank-line terminator, at the very end.
    assert frame.count("\n\n") == 1
    assert frame.index("\n\n") == len(frame) - 2


def test_non_serialisable_payload_values_do_not_raise():
    """`default=str` keeps a stray datetime from killing the whole stream."""
    from datetime import datetime

    frame = Event(id=1, topic="t", payload={"at": datetime(2026, 7, 30)}).frame()

    assert "2026-07-30" in frame


# ---------------------------------------------------------------------------
# Fan-out and isolation
# ---------------------------------------------------------------------------


def _rows(*specs):
    """Outbox rows with no audience set.

    `audience` is `not null default 'community'` in `0028`, so a row that omits
    it is community-wide -- which is also how every row written before that
    migration reads. These exercise routing by community; the audience filter
    has its own section below.
    """
    return [
        {"id": i, "community_id": c, "topic": t, "payload": p}
        for i, c, t, p in specs
    ]


def test_dispatch_routes_each_row_to_its_own_community_only():
    async def body():
        hub = RealtimeHub()
        alpha, beta = sub(ALPHA), sub(BETA)
        hub._subscribers = {ALPHA: {alpha}, BETA: {beta}}

        hub._dispatch(
            _rows(
                (1, ALPHA, "access_request.created", {"n": 1}),
                (2, BETA, "access_request.created", {"n": 2}),
                (3, ALPHA, "dashboard.refresh", {"n": 3}),
            )
        )

        assert [e.id for e in _drain(alpha)] == [1, 3]
        assert [e.id for e in _drain(beta)] == [2]

    run(body)


def test_every_subscriber_in_a_community_gets_the_same_event():
    """Two admins on one community must cost one query, not two -- which only
    works if a single fetched row fans out to both."""

    async def body():
        hub = RealtimeHub()
        first, second = sub(ALPHA, ADMIN_M), sub(ALPHA, OTHER_M)
        hub._subscribers = {ALPHA: {first, second}}

        hub._dispatch(_rows((5, ALPHA, "access_request.created", {})))

        assert [e.id for e in _drain(first)] == [5]
        assert [e.id for e in _drain(second)] == [5]

    run(body)


def test_events_for_an_unwatched_community_are_discarded_not_buffered():
    async def body():
        hub = RealtimeHub()
        alpha = sub(ALPHA)
        hub._subscribers = {ALPHA: {alpha}}

        hub._dispatch(_rows((9, BETA, "access_request.created", {})))

        assert _drain(alpha) == []
        # The cursor still advances, or the poller re-reads that row forever.
        assert hub._cursor == 9

    run(body)


def test_cursor_advances_to_the_highest_id_seen():
    async def body():
        hub = RealtimeHub()
        hub._dispatch(_rows((3, ALPHA, "t", {}), (11, ALPHA, "t", {})))

        assert hub._cursor == 11

    run(body)


# ---------------------------------------------------------------------------
# Backpressure
# ---------------------------------------------------------------------------


def test_a_full_queue_degrades_instead_of_blocking_the_poller():
    """One stalled browser must not stop delivery for everyone else."""
    subscriber = sub(ALPHA)
    for i in range(realtime.QUEUE_MAXSIZE + 25):
        subscriber.push(Event(id=i, topic="t", payload={}))

    assert subscriber.queue.qsize() == realtime.QUEUE_MAXSIZE
    assert subscriber.dropped is True


def test_a_lagging_admin_is_told_to_resync_on_the_topic_already_wired():
    """Dropped events are unrecoverable, so the client is sent the topic its
    existing listener already reacts to by re-fetching the snapshot."""
    event = realtime._resync_event(99, "admin")

    assert event.topic == "dashboard.refresh"
    assert event.payload == {"resync": True}
    assert json.loads(event.frame().split("data: ")[1].strip()) == {"resync": True}


def test_a_lagging_resident_is_not_told_to_refresh_the_admin_dashboard():
    """`dashboard.refresh` means 're-read the admin snapshot', which a resident
    would be refused. It is also a topic `0028` restricts to {admin,manager},
    so sending it to a resident here would contradict the migration."""
    assert realtime._resync_event(99, "resident").topic == "stream.resync"
    assert realtime._resync_event(99, "security").topic == "stream.resync"
    assert realtime._resync_event(99, "manager").topic == "dashboard.refresh"


# ---------------------------------------------------------------------------
# Subscription lifecycle
# ---------------------------------------------------------------------------


def test_subscribe_yields_live_events_and_unregisters_on_exit():
    async def body():
        hub = RealtimeHub(poll_interval=0.01)
        # Keep the background poller inert; this drives _dispatch directly.
        hub._fetch = lambda cursor: []  # type: ignore[method-assign]

        stream = hub.subscribe(
            ALPHA, membership_id=ADMIN_M, role="admin", last_event_id=0
        )
        frames: list[str] = []

        async def consume():
            async for frame in stream:
                frames.append(frame)
                break

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)  # let subscribe() register before dispatching
        hub._dispatch(_rows((1, ALPHA, "access_request.created", {"pending_count": 3})))
        await asyncio.wait_for(task, timeout=2)
        await stream.aclose()

        assert "event: access_request.created" in frames[0]
        assert json.loads(frames[0].split("data: ")[1].strip())["pending_count"] == 3
        assert hub.subscriber_count == 0, "subscriber leaked after disconnect"
        await hub.stop()

    run(body)


def test_reconnecting_with_a_last_event_id_replays_the_gap():
    """A browser that drops its connection mid-stream must not lose the join
    requests that arrived while it was away."""

    async def body():
        hub = RealtimeHub(poll_interval=0.01)
        hub._fetch = lambda cursor: []  # type: ignore[method-assign]
        seen = {}

        async def fake_backfill(subscriber, last_event_id):
            seen["community_id"] = subscriber.community_id
            seen["last_event_id"] = last_event_id
            return [Event(id=5, topic="access_request.created", payload={}).frame()]

        hub._backfill = fake_backfill  # type: ignore[method-assign]

        stream = hub.subscribe(
            ALPHA, membership_id=ADMIN_M, role="admin", last_event_id=4
        )
        first = await stream.__anext__()
        await stream.aclose()
        await hub.stop()

        assert seen == {"community_id": ALPHA, "last_event_id": 4}
        assert "id: 5" in first

    run(body)


def test_a_failing_poll_does_not_kill_the_loop():
    """A transient Supabase error must not silently freeze every dashboard in
    the process -- the loop has to survive and try again."""

    async def body():
        hub = RealtimeHub(poll_interval=0.01)
        calls = {"n": 0}

        def explode(cursor):
            calls["n"] += 1
            raise RuntimeError("supabase is having a moment")

        hub._fetch = explode  # type: ignore[method-assign]
        hub._subscribers = {ALPHA: {sub(ALPHA)}}

        await hub.start()
        await asyncio.sleep(0.1)
        await hub.stop()

        assert calls["n"] > 1, "loop stopped after the first failure"

    run(body)


def test_the_poller_does_not_query_when_nobody_is_listening():
    """Idle cost must be zero, not one query per tick forever."""

    async def body():
        hub = RealtimeHub(poll_interval=0.01)
        calls = {"n": 0}

        def counting_fetch(cursor):
            calls["n"] += 1
            return []

        hub._fetch = counting_fetch  # type: ignore[method-assign]
        await hub.start()
        await asyncio.sleep(0.06)
        await hub.stop()

        assert calls["n"] == 0

    run(body)


def _drain(subscriber: _Subscriber) -> list[Event]:
    out = []
    while not subscriber.queue.empty():
        out.append(subscriber.queue.get_nowait())
    return out


# ---------------------------------------------------------------------------
# The audience filter (0028)
#
# Community membership was never enough. `GET /dashboard/events` is guarded by
# `get_active_membership` -- any active member -- and before `0028` the hub fanned
# out on community alone, so a resident opening the stream received
# `access_request.created` for their neighbours, applicant name included.
# ---------------------------------------------------------------------------


def _row(event_id, *, audience="community", roles=None, recipient=None, topic="t"):
    return {
        "id": event_id,
        "community_id": ALPHA,
        "topic": topic,
        "payload": {},
        "audience": audience,
        "audience_roles": roles,
        "recipient_membership_id": recipient,
    }


_JOIN_REQUEST = _row(
    1,
    audience="role",
    roles=["admin", "manager"],
    topic="access_request.created",
)


def test_a_resident_does_not_receive_a_neighbours_join_request():
    """The disclosure this migration exists to close."""
    assert sub(role="resident").accepts(_JOIN_REQUEST) is False


def test_an_admin_still_receives_join_requests():
    assert sub(role="admin").accepts(_JOIN_REQUEST) is True


def test_every_role_in_the_list_matches_not_just_the_first():
    assert sub(role="manager").accepts(_JOIN_REQUEST) is True


def test_a_role_audience_excludes_every_role_not_listed():
    """An allowlist, not a denylist on 'resident' -- so a role added to the
    enum later is excluded by default rather than included by default."""
    for role in ("resident", "worker", "security", ""):
        assert sub(role=role).accepts(_JOIN_REQUEST) is False, role


def test_a_member_audience_reaches_exactly_one_membership():
    row = _row(2, audience="member", recipient=RESIDENT_M)

    assert sub(membership_id=RESIDENT_M, role="resident").accepts(row) is True
    assert sub(membership_id=OTHER_M, role="resident").accepts(row) is False
    # Not even an admin. A notification addressed to a member is that member's.
    assert sub(membership_id=ADMIN_M, role="admin").accepts(row) is False


def test_a_community_audience_reaches_everyone_in_the_community():
    row = _row(3, topic="notice.published")

    assert sub(role="resident").accepts(row) is True
    assert sub(role="admin").accepts(row) is True


def test_a_row_written_before_the_migration_reads_as_community_wide():
    """`audience` is `not null default 'community'`, but a `select` against an
    older projection can still hand us a row without the key."""
    legacy = {"id": 4, "community_id": ALPHA, "topic": "t", "payload": {}}

    assert sub(role="resident").accepts(legacy) is True


def test_an_unclassifiable_row_is_delivered_to_nobody():
    """`sse_events_audience_shape_check` makes these unwritable. If one arrives
    anyway the reader must fail closed -- guessing 'community' is a leak."""
    for bad in (
        _row(5, audience="everyone"),
        _row(6, audience="role", roles=[]),
        _row(7, audience="member", recipient=None),
    ):
        assert sub(role="admin").accepts(bad) is False, bad["audience"]


def test_dispatch_applies_the_filter_per_subscriber_not_per_community():
    """Two people on one community, one row, two different outcomes -- from a
    single fetch. The filter has to sit inside the fan-out loop, not around it."""

    async def body():
        hub = RealtimeHub()
        admin = sub(role="admin", membership_id=ADMIN_M)
        resident = sub(role="resident", membership_id=RESIDENT_M)
        hub._subscribers = {ALPHA: {admin, resident}}

        hub._dispatch([
            _JOIN_REQUEST,
            _row(2, audience="member", recipient=RESIDENT_M, topic="complaint.updated"),
            _row(3, topic="notice.published"),
        ])

        assert [e.topic for e in _drain(admin)] == [
            "access_request.created", "notice.published",
        ]
        assert [e.topic for e in _drain(resident)] == [
            "complaint.updated", "notice.published",
        ]
        # Every row is still consumed exactly once, whoever it reaches.
        assert hub._cursor == 3

    run(body)


def test_the_cursor_advances_past_rows_nobody_in_the_audience_is_watching():
    """Filtering must not make the poller re-read the same row forever."""

    async def body():
        hub = RealtimeHub()
        resident = sub(role="resident", membership_id=RESIDENT_M)
        hub._subscribers = {ALPHA: {resident}}

        hub._dispatch([_JOIN_REQUEST])

        assert _drain(resident) == []
        assert hub._cursor == 1

    run(body)


def test_the_backfill_uses_the_same_filter_as_live_dispatch(monkeypatch):
    """A reconnect must not be the way round the audience. The query narrows
    and `accepts` decides, so a row the query lets through is still dropped."""
    from app.core import supabase_client
    from app.repositories import dashboard_repository

    asked = {}

    def fake_read_events(client, **kwargs):
        asked.update(kwargs)
        return [_JOIN_REQUEST, _row(2, audience="member", recipient=RESIDENT_M)]

    monkeypatch.setattr(dashboard_repository, "read_events", fake_read_events)
    monkeypatch.setattr(supabase_client, "get_service_client", lambda: object())

    async def body():
        resident = sub(role="resident", membership_id=RESIDENT_M)
        frames = await RealtimeHub()._backfill(resident, last_event_id=1)

        # The identity reached the query, so the narrowing happened in Postgres
        # rather than only after the 100-row cap had been applied.
        assert asked["membership_id"] == RESIDENT_M
        assert asked["role"] == "resident"
        # And the admin-only row is gone even though the fake handed it over.
        assert len(frames) == 1
        assert "id: 2" in frames[0]

    run(body)


def test_a_failing_backfill_yields_no_frames_not_an_exception(monkeypatch):
    from app.core import supabase_client
    from app.repositories import dashboard_repository

    def explode(client, **kwargs):
        raise RuntimeError("supabase is having a moment")

    monkeypatch.setattr(dashboard_repository, "read_events", explode)
    monkeypatch.setattr(supabase_client, "get_service_client", lambda: object())

    async def body():
        assert await RealtimeHub()._backfill(sub(), last_event_id=1) == []

    run(body)


def test_the_backfill_narrowing_clause_never_widens_past_the_caller():
    """The PostgREST `or=` is hand-written, so what it asks for is worth
    asserting: the caller's own membership and role, and nothing else."""
    from app.repositories.dashboard_repository import _audience_filter

    clause = _audience_filter(RESIDENT_M, "resident")

    assert "audience.eq.community" in clause
    assert "audience_roles.cs.{resident}" in clause
    assert f"recipient_membership_id.eq.{RESIDENT_M}" in clause
    assert "admin" not in clause
    assert OTHER_M not in clause


def test_a_filter_value_that_is_not_a_role_or_a_uuid_is_dropped_not_escaped():
    """These come from a membership row, so this should be unreachable. If it
    ever is reachable, the clause must degrade to something harmless rather
    than carry an operator into the query string -- and `accepts` still gates."""
    from app.repositories.dashboard_repository import _audience_filter

    clause = _audience_filter("not-a-uuid", "admin,audience.eq.member")

    assert clause == "audience.eq.community"


# ---------------------------------------------------------------------------
# The snapshot field behind the sidebar badge
# ---------------------------------------------------------------------------

_PENDING = [{"id": "r1", "applicant_name": "Asha", "applicant_email": "a@example.com"}]
_WEEKLY = {"residents": 2, "complaints": 1, "visitorRequests": 0, "bookings": 3}


def _snapshot_for(role, monkeypatch):
    """Run `dashboard_service.snapshot` with every database call stubbed out."""
    from app.domain.schemas import MembershipContext
    from app.services import dashboard_service

    empty = (
        "list_memberships", "list_complaints", "list_visitors", "list_amenities",
        "list_bookings", "list_invoices", "list_payments", "list_notices",
        "list_departments", "list_activity",
    )
    for name in empty:
        monkeypatch.setattr(
            dashboard_service.dashboard_repository, name,
            lambda *a, **k: [], raising=True,
        )
    monkeypatch.setattr(
        dashboard_service.dashboard_repository, "schema_generation", lambda: "current"
    )
    monkeypatch.setattr(
        dashboard_service.dashboard_repository,
        "list_pending_access_requests",
        lambda *a, **k: list(_PENDING),
    )
    monkeypatch.setattr(
        dashboard_service.dashboard_repository,
        "weekly_new_counts",
        lambda *a, **k: dict(_WEEKLY),
    )
    monkeypatch.setattr(dashboard_service, "get_service_client", lambda: object())

    return dashboard_service.snapshot(
        MembershipContext(id="m1", community_id=ALPHA, role=role)
    )


def test_an_admin_receives_the_pending_join_requests(monkeypatch):
    """The field the sidebar badge counts. Absent from the payload until now,
    which is why the badge could never render."""
    assert _snapshot_for("admin", monkeypatch).pendingRequests == _PENDING


def test_a_resident_never_receives_other_residents_join_requests(monkeypatch):
    """These rows carry a third party's name, email and phone. Role is the only
    thing standing between a resident and that list."""
    assert _snapshot_for("resident", monkeypatch).pendingRequests == []


def test_a_security_guard_does_not_receive_them_either(monkeypatch):
    """The gate is an allowlist on 'admin', not a denylist on 'resident' --
    so every other role is excluded too."""
    assert _snapshot_for("security", monkeypatch).pendingRequests == []


# ---------------------------------------------------------------------------
# The trend counts behind the dashboard chips
# ---------------------------------------------------------------------------


def test_the_snapshot_always_carries_the_four_weekly_new_counts(monkeypatch):
    """The frontend replaces its hardcoded '+2 this week' chips with exactly
    this object, so the field name and its four keys are load-bearing."""
    assert _snapshot_for("admin", monkeypatch).weeklyNew.model_dump() == _WEEKLY


def test_weekly_new_defaults_to_zeroes_never_to_absence():
    """`0` when nothing was created; the key itself must never be missing."""
    from app.domain.schemas import DashboardSnapshot

    payload = DashboardSnapshot().model_dump()

    assert payload["weeklyNew"] == {
        "residents": 0, "complaints": 0, "visitorRequests": 0, "bookings": 0,
    }


# ---------------------------------------------------------------------------
# The projections, pinned to the tables residents actually write
#
# The hosted project is a legacy database with every repository migration
# applied on top, so `0032` renamed its visitor event log to
# `legacy_visitor_events` and `0023` renamed its booking series tables to
# `legacy_amenity_booking_*`. Embedding or reading the old names is PGRST200 /
# PGRST205 on every call -- the 500 that took down the whole snapshot.
#
# **Corrected 2026-08-23.** Renaming the legacy tables was only half the story.
# `0032` and `0023` did not just free the names up, they moved the *writes*:
# residents have created visitor requests in `visitor_requests` and bookings in
# `amenity_bookings` ever since, on hosted as much as on a fresh database. The
# legacy read arms kept asking the pre-baseline tables and got a correct answer
# to the wrong question -- the owner's probe of 2026-08-23 counted
# `visitor_access_requests` = 0 against `visitor_requests` = 3, and
# `legacy_amenity_booking_series` = 0 (runbook §22, probes (g) and (h)). So
# these two reads have no schema-generation branch any more, and the tests
# below pin the single source instead of the pair. Every other legacy arm --
# complaints, amenities, invoices, payments, memberships, notices, work orders
# -- is genuinely two shapes of one table and is untouched.
# ---------------------------------------------------------------------------


class _RecordingClient:
    """Capture `(table, select)` pairs; answer every query with nothing."""

    def __init__(self):
        self.queries = []

    def table(self, name):
        self.queries.append({"table": name, "select": None, "filters": []})
        return self

    def select(self, columns, **kwargs):
        self.queries[-1]["select"] = columns
        self.queries[-1]["select_kwargs"] = kwargs
        return self

    def eq(self, column, value):
        self.queries[-1]["filters"].append(("eq", column, value))
        return self

    def gte(self, column, value):
        self.queries[-1]["filters"].append(("gte", column, value))
        return self

    def is_(self, *args):
        return self

    def in_(self, *args):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args):
        return self

    def execute(self):
        import types

        return types.SimpleNamespace(data=[], count=0)


def test_the_visitor_projection_reads_the_table_residents_write():
    """One source, on every schema generation. Reading
    `visitor_access_requests` was reading the empty half of a split brain: the
    rows are in `visitor_requests` and have been since `0032`."""
    from app.repositories import dashboard_repository

    client = _RecordingClient()
    dashboard_repository.list_visitors(client, ALPHA)

    (query,) = client.queries
    assert query["table"] == "visitor_requests"
    assert "visitor_events(event_type,created_at)" in query["select"]
    assert "legacy_visitor_events" not in query["select"]
    # `valid_from`/`valid_until` are this table's window columns; the legacy
    # pair `expected_from`/`expected_until` belong to a table nothing writes.
    assert "valid_from" in query["select"] and "valid_until" in query["select"]
    assert "expected_from" not in query["select"]
    # `0032` gave the table a `purpose`; the resident fills it in, and the card
    # read "Guest" for everyone while the projection left it out.
    assert "purpose" in query["select"]


def test_the_visitor_projection_takes_no_schema_generation_argument():
    """The branch is gone, not defaulted. A `legacy=` keyword left in place
    would let a caller reintroduce the pre-baseline read by passing True."""
    import inspect

    from app.repositories import dashboard_repository

    assert "legacy" not in inspect.signature(
        dashboard_repository.list_visitors
    ).parameters
    assert "legacy" not in inspect.signature(
        dashboard_repository.list_bookings
    ).parameters
    assert "legacy" not in inspect.signature(
        dashboard_repository.weekly_new_counts
    ).parameters
    # The arms that are still genuinely two shapes of one table keep theirs.
    for still_branched in ("list_complaints", "list_amenities", "list_invoices",
                           "list_payments"):
        assert "legacy" in inspect.signature(
            getattr(dashboard_repository, still_branched)
        ).parameters, still_branched


def test_the_booking_projection_reads_amenity_bookings_not_the_series_tables():
    """`0023` moved the booking RPCs onto `amenity_bookings` and parked the old
    tables under `legacy_` names. Nothing has written a series row since --
    hosted holds none -- so the two-query series read answered 0 forever."""
    from app.repositories import dashboard_repository

    client = _RecordingClient()
    dashboard_repository.list_bookings(client, ALPHA)

    assert [q["table"] for q in client.queries] == ["amenity_bookings"]


def test_the_service_reads_events_from_the_key_the_projection_embeds():
    """The repository's embed key and the service's `.get` must move together;
    this is the pair that drifted apart when `0032` took the old name."""
    from app.services.dashboard_service import _visitors

    row = {
        "id": "v2", "requested_by_membership_id": "m1",
        "visitor_events": [{"event_type": "created"}],
    }

    assert _visitors([row], {})[0]["events"] == [{"event_type": "created"}]


def test_the_visitor_card_keeps_every_key_the_frozen_shape_promises():
    """Collapsing the branch must not move the wire contract by one key. The
    window comes from `valid_from`/`valid_until` now, and nothing else about
    the card changes."""
    from app.services.dashboard_service import _visitors

    (card,) = _visitors(
        [{
            "id": "v1", "requested_by_membership_id": "m1",
            "visitor_name": "Ravi", "visitor_phone_e164": "+919000000000",
            "purpose": "Delivery", "status": "approved",
            "valid_from": "2026-08-23T09:00:00+00:00",
            "valid_until": "2026-08-23T11:00:00+00:00",
            "created_at": "2026-08-22T09:00:00+00:00",
            "visitor_events": [],
        }],
        {"m1": {"id": "p1", "name": "Asha", "flat": "A-101", "tower": "A"}},
    )

    assert set(card) == {
        "id", "name", "phone", "purpose", "status", "userId", "requestedBy",
        "flat", "tower", "date", "expectedDate", "expectedTime", "eta",
        "validUntil", "checkedInAt", "checkedOutAt", "createdAt", "events",
    }
    assert card["purpose"] == "Delivery"
    assert card["expectedDate"] == "2026-08-23"
    assert card["validUntil"] == "2026-08-23T11:00:00+00:00"
    assert card["requestedBy"] == "Asha"


def test_the_booking_row_keeps_every_key_the_frozen_shape_promises():
    """`bookingGroupId` was the series id on the legacy arm and is the row's own
    id now, because `amenity_bookings` has no series above it.
    `cancellationReason` stays in the payload as `None` -- the key is part of
    the contract even where the column is not."""
    from app.services.dashboard_service import _bookings

    (row,) = _bookings(
        [{
            "id": "b1", "amenity_id": "a1", "booked_by_membership_id": "m1",
            "starts_at": "2026-08-23T09:00:00+00:00",
            "ends_at": "2026-08-23T10:00:00+00:00",
            "status": "approved", "created_at": "2026-08-22T09:00:00+00:00",
        }],
        {"m1": {"id": "p1", "name": "Asha", "flat": "A-101"}},
    )

    assert set(row) == {
        "id", "bookingGroupId", "amenityId", "residentId", "residentName",
        "residentFlat", "date", "startTime", "endTime", "status", "state",
        "cancellationReason", "createdAt", "updatedAt",
    }
    assert row["bookingGroupId"] == "b1"
    assert row["residentName"] == "Asha"
    assert row["cancellationReason"] is None


def test_weekly_new_counts_ask_the_tables_residents_write():
    """Head-only counts, filtered to the window -- and pointed at the tables the
    rows are actually in. Counting `visitor_access_requests` and
    `legacy_amenity_booking_series` made both chips read `+0 this week` on a
    project where requests were arriving."""
    from app.repositories import dashboard_repository

    client = _RecordingClient()
    counts = dashboard_repository.weekly_new_counts(
        client, ALPHA, since_iso="2026-08-05T00:00:00+00:00"
    )

    assert counts == {
        "residents": 0, "complaints": 0, "visitorRequests": 0, "bookings": 0,
    }
    assert [q["table"] for q in client.queries] == [
        "community_memberships", "complaints", "visitor_requests",
        "amenity_bookings",
    ]
    for query in client.queries:
        assert query["select_kwargs"] == {"count": "exact", "head": True}
        assert ("gte", "created_at", "2026-08-05T00:00:00+00:00") in query["filters"]
        assert ("eq", "community_id", ALPHA) in query["filters"]
    memberships = client.queries[0]
    assert ("eq", "role", "resident") in memberships["filters"]
    assert ("eq", "status", "active") in memberships["filters"]


def test_weekly_new_counts_on_an_executor_ask_the_same_four_tables():
    """The snapshot hands its pool down so the counts join the concurrent
    batch; the executor path must be the sequential path, only faster."""
    from concurrent.futures import ThreadPoolExecutor

    from app.repositories import dashboard_repository

    client = _RecordingClient()
    # One worker keeps the shared recorder's bookkeeping deterministic.
    with ThreadPoolExecutor(max_workers=1) as pool:
        counts = dashboard_repository.weekly_new_counts(
            client, ALPHA,
            since_iso="2026-08-05T00:00:00+00:00", executor=pool,
        )

    assert counts == {
        "residents": 0, "complaints": 0, "visitorRequests": 0, "bookings": 0,
    }
    assert sorted(q["table"] for q in client.queries) == [
        "amenity_bookings", "community_memberships", "complaints", "visitor_requests",
    ]


# ---------------------------------------------------------------------------
# The reads run concurrently; the assembly must not care
# ---------------------------------------------------------------------------


def _stub_reads(monkeypatch, **overrides):
    """Stub every repository read the snapshot performs, `overrides` winning."""
    from app.services import dashboard_service

    reads = {
        "list_memberships": lambda *a, **k: [],
        "list_complaints": lambda *a, **k: [],
        "list_visitors": lambda *a, **k: [],
        "list_amenities": lambda *a, **k: [],
        "list_bookings": lambda *a, **k: [],
        "list_invoices": lambda *a, **k: [],
        "list_payments": lambda *a, **k: [],
        "list_notices": lambda *a, **k: [],
        "list_departments": lambda *a, **k: [],
        "list_activity": lambda *a, **k: [],
        "list_pending_access_requests": lambda *a, **k: [],
        "weekly_new_counts": lambda *a, **k: dict(_WEEKLY),
    }
    reads.update(overrides)
    for name, stub in reads.items():
        monkeypatch.setattr(
            dashboard_service.dashboard_repository, name, stub, raising=True
        )
    monkeypatch.setattr(
        dashboard_service.dashboard_repository, "schema_generation", lambda: "current"
    )
    monkeypatch.setattr(dashboard_service, "get_service_client", lambda: object())


def test_the_snapshot_assembles_correctly_when_reads_finish_out_of_order(monkeypatch):
    """The earliest-submitted reads finish last here, so any assembly that
    depended on completion order (rather than on which future is which) would
    scramble the payload."""
    import time

    from app.domain.schemas import MembershipContext
    from app.services import dashboard_service

    def slow(value, delay):
        def read(*args, **kwargs):
            time.sleep(delay)
            return value
        return read

    _stub_reads(
        monkeypatch,
        # Submitted first, resolves last.
        list_memberships=slow([{
            "id": "m1", "profile_id": "p1", "role": "admin", "status": "active",
            "department_id": None, "profiles": {"full_name": "Asha"},
            "unit_residencies": [],
        }], 0.05),
        list_notices=slow([{"id": "n1", "title": "Water", "body": "off at noon",
                            "published_at": "2026-08-11T00:00:00Z",
                            "created_at": "2026-08-11T00:00:00Z"}], 0.02),
        # Submitted late, resolves first.
        list_departments=lambda *a, **k: [
            {"id": "d1", "name": "Gate", "description": "", "is_active": True}
        ],
    )

    snap = dashboard_service.snapshot(
        MembershipContext(id="m1", community_id=ALPHA, role="admin")
    )

    assert [u["name"] for u in snap.users] == ["Asha"]
    assert [n["id"] for n in snap.notices] == ["n1"]
    assert [d["name"] for d in snap.departments] == ["Gate"]
    assert snap.weeklyNew.model_dump() == _WEEKLY


def test_a_failing_read_fails_the_snapshot_with_its_own_exception(monkeypatch):
    """Concurrency must not soften errors into a partial payload: the read's
    own exception type propagates, exactly as it did sequentially."""
    import pytest

    from app.domain.schemas import MembershipContext
    from app.services import dashboard_service

    class VisitorReadError(RuntimeError):
        pass

    def boom(*args, **kwargs):
        raise VisitorReadError("PGRST200")

    _stub_reads(monkeypatch, list_visitors=boom)

    with pytest.raises(VisitorReadError):
        dashboard_service.snapshot(
            MembershipContext(id="m1", community_id=ALPHA, role="admin")
        )
