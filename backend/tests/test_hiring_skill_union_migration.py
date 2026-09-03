"""`20260830090000_hiring_skill_union.sql` -- the three hiring functions that
never learned about `department_skills`.

`20260812090100_skills_and_categories.sql` gave a department an explicit way to
say what it needs and taught exactly one reader about it:
`search_hireable_service_providers`, whose `needed` CTE became the union of the
category path with the new table. Three functions were left gating on the
category path alone -- and that path runs through
`complaint_categories.skill_id`, which `link_category_skill` fills by **exact
name match** against the catalogue. A "Security Management" category against
catalogue entries *Security Guard* and *Gate Officer* derives nothing, so all
three behaved as though the department needed nothing at all: the manager saw
the guard on the candidate list and was refused at invite, and the guard could
neither find the community nor apply to it.

The file's promises, each pinned below:

* **The same three functions, plus one predicate each.** Every body is carried
  forward WHOLE from its live definition -- `20260811162409` for
  `apply_to_department` and `invite_service_provider`, `20260812181443` for
  `search_serviceable_communities` -- and this suite diffs each pair, failing on
  any change outside the marked skill gate. A copied-forward function is the
  shape that silently withdraws a sibling's fix.
* **Signatures byte-identical.** Postgres resolves by argument list: a changed
  one creates a SECOND function and leaves the ungated original standing for
  `app/repositories/hiring_repository.py` to keep calling. The grants are
  reissued anyway, matching what both source files do.
* **UNION, not replacement.** Both paths survive in all three. A department
  that has declared no skills keeps hiring off its categories exactly as
  before; this file adds a second way to say what a department needs and
  withdraws neither the first nor anything else.
* **The two refusals are unchanged text.** `HB403` and `HB409` and their
  sentences are user-facing copy the envelope carries verbatim; this file
  changes *when* they fire, not what they say.
* **It touches nothing else.** No table, no policy, no constraint, no trigger,
  no fourth function -- `department_skills` is only read.

**Not verifiable statically:** that a department whose categories derive no
skill can now actually hire and be applied to, and that the union does not
change who a department with categories *and* declared skills already saw. Both
need the applied database; runbook section 35's post-checks are where they are
proved.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260830090000_hiring_skill_union.sql"

#: The files holding the live bodies this one carries forward. They are also
#: the rollback route named in the header: the pre-image of all three functions
#: lives in them verbatim, which is why this file copied rather than retyped.
ONBOARDING = MIGRATIONS / "20260811162409_service_professional_onboarding.sql"
NEARBY = MIGRATIONS / "20260812181443_search_nearby_communities.sql"

#: The file that introduced `department_skills` and taught one reader about it,
#: and the file that carried that reader forward. Together they hold the union
#: shape this migration copies.
SKILLS = MIGRATIONS / "20260812090100_skills_and_categories.sql"
LOCATION_LABELS = MIGRATIONS / "20260821113000_location_labels.sql"

#: The predecessor the filename had to sort after, so a fresh replay applies
#: this file last.
PREDECESSOR = MIGRATIONS / "20260829120000_drop_legacy_approve_overload.sql"

#: `(function name, source file)` -- the three, and where each body comes from.
FUNCTIONS = (
    ("apply_to_department", ONBOARDING),
    ("invite_service_provider", ONBOARDING),
    ("search_serviceable_communities", NEARBY),
)

#: Signatures, spelled the way the source files' own `grant` statements spell
#: them. Byte-identical is the property that keeps the existing ACL.
SIGNATURES = {
    "apply_to_department": "public.apply_to_department(uuid, text)",
    "invite_service_provider": (
        "public.invite_service_provider(uuid, uuid, text, text, text, text)"
    ),
    "search_serviceable_communities": (
        "public.search_serviceable_communities(text, integer, integer)"
    ),
}

#: The refusals, unchanged. The envelope carries each verbatim to a screen.
REFUSALS = {
    "apply_to_department": (
        "Your skills do not match this department.",
        "HB403",
    ),
    "invite_service_provider": (
        "This person does not have a required skill.",
        "HB409",
    ),
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


def body(path: Path, name: str) -> str:
    """One file's whole `create or replace function public.<name>` statement,
    comments and all -- the comments are half of what is compared between the
    two files."""
    found = re.search(
        rf"create or replace function public\.{name}\(.*?\n\$\$;",
        path.read_text(encoding="utf-8"),
        re.S,
    )
    assert found is not None, f"{name} not found in {path.name}"
    return found.group(0)


def diff(name: str, source: Path) -> tuple[list[str], list[str]]:
    """`(added, removed)` between the source body and this file's, stripped and
    with pure-comment additions dropped -- what is left is the substance."""
    old = body(source, name).splitlines()
    new = body(MIGRATION, name).splitlines()
    added = [
        line[1:].strip()
        for line in difflib.unified_diff(old, new, lineterm="", n=0)
        if line.startswith("+") and not line.startswith("+++")
    ]
    removed = [
        line[1:].strip()
        for line in difflib.unified_diff(old, new, lineterm="", n=0)
        if line.startswith("-") and not line.startswith("---")
    ]
    return (
        [line for line in added if line and not line.startswith("--")],
        [line for line in removed if line and not line.startswith("--")],
    )


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_the_migration_file_exists() -> None:
    """The filename is frozen: the runbook section and two sibling agents name
    this exact string."""
    assert MIGRATION.exists(), MIGRATION.name
    assert MIGRATION.name == "20260830090000_hiring_skill_union.sql"


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(MIGRATION.read_text(encoding="utf-8"))


def test_it_sorts_after_the_last_applied_migration() -> None:
    """Filename order is apply order. Sorting before `20260829120000` would put
    it inside a replay window it was never tested in."""
    assert PREDECESSOR.exists(), PREDECESSOR.name
    assert MIGRATION.name > PREDECESSOR.name, PREDECESSOR.name


def test_it_sorts_after_every_file_whose_bodies_it_carries_forward() -> None:
    """Forward-only. If this file sorted *before* either source, a fresh replay
    would apply the union and then overwrite it with the category-only version
    -- silently, because both declare the same names."""
    for source in (ONBOARDING, NEARBY, SKILLS, LOCATION_LABELS):
        assert MIGRATION.name > source.name, source.name


def test_it_is_the_last_word_on_all_three_functions() -> None:
    """Not "it is last in the directory" -- the property that decides which
    bodies the database ends up holding is being last among the files that
    declare each function."""
    for name, _ in FUNCTIONS:
        declares = sorted(
            path.name
            for path in MIGRATIONS.glob("*.sql")
            if re.search(
                rf"^create (or replace )?function public\.{name}\b",
                path.read_text(encoding="utf-8"),
                re.M,
            )
        )
        assert declares, f"nothing declares {name} at all"
        assert declares[-1] == MIGRATION.name, (name, declares)


# ---------------------------------------------------------------------------
# Exactly the three, with unchanged signatures
# ---------------------------------------------------------------------------


def test_it_re_issues_exactly_the_three_functions() -> None:
    """Three `create or replace function` statements and no fourth. A file that
    carries three bodies forward has no business carrying a neighbour's."""
    text = flat().lower()

    assert len(re.findall(r"create or replace function", text)) == 3
    for name, _ in FUNCTIONS:
        assert f"create or replace function public.{name}(" in text, name

    # The one reader that already knew about `department_skills` is not
    # re-issued here: `20260821113000` owns it and re-stating its body would be
    # a second copy to keep in step.
    assert "function public.search_hireable_service_providers" not in text


