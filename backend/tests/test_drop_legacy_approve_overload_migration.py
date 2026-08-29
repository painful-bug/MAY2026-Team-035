"""`20260829120000_drop_legacy_approve_overload.sql` -- dropping a stray
prototype overload that exists on the hosted database in no migration in this
tree.

`approve_access_request(p_access_request_id uuid, p_profile_id uuid,
p_default_invoice_amount numeric, p_due_at timestamptz)` is `SECURITY
DEFINER` code that approves an access request and, in one call, inserts a
membership, a residency and an ISSUED `maintenance` invoice numbered
`'MNT-YYYYMMDD-<request uuid>'`. It surfaced while checking runbook section
33's pre-check (a) on 2026-08-29: nothing in this tree references its
parameter names or its invoice prefix, and the current backend calls the
residency-shaped overload by different named parameters entirely. Because
`20260828090000_residence_claim_on_join.sql` only drops the residency-shaped
4-arg signature (`uuid, uuid, uuid, public.residency_relationship`), the
stray survives that file untouched, which is why section 33's own post-check
(a) ("exactly one row, pronargs = 6") reports two rows without this file.

The file's promises, each pinned below:

* **It sorts after `20260828090000`.** Filename order is apply order.
* **One drop, idempotent, named exactly.** `drop function if exists
  public.approve_access_request(uuid, uuid, numeric, timestamptz);` --
  `if exists` so a re-run or an already-clean database no-ops.
* **The proof probes the exact stray signature.** `to_regprocedure` on
  `(uuid,uuid,numeric,timestamptz)` and raises if it is still resolvable.
* **It reloads PostgREST's schema cache.** `notify pgrst, 'reload schema'`.
* **It is independent of §33's 6-arg signature.** No `drop` or `create`
  anywhere in the file names `public.residency_relationship` or the 6-arg
  shape -- this file owns the stray alone and applies in either order
  relative to §33.
* **The runbook documents it as section 34** with the ledger insert carrying
  the right version.

**Not verifiable statically:** that the stray actually exists on the hosted
database before the apply, and that PostgREST's schema cache actually drops
the signature rather than continuing to answer for it until the next
restart. Runbook section 34's pre/post-checks are where those are proved.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260829120000_drop_legacy_approve_overload.sql"
RUNBOOK = BACKEND.parent / "docs" / "plans" / "MIGRATION_APPLY_RUNBOOK.md"

#: The migration this file must sort after -- filename order is apply order,
#: and this file's header says applying before it breaks nothing but still
#: instructs applying in filename order.
PREDECESSOR = MIGRATIONS / "20260828090000_residence_claim_on_join.sql"

#: The exact stray signature this file exists to remove.
STRAY_SIGNATURE = "public.approve_access_request(uuid, uuid, numeric, timestamptz)"


def statements(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def sql() -> str:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def flat() -> str:
    """The SQL with whitespace collapsed, for assertions that span lines."""
    return " ".join(sql().split())


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_the_migration_file_exists() -> None:
    assert MIGRATION.exists(), MIGRATION.name
    assert MIGRATION.name == "20260829120000_drop_legacy_approve_overload.sql"


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(MIGRATION.read_text(encoding="utf-8"))


def test_it_sorts_after_residence_claim_on_join() -> None:
    """Forward-only. Filename order is apply order, and this file's own header
    says applying before §33 breaks nothing -- but the version string still
    has to sort after it, because that is what "apply in filename order"
    means in practice."""
    assert PREDECESSOR.exists(), PREDECESSOR.name
    assert MIGRATION.name > PREDECESSOR.name, PREDECESSOR.name


# ---------------------------------------------------------------------------
# One drop, idempotent, named exactly
# ---------------------------------------------------------------------------


def test_the_drop_names_exactly_the_stray_signature_with_if_exists() -> None:
    """The statement of substance. `if exists` is what makes a re-run or an
    already-clean database a no-op instead of an error."""
    text = flat()
    assert (
        f"drop function if exists {STRAY_SIGNATURE};" in text
    ), text


def test_it_drops_exactly_one_function_and_creates_none() -> None:
    """A one-statement file. No `create function`, no `create or replace
    function` -- this migration removes code, it does not install any."""
    text = flat().lower()
    assert text.count("drop function") == 1
    assert "create function" not in text
    assert "create or replace function" not in text


def test_it_touches_no_table_policy_or_constraint() -> None:
    """The whole change is one function drop plus its proof and the schema
    reload."""
    text = flat().lower()
    for forbidden in (
        "create table", "alter table", "drop table",
        "create policy", "drop policy", "create trigger", "drop trigger",
        "alter type", "add constraint", "drop constraint", "truncate",
        "delete from", "insert into", "update public.",
    ):
        assert forbidden not in text, forbidden


# ---------------------------------------------------------------------------
# The proof probes the exact stray signature
# ---------------------------------------------------------------------------


def test_the_proof_block_probes_the_stray_via_to_regprocedure() -> None:
    text = flat()
    assert "to_regprocedure(" in text
    assert "'public.approve_access_request(uuid,uuid,numeric,timestamptz)'" in text
    assert "is not null" in text
    assert "raise exception" in text


def test_the_proof_raises_if_the_stray_survived() -> None:
    """The exception fires when the stray is *still* resolvable -- i.e. the
    drop did not take. A successful apply leaves `to_regprocedure` returning
    null, so the `is not null` branch is the failure path, not the success
    path."""
    text = flat()
    proof = re.search(r"do \$\$ begin (.*?) end \$\$;", text)
    assert proof is not None, "no proof DO block found"
    body = proof.group(1)
    assert "if to_regprocedure(" in body
    assert "raise exception" in body
    assert "survived the drop" in body


def test_it_signals_no_new_sqlstate() -> None:
    """The proof's `raise exception` carries no `using errcode` -- it is a
    migration-apply guard, not an API-facing error path, so it needs no
    SQLSTATE mapping in `app/core/pg_errors.py`."""
    text = flat()
    assert "using errcode" not in text


# ---------------------------------------------------------------------------
# It reloads the schema cache
# ---------------------------------------------------------------------------


def test_it_reloads_postgrest_schema_cache() -> None:
    assert "notify pgrst, 'reload schema';" in flat()


def test_the_reload_is_the_last_statement() -> None:
    """A dropped signature is a catalogue change; the reload has to come after
    the drop has actually happened, which `create or replace function`-only
    files (like §32) do not need but a `drop function` file does."""
    text = flat()
    drop_index = text.index("drop function if exists")
    reload_index = text.index("notify pgrst, 'reload schema';")
    assert drop_index < reload_index


# ---------------------------------------------------------------------------
# Independence from §33's 6-arg signature
# ---------------------------------------------------------------------------


def test_it_does_not_reference_the_six_argument_signature() -> None:
    """This file owns the stray alone. It must not create, drop or otherwise
    name §33's `(uuid, uuid, uuid, public.residency_relationship, text,
    text)` shape -- doing so would couple this file's applicability to
    whether §33 has run, which the header explicitly says is not the case."""
    text = flat().lower()
    assert "residency_relationship" not in text
    assert "p_unit_code" not in text
    assert "p_building_code" not in text
    # No six-argument approve_access_request declaration or drop of any kind.
    assert re.search(
        r"(drop|create)\s+(?:or\s+replace\s+)?function\s+public\.approve_access_request\("
        r"\s*uuid\s*,\s*uuid\s*,\s*uuid\s*,",
        text,
    ) is None


def test_it_declares_no_function_body_of_its_own() -> None:
    """A pure drop -- no `create function ... as $$ ... $$` anywhere. The
    stray is removed, not replaced."""
    text = flat().lower()
    assert "language plpgsql" not in text
    assert "security definer" not in text


# ---------------------------------------------------------------------------
# The runbook documents it as section 34
# ---------------------------------------------------------------------------


def test_the_runbook_has_a_section_34_naming_this_file() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "## 34. `20260829120000_drop_legacy_approve_overload.sql`" in text


def test_the_runbook_ledger_insert_carries_the_right_version() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    section = text.split("## 34.", 1)[1]
    assert "values ('20260829120000', 'drop_legacy_approve_overload')" in section


def test_the_runbook_pointer_paragraph_names_section_34_as_newest() -> None:
    """The top-of-file pointer paragraph that used to say "§33 is the newest"
    has to be updated in the same commit, or the runbook contradicts
    itself about which section is current."""
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "**§34 is the newest.**" in text
    assert "**§33 is the newest.**" not in text
