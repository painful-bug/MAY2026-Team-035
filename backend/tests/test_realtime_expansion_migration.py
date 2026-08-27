"""`20260826090000_realtime_expansion.sql` -- three emitters the outbox was
missing: work orders, resident-visible amenity changes, and direct messages.

The file's promises, each pinned below:

* **Hints, not truth.** Every payload is ids and one status word. Nothing that
  a client could render without re-reading -- no body, no title, no name --
  because a frame that carried content would be a second copy of it able to
  drift from the RLS-scoped read (`0030`'s reasoning, kept).
* **Additional, not a replacement.** The generic `dashboard.refresh` triggers
  on the amenity tables stay. The only trigger names this file drops are its
  own three, so `0028`'s {admin, manager} scoping of the generic topic is
  untouched and admins converge exactly as before.
* **The sender is excluded, the recipient is resolved.** `message.created` is
  `audience = 'member'` per recipient participant, bridged from the thread's
  profile ids (`0046`) to an active membership (`0028`'s addressing), with the
  author skipped by `is not distinct from` so a system line still reaches both.
* **Ordering** is asserted against ONE named predecessor (ruling G9,
  `docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`), plus the files that create
  every object this one touches.

**Not verifiable statically:** that hosted's `sse_events` carries `0028`'s
audience columns and shape constraint. Both sort long before this file and the
runbook's ledger says they are applied; the apply itself is the only proof.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260826090000_realtime_expansion.sql"

#: The file this one had to sort after when it was written -- the named
#: predecessor idiom of ruling G9, not a NEW_FILES set that needs editing every
#: time a sibling lands.
LATEST_PREDECESSOR = MIGRATIONS / "20260824090000_supervisor_take_up.sql"

EMITTERS = (
    "emit_work_order_sse_event",
    "emit_amenity_sse_event",
    "emit_message_sse_event",
)

#: The only trigger names this file may drop or create: its own.
OWN_TRIGGERS = {
    "work_orders_sse_event",
    "amenity_bookings_amenity_sse",
    "amenity_booking_series_amenity_sse",
    "dm_messages_sse_event",
}


def statements(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def sql() -> str:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def flat() -> str:
    """The SQL with whitespace collapsed, for assertions that span lines."""
    return " ".join(sql().split())


def function_body(name: str) -> str:
    """One emitter's `create or replace function ... $$ body $$` text."""
    found = re.search(
        rf"create or replace function public\.{name}\(\)(.*?)\$\$(.*?)\$\$;",
        flat(),
    )
    assert found is not None, f"{name} not found"
    return found.group(1) + found.group(2)


def creators_of(table: str) -> list[str]:
    """Every migration that creates ``table``, derived from the texts."""
    return [
        path.name
        for path in sorted(MIGRATIONS.glob("*.sql"))
        if re.search(
            rf"create\s+table\s+(?:if\s+not\s+exists\s+)?public\.{table}\b",
            statements(path.read_text(encoding="utf-8")),
            re.I,
        )
    ]


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(MIGRATION.read_text(encoding="utf-8"))


def test_it_sorts_after_the_file_it_had_to_follow() -> None:
    """Forward-only: a version below the latest on a shared branch is invisible
    to a fresh replay that has already passed it."""
    assert LATEST_PREDECESSOR.exists(), LATEST_PREDECESSOR.name
    assert MIGRATION.name > LATEST_PREDECESSOR.name, LATEST_PREDECESSOR.name


def test_it_sorts_after_everything_it_reasons_about() -> None:
    """The outbox (`0007`), its audience columns (`0028`), the member-emitter
    template (`0030`), and every file creating a table this one triggers on
    must all be applied before this file runs on a fresh replay."""
    for earlier in (
        "0007_dashboard_realtime_outbox.sql",
        "0028_event_audience.sql",
        "0030_notifications.sql",
    ):
        assert (MIGRATIONS / earlier).exists(), earlier
        assert MIGRATION.name > earlier

    for table in ("work_orders", "amenity_bookings", "dm_threads", "dm_messages"):
        creators = creators_of(table)
        assert creators, f"nothing creates public.{table} -- derivation broken"
        assert MIGRATION.name > max(creators), (table, creators)


