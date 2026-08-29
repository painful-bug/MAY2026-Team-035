"""`20260828090000_residence_claim_on_join.sql` -- what a static reader can
prove about the file that makes approval put people somewhere.

The 2026-08-27 rulings are three: the applicant claims their residence as free
text at request time (the privacy invariant keeps the unit list away from
non-members, so there is nothing to pick from), **approval requires a unit**,
and the inventory gap is closed by find-or-create at approval. The hazards of
implementing them are each a different shape, so the checks below are three
suites wearing one hat.

**The RPC is a signature change on a carried body.** PostgREST cannot dispatch
overloads, so the old 4-argument `approve_access_request` must be dropped, not
joined -- and a copy's hazard is what it quietly drops on the way through. The
body's load-bearing statements are therefore not typed in here from a review:
they are **extracted from `20260730170036`'s own text** -- the last file to
define this function, hence the body the database is holding -- and each must
survive verbatim. The one deliberate removal, the `if target_unit_id is not
null` guard around the residency insert, is asserted as an absence: after the
gate the condition is always true, and the ruling is precisely that no
approval happens without a unit.

**The gate is new code**, and what matters is where it stands: `HBUNT` must
fire before the membership insert, so a refused approval writes nothing and
the request stays cleanly pending for the retry that carries a unit.

**The view is an append.** `create or replace view` permits appending and
nothing else; a reorder fails the apply, but a *dropped* column would fail it
too while a test that hardcodes the new list would happily bless a wrong one.
The old order is derived from `0024`'s own text and must survive as a prefix.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

from app.core import pg_errors
from app.core.exceptions import ValidationError

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
CLAIM = MIGRATIONS / "20260828090000_residence_claim_on_join.sql"

#: The body this file carries forward: the last previous definer of
#: `approve_access_request`, which is the definition the database is holding.
LEGACY_COMPATIBLE = (
    MIGRATIONS / "20260730170036_make_resident_approval_legacy_index_compatible.sql"
)
#: The file whose view definition section 3 appends to.
REALTIME_JOIN = MIGRATIONS / "0024_realtime_join_requests.sql"
#: The find-or-create shape's reference: one building per villa.
FOUNDER = MIGRATIONS / "20260805144502_replace_legacy_founder_rpc.sql"

OLD_SIGNATURE = "public.approve_access_request(uuid, uuid, uuid, public.residency_relationship)"
NEW_SIGNATURE = (
    "public.approve_access_request(uuid, uuid, uuid, public.residency_relationship, text, text)"
)

#: The statements of `20260730170036`'s body that must survive the copy, each
#: written as (start marker, end marker) over that file's own text so the
#: expected fragment is extracted rather than reviewed. The guard being
#: deliberately removed sits between the last two, so no span crosses it.
CARRIED_SPANS = (
    # The lock, and the not-found refusal behind it.
    ("  select * into request_row", "raise exception 'Access request not found';"),
    # The reviewer must hold active admin on this community.
    (
        "  select id into reviewer_membership_id",
        "raise exception 'Active administrator membership required';",
    ),
    # The idempotent already-approved return, and the pending check after it.
    (
        "  if request_row.status = 'approved' then",
        "raise exception 'Access request is no longer pending';",
    ),
    # coalesce(p_unit_id, requested_unit_id) and the community/active check.
    (
        "  if target_unit_id is null then",
        "raise exception 'Selected unit does not belong to this community';",
    ),
    # The membership insert, its unique_violation fallback, and the re-select
    # that names the incompatible-membership refusal.
    (
        "  begin\n    insert into public.community_memberships(",
        "raise exception 'Applicant already has an incompatible membership';",
    ),
    # The residency insert -- hosted-only `created_by_membership_id` included
    # -- and its swallow. Extracted from inside the old guard, so the span
    # starts at `begin`, which is the part that survives un-indented.
    (
        "insert into public.unit_residencies(",
        "when unique_violation then null;",
    ),
    # The final update of the request row.
    ("  update public.access_requests\n  set status = 'approved',", "where id = request_row.id;"),
)


def sql() -> str:
    return CLAIM.read_text(encoding="utf-8")


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped, so no check ever
    asserts against the header's prose instead of the SQL. This file's header
    quotes the very signatures and SQLSTATEs the checks below reason about, and
    its last section is nothing but commented-out queries."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def body(text: str) -> str:
    """The function body: from its `as $$` through the closing `$$;`."""
    start = text.index("create function public.approve_access_request(")
    open_marker = text.index("as $$", start)
    return text[open_marker : text.index("\n$$;", open_marker)]


def old_body() -> str:
    text = LEGACY_COMPATIBLE.read_text(encoding="utf-8")
    start = text.index("create or replace function public.approve_access_request(")
    open_marker = text.index("as $$", start)
    return text[open_marker : text.index("\n$$;", open_marker)]


def carried(span: tuple[str, str]) -> str:
    """The expected fragment, extracted from the predecessor's own text."""
    source = old_body()
    start_marker, end_marker = span
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start) + len(end_marker)]


