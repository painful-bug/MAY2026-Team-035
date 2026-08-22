"""`20260821170000_blocked_invitee_notice.sql` -- what a static reader can prove
about a file nobody in this repository runs.

The file is pasted into the Supabase SQL editor by a person, once, against a live
database. It does one thing: it redeclares `claim_staff_invitations` so that the
person whose leadership invitation was refused is told why, on the same
`blocked_at is null` edge that already tells the department.

That is a small change to a function with a large number of properties, and the
properties are the reason this file exists rather than a diff review:

**Is the copy additive?** The body is copied whole from
`20260821140000_leadership_exclusivity.sql` under the house convention
(`20260812113000` 1). "Whole" is checkable: every non-blank line of the applied
version has to still be there. A copy that quietly dropped the already-a-member
skip, the rank derivation or one of the two inserts would not error -- it would
delete a feature from a function that runs on every membership-less sign-in.

**Is the refusal still a skip?** `claim_staff_invitations` runs inside
`resolve_session` and `auth_service._claim_staff_invitations` swallows what it
raises, so a `raise` anywhere in the loop abandons every *other* pending
invitation in the same call, silently. `notify_profile` is a new call inside that
loop, and this is the check that it did not arrive with an exception behind it.

**Does it fire once?** Both notifications must sit inside the same
`blocked_at is null` guard. A blocked person keeps signing in; a message outside
that guard is a message re-sent on every session read.

**Is the wording the wording?** The two sentences were approved by the product
owner on 2026-08-21 and are frozen. They are asserted character for character
here, because the one thing a reviewer cannot see in a 300-line SQL file is a
comma somebody improved.

**Is anything destructive?** Nothing here may delete or alter a row that is not
the invitation being marked.

Whether Postgres accepts the body is a question only Postgres answers; `pglast`
parsing it is as close as this suite gets. The rest is in
`docs/plans/MIGRATION_APPLY_RUNBOOK.md` 15.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
NOTICE = MIGRATIONS / "20260821170000_blocked_invitee_notice.sql"

#: The file this one copies the function from, and the two it must not overtake.
LEADERSHIP = MIGRATIONS / "20260821140000_leadership_exclusivity.sql"
LABELS = MIGRATIONS / "20260821113000_location_labels.sql"
NOTIFICATIONS = MIGRATIONS / "0041_person_notifications.sql"  # notify_profile
PROVISIONING = MIGRATIONS / "20260812090200_staff_provisioning.sql"

#: The event type. Dotted, in the namespace the department's half already opened.
INVITEE_KIND = "staff_invitation.not_applied"
DEPARTMENT_KIND = "staff_invitation.blocked"

#: Approved verbatim by the product owner, 2026-08-21. `{}` is the community's
#: name, concatenated at write time. Written here with real apostrophes; the SQL
#: doubles them, and `unescaped()` below undoes that before comparing.
PROVIDER_SENTENCE = (
    "couldn't be applied. This account is registered as a marketplace service "
    "professional, and department leadership can't be combined with a provider "
    "profile. Ask the community to invite a different email address."
)
ELSEWHERE_SENTENCE = (
    "couldn't be applied because you already manage or supervise another "
    "community. Leadership is held in one community at a time — once your "
    "current engagement ends, the invitation can be applied on your next sign-in."
)
OPENING = "Your invitation to join "


def sql() -> str:
    return NOTICE.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped.

    This file's header reproduces both approved sentences in prose so a reader of
    the SQL sees them without leaving the file. A check that read the comments
    would be asserting against that copy rather than against the string the
    database will actually store.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def unescaped(text: str) -> str:
    """SQL string literals with their doubled apostrophes turned back into one."""
    return text.replace("''", "'")


def body(text: str, header: str) -> str:
    """One ``create ... as $$ ... $$;`` body, by the regex that starts it."""
    start = re.search(header, text, re.M)
    assert start, f"no block matching {header!r}"
    end = text.index("$$;", text.index("as $$", start.start()))
    return text[start.start() : end]


def claim(text: str) -> str:
    return body(text, r"^create or replace function public\.claim_staff_invitations")


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_sorts_after_every_file_whose_work_it_builds_on() -> None:
    """Filename order is apply order.

    `20260821140000` is the constraint that matters: this file copies its
    `claim_staff_invitations` forward, and sorting before it would restore the
    version with no invitee notification -- silently, because both files declare
    the same name and the last one applied wins.

    **The check used to be "and it is the last file in the directory", and that
    became wrong on 2026-08-21** when `20260821200000_departure_continuity.sql`
    was added -- the same thing that had already happened twice that day, to
    `test_location_label_migration.py` and then to
    `test_leadership_exclusivity_migration.py`, and it is answered here the same
    way. Being last in the directory was never the property; being last *among
    the files that declare this function* is. The departure-continuity file
    declares no `claim_staff_invitations` at all, so it cannot undo anything
    here, and `test_nothing_later_redeclares_the_claim` below is what holds the
    line for one that ever does.
    """
    for earlier in (NOTIFICATIONS, PROVISIONING, LABELS, LEADERSHIP):
        assert NOTICE.name > earlier.name

    # And it is genuinely the last word on this function, not merely later than
    # four named files.
    declares = sorted(
        path.name
        for path in MIGRATIONS.glob("*.sql")
        if re.search(
            r"^create (or replace )?function public\.claim_staff_invitations\b",
            path.read_text(encoding="utf-8"),
            re.M,
        )
    )
    assert declares, "nothing declares claim_staff_invitations at all"
    assert declares[-1] == NOTICE.name


def test_nothing_later_redeclares_the_claim() -> None:
    """The same conditional exemption this file needed from
    `test_leadership_exclusivity_migration.py`, now owed to the next author.

    A later file may redeclare `claim_staff_invitations` -- that is the house
    convention for changing somebody else's function -- but only by carrying both
    halves of the announcement forward. One that told the department and dropped
    the invitee would put the gap this file closed straight back.
    """
    clashes = []
    for path in MIGRATIONS.glob("*.sql"):
        if path.name <= NOTICE.name:
            continue
        text = path.read_text(encoding="utf-8")
        if not re.search(
            r"^create (or replace )?function public\.claim_staff_invitations\b",
            text,
            re.M,
        ):
            continue
        loop = claim(text)
        for fragment in (INVITEE_KIND, DEPARTMENT_KIND, "if v_row.blocked_at is null then"):
            if fragment not in loop:
                clashes.append((path.name, fragment))
    assert not clashes, f"a later migration drops one half of the announcement: {clashes}"


def test_the_copied_body_is_purely_additive() -> None:
    """The house convention, checked rather than promised.

    Every non-blank line of the version `20260821140000` put on the hosted
    database has to still be present. This is the check that catches a copy made
    by retyping instead of by extracting -- the already-a-member skip, the rank
    derivation, both inserts and the claimed-clears-blocked update are all lines
    that can vanish without anything erroring.
    """
    applied = claim(LEADERSHIP.read_text(encoding="utf-8"))
    copied = claim(sql())

    missing = [
        line
        for line in (raw.rstrip() for raw in applied.splitlines())
        if line.strip() and line not in copied
    ]
    assert not missing, f"the copy lost these lines from {LEADERSHIP.name}: {missing}"


def test_the_signature_and_return_type_are_untouched() -> None:
    """`create or replace` cannot change a return type, and would fail on the
    hosted database if this file tried. It also must not gain a defaulted
    parameter, which would create an overload rather than replace anything."""
    copied = claim(sql())
    for column in (
        "membership_id uuid",
        "community_id  uuid",
        "department_id uuid",
        "role          text",
        "rank          text",
    ):
        assert column in copied, column
    assert "p_profile_id uuid" in copied
    assert "p_email      text" in copied
    assert "default" not in copied.split("returns table")[0]


def test_the_refusal_is_still_a_skip() -> None:
    """The property the whole claim-time design rests on, and the one a new call
    inside the loop is most likely to break."""
    loop = claim(sql())
    loop = loop[loop.index("for v_row in") :]

    assert "raise exception" not in loop
    assert "raise " not in loop
    assert loop.count("continue;") == 2  # already-a-member, and blocked
    # The status stays pending, so both admin verbs still apply.
    assert "status = 'blocked'" not in loop
    assert "blocked_reason = v_block" in loop
    assert "blocked_at     = coalesce(blocked_at, now())" in loop


def test_both_notifications_fire_once_and_on_the_same_edge() -> None:
    """One guard, two `perform`s. Two guards could drift; no guard would re-send
    the message on every session read a blocked person makes."""
    loop = claim(sql())
    loop = loop[loop.index("for v_row in") :]

    assert loop.count("if v_row.blocked_at is null then") == 1

    # Bounded by the guard's *own* `end if;` -- the already-a-member skip above
    # closes one earlier in the loop.
    edge = loop.index("if v_row.blocked_at is null then")
    guarded = loop[edge : loop.index("end if;", edge)]
    assert "notify_department_leadership" in guarded
    assert "notify_profile" in guarded
    assert guarded.count("perform public.notify") == 2


def test_the_invitee_is_addressed_as_a_person_and_never_as_a_membership() -> None:
    """`notify_profile`, with the claim's own `p_profile_id`.

    The recipient may hold no membership at all (a registered provider hired
    nowhere) or one in a *different* community (the sitting leader). Addressing
    either through `notify_member` would file the message under a community it is
    not about, and `20260821140000` 8's feed policy would hide it the day that
    membership ended.
    """
    loop = claim(sql())
    call = loop[loop.index("perform public.notify_profile") :]
    call = call[: call.index("));") + 3]

    assert call.startswith("perform public.notify_profile(\n          p_profile_id,")
    assert f"'{INVITEE_KIND}'" in call
    # Distinct from the department's kind: same event, opposite voice.
    assert INVITEE_KIND != DEPARTMENT_KIND
    assert DEPARTMENT_KIND not in call


def test_the_two_approved_sentences_are_stored_verbatim() -> None:
    """Frozen product wording, 2026-08-21. Both are one uninterrupted `body`
    string -- not split across `title` and `body`, which would make the sentence
    depend on which surface reassembled it."""
    text = unescaped(statements(sql()))

    assert OPENING + "'" in text  # the community's name is concatenated in
    assert PROVIDER_SENTENCE in text
    assert ELSEWHERE_SENTENCE in text
    # The em dash in the already-leads sentence is part of the approved wording.
    assert "—" in ELSEWHERE_SENTENCE


def test_the_payload_names_the_community_and_offers_no_link() -> None:
    """The `url` decision, pinned where it was made.

    There is no screen for this: the invitee is not a member of that community,
    no portal lists invitations addressed to you, and the two blocked
    populations land in different portals. `notifications_service` renders a
    missing `url` as `""` and `NotificationBell` then navigates nowhere, which
    is the house answer -- "a guess about where a notification should land is a
    worse failure than no link".
    """
    loop = claim(sql())
    call = loop[loop.index("perform public.notify_profile") :]
    call = call[: call.index("));") + 3]

    assert "'url'" not in call
    for key in ("'title'", "'body'", "'invitationId'", "'communityId'", "'communityName'"):
        assert key in call, key
    # The name comes from `communities`, read inside the same guard.
    assert "from public.communities c where c.id = v_row.community_id" in loop


def test_nothing_is_destructive_and_nothing_else_is_declared() -> None:
    """One function and one counting block. A file this small has no business
    touching a table, a policy, a trigger or a grant."""
    text = statements(sql()).lower()

    for forbidden in (
        "drop table",
        "drop column",
        "drop function",
        "drop policy",
        "drop trigger",
        "truncate",
        "delete from",
        "alter table",
        "create policy",
        "create trigger",
        "create view",
    ):
        assert forbidden not in text, forbidden

    # Exactly one function, and it is the claim.
    assert len(re.findall(r"^create (or replace )?function ", text, re.M)) == 1
    assert "create or replace function public.claim_staff_invitations" in text

    # The only writes are the two `staff_invitations` updates the copied body
    # already owned.
    assert text.count("update public.staff_invitations") == 2
    for table in ("community_memberships", "service_providers", "staff_assignments"):
        assert f"update public.{table}" not in text


def test_the_pre_existing_blocked_rows_are_counted_and_left_alone() -> None:
    """`20260821140000` 9's argument at a smaller scale: an invitation blocked
    before this file was applied has already crossed the edge, and re-arming it
    would mean writing `blocked_at` backwards. The count goes in the deploy log;
    nothing is repaired."""
    text = statements(sql())

    counting = text[text.index("do $$") :]
    assert "from public.staff_invitations s" in counting
    assert "s.blocked_at is not null" in counting
    assert "raise notice" in counting
    assert "raise exception" not in counting
    # The notice names `update_staff_invitation` as the remedy; it must not
    # *run* an update of its own.
    assert "update public." not in counting
