"""`20260821113000_location_labels.sql` -- what a hand-applied file cannot be
allowed to get wrong.

This migration is pasted into the Supabase SQL editor by a person, once, against
a live database. Nothing in this repository runs it first. It is also the most
dangerous shape a migration takes here: **four functions and two views are
dropped and rewritten whole** to gain one column each, and every one of them is
load-bearing for a different screen. So the checks a static reader can make are
worth more than usual, and they are these:

**Is it idempotent?** Its own header says so, and a header is not what makes it
true. The recovery from a half-applied hand-run is to run the file again.

**Is every old signature actually gone?** Three functions gain a parameter.
`create or replace` cannot add one -- a defaulted parameter creates an
*overload*, after which every existing PostgREST call is "function is not
unique" and fails. The drop has to name the old signature exactly, so the drops
here are diffed against the signatures the previous migrations declared.

**Did the bodies survive the copy?** `search_hireable_service_providers` is
rewritten to add one returned column. A rewrite that quietly changes a radius
predicate or an `order by` would not error; it would change who gets hired.
Every predicate that decides *which* people come back is asserted to have been
carried over character for character.

**Did the coordinates stay out of the hiring read?** The whole feature is a
label on a card that deliberately withholds a home coordinate. A file that adds
`p.latitude` while it is in there widening the same function is the way that
protection dies.

Whether Postgres accepts the bodies is a question only Postgres answers;
`pglast` parsing it is as close as this suite gets.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

from app.domain.geo_schemas import LOCATION_LABEL_MAX_LENGTH

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
LABELS = MIGRATIONS / "20260821113000_location_labels.sql"

#: The file that currently owns each object this one rewrites.
PROVIDERS = MIGRATIONS / "0034_service_providers.sql"            # the overview view
DEPARTURES = MIGRATIONS / "0045_departure_scheduling.sql"        # upsert_service_provider
ONBOARDING = MIGRATIONS / "20260811162409_service_professional_onboarding.sql"
SKILLS = MIGRATIONS / "20260812090100_skills_and_categories.sql"  # the hiring search


def sql() -> str:
    return LABELS.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped.

    This file's header explains the accessibility defect behind the column at
    length, and names every statement it is about to make. A check that read the
    prose would be asserting against its own explanation.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def block(text: str, header: str) -> str:
    """One ``create ... as $$ ... $$;`` body, by the regex that starts it."""
    start = re.search(header, text, re.M)
    assert start, f"no block matching {header!r}"
    end = text.index("$$;", text.index("as $$", start.start()))
    return text[start.start() : end]


def squashed(text: str) -> str:
    """Comments gone, runs of whitespace collapsed. For comparing two bodies."""
    return re.sub(r"\s+", " ", statements(text)).strip()


def tightened(text: str) -> str:
    """Comments gone and **all** whitespace gone.

    For comparing signatures, where the only difference between two spellings of
    the same argument list is where somebody wrapped the line.
    """
    return re.sub(r"\s+", "", statements(text))


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_sorts_after_every_file_whose_work_it_rewrites() -> None:
    """Filename order is apply order.

    `0034` owns `service_provider_overview`, `0045` owns the current
    `upsert_service_provider`, `20260811162409` owns `register_service_provider`,
    `set_my_community_location`, `create_founder_community` and
    `community_settings_overview`, and `20260812090100` owns the hiring search.
    Sorting before any of them would mean this file's work is silently undone by
    the older definition.
    """
    for earlier in (PROVIDERS, DEPARTURES, ONBOARDING, SKILLS):
        assert LABELS.name > earlier.name


def test_nothing_later_redeclares_what_this_file_owns() -> None:
    """Last declaration of a name wins, and this file's *label work* must survive.

    The check the name suggests -- nobody may ever redeclare these seven -- is
    stricter than the property that matters, and it became wrong on 2026-08-21
    when `20260821140000_leadership_exclusivity.sql` added a leadership refusal
    to `register_service_provider`. That file redeclares the name deliberately
    and copies this one's body whole, which is the house convention
    (`20260812113000` 1: "the body below was extracted mechanically from that
    file, so the starting point is provably the applied text").

    So the assertion is the real invariant instead: a later redeclaration is a
    clash **unless it carries the label parameter forward**. A file that
    reverted to the seven-argument signature would still fail here, which is the
    accident this test exists to catch.
    """
    owned = (
        "service_provider_overview",
        "community_settings_overview",
        "upsert_service_provider",
        "register_service_provider",
        "set_my_community_location",
        "create_founder_community",
        "search_hireable_service_providers",
    )
    clashes = []
    for path in MIGRATIONS.glob("*.sql"):
        if path.name <= LABELS.name:
            continue
        text = path.read_text(encoding="utf-8")
        for name in owned:
            start = re.search(
                r"^create (or replace )?(view|function) public\." + name + r"\b",
                text,
                # Case-insensitive because this directory is swept, not read:
                # every migration here is lowercase, but `supabase db diff`
                # writes uppercase, and a redeclaration this pattern cannot see
                # is exactly the shape issue #41's snapshot had.
                re.M | re.I,
            )
            if not start:
                continue
            # The declaration, bounded by the next top-level `create` so a view
            # (which has no `$$`) is measured the same way a function is.
            following = re.search(r"^create ", text[start.end() :], re.M | re.I)
            declaration = text[
                start.start() : start.end()
                + (following.start() if following else len(text))
            ]
            if "location_label" not in declaration:
                clashes.append((path.name, name))
    assert not clashes, (
        "a later migration redeclares one of these and drops the location "
        f"label with it: {clashes}"
    )


def test_every_ddl_statement_is_guarded() -> None:
    """Re-running a hand-applied file must be a no-op.

    The unguarded forms are asserted *absent* rather than the guarded ones
    asserted present: present only says a guarded statement exists somewhere,
    absent says an unguarded one does not.
    """
    body = statements(sql())

    assert "add column if not exists location_label text" in body
    assert not re.search(r"add column location_label", body)
    # `add constraint` has no `if not exists`; the guard is the DO block.
    assert "conname  = 'service_providers_location_label_check'" in body
    assert "conname  = 'communities_location_label_check'" in body
    assert "drop view if exists public.service_provider_overview;" in body
    assert body.count("drop function if exists") == 4


def test_each_changed_function_is_dropped_by_the_signature_it_actually_has() -> None:
    """The overload trap, asserted against the previous files rather than a
    remembered list.

    Adding a defaulted parameter with `create or replace` leaves *two* functions
    of that name, and PostgREST then fails every call with "function is not
    unique". The drop must therefore name the exact argument list the earlier
    migration declared -- so each expected drop below is built from the file that
    owns the old definition, not typed out here.
    """
    body = tightened(sql())

    #: ``function name -> (old argument list, the file that still declares it)``.
    changed = {
        "upsert_service_provider": (
            "text,text,text,text,numeric,numeric,numeric",
            DEPARTURES,
        ),
        "register_service_provider": (
            "text,text,text,numeric,numeric,numeric,uuid[]",
            ONBOARDING,
        ),
        "set_my_community_location": ("uuid,numeric,numeric", ONBOARDING),
        "search_hireable_service_providers": ("uuid,text,integer,integer", SKILLS),
    }
    for name, (signature, owner) in changed.items():
        # The owning migration must still say this is the signature -- otherwise
        # the drop below is correct only by coincidence.
        assert f"public.{name}({signature})" in tightened(
            owner.read_text(encoding="utf-8")
        ), f"{name} no longer has that signature in {owner.name}"
        assert f"dropfunctionifexistspublic.{name}({signature});" in body, name


def test_the_hiring_search_gains_a_label_and_still_returns_no_coordinates() -> None:
    """The point of the whole feature, and the line it must not cross.

    `_CANDIDATE_SELECT` in the repository withholds `latitude`/`longitude` from
    every hiring read. This function is the other half of that promise, and it
    is being rewritten here -- which is exactly when a coordinate would slip in.
    """
    returns = re.search(
        r"create function public\.search_hireable_service_providers.*?returns table \((.*?)\)\s*language",
        sql(),
        re.S,
    )
    assert returns, "the hiring search is not recreated here"
    columns = returns.group(1)

    assert "location_label text" in columns
    assert "latitude" not in columns
    assert "longitude" not in columns


def test_the_rules_that_decide_who_is_hireable_are_carried_over_unchanged() -> None:
    """Distance mechanics are not this file's business.

    Every predicate that decides *which* providers come back, and the ordering
    that decides in what order, is compared against the definition
    `20260812090100` left behind. A rewrite that dropped a `not exists` would
    offer a manager somebody they had blacklisted, and nothing would error.
    """
    old = squashed(
        block(
            SKILLS.read_text(encoding="utf-8"),
            r"^create or replace function public\.search_hireable_service_providers",
        )
    )
    new = squashed(
        block(
            sql(),
            r"^create function public\.search_hireable_service_providers",
        )
    )

    carried = [
        "extensions.st_dwithin(p.location, v_community.location, 500000)",
        "extensions.st_dwithin(p.location, v_community.location, p.service_radius_km * 1000)",
        "from public.blacklisted_service_providers b",
        "from public.staff_assignments sa",
        "order by extensions.st_distance(v_community.location, p.location), lower(p.display_name), p.id",
        "limit greatest(1, least(coalesce(p_limit, 20), 20))",
        "if not public.can_hire_for_department(p_department_id) then",
    ]
    for fragment in carried:
        assert fragment in old, f"{fragment!r} is not what {SKILLS.name} says"
        assert fragment in new, f"{fragment!r} was lost in the rewrite"


def test_the_provider_overview_keeps_every_column_it_had() -> None:
    """The view is dropped and recreated for one column.

    A recreated view that is *slightly* different is the failure mode nobody
    notices: nothing errors, and a profile screen quietly loses `communityCount`
    or `skillNames`. So the old column list is read out of `0034` and each name
    is required to still be there.
    """
    old_view = PROVIDERS.read_text(encoding="utf-8")
    old_body = old_view[
        old_view.index("create view public.service_provider_overview") : old_view.index(
            ") mem on true;"
        )
    ]
    new_view = sql()
    new_body = new_view[
        new_view.index("create view public.service_provider_overview") : new_view.index(
            ") mem on true;"
        )
    ]

    columns = set(re.findall(r"\bp\.(\w+)", old_body)) | set(
        re.findall(r"\bas (\w+)", old_body)
    )
    assert columns, "no columns were parsed out of the old view"
    missing = sorted(name for name in columns if name not in new_body)

    assert not missing, f"the recreated view lost: {missing}"
    assert "p.location_label," in new_body


def test_the_stored_cap_is_the_one_the_wire_model_truncates_to() -> None:
    """120 characters is a privacy boundary, not a storage decision -- long
    enough for "suburb, city, state" and too short for a street address.

    The number lives in two places by necessity (a `check` constraint and the
    label builder that must not emit one the constraint would refuse), so the
    two are compared rather than trusted.
    """
    body = statements(sql())

    assert f"between 1 and {LOCATION_LABEL_MAX_LENGTH}" in body
    assert f"left(btrim(coalesce(p_label, '')), {LOCATION_LABEL_MAX_LENGTH})" in body


def test_nothing_here_touches_a_distance_function_or_a_generated_column() -> None:
    """The one prohibition the change carried from the start: input quality only.

    `location` stays generated from `latitude`/`longitude`, and
    `search_serviceable_communities` -- the provider's own side of the same
    proximity maths -- is not mentioned at all.
    """
    body = statements(sql())

    assert "search_serviceable_communities" not in body
    assert "generated always as" not in body
    assert "drop column" not in body
    assert not re.search(r"alter table public\.\w+\s+alter column", body)