def stripped_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def survives(fragment: str, whole: str) -> bool:
    """``fragment`` appears in ``whole`` as a contiguous run of statements.

    Indentation-normalised, because the one deliberate removal -- the
    `if target_unit_id is not null` guard -- un-nests the residency insert by
    one level. Every *line* must still survive, in order and unbroken; only
    the leading whitespace may differ."""
    needle = stripped_lines(fragment)
    haystack = stripped_lines(whole)
    return any(
        haystack[i : i + len(needle)] == needle
        for i in range(len(haystack) - len(needle) + 1)
    )


def view_columns(text: str) -> list[str]:
    """The output column names of the `pending_access_request_overview`
    definition in ``text``, in order, derived from the select list itself."""
    stripped = statements(text)
    start = stripped.index(
        "create or replace view public.pending_access_request_overview"
    )
    select_start = stripped.index("select", start)
    from_end = stripped.index("from public.access_requests", select_start)
    names = []
    for item in stripped[select_start + len("select") : from_end].split(","):
        item = item.strip()
        if not item:
            continue
        names.append(
            item.split(" as ")[-1].strip() if " as " in item else item.split(".")[-1]
        )
    return names


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(sql())


def test_it_is_the_last_word_on_approve_access_request() -> None:
    """Filename order is apply order, and `create or replace` means the last
    file to define a function wins. Not "it is the newest file in the
    directory" -- that property expires the day the next migration lands -- but
    last *among the files that define this function*, derived by scanning the
    directory's own text rather than naming the predecessors from memory."""
    definers = sorted(
        path.name
        for path in MIGRATIONS.glob("*.sql")
        if re.search(
            r"^\s*create (or replace )?function public\.approve_access_request\s*\(",
            path.read_text(encoding="utf-8"),
            re.M | re.I,
        )
    )
    assert len(definers) >= 2, "the derivation found no predecessor at all"
    assert LEGACY_COMPATIBLE.name in definers
    assert definers[-1] == CLAIM.name, definers


def test_it_sorts_after_every_file_it_reasons_about() -> None:
    for earlier in (REALTIME_JOIN, FOUNDER, LEGACY_COMPATIBLE):
        assert earlier.exists(), earlier.name
        assert CLAIM.name > earlier.name, earlier.name


def test_it_declares_no_function_beyond_the_one_it_re_issues() -> None:
    declared = set(
        re.findall(
            r"^create (?:or replace )?function public\.(\w+)",
            statements(sql()),
            re.M,
        )
    )
    assert declared == {"approve_access_request"}, sorted(declared)


# ---------------------------------------------------------------------------
# The signature change -- a drop, then exactly one create
# ---------------------------------------------------------------------------


def test_the_old_signature_is_dropped_by_name_and_before_the_create() -> None:
    """PostgREST refuses to dispatch overloads: with both signatures in the
    catalogue, `POST /rpc/approve_access_request` answers 300 for every caller.
    The drop must name the exact old signature -- a bare `drop function` is an
    error with two candidates -- and precede the create, or it drops the new
    body instead."""
    text = statements(sql())
    drop = f"drop function if exists {OLD_SIGNATURE};"
    assert drop in text
    assert text.index(drop) < text.index(
        "create function public.approve_access_request("
    )


