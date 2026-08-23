"""`20260821140000_leadership_exclusivity.sql` -- what only a static reader can
check about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a
live database. It installs two triggers, rewrites six functions it does not own,
adds two columns and replaces three RLS policies -- and every one of those is
load-bearing for a rule the product owner froze on 2026-08-21:

    RULING 1  leadership is invite-only and never from the marketplace pool
    RULING 2  leadership is exclusive to one community
    RULING 3  removal severs access completely

So the questions worth asking without a database are these.

**Does it parse, and does it sort last?** A migration that lands before the file
owning a function it rewrites is silently undone. `20260821113000` (the
location-picker work) is the tightest constraint: this file copies
`register_service_provider` forward, and copying it forward is only correct if
this file wins.

**Did the copied bodies survive?** Five functions are reproduced whole to gain a
guard each -- the convention `20260812113000` set. A copy that quietly dropped
`p_location_label`, or the already-a-member skip in the claim, or the
separate-account refusal in registration, would not error. It would delete a
feature.

**Is the claim's refusal a skip rather than a raise?** This is the design
decision the charter asked to be recorded, and it is visible in the SQL: the
blocked branch ends in `continue`, and there is no `raise` anywhere between the
loop's `for` and its `end loop` that a blocked invitation reaches. A `raise`
there would be swallowed by `_claim_staff_invitations` and would abandon every
other pending invitation in the same call, silently.

**Do the errcodes exist in Python?** A SQLSTATE the API cannot map surfaces as a
500 with a generic message, which is precisely the outcome custom SQLSTATEs
exist to prevent.

**Is anything destructive?** Nothing here may delete a row. Both memberships and
provider profiles are somebody's account, and section 9 of the file argues at
length that repairing them is not a migration's decision.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

from app.core import pg_errors

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
LEADERSHIP = MIGRATIONS / "20260821140000_leadership_exclusivity.sql"

#: The file that currently owns each object this one rewrites.
WORK_ORDERS = MIGRATIONS / "0036_work_orders.sql"            # is_own_staff_assignment
NOTIFICATIONS = MIGRATIONS / "0041_person_notifications.sql"  # notify_member, the policy
MESSAGES = MIGRATIONS / "0046_direct_messages.sql"            # the dm policies
PROVISIONING = MIGRATIONS / "20260812090200_staff_provisioning.sql"
LABELS = MIGRATIONS / "20260821113000_location_labels.sql"    # register_service_provider


def sql() -> str:
    return LEADERSHIP.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped.

    This file's headers argue every decision it makes, and several of them quote
    the very identifiers the assertions below look for. A check that read the
    prose would be asserting against its own explanation.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def body(text: str, header: str) -> str:
    """One ``create ... as $$ ... $$;`` body, by the regex that starts it."""
    start = re.search(header, text, re.M)
    assert start, f"no block matching {header!r}"
    end = text.index("$$;", text.index("as $$", start.start()))
    return text[start.start() : end]


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_sorts_after_every_file_whose_work_it_rewrites() -> None:
    """Filename order is apply order.

    ``20260821113000`` is the one that matters most and the one most recently
    added: it put ``p_location_label`` on ``register_service_provider``, and
    this file copies that signature forward. Sorting before it would restore the
    seven-argument version and break the location picker.
    """
    for earlier in (WORK_ORDERS, NOTIFICATIONS, MESSAGES, PROVISIONING, LABELS):
        assert LEADERSHIP.name > earlier.name


#: What a later redeclaration of `claim_staff_invitations` must still contain,
#: fragment by fragment, with the property each one is standing in for. These
#: are the claim-time semantics the three rulings are made of; a copy that lost
#: any of them would not error, it would delete a decision.
CLAIM_SEMANTICS = {
    "continue;": "the refusal is a skip, not a raise",
    "blocked_reason = v_block": "the refusal is recorded on the invitation",
    "blocked_at     = coalesce(blocked_at, now())": "the first refusal is the one stamped",
    "if v_row.blocked_at is null then": "the announcement fires on the edge, once",
    "notify_department_leadership": "the inviting department is still told",
}


def test_nothing_later_redeclares_what_this_file_owns() -> None:
    """Last declaration of a name wins, and this file's *claim-time work* must
    survive.

    The check the name suggests -- nobody may ever redeclare these nine -- is
    stricter than the property that matters, and it became wrong on 2026-08-21
    when `20260821170000_blocked_invitee_notice.sql` added the invitee's half of
    the blocked-invitation announcement. That file redeclares
    `claim_staff_invitations` deliberately and copies this one's body whole,
    which is the house convention (`20260812113000` 1: "the body below was
    extracted mechanically from that file, so the starting point is provably the
    applied text"). `test_location_label_migration.py` had the same thing
    happen to it a few hours earlier, and answered it the same way.

    So `claim_staff_invitations` is exempted **conditionally**: a later
    declaration of it is a clash unless it carries every claim-time semantic
    this file established -- the skip, the two blocked columns, the edge guard
    and the department notification. A file that reverted the refusal to a
    `raise`, or dropped the department's message while adding somebody else's,
    would still fail here, which is the accident this test exists to catch. The
    other eight names remain nobody's to redeclare.
    """
    owned = (
        "is_own_staff_assignment",
        "notify_member",
        "claim_staff_invitations",
        "invite_staff_member",
        "update_staff_invitation",
        "department_staff_invitations",
        "register_service_provider",
        "enforce_leadership_exclusivity",
        "enforce_provider_not_leadership",
    )
    clashes = []
    for path in MIGRATIONS.glob("*.sql"):
        if path.name <= LEADERSHIP.name:
            continue
        text = path.read_text(encoding="utf-8")
        for name in owned:
            if not re.search(
                r"^create (or replace )?(view|function) public\." + name + r"\b",
                text,
                # Case-insensitive because this directory is swept, not read:
                # every migration here is lowercase, but `supabase db diff`
                # writes uppercase, and a redeclaration this pattern cannot see
                # is exactly the shape issue #41's snapshot had.
                re.M | re.I,
            ):
                continue
            if name != "claim_staff_invitations":
                clashes.append((path.name, name, "redeclared at all"))
                continue
            claim = body(
                text, r"^create or replace function public\.claim_staff_invitations"
            )
            loop = claim[claim.index("for v_row in") :]
            if "raise exception" in loop:
                clashes.append((path.name, name, "the loop can raise again"))
            if "status = 'blocked'" in loop:
                clashes.append((path.name, name, "a blocked invitation stops being pending"))
            for fragment, why in CLAIM_SEMANTICS.items():
                if fragment not in loop:
                    clashes.append((path.name, name, why))
    assert not clashes, f"a later migration wins over this one: {clashes}"


def test_every_ddl_statement_is_guarded() -> None:
    """Re-running a hand-applied file must be a no-op.

    The recovery from a half-applied hand-run is to run the file again, so
    every statement has to tolerate its own effect already being present.
    """
    text = statements(sql())

    assert "add column if not exists blocked_reason text" in text
    assert "add column if not exists blocked_at     timestamptz" in text
    assert not re.search(r"add column blocked_", text)

    # Both triggers, dropped before being created: `create trigger` has no
    # `or replace` before PostgreSQL 14 and Supabase does not guarantee one.
    assert text.count("drop trigger if exists") == 2
    assert text.count("create trigger") == 2

    # Three policies replaced, each dropped first.
    assert text.count("drop policy if exists") == 3
    assert text.count("create policy") == 3

    # The one function whose `returns table` signature changes cannot be
    # `create or replace`d.
    assert (
        "drop function if exists public.department_staff_invitations(uuid, text);"
        in text
    )


def test_nothing_is_destructive() -> None:
    """Section 9's argument, enforced rather than promised.

    An account holding two leaderships, or a leadership and a provider profile,
    is somebody's job and somebody's livelihood. Which one they keep is not a
    question this file may answer, so it counts them into a `notice` and touches
    nothing.
    """
    text = statements(sql()).lower()
    for forbidden in ("drop table", "drop column", "truncate", "delete from"):
        assert forbidden not in text, forbidden
    # The only `update` statements are the two inside `claim_staff_invitations`
    # that mark an invitation, both of which the file already owned.
    assert "update public.community_memberships" not in text
    assert "update public.service_providers" not in text
    assert "update public.staff_assignments" not in text


# ---------------------------------------------------------------------------
# Rulings 1 and 2: the invariants
# ---------------------------------------------------------------------------


def test_the_roster_trigger_fires_before_the_write_on_the_right_columns() -> None:
    """A trigger that fires `after` cannot refuse, and one that watches the
    wrong columns does not fire when the rank changes."""
    text = statements(sql())
    trigger = text[text.index("create trigger staff_assignments_leadership_exclusivity"):]
    trigger = trigger[: trigger.index(";")]

    assert "before insert or update of" in trigger
    for column in ("rank", "status", "membership_id", "service_provider_id"):
        assert column in trigger
    assert "for each row" in trigger


def test_the_roster_trigger_refuses_both_rulings_with_distinct_codes() -> None:
    """One trigger, two answers.

    Collapsing them into one code would leave a client unable to offer "hire
    them at technician rank" for one and "wait until they leave" for the other.
    """
    guard = body(
        sql(), r"^create or replace function public\.enforce_leadership_exclusivity"
    )

    # Ruling 1, asked of the row *and* of the account behind it: the column
    # catches a marketplace hire promoted to supervisor, the `exists` catches an
    # account that registered separately.
    assert "new.service_provider_id is not null" in guard
    assert "from public.service_providers" in guard
    assert "errcode = 'HBMKT'" in guard

    # Ruling 2, across every community.
    assert "sa.rank in ('manager', 'supervisor')" in guard
    assert "errcode = 'HBLED'" in guard

    # The early return, so an ordinary technician row and every deactivation
    # pass straight through -- including `remove_department_member`'s own
    # update, which sets rank to `member` and status to `inactive` at once.
    assert "if new.rank not in ('manager', 'supervisor') or new.status <> 'active'" in guard

    # A typed-in roster name has no account, so there is nothing to be
    # exclusive about. Without this the trigger would refuse the department
    # form's own roster rows.
    assert "if v_profile is null then" in guard


def test_the_provider_trigger_closes_the_same_door_from_the_other_side() -> None:
    guard = body(
        sql(), r"^create or replace function public\.enforce_provider_not_leadership"
    )
    assert "public.active_leadership_community(new.profile_id) is not null" in guard
    assert "errcode = 'HBMKT'" in guard


def test_the_leadership_predicate_asks_all_three_active_conditions() -> None:
    """It has to agree with `can_supervise_department`, which one policy asks
    beside it. A predicate that said somebody leads while the authorisation
    predicate said they do not is a hole in one direction or a lockout in the
    other."""
    predicate = body(
        sql(), r"^create or replace function public\.active_leadership_community"
    )
    assert "sa.status = 'active'" in predicate
    assert "m.status = 'active'" in predicate
    assert "m.ended_at is null" in predicate
    assert "sa.rank in ('manager', 'supervisor')" in predicate


# ---------------------------------------------------------------------------
# The copies
# ---------------------------------------------------------------------------


def test_registration_keeps_the_location_label_and_the_older_refusal() -> None:
    """Two features this copy could have deleted without erroring.

    ``p_location_label`` is 2026-08-21's location-picker work, and the
    separate-account refusal is 2026-08-12's. Both live in the body being copied
    forward, and both are invisible in a diff that only reads the new lines.
    """
    register = body(
        sql(), r"^create or replace function public\.register_service_provider"
    )
    assert "p_location_label text default null" in register
    assert "p_location_label\n  );" in register.replace("\r\n", "\n")
    assert "Use a separate account for your professional profile." in register
    assert "errcode = 'HBLOC'" in register
    # The new refusal, and before the old one: a supervisor holds a `worker`
    # membership, which the older check deliberately permits, so it would fall
    # through into a message written for a different reader.
    assert register.index("HBMKT") < register.index(
        "Use a separate account for your professional profile."
    )


def test_the_claim_keeps_every_rule_it_already_had() -> None:
    claim = body(sql(), r"^create or replace function public\.claim_staff_invitations")

    # The derivation table from `20260812090200`'s header.
    assert "if v_row.rank = 'manager' then" in claim
    assert "elsif v_kind = 'security' then" in claim
    # The already-a-member skip that predates this file.
    assert "m.community_id = v_row.community_id" in claim
    # Idempotence: only pending rows are considered.
    assert "s.status = 'pending'" in claim
    # Both writes still happen for an invitation that is not blocked.
    assert "insert into public.community_memberships" in claim
    assert "insert into public.staff_assignments" in claim


def test_the_claim_skips_rather_than_raises() -> None:
    """The claim-time refusal design, asserted where it is decided.

    ``claim_staff_invitations`` runs inside ``resolve_session`` on every
    membership-less session read, and ``_claim_staff_invitations``
    (``auth_service.py``) swallows whatever it raises. So a refusal spelled as
    an exception would not refuse *this* invitation, it would abandon the whole
    call -- including any legitimate invitation later in the same loop -- and it
    would do it silently, on a screen that looks fine.
    """
    claim = body(sql(), r"^create or replace function public\.claim_staff_invitations")
    loop = claim[claim.index("for v_row in") :]

    assert "raise exception" not in loop
    assert loop.count("continue;") == 2  # already-a-member, and blocked
    assert "blocked_reason = v_block" in loop
    assert "blocked_at     = coalesce(blocked_at, now())" in loop
    # The status is untouched, so the admin's correct and withdraw verbs both
    # still apply to a blocked invitation.
    assert "status = 'blocked'" not in loop
    # The department is told, once, on the transition.
    assert "if v_row.blocked_at is null then" in loop
    assert "notify_department_leadership" in loop


def test_the_invitation_refuses_early_and_still_refuses_the_old_collisions() -> None:
    invite = body(sql(), r"^create or replace function public\.invite_staff_member")
    assert "That person already belongs to this community." in invite
    assert "errcode = 'HBMKT'" in invite
    assert "errcode = 'HBLED'" in invite
    # An address with no profile yet is the ordinary case for leadership, and
    # it must not be an error.
    assert "if v_invitee is not null then" in invite

    correct = body(sql(), r"^create or replace function public\.update_staff_invitation")
    assert "errcode = 'HBMKT'" in correct
    assert "errcode = 'HBLED'" in correct
    # Correcting the address is a new question, so any old reason is cleared.
    assert "blocked_reason     = null" in correct


def test_the_invitation_read_carries_the_new_columns() -> None:
    read = body(sql(), r"^create function public\.department_staff_invitations")
    assert "blocked_reason text" in read
    assert "blocked_at     timestamptz" in read
    assert "s.blocked_reason, s.blocked_at" in read
    # The authorisation it always had.
    assert "can_manage_department" in read


# ---------------------------------------------------------------------------
# Ruling 3
# ---------------------------------------------------------------------------


def test_the_ownership_predicate_now_asks_whether_the_row_is_live() -> None:
    """`is_own_staff_assignment` is the predicate behind the worker calendar,
    the job list, leave, availability, every work order the caller was ever
    assigned, their old departures and their old gate rota. It had no time
    condition at all, so a removed worker satisfied it forever."""
    predicate = body(
        sql(), r"^create or replace function public\.is_own_staff_assignment"
    )
    assert "sa.status = 'active'" in predicate
    assert "m.status = 'active'" in predicate
    assert "m.ended_at is null" in predicate
    # The provider arm survives: a marketplace professional is identified by
    # their provider row, and the roster row's own status already catches a
    # removal.
    assert "p.profile_id = auth.uid()" in predicate


def test_the_mailbox_policies_ask_for_an_active_membership() -> None:
    """`0046`'s policies were keyed on the participant columns alone, so a
    removed supervisor kept reading every community-A thread forever --
    including the manager's side of their own departure."""
    text = statements(sql())
    for policy in ("dm_threads_read", "dm_messages_read"):
        block = text[text.index(f"create policy {policy} ") :]
        block = block[: block.index(");") + 2]
        assert "public.is_community_member" in block, policy
        assert "auth.uid()" in block, policy


def test_the_feed_policy_asks_whether_the_membership_is_still_live() -> None:
    text = statements(sql())
    policy = text[text.index("create policy notifications_read_own") :]
    policy = policy[: policy.index(");") + 2]
    assert "recipient_profile_id = auth.uid()" in policy
    assert "public.membership_is_live(recipient_membership_id)" in policy

    # Null means "not about a community at all" and must stay readable: that is
    # the whole population `0041` added the profile column for -- a service
    # professional who has registered and not been hired.
    live = body(sql(), r"^create or replace function public\.membership_is_live")
    assert "p_membership_id is null" in live


def test_the_farewell_notification_survives_the_feed_scoping() -> None:
    """The trap in section 8, closed in section 8.

    ``remove_department_member`` ends the membership and *then* tells the person
    they were removed, keyed to the membership it just ended. Under the policy
    alone that message would be written and instantly invisible -- the one
    notification a removed person most needs, lost to the rule meant to protect
    them.
    """
    notify = body(sql(), r"^create or replace function public\.notify_member")
    assert "case when v_live then p_membership_id else null end" in notify
    # The two refusals `0041` wrote are still there.
    assert "notify_member requires a recipient membership" in notify
    assert "notify_member was given a membership that does not exist" in notify


# ---------------------------------------------------------------------------
# The Python side of the wire
# ---------------------------------------------------------------------------


def test_every_custom_sqlstate_this_file_raises_is_mapped_in_python() -> None:
    """An unmapped SQLSTATE is a 500 with a generic message, which is exactly
    what custom codes exist to prevent. This catches the half-landed change
    where the SQL ships and ``pg_errors`` does not."""
    raised = set(re.findall(r"errcode = '(HB[A-Z0-9]{3})'", sql()))
    assert {"HBMKT", "HBLED"} <= raised
    assert raised <= set(pg_errors._CUSTOM)


def test_the_two_new_codes_are_conflicts_and_are_distinguishable() -> None:
    from app.core.exceptions import ConflictError

    marketplace = pg_errors._CUSTOM["HBMKT"]
    elsewhere = pg_errors._CUSTOM["HBLED"]
    assert marketplace[0] is ConflictError
    assert elsewhere[0] is ConflictError
    assert marketplace[1] != elsewhere[1]
