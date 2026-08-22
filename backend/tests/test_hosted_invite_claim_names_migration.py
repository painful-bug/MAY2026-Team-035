"""`20260823150000_hosted_invite_claim_names.sql` -- the name the backend calls
must be a name the database has, on both databases at once.

The hosted project has only `claim_resident_invite(uuid, uuid)`; a fresh one has
only `claim_email_invitation(uuid, uuid)`, from `0001_baseline.sql`. The backend
calls the second name, so every resident email-invite redemption on hosted
answers PGRST202 and the invitee reads "This invite could not be claimed."
(owner probe 2026-08-23, runbook §22 probe (e), §24).

The file creates the missing *name* as a wrapper over the function hosted
already has, under a condition that is false on any database that already has
the name. Three things have to hold for that to be honest, and none of them is
reviewed here -- each is derived:

* the name created is the name the backend's `.rpc(...)` call actually passes,
  read out of `memberships_repository.py`;
* the wrapper's signature, return shape and security posture are
  `0001_baseline.sql`'s, read out of `0001_baseline.sql`;
* the condition cannot fire on a fresh database, because nothing in this
  directory creates `claim_resident_invite` -- which is checked across every
  file rather than asserted.

**Not verifiable statically:** that hosted's `claim_resident_invite` does what
`0001`'s `claim_email_invitation` does. The owner's probe established the
identical signature and return shape `TABLE(membership_id uuid, community_id
uuid, unit_id uuid)`; the bodies are two databases' business and no test here
can see either.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260823150000_hosted_invite_claim_names.sql"
BASELINE = MIGRATIONS / "0001_baseline.sql"
MEMBERSHIPS_REPOSITORY = BACKEND / "app" / "repositories" / "memberships_repository.py"

#: The three files this package adds, so "sorts after everything that existed"
#: can be asked without naming the file that happened to be last.
NEW_FILES = {
    "20260823150000_hosted_invite_claim_names.sql",
    "20260823153000_hosted_request_status_withdrawn.sql",
    "20260823160000_visitor_requests_sse.sql",
}

WRAPPER = "claim_email_invitation"
DELEGATE = "claim_resident_invite"


def statements(text: str) -> str:
    """``text`` with whole-line ``--`` comments dropped, so no check ever
    asserts against a header's prose instead of the SQL. This header quotes
    both function names many times."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def sql() -> str:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def baseline_declaration() -> str:
    """`0001_baseline.sql`'s `claim_email_invitation` header, up to the `as $$`
    that begins its body -- the part this file has to reproduce."""
    text = BASELINE.read_text(encoding="utf-8")
    start = text.index(f"create or replace function public.{WRAPPER}(")
    return text[start : text.index("as $$", start)]


def rpc_name_the_backend_calls() -> str:
    """The RPC name `memberships_repository.claim_resident_invite` passes to
    PostgREST -- derived, so the pin follows the code if the code moves."""
    source = MEMBERSHIPS_REPOSITORY.read_text(encoding="utf-8")
    body = re.search(
        r"def claim_resident_invite\((?:.|\n)*?(?=\n(?:def |@|\Z))", source
    )
    assert body is not None, "claim_resident_invite() not found where expected"
    called = re.findall(r"\.rpc\(\s*\"([^\"]+)\"", body.group(0))
    assert len(called) == 1, f"expected one rpc call, found {called}"
    return called[0]


def test_the_migration_parses_as_postgresql() -> None:
    """The floor: CI replays this directory into an empty database."""
    parse_sql(MIGRATION.read_text(encoding="utf-8"))


def test_it_sorts_after_every_file_that_already_existed() -> None:
    """Forward-only. A version below the latest on a shared branch is invisible
    to a fresh replay that has already passed it."""
    existing = sorted(
        path.name for path in MIGRATIONS.glob("*.sql") if path.name not in NEW_FILES
    )
    assert existing, "no pre-existing migrations found -- the glob is wrong"
    assert MIGRATION.name > existing[-1], existing[-1]


def test_the_name_it_creates_is_the_name_the_backend_calls() -> None:
    """The whole point of the file. If the repository is ever rewritten to call
    `claim_resident_invite` directly this fails, and it should: the wrapper
    would then be dead weight on hosted and the fresh databases would break."""
    created = re.findall(r"create function public\.(\w+)\(", sql())
    assert created == [rpc_name_the_backend_calls()], created


def test_the_wrapper_declares_the_baselines_signature_and_return_shape() -> None:
    """Derived from `0001_baseline.sql`, not typed in. PostgREST resolves an RPC
    by name *and* argument names, and the service layer unpacks the result by
    column name, so a wrapper that differs in either is a different function
    wearing the right name."""
    declaration = baseline_declaration()

    arguments = re.search(rf"{WRAPPER}\(([^)]*)\)", declaration).group(1)
    returns = re.search(r"returns table\(([^)]*)\)", declaration).group(1)

    text = sql()
    assert f"create function public.{WRAPPER}({arguments})" in text, arguments
    assert f"returns table({returns})" in text, returns