def test_the_new_signature_is_the_frozen_six_arguments() -> None:
    """A wrong signature here simply becomes the signature, and the repository
    call answers 404 forever. The four existing parameters keep their names and
    order -- PostgREST dispatches named payload keys -- and the two new ones
    default to null so a pre-migration backend's 4-key payload still binds."""
    text = statements(sql())
    assert (
        "create function public.approve_access_request(\n"
        "  p_request_id uuid,\n"
        "  p_reviewer_profile_id uuid,\n"
        "  p_unit_id uuid default null,\n"
        "  p_relationship public.residency_relationship default null,\n"
        "  p_unit_code text default null,\n"
        "  p_building_code text default null\n"
        ")" in text
    )
    assert "returns jsonb" in text
    assert "security definer" in text
    assert "set search_path = public" in text


def test_the_audience_is_service_role_only_on_the_new_signature() -> None:
    """The drop took the old ACL with it, so the grant is not a restatement --
    and it must name the 6-argument signature, because the 4-argument one no
    longer exists to be granted. service_role only: the backend calls this RPC
    through the service client, and the reviewer check inside the body is the
    authorisation, exactly as before."""
    text = statements(sql())
    assert (
        f"revoke all on function {NEW_SIGNATURE}\n  from public, anon, authenticated;"
        in text
    )
    assert f"grant execute on function {NEW_SIGNATURE}\n  to service_role;" in text
    grants = re.findall(r"grant execute on function[^;]+;", text)
    assert len(grants) == 1, grants
    assert "service_role" in grants[0]
    assert OLD_SIGNATURE not in "".join(grants)


# ---------------------------------------------------------------------------
# The carried body -- extracted from the predecessor, not reviewed
# ---------------------------------------------------------------------------


def test_every_load_bearing_statement_of_the_old_body_survives() -> None:
    """The copy's hazard is what it quietly drops. Each span is extracted from
    `20260730170036`'s own text -- the definition the database is holding --
    and must appear verbatim in the new body: the FOR UPDATE lock, the
    reviewer's active-admin check, the idempotent already-approved return, the
    pending check, the `coalesce(p_unit_id, requested_unit_id)` fallthrough
    with its community/active validation, the membership insert with its
    unique_violation fallback and incompatible-membership refusal, the
    residency insert with `created_by_membership_id` (hosted-only, kept) and
    its swallow, and the final update."""
    new = body(sql())
    for span in CARRIED_SPANS:
        fragment = carried(span)
        assert survives(fragment, new), (
            f"dropped in the copy: {span[0]!r}..{span[1]!r}"
        )
    assert "for update;" in new
    assert (
        "coalesce(p_relationship, request_row.requested_relationship)" in new
    )


def test_the_residency_insert_lost_its_guard_and_nothing_else() -> None:
    """Ruling 2 makes the guard dead: after the gate, `target_unit_id` cannot
    be null. A guard that can no longer be false is a sentence claiming this
    function still mints unitless residents, so it goes -- and its removal is
    the ONLY removal around that insert."""
    new = body(sql())
    assert "if target_unit_id is not null then\n    begin" in old_body()
    assert "if target_unit_id is not null then\n    begin" not in new
    # The insert itself survives, swallow included (asserted fragment-for-
    # fragment in the carried-spans test); here, that it is unconditional:
    # nothing between the gate's `end if;` block and the membership insert
    # re-tests target_unit_id.
    residency = new.index("insert into public.unit_residencies(")
    membership = new.index("insert into public.community_memberships(")
    assert membership < residency
    assert "if target_unit_id is not null" not in new[membership:residency]


# ---------------------------------------------------------------------------
# The resolution, and the gate
# ---------------------------------------------------------------------------


def test_the_gate_refuses_before_anything_is_written() -> None:
    """The whole of ruling 2. `HBUNT` must stand before the membership insert,
    so a refused approval writes no membership and no residency -- the admin
    supplies a unit and presses Accept again on a request that is still
    cleanly pending. (The find-or-create path cannot reach the gate with a
    fresh unit behind it: creating a unit resolves `target_unit_id`, so the
    gate only ever fires when nothing was given at all.)"""
    new = body(sql())
    gate = new.index("using errcode = 'HBUNT'")
    assert gate < new.index("insert into public.community_memberships(")
    assert (
        "raise exception 'Approving a resident requires a unit. "
        "Provide the flat or villa to place them in.'" in new
    )
    # And after the carried validation: an explicit p_unit_id keeps winning.
    assert new.index("'Selected unit does not belong to this community'") < gate