def test_the_signatures_are_byte_identical() -> None:
    """The parameter lists are copied, not retyped, so the existing grants
    survive the replace. A changed one would create a SECOND function and leave
    the ungated original standing for the repositories to keep calling."""
    text = MIGRATION.read_text(encoding="utf-8")

    for name, source in FUNCTIONS:
        old = body(source, name)
        new = body(MIGRATION, name)
        # Everything from `create` through the opening `as $$` -- the signature,
        # the return type and the volatility/security decorations.
        head = re.compile(r"^(.*?as \$\$)", re.S)
        assert head.search(old).group(1) == head.search(new).group(1), name

    assert "returns uuid" in text
    assert "returns table (" in text
    assert text.count("security definer") == 3
    assert text.count("set search_path = public") == 3


def test_the_grants_are_reissued_for_all_three() -> None:
    """Reissued rather than relied upon, matching what both source files do:
    this is the file a reader finds first if they ask who may call these."""
    text = flat()

    for signature in SIGNATURES.values():
        revoke = f"revoke all on function {signature} from public, anon;"
        grant = f"grant execute on function {signature} to authenticated;"
        assert revoke in text, signature
        assert grant in text, signature


# ---------------------------------------------------------------------------
# One predicate each, and nothing else
# ---------------------------------------------------------------------------