# ---------------------------------------------------------------------------
# The emitters, as a set
# ---------------------------------------------------------------------------


def test_every_emitter_is_security_definer_with_a_pinned_search_path() -> None:
    """The posture of every emitter since `0007`: the trigger runs as the
    definer so RLS on `sse_events` (service-role only, `0024`) does not block
    the write, and the search path is pinned so nothing resolves elsewhere."""
    for name in EMITTERS:
        body = function_body(name)
        assert "security definer" in body, name
        assert "set search_path = public" in body, name


def test_it_drops_nothing_it_did_not_create_and_is_idempotent() -> None:
    """Every `drop trigger` names one of this file's own triggers -- the
    generic `dashboard_sse_*` / `amenity_bookings_sse` triggers survive -- and
    every function lands via `create or replace`. Nothing else is touched."""
    text = flat().lower()

    dropped = set(re.findall(r"drop trigger if exists (\w+)", text))
    assert dropped <= OWN_TRIGGERS, dropped - OWN_TRIGGERS
    assert "dashboard_sse" not in text
    assert len(re.findall(r"create or replace function", text)) == len(EMITTERS)

    for forbidden in (
        "drop function", "drop table", "drop policy", "create table",
        "create policy", "alter table", "alter type", "truncate",
        "delete from", "update public.",
    ):
        assert forbidden not in text, forbidden


# ---------------------------------------------------------------------------
# 1. Work orders
# ---------------------------------------------------------------------------


def test_work_order_events_reach_the_community_with_a_minimal_hint() -> None:
    body = function_body("emit_work_order_sse_event")

    assert "'work_order.changed'" in body
    assert "'community'" in body
    for key in ("'table'", "'work_order_id'", "'complaint_id'", "'status'"):
        assert key in body, key
    # A hint, not truth: nothing renderable rides in the frame.
    for leak in ("'title'", "'body'", "'location'", "'priority'", "'name'"):
        assert leak not in body, leak
    # No role list and no recipient: the community audience shape (`0028`).
    assert "audience_roles" not in body
    assert "recipient_membership_id" not in body


def test_the_work_order_emitter_handles_delete_from_the_old_row() -> None:
    """`to_jsonb(old)` on DELETE and `return old`, `0007`'s own arm -- a
    deleted job must still nudge the dashboards that listed it."""
    body = function_body("emit_work_order_sse_event")

    assert "tg_op = 'DELETE' then to_jsonb(old)" in body
    assert "if tg_op = 'DELETE' then return old; end if;" in body


def test_the_work_order_trigger_covers_every_write() -> None:
    assert (
        "create trigger work_orders_sse_event "
        "after insert or update or delete on public.work_orders "
        "for each row execute function public.emit_work_order_sse_event();"
    ) in flat()


# ---------------------------------------------------------------------------
# 2. Amenities
# ---------------------------------------------------------------------------


def test_the_amenity_hint_is_the_table_and_the_amenity_and_nothing_else() -> None:
    body = function_body("emit_amenity_sse_event")

    assert "'amenity.changed'" in body
    assert "'community'" in body
    assert "'amenity_id'" in body
    assert "'table'" in body
    # The booker, the slot and the status stay behind the read.
    for leak in ("'booked_by", "'starts_at'", "'ends_at'", "'status'"):
        assert leak not in body, leak


def test_the_amenity_trigger_is_additional_on_amenity_bookings() -> None:
    """A second trigger beside `0007`'s generic one, under a name of its own --
    the test above proves the generic name is never dropped, this one proves
    the new trigger exists at all."""
    assert (
        "create trigger amenity_bookings_amenity_sse "
        "after insert or update or delete on public.amenity_bookings "
        "for each row execute function public.emit_amenity_sse_event();"
    ) in flat()