def test_the_code_match_is_case_insensitive_and_the_create_is_exact() -> None:
    """The Python side canonicalises case, but an admin typing 'c-505' at a
    community holding 'C-505' means the same flat -- while the create keeps
    the admin's exact spelling, so the community's own convention sticks."""
    new = body(sql())
    assert "upper(u.unit_code) = upper(v_unit_code)" in new
    assert "v_unit_code text := nullif(btrim(coalesce(p_unit_code, '')), '')" in new
    assert (
        "v_building_code text := nullif(btrim(coalesce(p_building_code, '')), '')"
        in new
    )


def test_an_inactive_unit_is_a_refusal_in_words_not_a_silent_duplicate() -> None:
    new = body(sql())
    assert "if target_unit_id is not null and v_unit_status <> 'active' then" in new
    inactive = new.index("using errcode = 'HB422'")
    assert new.index("upper(u.unit_code)") < inactive < new.index("HBUNT")


def test_the_find_or_create_is_race_safe_and_mirrors_the_founder_shape() -> None:
    """Both inserts land `on conflict do nothing` against the schema's own
    unique constraints -- `buildings (community_id, code)` and
    `units (community_id, unit_code)` -- and re-select, so two admins approving
    into the same new tower race against the constraint instead of each other.
    The villa branch is the founder RPC's shape: each villa is its own
    building, `building_type 'villa'`, `unit_type 'villa'`, and with no
    building given the villa code names both."""
    new = body(sql())
    assert "on conflict (community_id, code) do nothing" in new
    assert "on conflict (community_id, unit_code) do nothing" in new
    assert "if v_building_code is null and v_community_type = 'layout_villa' then" in new
    assert "v_building_code := v_unit_code;" in new
    assert (
        "case when v_community_type = 'layout_villa' then 'villa' else 'block' end"
        in new
    )
    assert (
        "case when v_community_type = 'layout_villa' then 'villa' else 'flat' end"
        in new
    )
    # The founder file really does give each villa its own building; the
    # reference is read, not remembered.
    founder = FOUNDER.read_text(encoding="utf-8")
    assert "'villa'" in founder
    # A created unit is immediately usable: status 'active' is stated, not
    # left to the column default a hosted schema might have drifted.
    assert "'active'\n      )" in new


# ---------------------------------------------------------------------------
# The SQLSTATEs, and the Python side of the wire
# ---------------------------------------------------------------------------


def test_every_sqlstate_it_raises_is_one_the_api_can_map() -> None:
    """An unmapped SQLSTATE is a 500 with a generic message, which is exactly
    what custom codes exist to prevent. This is the check that forces the
    `pg_errors` mapping to land in the same commit as the SQL."""
    raised = set(re.findall(r"errcode = '([A-Z0-9]{5})'", statements(sql())))
    assert raised == {"HB422", "HBUNT"}, raised
    assert raised <= set(pg_errors._CUSTOM) | set(pg_errors._STANDARD)


def test_the_new_code_is_a_validation_error_the_client_can_point_at_a_field() -> None:
    """`HBUNT` is the admin's fixable omission -- supplying a unit makes the
    same call succeed -- so it maps like `HB422` (a 422) but under its own
    `code`, the way `HBLOC` is distinguishable from generic validation."""
    error_class, code = pg_errors._CUSTOM["HBUNT"]
    assert error_class is ValidationError
    assert code == "approval_requires_unit"
    assert code != pg_errors._CUSTOM["HB422"][1]


# ---------------------------------------------------------------------------
# The columns, and their CHECKs
# ---------------------------------------------------------------------------


