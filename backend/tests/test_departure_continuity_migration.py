"""`20260821200000_departure_continuity.sql` -- what a static reader can prove
about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a live
database. It closes the gap that a supervisor's removal opens: five notification
kinds are addressed to `work_orders.supervisor_membership_id`, and nothing
anywhere re-pointed that column when the person it named stopped being a
supervisor. After the removal those messages are written to an ended membership
and `20260821140000` 8's feed policy hides them, so a department's live jobs
report their progress into a mailbox nobody can open.

The properties worth asserting without a database are these.

**Does it sort last, and does it stay out of the other files' way?** Three
sibling files pin earlier migrations by name. This one must not redeclare
anything they own -- in particular `claim_staff_invitations`, whose fix (product
ruling 8) is Python-side and deliberately not here.

**Is the copy of `notify_complaint_staff` additive?** It is reproduced whole from
`20260812090300` under the house convention (`20260812113000` 1) to gain one
recipient arm. A copy that quietly dropped the admin call, the null-community
guard or the department-manager predicate would not error -- it would delete an
audience.

**Does re-stamping have exactly one target rule?** The trigger and the backfill
both call `department_supervision_successor`, and that is the point of its
existing: two implementations of "who inherits this" would drift, and the drift
would be invisible until somebody compared a live queue against a deploy log.

**Does it move only live work?** A completed or cancelled job needs no
supervisor, and renaming one is falsifying a record rather than repairing it.

**Is anything destructive?** Nothing here may delete a row or drop a column. The
one `drop` is the roster view, recreated in the same file, and the one `update`
is the re-stamp itself.

Whether Postgres accepts the bodies is a question only Postgres answers; `pglast`
parsing it is as close as this suite gets. The rest is in
`docs/plans/MIGRATION_APPLY_RUNBOOK.md` 16.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

from app.core import pg_errors

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
CONTINUITY = MIGRATIONS / "20260821200000_departure_continuity.sql"

#: The file that currently owns each object this one rewrites or leans on.
WORK_ORDERS = MIGRATIONS / "0036_work_orders.sql"             # supervisor_membership_id
# notify_department_leadership
DEPARTURES = MIGRATIONS / "0043_staff_departures.sql"
SCHEDULING = MIGRATIONS / "0045_departure_scheduling.sql"     # the roster view, removal
ROUTING = MIGRATIONS / "20260812090300_complaint_department_routing.sql"
# membership_is_live
LEADERSHIP = MIGRATIONS / "20260821140000_leadership_exclusivity.sql"

#: The five notification kinds keyed to `work_orders.supervisor_membership_id`.
#: Named here rather than in prose because they are the reason the column has to
#: be re-pointed at all -- every one of them is delivered to whoever it names.
#: `work_order.resident_` is a prefix, not a kind: `0036` 868 concatenates the
#: resident's answer onto it, so `_accepted` and `_declined` never appear as
#: literals anywhere.
SUPERVISOR_KINDS = (
    "work_order.no_candidates",
    "work_order.resident_",
    "work_order.accepted",
    "work_order.completed",
    "work_order.failed",
)

#: What "live" means, everywhere in this file. `staff_open_commitment_count`
#: (`0043` 253) already spelled it this way and the two must agree, or a job
#: counted as booked against somebody is a job nobody re-stamps.
TERMINAL = "w.status not in ('completed', 'cancelled', 'failed')"


def sql() -> str:
    return CONTINUITY.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped.

    This file's header argues every decision it makes and names most of the
    identifiers the assertions below look for -- including the trigger-versus-RPC
    choice, at length. A check that read the prose would be asserting against its
    own explanation.
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


def test_it_sorts_after_every_file_whose_work_it_builds_on() -> None:
    """Filename order is apply order.

    `20260821140000` is the tightest: this file calls `membership_is_live`, which
    that one declares, and it relies on that file's roster trigger having already
    settled what a leadership row may be. `0045` matters for the roster view --
    sorting before it would mean this file's version is silently replaced by the
    one with the dead complaint count.
    """
    for earlier in (WORK_ORDERS, DEPARTURES, SCHEDULING, ROUTING, LEADERSHIP):
        assert CONTINUITY.name > earlier.name


def test_it_leaves_the_claim_alone() -> None:
    """Product ruling 8's fix is Python-side, and that is a decision.

    `claim_staff_invitations` is the most-rewritten function in this directory
    and `20260821170000` -- which the owner has in hand and may not have applied
    when this file goes in -- is its current owner. A redeclaration here would
    have to guess which generation of that body is on the database, and guessing
    wrong reverts the invitee notification without erroring. The claim-pass gap
    is a call site in `auth_service`, so it is fixed at the call site.
    """
    text = statements(sql())
    assert "claim_staff_invitations" not in text
    assert "staff_invitations" not in text


def test_it_redeclares_nothing_the_sibling_files_pin() -> None:
    """The three static-check files next to this one each guard a name list.

    Asserted here as well as there, so the failure names *this* file when it is
    this file that broke the rule.
    """
    text = statements(sql())
    for owned in (
        "register_service_provider",
        "search_hireable_service_providers",
        "service_provider_overview",
        "upsert_service_provider",
        "notify_member",
        "invite_staff_member",
        "update_staff_invitation",
        "is_own_staff_assignment",
        "enforce_leadership_exclusivity",
        "membership_is_live",
        # Removal itself: covered by the trigger instead, so the four entry
        # paths and the PostgREST bypass all get continuity from one place.
        "remove_department_member",
        # Ruling 9: the serviceman release mechanics are not this file's.
        "release_staff_commitments",
        "claim_dispatch_batch",
    ):
        assert not re.search(
            r"^create (or replace )?(view|function) public\." + owned + r"\b",
            text,
            re.M,
        ), owned


def test_it_never_writes_the_dead_complaint_column() -> None:
    """Product ruling 1: complaints stay department-pooled.

    `complaints.assigned_to_membership_id` is written by exactly one function
    (`update_complaint`, `0031` 668) and read by nothing. This file re-points
    *work orders*, which is a different question, and the whole design depends on
    not answering the other one by accident.
    """
    text = statements(sql())
    assert "assigned_to_membership_id" not in text
    assert "assignee_label" not in text
    assert "update public.complaints" not in text


# ---------------------------------------------------------------------------
# Ruling 2: the re-stamp
# ---------------------------------------------------------------------------


def test_the_target_rule_exists_exactly_once() -> None:
    """One function answers "who inherits this", and both callers ask it.

    The trigger and the backfill are written months apart in reading order and
    would be the obvious place for two slightly different orderings to appear.
    They cannot: neither contains a successor search of its own.
    """
    text = statements(sql())
    declaration = (
        "create or replace function public.department_supervision_successor"
    )
    assert text.count(declaration) == 1

    trigger = body(
        text, r"^create or replace function public\.carry_department_supervision"
    )
    assert "department_supervision_successor" not in trigger
    assert "restamp_department_supervision" in trigger

    backfill = text[text.index("do $$") :]
    assert "department_supervision_successor" not in backfill
    assert "restamp_department_supervision" in backfill


def test_the_successor_is_a_live_supervisor_then_the_manager_then_nobody() -> None:
    """The three steps, in that order, and the third one really is "nobody".

    A wrong address is worse than a stale one -- the stale one at least names the
    person the department remembers assigning the job to -- so the search must be
    able to return null rather than widening until it finds somebody.
    """
    successor = body(
        sql(), r"^create or replace function public\.department_supervision_successor"
    )

    assert successor.index("sa.rank          = 'supervisor'") < successor.index(
        "sa.rank          = 'manager'"
    )
    # Both arms ask the same liveness question the feed policy asks, so a
    # successor cannot be somebody whose own membership has ended.
    assert successor.count("m.status   = 'active'") == 2
    assert successor.count("m.ended_at is null") == 3  # two roster arms + the role arm
    assert "sa.status        = 'active'" in successor
    # No community-admin arm, and no unconditional fallback.
    assert "role::text   = 'manager'" in successor
    assert "'admin'" not in successor
    # `desc` alone is `desc nulls first`, which would rank a manager pinned to no
    # department above one pinned to this department -- 2b and 2c backwards.
    assert "desc nulls last" in successor
    assert "return v_target;\nend;" in successor.replace("\r\n", "\n")


def test_the_successor_choice_is_deterministic_and_load_aware() -> None:
    """Two supervisors and a coin toss is a re-run of the backfill that moves
    work around for no reason. The ordering is total: load, then age, then id."""
    successor = body(
        sql(), r"^create or replace function public\.department_supervision_successor"
    )
    assert "order by (" in successor
    assert "), sa.created_at, sa.id" in successor
    # The load term counts the same live-work predicate everything else uses.
    assert TERMINAL in successor


def test_only_live_work_is_re_stamped_and_only_within_the_department() -> None:
    """Two scopes, both load-bearing.

    A completed job needs no supervisor and rewriting it names somebody who was
    not there. And a membership can appear on more than one department's work --
    an admin membership that raised jobs in two of them -- so re-stamping by
    membership alone would hand all of it to whichever department lost them
    first.
    """
    restamp = body(
        sql(), r"^create or replace function public\.restamp_department_supervision"
    )
    assert restamp.count(TERMINAL) == 2  # the pre-check and the update
    assert restamp.count("w.department_id            = p_department_id") == 2
    assert "update public.work_orders" in restamp
    assert "get diagnostics v_moved = row_count;" in restamp
    # Nothing to move to means nothing moves, rather than a null being written.
    assert "if v_target is null then\n    return 0;" in restamp.replace("\r\n", "\n")


def test_the_trigger_fires_after_the_write_on_the_columns_removal_touches() -> None:
    """`after`, deliberately.

    By then the departing row is already `inactive` in the snapshot the successor
    search reads, so "a remaining active supervisor" excludes them by
    construction rather than by an `id <> old.id` a later edit could drop. And
    the columns are the ones `remove_department_member` writes -- it sets
    `status` and `rank` in one update, which is one fire and not two.
    """
    text = statements(sql())
    trigger = text[text.index("create trigger staff_assignments_carry_supervision") :]
    trigger = trigger[: trigger.index(";")]

    assert "after update of rank, status, membership_id" in trigger
    assert "for each row" in trigger
    # The guard: they *were* live leadership, and now they are not.
    assert "old.status = 'active'" in trigger
    assert "old.rank in ('manager', 'supervisor')" in trigger
    assert "new.status <> 'active'" in trigger
    assert "new.rank not in ('manager', 'supervisor')" in trigger
    assert "old.membership_id is not null" in trigger

    # `create trigger` has no `or replace` before PostgreSQL 14 and Supabase does
    # not guarantee one, so re-running the file has to survive its own effect.
    assert (
        "drop trigger if exists staff_assignments_carry_supervision"
        " on public.staff_assignments;"
        in text
    )


def test_the_trigger_is_what_covers_the_postgrest_bypass() -> None:
    """`staff_assignments_admin_write` is `for all to authenticated` with direct
    grants (`20260812200000` 26-31), so an admin can flip `status = 'inactive'`
    without any RPC. That is the fifth removal path and the reason this is a
    trigger at all -- an edit to `remove_department_member` would cover four.

    Checkable statically only as an absence: nothing here may make the
    re-stamping conditional on having arrived through a function.
    """
    trigger = body(
        sql(), r"^create or replace function public\.carry_department_supervision"
    )
    assert "auth.uid()" not in trigger
    assert "current_user" not in trigger
    # The re-stamp runs before any rank test, so a demoted manager's work moves
    # even though the last-supervisor notice below does not apply to them.
    assert trigger.index("restamp_department_supervision") < trigger.index(
        "old.rank <> 'supervisor'"
    )


# ---------------------------------------------------------------------------
# Ruling 3: the manager is told
# ---------------------------------------------------------------------------


def test_the_cover_notice_fires_once_on_the_last_supervisor_edge() -> None:
    """Three gates, each for its own reason: the row was a supervisor, the
    department is one that has a complaint queue, and nobody is left."""
    trigger = body(
        sql(), r"^create or replace function public\.carry_department_supervision"
    )
    assert "if old.rank <> 'supervisor' then" in trigger
    assert "v_department.kind <> 'service'" in trigger
    assert "if v_left > 0 then" in trigger
    assert trigger.count("perform public.notify_department_leadership") == 1
    # The departing person is not told they are covering their own queue.
    assert "old.membership_id);" in trigger


def test_the_cover_notice_reuses_the_existing_leadership_audience() -> None:
    """With zero supervisors left, `notify_department_leadership`'s audience is
    exactly "the community's admins plus this department's manager" -- which is
    precisely the set now covering. A new recipient loop would be a second
    implementation of a rule `0043` 6 already wrote."""
    trigger = body(
        sql(), r"^create or replace function public\.carry_department_supervision"
    )
    assert "notify_department_leadership" in trigger
    assert "notify_community_roles" not in trigger
    assert "insert into public.notifications" not in trigger

    # Dotted namespace, like every other kind in this directory.
    assert "'department.supervision_uncovered'" in trigger


def test_the_cover_notice_links_somewhere_that_exists_for_its_reader() -> None:
    """`/admin/complaints`, not `/manager/complaints`.

    `frontend/src/features/notifications/portalUrl.js` rewrites the admin path to
    the manager's for a manager reader, and that module exists precisely because
    SQL does not know who will read the row. Writing the manager's path here
    would break it for the admins in the same audience.
    """
    trigger = body(
        sql(), r"^create or replace function public\.carry_department_supervision"
    )
    assert "'url', '/admin/complaints'" in trigger
    assert "/manager/" not in trigger


# ---------------------------------------------------------------------------
# Ruling 7 / R18: the complaint audience
# ---------------------------------------------------------------------------


def test_the_complaint_audience_copy_keeps_every_recipient_it_had() -> None:
    """The house convention, checked rather than promised.

    `notify_complaint_staff` is the helper behind six call sites across five
    migrations, so a recipient lost in this copy is a message lost on every one
    of them. Each of the three things the original did is asserted present.
    """
    old = body(
        ROUTING.read_text(encoding="utf-8"),
        r"^create or replace function public\.notify_complaint_staff",
    )
    new = body(sql(), r"^create or replace function public\.notify_complaint_staff")

    for carried in (
        # The null-community early return: a complaint id that matches nothing
        # must not fall through into the loops.
        "if v_complaint.community_id is null then",
        # The admins, by role, through the helper that already knows them.
        "perform public.notify_community_roles(",
        "array['admin']",
        # The department early return, and the manager predicate itself.
        "if v_complaint.department_id is null then",
        "m.department_id = v_complaint.department_id",
        "perform public.notify_member(v_manager.id, p_kind, p_payload);",
    ):
        assert carried in old, f"{carried!r} is not what {ROUTING.name} says"
        assert carried in new, f"{carried!r} was lost in the copy"

    # The signature cannot move: `create or replace` would refuse a changed
    # return type, and a new defaulted parameter would create an overload.
    assert "p_exclude_membership uuid default null" in new
    assert "returns void" in new


def test_the_complaint_audience_gains_supervisors_by_roster_rank() -> None:
    """R18, recorded as done in 2026-08-13's ruling table and never implemented.

    A supervisor is a rank on a roster row in one department, deliberately
    (`0043` 386), so no role-based helper can express them. The arm added here is
    `notify_department_leadership`'s own predicate, narrowed to the complaint's
    department.
    """
    new = body(sql(), r"^create or replace function public\.notify_complaint_staff")

    assert "from public.staff_assignments sa" in new
    assert "sa.rank in ('manager', 'supervisor')" in new
    assert "sa.department_id = v_complaint.department_id" in new
    assert "sa.status        = 'active'" in new


def test_nobody_in_the_complaint_audience_is_told_twice() -> None:
    """An admin who also sits on the department's roster as its supervisor
    satisfies both arms, and being told twice about one complaint reads as a bug
    in the app (`0043` 416, the same argument one level up)."""
    new = body(sql(), r"^create or replace function public\.notify_complaint_staff")
    assert "select distinct m.id" in new
    # The admins were already reached by `notify_community_roles` above.
    assert "m.role::text   <> 'admin'" in new
    # And the caller is still excluded from being told about their own action.
    assert "p_exclude_membership is null or m.id <> p_exclude_membership" in new


# ---------------------------------------------------------------------------
# Ruling 5: the roster count
# ---------------------------------------------------------------------------


def test_the_roster_view_keeps_every_column_it_had_but_the_dead_one() -> None:
    """The view is dropped and recreated for one column.

    A recreated view that is *slightly* different is the failure nobody notices:
    nothing errors, and a roster tile quietly loses `departureStatus`. So the old
    column list is read out of `0045` and each name is required to still be
    there -- except the one being removed.
    """
    old_text = SCHEDULING.read_text(encoding="utf-8")
    old = old_text[
        old_text.index("create view public.department_staff_overview") : old_text.index(
            ") dep on true;"
        )
    ]
    # Comments stripped: this file's own `-- CHANGED` marker names the column it
    # removed, and a check that read it would report the column still present.
    new = statements(sql())
    new = new[
        new.index("create view public.department_staff_overview") : new.index(
            ") dep on true;"
        )
    ]

    columns = set(re.findall(r"\bs\.(\w+)", old)) | set(re.findall(r"\bas (\w+)", old))
    columns.discard("active_assignment_count")
    assert columns, "no columns were parsed out of the old view"
    missing = sorted(name for name in columns if name not in new)
    assert not missing, f"the recreated view lost: {missing}"

    assert "active_assignment_count" not in new
    assert "supervised_work_order_count" in new
    assert "security_invoker = true" in new
    # A recreate drops the grants it had.
    assert "grant select on public.department_staff_overview to authenticated;" in sql()


def test_the_new_count_is_a_definer_function_like_its_sibling() -> None:
    """`0043` 245's argument, one column along.

    The view is `security_invoker`, so a count computed inline would be filtered
    by the reader's own RLS on `work_orders` and would under-report for exactly
    the readers who need it. A number against a roster id the caller already
    holds leaks nothing.
    """
    counter = body(
        sql(), r"^create or replace function public\.staff_supervised_work_order_count"
    )
    assert "security definer" in counter
    assert "stable" in counter
    assert "w.supervisor_membership_id = s.membership_id" in counter
    assert TERMINAL in counter
    # Leadership only, and zero for everybody else rather than absent.
    assert "s.rank in ('manager', 'supervisor')" in counter
    assert "coalesce((" in counter

    # Granted to `authenticated` -- the view calls it as the reader.
    text = statements(sql())
    assert (
        "grant execute on function"
        " public.staff_supervised_work_order_count(uuid)"
        "\n  to authenticated;"
        in text.replace("\r\n", "\n")
    )


def test_the_python_wire_model_agrees_with_the_view() -> None:
    """The half-landed change this catches: the SQL ships and the repository
    still asks PostgREST for a column that no longer exists, which is a 400 on
    every roster read rather than a wrong number."""
    from app.domain.department_schemas import StaffMember
    from app.repositories import departments_repository, hiring_repository

    assert "supervised_work_order_count" in StaffMember.model_fields
    assert "active_assignment_count" not in StaffMember.model_fields
    for projection in (
        departments_repository._STAFF_SELECT,
        hiring_repository._STAFF_MEMBER_SELECT,
    ):
        assert "supervised_work_order_count" in projection
        assert "active_assignment_count" not in projection


# ---------------------------------------------------------------------------
# The backfill, and what the file may not do
# ---------------------------------------------------------------------------


def test_the_backfill_repairs_and_reports_and_refuses_nothing() -> None:
    """The mechanical repair, bounded.

    Every removal before this file left its live work orders addressed to an
    ended membership. Those are repaired to the same rule the trigger uses -- not
    to a remembered one -- and anything with no successor is counted rather than
    guessed at. A `raise exception` here would abort an otherwise clean apply
    over data the file exists to tidy.
    """
    text = statements(sql())
    backfill = text[text.index("do $$") :]

    assert "not public.membership_is_live(w.supervisor_membership_id)" in backfill
    assert TERMINAL in backfill
    assert "raise notice" in backfill
    assert "raise exception" not in backfill
    # A work order with no department has nothing to search; counted, not moved.
    assert "if v_row.department_id is null then" in backfill
    # No write of its own: the repair goes through the same function.
    assert "update public." not in backfill


def test_nothing_is_destructive() -> None:
    """Section 7 repairs an address. It may not remove anything, and the only
    `drop` in the file is the roster view it recreates two lines later."""
    text = statements(sql()).lower()

    for forbidden in (
        "drop table",
        "drop column",
        "drop function",
        "drop policy",
        "truncate",
        "delete from",
        "alter table",
        "create policy",
    ):
        assert forbidden not in text, forbidden

    assert text.count("drop view if exists") == 1
    assert text.count("create view") == 1
    # One `update` statement in the whole file, and it is the re-stamp.
    assert text.count("update public.") == 1
    assert "update public.work_orders" in text


def test_it_raises_nothing_so_there_is_no_sqlstate_to_map() -> None:
    """A SQLSTATE the API cannot map surfaces as a 500 with a generic message.
    This file refuses nothing, which is why `pg_errors` is untouched -- asserted
    rather than assumed, because the check that matters is the same one either
    way."""
    raised = set(re.findall(r"errcode = '(HB[A-Z0-9]{3})'", sql()))
    assert not raised
    assert raised <= set(pg_errors._CUSTOM)


def test_the_five_notification_kinds_it_exists_for_are_named_somewhere() -> None:
    """Not an assertion about this file's SQL -- it writes none of them -- but
    about the claim the whole design rests on: these kinds are addressed to
    `supervisor_membership_id`, so re-pointing that column is what re-points
    them. If one is ever re-keyed to something else, this fails and somebody
    re-reads the argument."""
    keyed = ""
    for path in MIGRATIONS.glob("*.sql"):
        keyed += path.read_text(encoding="utf-8")

    assert "supervisor_membership_id" in keyed
    for kind in SUPERVISOR_KINDS:
        assert f"'{kind}'" in keyed, kind