def test_apply_to_department_changes_only_its_skill_gate() -> None:
    """`20260811162409`'s body, diffed line by line. Every substantive addition
    belongs to the union predicate; the only removals are the category-only
    join it replaces. A third change -- a dropped notification, a moved guard,
    a reworded error -- fails here, which is the whole reason a copied-forward
    function gets a diff test instead of a spot check."""
    added, removed = diff("apply_to_department", ONBOARDING)

    assert removed == [
        "from public.department_categories dc",
        "join public.complaint_categories cc on cc.id = dc.category_id",
        "join public.service_provider_skills sps on sps.skill_id = cc.skill_id",
        "and sps.service_provider_id = v_provider.id",
        "where dc.department_id = v_department.id",
    ], removed

    assert added == [
        "with needed as (",
        "select distinct cc.skill_id",
        "from public.department_categories dc",
        "join public.complaint_categories cc on cc.id = dc.category_id",
        "where dc.department_id = v_department.id and cc.skill_id is not null",
        "union",
        "select distinct ds.skill_id",
        "from public.department_skills ds",
        "where ds.department_id = v_department.id",
        ")",
        "from public.service_provider_skills sps",
        "join needed n on n.skill_id = sps.skill_id",
        "where sps.service_provider_id = v_provider.id",
    ], added


def test_invite_service_provider_changes_only_its_skill_gate() -> None:
    """The same diff on the department's side of the handshake. This is the
    refusal a manager meets *after* the candidate search -- which already reads
    `department_skills` -- has offered them the person."""
    added, removed = diff("invite_service_provider", ONBOARDING)

    assert removed == [
        "select 1 from public.department_categories dc",
        "join public.complaint_categories cc on cc.id = dc.category_id",
        "join public.service_provider_skills sps on sps.skill_id = cc.skill_id",
        "and sps.service_provider_id = v_provider.id",
        "join public.skills s on s.id = sps.skill_id and s.is_active",
        "where dc.department_id = v_department.id",
    ], removed

    assert added == [
        "with needed as (",
        "select distinct cc.skill_id",
        "from public.department_categories dc",
        "join public.complaint_categories cc on cc.id = dc.category_id",
        "where dc.department_id = v_department.id and cc.skill_id is not null",
        "union",
        "select distinct ds.skill_id",
        "from public.department_skills ds",
        "where ds.department_id = v_department.id",
        ")",
        "select 1",
        "from public.service_provider_skills sps",
        "join needed n on n.skill_id = sps.skill_id",
        "join public.skills s on s.id = sps.skill_id and s.is_active",
        "where sps.service_provider_id = v_provider.id",
    ], added