def test_the_wrapper_keeps_the_baselines_security_posture() -> None:
    """`security definer` with a pinned `search_path`, exactly as `0001` wrote
    it. A definer function without the pin is the classic search-path
    escalation, and this one is reachable from an unauthenticated redeem."""
    declaration = baseline_declaration()
    assert "security definer" in declaration
    assert re.search(r"set search_path\s*=\s*public", declaration)

    text = sql()
    assert "language plpgsql security definer set search_path = public" in text


def test_the_wrapper_keeps_the_baselines_acl() -> None:
    """`0001` revokes from `public, anon, authenticated` and grants only to
    `service_role`; nothing later in this directory touches that ACL. Only the
    backend's service client may claim an invite, and creating a second entry
    point must not be a second door."""
    baseline = statements(BASELINE.read_text(encoding="utf-8"))
    signature = rf"public\.{WRAPPER}\(uuid,uuid\)"
    revoked_from = re.search(
        rf"revoke all on function {signature} from ([^;]+);", baseline
    ).group(1)
    granted_to = re.search(
        rf"grant execute on function {signature} to ([^;]+);", baseline
    ).group(1)
    assert {role.strip() for role in revoked_from.split(",")} == {
        "public", "anon", "authenticated"
    }
    assert granted_to.strip() == "service_role"

    text = " ".join(sql().split())
    assert (
        f"revoke all on function public.{WRAPPER}(uuid,uuid) "
        f"from {revoked_from.strip()}" in text
    )
    assert (
        f"grant execute on function public.{WRAPPER}(uuid,uuid) "
        f"to {granted_to.strip()}" in text
    )

    # And no other migration has re-opened it since.
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name in {BASELINE.name, MIGRATION.name}:
            continue
        assert not re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{WRAPPER}",
            statements(path.read_text(encoding="utf-8")),
            re.I,
        ), path.name


def test_the_create_is_guarded_on_both_halves_of_the_divergence() -> None:
    """Conditional both ways: the delegate must exist and the wrapper must not.
    The first half keeps it off a database that has no `claim_resident_invite`;
    the second makes it idempotent and keeps it from replacing `0001`'s real
    implementation with a wrapper over a function that is not there."""
    text = " ".join(sql().split())
    assert f"to_regprocedure('public.{DELEGATE}(uuid,uuid)') is not null" in text
    assert f"to_regprocedure('public.{WRAPPER}(uuid,uuid)') is null" in text


def test_nothing_in_this_directory_creates_the_delegate() -> None:
    """Which is what makes the file a no-op on a fresh database, and it is
    checked rather than assumed: `claim_resident_invite` is a hosted-only
    function with no declaration anywhere in this repository, so the guard's
    first half is false on every database built from these files."""
    creators = [
        path.name
        for path in sorted(MIGRATIONS.glob("*.sql"))
        if re.search(
            rf"create\s+(or\s+replace\s+)?function\s+public\.{DELEGATE}\b",
            statements(path.read_text(encoding="utf-8")),
            re.I,
        )
    ]
    assert creators == [], creators


def test_the_body_only_delegates() -> None:
    """One statement in the wrapper, and it is a select from the delegate. A
    wrapper that reimplemented the claim would be the second copy of a
    transaction this project deliberately has one of."""
    body = re.search(r"\$body\$((?:.|\n)*?)\$body\$", sql()).group(1)
    lowered = " ".join(body.split()).lower()

    assert lowered.count("return query") == 1
    assert f"from public.{DELEGATE}(p_invite_id, p_profile_id)" in lowered
    for forbidden in ("insert into", "update ", "delete from", "raise exception"):
        assert forbidden not in lowered, forbidden


def test_it_creates_nothing_else_and_drops_nothing() -> None:
    """A targeted file, in the shape rule 2 of the migrations README asks for."""
    text = sql().lower()

    assert len(re.findall(r"create function", text)) == 1
    for forbidden in (
        "drop function", "drop table", "drop trigger", "drop policy",
        "create table", "create trigger", "create policy", "create type",
        "alter table", "alter type", "truncate", "delete from", "insert into",
    ):
        assert forbidden not in text, forbidden


def test_it_reloads_the_postgrest_schema_cache_last() -> None:
    """A function PostgREST has never seen still answers PGRST202 until the
    cache turns over, so the fix would look like no fix at all for a while."""
    text = sql()
    assert "notify pgrst, 'reload schema';" in text
    tail = [line for line in text.splitlines() if line.strip()][-1]
    assert tail.strip() == "notify pgrst, 'reload schema';"