def test_both_claim_columns_are_added_idempotently_with_the_trim_length_check() -> None:
    """Re-running a hand-applied file must be a no-op: `if not exists` on the
    columns, a `pg_constraint` guard on each CHECK. The CHECK itself is the
    `rejection_reason` convention with the blank refusal added: null, or a
    non-blank string of at most 120 characters."""
    text = statements(sql())
    for column in ("requested_building_text", "requested_unit_text"):
        assert re.search(rf"add column if not exists {column}\s+text", text), column
        assert f"conname  = 'access_requests_{column}_check'" in text
        assert (
            f"check ({column} is null\n"
            f"             or (btrim({column}) <> ''\n"
            f"                 and char_length({column}) <= 120))" in text
        ), column
    assert not re.search(r"add column (?!if not exists)", text)


# ---------------------------------------------------------------------------
# The view -- the old order survives as a prefix
# ---------------------------------------------------------------------------


def test_the_view_appends_and_keeps_every_column_where_it_was() -> None:
    """`create or replace view` permits appending and nothing else -- a
    reorder fails the apply, a rename fails it, and a drop fails it. The old
    order is derived from `0024`'s own text, so this test cannot bless a
    reorder that a retyped list would have hidden."""
    old = view_columns(REALTIME_JOIN.read_text(encoding="utf-8"))
    new = view_columns(sql())

    assert old, "the derivation read no columns out of 0024"
    assert new[: len(old)] == old, "the old columns moved"
    assert new[len(old) :] == [
        "requested_building_text",
        "requested_unit_text",
        "community_type",
    ], new[len(old) :]


def test_the_view_keeps_security_invoker_and_reissues_its_comment() -> None:
    """`security_invoker = true` is the property that makes this view answer
    with the caller's RLS rather than the owner's; losing it in the recreate
    would open every community's pending queue to every admin. The comment is
    re-issued because `create or replace view` keeps the old one only if
    nobody states a new truth -- and the view now carries three more columns."""
    text = statements(sql())
    start = text.index("create or replace view public.pending_access_request_overview")
    assert (
        text[start:].startswith(
            "create or replace view public.pending_access_request_overview\n"
            "with (security_invoker = true) as"
        )
    )
    assert "comment on view public.pending_access_request_overview is" in text


# ---------------------------------------------------------------------------
# The tail of the file
# ---------------------------------------------------------------------------


def test_the_in_transaction_proof_checks_the_three_failures_with_no_symptom() -> None:
    """A drop that left the old signature, a create that lost the gate, and a
    view recreate that did not append are each an apply that *looks* clean.
    The proof raises on all three, so a half-applied paste rolls back rather
    than reporting success."""
    blocks = re.findall(r"do \$\$((?:.|\n)*?)\$\$;", statements(sql()))
    proof = blocks[-1]
    assert f"'{NEW_SIGNATURE.replace(', ', ',')}'" in proof.replace("\n    ", "")
    assert "is not null then" in proof  # the old signature must be GONE
    assert "'HBUNT'" in proof or "HBUNT" in proof
    assert "ordinal_position > 11" in proof
    assert "requested_building_text,requested_unit_text,community_type" in proof
    assert proof.count("raise exception") >= 5


def test_the_last_statement_reloads_the_postgrest_catalogue() -> None:
    """A changed signature IS a catalogue change: without the reload PostgREST
    keeps answering for the 4-argument shape it remembers, and the approve
    button 404s until the next restart. Last, so everything the reload
    advertises exists by the time it fires -- and nothing executable follows
    it, which also proves the post-checks are comment-only."""
    parsed = parse_sql(sql())
    last = parsed[-1].stmt
    assert type(last).__name__ == "NotifyStmt", type(last).__name__
    assert last.conditionname == "pgrst"
    assert last.payload == "reload schema"


def test_the_post_checks_are_comment_only_and_guard_free() -> None:
    """The SQL editor has no `auth.uid()`, and this RPC is service-role-only
    and WRITES on success -- a post-check that called it would either refuse
    or mint a real membership. The post-checks inspect the catalogue instead,
    and are commented out so they never run inside the apply's transaction."""
    section = sql()[sql().index("-- Post-checks, to be run AFTER") :]
    queries = "\n".join(
        line for line in section.splitlines() if re.match(r"^--\s{3,}", line)
    )
    assert "pg_proc" in queries
    assert "information_schema.columns" in queries
    for guarded in ("auth.uid()", "perform public.approve_access_request"):
        assert guarded not in queries, guarded
    assert statements(section).strip() == ""