def test_search_serviceable_communities_changes_only_its_matching_cte() -> None:
    """`20260812181443`'s body, diffed. The category join inside
    `matching_departments` is lifted into a `department_needs` CTE that unions
    it with the declared list; the surrounding query -- the proximity rule that
    file exists for, the blacklist and membership exclusions, the ordering and
    the paging -- is untouched."""
    added, removed = diff("search_serviceable_communities", NEARBY)

    assert removed == [
        "with matching_departments as (",
        "join public.department_categories dc on dc.department_id = d.id",
        "join public.complaint_categories cc on cc.id = dc.category_id "
        "and cc.skill_id is not null",
        "on sps.skill_id = cc.skill_id and sps.service_provider_id = v_provider.id",
        "join public.skills s on s.id = cc.skill_id and s.is_active",
    ], removed

    assert added == [
        "with department_needs as (",
        "select dc.department_id, cc.skill_id",
        "from public.department_categories dc",
        "join public.complaint_categories cc on cc.id = dc.category_id "
        "and cc.skill_id is not null",
        "union",
        "select ds.department_id, ds.skill_id",
        "from public.department_skills ds",
        "),",
        "matching_departments as (",
        "join department_needs dn on dn.department_id = d.id",
        "on sps.skill_id = dn.skill_id and sps.service_provider_id = v_provider.id",
        "join public.skills s on s.id = dn.skill_id and s.is_active",
    ], added

    # The `with` that opened `matching_departments` is now the one that opens
    # `department_needs`, so the CTE list is still a single `with`.
    assert flat().count("with matching_departments as (") == 0
    assert flat().count("with department_needs as (") == 1


def test_every_changed_block_is_marked_in_place() -> None:
    """The `-- CHANGED` convention `20260812113000` set, for the reason it set
    it: a partial edit to a function body that lives in another file is a diff
    nobody can review."""
    text = MIGRATION.read_text(encoding="utf-8")

    # One per skill gate, plus the lifted join in `matching_departments`. The
    # colon is the marker; the header's prose mention of the convention is not.
    assert text.count("-- CHANGED:") == 4
    for name, _ in FUNCTIONS:
        assert re.search(
            rf"create or replace function public\.{name}\(.*?-- CHANGED.*?\n\$\$;",
            text,
            re.S,
        ), name


# ---------------------------------------------------------------------------
# UNION, not replacement
# ---------------------------------------------------------------------------


def test_all_three_bodies_now_read_department_skills() -> None:
    """The defect, stated as the property that fixes it. Before this file, one
    of the four readers of a department's needs knew the table existed."""
    for name, _ in FUNCTIONS:
        assert "public.department_skills" in body(MIGRATION, name), name


def test_all_three_bodies_keep_the_category_path() -> None:
    """UNION, not replacement. A department that has picked no skills yet must
    keep hiring exactly as it did yesterday -- this file adds a second way for
    a department to say what it needs, it does not withdraw the first."""
    for name, _ in FUNCTIONS:
        text = body(MIGRATION, name)
        assert "public.complaint_categories" in text, name
        assert "public.department_categories" in text, name
        assert "cc.skill_id is not null" in text, name
        assert re.search(r"^\s*union\s*$", text, re.M), name


def test_no_bare_category_only_gate_survives_in_this_file() -> None:
    """The two shapes the source files used, verbatim. Either one still present
    would be a gate this migration was written to widen and did not."""
    text = flat()

    for orphan in (
        "join public.service_provider_skills sps on sps.skill_id = cc.skill_id",
        "on sps.skill_id = cc.skill_id and sps.service_provider_id = v_provider.id",
        "join public.department_categories dc on dc.department_id = d.id",
    ):
        assert orphan not in text, orphan

    # Every `service_provider_skills` join in the file matches against a set
    # that has a `department_skills` branch, never against `cc.skill_id`.
    assert "cc.skill_id" in text  # it survives, inside the union's first branch
    assert text.count("sps.skill_id = cc.skill_id") == 0


def test_the_union_is_the_shape_the_candidate_search_already_uses() -> None:
    """Copied from `search_hireable_service_providers`, not invented here. The
    list a department is offered and the list it will accept have to be one
    list, and the only way to keep them one is to write them the same way."""
    reference = " ".join(
        statements(LOCATION_LABELS.read_text(encoding="utf-8")).split()
    )
    fragment = (
        "select distinct ds.skill_id from public.department_skills ds "
        "where ds.department_id ="
    )

    assert fragment in reference, "the reference shape moved -- re-derive it"
    assert fragment in flat()


# ---------------------------------------------------------------------------
# The refusals are unchanged text
# ---------------------------------------------------------------------------