def test_the_series_attach_is_guarded_by_existence() -> None:
    """No current database holds `public.amenity_booking_series` -- `0023`
    never creates it and hosted parked its legacy namesake -- so an unguarded
    `create trigger` would fail the fresh replay. The guard is `to_regclass`,
    `0007`'s posture for the same situation."""
    text = flat()
    guard = text.index("to_regclass('public.amenity_booking_series')")
    attach = text.index("create trigger amenity_booking_series_amenity_sse")

    assert guard < attach
    assert "execute 'create trigger amenity_booking_series_amenity_sse" in text


# ---------------------------------------------------------------------------
# 3. Messages
# ---------------------------------------------------------------------------


def test_a_message_is_addressed_to_the_member_not_the_community() -> None:
    body = function_body("emit_message_sse_event")

    assert "'message.created'" in body
    assert "'member'" in body
    assert "recipient_membership_id" in body
    for key in ("'thread_id'", "'message_id'"):
        assert key in body, key
    # The body travels only through the RLS-scoped read.
    assert "new.body" not in body
    assert "'body'" not in body


def test_the_sender_is_excluded_and_a_system_line_reaches_both() -> None:
    """`is not distinct from` against the author: the sender is skipped, and a
    null author (the `0046` lock notice) equals neither participant, so both
    get the nudge."""
    body = function_body("emit_message_sse_event")

    assert "is not distinct from new.author_profile_id" in body
    assert "participant_a_profile_id" in body
    assert "participant_b_profile_id" in body


def test_the_recipient_is_resolved_to_an_active_membership() -> None:
    """The bridge from `0046`'s profile-addressed thread to `0028`'s
    membership-addressed stream, with the same liveness predicate every other
    membership lookup in the directory uses."""
    body = function_body("emit_message_sse_event")

    assert "m.community_id = v_thread.community_id" in body
    assert "m.status = 'active'" in body
    assert "m.ended_at is null" in body


def test_the_message_trigger_fires_on_insert_only() -> None:
    """Messages are append-only (`0046` exposes no update or delete), so an
    update/delete arm would be a trigger waiting to fire on writes that cannot
    happen -- and a re-nudge on an edit is not a designed behaviour."""
    found = re.search(
        r"create trigger dm_messages_sse_event (.*?);",
        flat(),
    )
    assert found is not None
    definition = found.group(1)

    assert definition == (
        "after insert on public.dm_messages "
        "for each row execute function public.emit_message_sse_event()"
    ), definition


# ---------------------------------------------------------------------------
# The file proves its own work
# ---------------------------------------------------------------------------


def test_it_verifies_every_trigger_it_claims_to_have_made() -> None:
    """Named checks, not bare existence ones -- `work_orders` had no trigger at
    all, so 'some trigger is present' would pass against nothing useful. The
    series check is conditional on the same `to_regclass` that gates its
    attach, so the two cannot disagree."""
    text = flat()

    for table, trigger in (
        ("work_orders", "work_orders_sse_event"),
        ("amenity_bookings", "amenity_bookings_amenity_sse"),
        ("dm_messages", "dm_messages_sse_event"),
    ):
        assert f"tgrelid = 'public.{table}'::regclass" in text, table
        assert f"tgname = '{trigger}'" in text, trigger
        assert f"{trigger} missing on public.{table}" in text, trigger
    # The series arm may NOT use a literal `::regclass` cast: the cast is
    # resolved at expression-planning time, before the `to_regclass` guard is
    # evaluated, so it raises 42P01 on any database without the table -- which
    # is every current database. Hosted proved this on 2026-08-27.
    assert "tgrelid = 'public.amenity_booking_series'::regclass" not in text
    assert "tgrelid = to_regclass('public.amenity_booking_series')" in text
    assert "tgname = 'amenity_booking_series_amenity_sse'" in text
    assert (
        "amenity_booking_series_amenity_sse missing on public.amenity_booking_series"
        in text
    )
    assert "raise exception" in text
    assert "not tgisinternal" in text