def test_the_refusal_sentences_and_codes_are_untouched() -> None:
    """`HB403` and `HB409` map to 403 and 409 (`app/core/pg_errors.py`) and both
    messages travel to a screen verbatim. This file changes *when* they fire,
    not what they say -- a reword here is a reword on somebody's screen."""
    text = flat()

    for name, (sentence, code) in REFUSALS.items():
        assert f"raise exception '{sentence}' using errcode = '{code}';" in text, name
        assert sentence in body(MIGRATION, name), name


def test_it_invents_no_new_error_code() -> None:
    """The codes are exactly the ones the three source bodies already raised."""
    codes = set(re.findall(r"errcode = '(\w+)'", flat()))

    assert codes == {"HB403", "HB404", "HB409", "HBLOC"}, codes


# ---------------------------------------------------------------------------
# It touches nothing else
# ---------------------------------------------------------------------------


def test_it_alters_no_object() -> None:
    """Three functions, their grants, one comment and a schema reload. No DDL
    of any other kind: this file widens three predicates, and a migration that
    also moved a table would be answering a question nobody asked it."""
    text = flat().lower()

    for forbidden in (
        "create table", "alter table", "drop table", "drop function",
        "create policy", "drop policy", "create trigger", "drop trigger",
        "create index", "alter type", "add constraint", "drop constraint",
        "truncate", "delete from",
    ):
        assert forbidden not in text, forbidden


def test_department_skills_is_only_read() -> None:
    """The table this file teaches three functions about is not one it writes.
    Its writers are `set_department_skills` and friends in `20260812090100`;
    the only `insert` here is the `service_applications` row
    `apply_to_department` and `invite_service_provider` have always written."""
    text = flat().lower()

    for write in ("insert into public.department_skills",
                  "update public.department_skills",
                  "delete from public.department_skills"):
        assert write not in text, write

    inserts = set(re.findall(r"insert into (public\.\w+)", text))
    assert inserts == {"public.service_applications"}, inserts
    assert "update public." not in text


def test_it_reloads_the_schema_cache() -> None:
    """Changed function bodies are a catalogue change; without the reload
    PostgREST answers from the definitions it cached."""
    assert "notify pgrst, 'reload schema'" in flat()


# ---------------------------------------------------------------------------
# The file proves its own work
# ---------------------------------------------------------------------------


def test_it_reads_back_the_functions_it_installed() -> None:
    """`create or replace function` succeeds against a category-only body just
    as happily as against these, so the only proof the apply did what the
    header claims is to ask the database for the definitions it now holds. Each
    signature is spelled out in the probe because replacing an overload that is
    not the one the API calls would leave the gate shut with every other check
    passing."""
    text = flat()

    assert "to_regprocedure(" in text
    assert "pg_get_functiondef(" in text
    assert "position('public.department_skills' in v_def)" in text
    assert "position('public.complaint_categories' in v_def)" in text
    assert "position('union' in v_def)" in text

    for signature in SIGNATURES.values():
        assert f"'{signature}'" in text, signature

    for sentence, _ in REFUSALS.values():
        assert f"position('{sentence}' in" in text, sentence


# ---------------------------------------------------------------------------
# The API says the same thing the database does
# ---------------------------------------------------------------------------


def test_the_route_docstrings_carry_the_union_not_the_category_path_alone() -> None:
    """The docstrings are the source of the OpenAPI descriptions and of
    `docs/API.md`. A database that accepts and a document that promises a
    refusal are the same defect from the caller's side."""
    candidates = (
        BACKEND / "app" / "api" / "v1" / "routers" / "department_hiring.py"
    ).read_text(encoding="utf-8")
    communities = (
        BACKEND / "app" / "api" / "v1" / "routers" / "worker_communities.py"
    ).read_text(encoding="utf-8")

    assert "Holds a skill this department's categories need" not in candidates
    assert (
        "departments whose categories need one of the caller's skills"
        not in communities
    )

    for text in (candidates, communities):
        assert "declared" in text
