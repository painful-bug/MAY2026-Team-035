"""`20260827210000_one_live_job_per_complaint.sql` -- one live job per
complaint, and the lock that makes the answer stable.

Complaint `f40e11d4-e322-4847-be2f-8f2caf6df722` collected a second
`awaiting_resident` work order fifteen seconds after the resident booked the
first one's visit. Nothing refused it: the raise path never asked whether a job
on this complaint was already running. The owner's ruling of 2026-08-27
(`docs/plans/ONE_LIVE_JOB_SPEC.md`) is that a complaint carries several jobs
over its life and **one at a time**.

The file's promises, each pinned below:

* **The same function, plus exactly two things.** It `create or replace`s
  `create_work_order` under the unchanged signature, carrying the
  `20260823180000` body forward whole -- the G1 fork, the deadline, the event
  word, the notification -- and adding the row lock and the refusal. This suite
  diffs the two bodies and fails on any third change, because a copied-forward
  function is the shape that silently loses a sibling's fix.
* **The refusal is frozen.** The sentence and `HB409` are the contract §2 of the
  spec froze; the envelope carries the message verbatim and the client renders
  it, so a reword here is a reword on somebody's screen.
* **The live set is `_OPEN_STATES`.** The five states are **derived from
  `app/services/work_orders_service.py`**, not typed in here, so the SQL list
  and the Python tuple cannot drift apart without this test saying so. The three
  terminal states are asserted absent from the guard.
* **The lock comes before the guard.** A read-then-write with no lock is the
  race that produced the leak in the first place; `for update` on the complaint
  is what serializes two raises against one complaint.
* **It touches nothing else.** No table, no policy, no constraint, no other
  function, and nothing at all in the complaint lifecycle --
  `complaints.status` is not this file's business.

**Not verifiable statically:** that two concurrent raises actually serialize,
and that the guard returns 409 rather than 500 through the API. Both need the
applied database; runbook section 32's post-check is where they are proved.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from pglast import parse_sql

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "20260827210000_one_live_job_per_complaint.sql"
SERVICE = BACKEND / "app" / "services" / "work_orders_service.py"
ROUTER = BACKEND / "app" / "api" / "v1" / "routers" / "work_orders.py"

#: The file whose `create_work_order` body this one carries forward, and the
#: named predecessor it had to sort after when it was written (ruling G9,
#: `docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`).
PREDECESSOR = MIGRATIONS / "20260823180000_resident_sets_the_time.sql"

#: The refusal, frozen by `docs/plans/ONE_LIVE_JOB_SPEC.md` section 2. The
#: envelope carries it verbatim to the screen.
REFUSAL = (
    "A job is already live on this complaint. "
    "Finish, fail, or cancel it before raising another."
)

#: The signature, unchanged from `20260823180000`. Postgres resolves overloads
#: by argument list, so replacing a different one would leave the leak open.
SIGNATURE = (
    "p_complaint_id       uuid,",
    "p_department_id      uuid default null,",
    "p_skill_id           uuid default null,",
    "p_subject_kind       text default 'resident',",
    "p_location_text      text default null,",
    "p_scheduled_start_at timestamptz default null,",
    "p_scheduled_end_at   timestamptz default null,",
    "p_note               text default null",
)

TERMINAL_STATES = ("completed", "failed", "cancelled")


def statements(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def sql() -> str:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def flat() -> str:
    """The SQL with whitespace collapsed, for assertions that span lines."""
    return " ".join(sql().split())


def create_work_order_body(path: Path) -> str:
    """One file's whole `create or replace function public.create_work_order`
    statement, comments and all -- the comments are half of what is being
    compared between the two files."""
    found = re.search(
        r"create or replace function public\.create_work_order\(.*?\n\$\$;",
        path.read_text(encoding="utf-8"),
        re.S,
    )
    assert found is not None, f"create_work_order not found in {path.name}"
    return found.group(0)


def open_states() -> tuple[str, ...]:
    """`work_orders_service._OPEN_STATES`, read out of the service source.

    Derived rather than typed, for the reason the directory battery reads its
    sentinel table name out of `dashboard_repository.py`: a list copied into a
    test protects whatever it was copied from on the day it was written, and
    stops tracking it immediately afterwards.
    """
    found = re.search(
        r"^_OPEN_STATES\s*=\s*\(([^)]*)\)",
        SERVICE.read_text(encoding="utf-8"),
        re.M,
    )
    assert found is not None, "_OPEN_STATES not found in work_orders_service.py"
    states = tuple(re.findall(r"\"([a-z_]+)\"|'([a-z_]+)'", found.group(1)))
    flattened = tuple(a or b for a, b in states)
    assert len(flattened) == 5, flattened
    return flattened


def guard_predicate() -> str:
    """The `if exists (...) then` clause that refuses the raise."""
    found = re.search(r"if exists \( select 1 from public\.work_orders w (.*?)\)", flat())
    assert found is not None, "the live-job guard is not where it is expected"
    return found.group(1)


# ---------------------------------------------------------------------------
# Where it sits, and whether it is SQL
# ---------------------------------------------------------------------------


def test_the_migration_file_exists() -> None:
    """The filename is frozen by the spec: three other agents and the runbook
    name this exact string."""
    assert MIGRATION.exists(), MIGRATION.name
    assert MIGRATION.name == "20260827210000_one_live_job_per_complaint.sql"


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(MIGRATION.read_text(encoding="utf-8"))


def test_it_sorts_after_the_body_it_carries_forward() -> None:
    """Forward-only. If this file sorted *before* `20260823180000`, a fresh
    replay would apply the guard and then overwrite it with the unguarded
    version -- silently, because both declare the same name."""
    assert PREDECESSOR.exists(), PREDECESSOR.name
    assert MIGRATION.name > PREDECESSOR.name, PREDECESSOR.name


def test_it_is_the_last_word_on_create_work_order() -> None:
    """Not "it is last in the directory" -- the property that decides which body
    the database ends up holding is being last among the files that declare this
    function."""
    declares = sorted(
        path.name
        for path in MIGRATIONS.glob("*.sql")
        if re.search(
            r"^create (or replace )?function public\.create_work_order\b",
            path.read_text(encoding="utf-8"),
            re.M,
        )
    )
    assert declares, "nothing declares create_work_order at all"
    assert declares[-1] == MIGRATION.name, declares


# ---------------------------------------------------------------------------
# The same function, plus exactly two things
# ---------------------------------------------------------------------------


def test_the_signature_is_unchanged() -> None:
    """Eight parameters in the same order with the same defaults. Postgres
    resolves `create_work_order` by argument list: a ninth parameter, or a
    reordering, creates a SECOND function and leaves the unguarded one standing
    for `app/repositories` to keep calling."""
    text = MIGRATION.read_text(encoding="utf-8")
    for parameter in SIGNATURE:
        assert parameter in text, parameter
    assert "returns uuid" in sql()
    assert "security definer" in sql()
    assert "set search_path = public" in sql()


def test_it_adds_the_lock_and_the_refusal_and_nothing_else() -> None:
    """The body is `20260823180000`'s, diffed line by line. Every added line is
    a comment, the `for update` continuation, or part of the guard; every
    removed line is the unlocked `select` the `for update` replaces. A third
    change -- a dropped notification, a moved deadline, a reworded event --
    fails here, which is the whole reason a copied-forward function gets a diff
    test instead of a spot check."""
    old = create_work_order_body(PREDECESSOR).splitlines()
    new = create_work_order_body(MIGRATION).splitlines()

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

    assert removed == [
        "select * into v_complaint from public.complaints where id = p_complaint_id;"
    ], removed

    substantive = [line for line in added if line and not line.startswith("--")]
    assert substantive == [
        "select * into v_complaint from public.complaints where id = p_complaint_id",
        "for update;",
        "end if;",
        "if exists (",
        "select 1",
        "from public.work_orders w",
        "where w.complaint_id = v_complaint.id",
        "and w.status in ('draft', 'awaiting_resident', 'offered',",
        "'scheduled', 'in_progress')",
        ") then",
        "raise exception",
        f"'{REFUSAL}'",
        "using errcode = 'HB409';",
    ], substantive


def test_the_complaint_row_is_locked_before_the_guard_reads() -> None:
    """`for update` on the complaint, and it comes first. The guard is a read
    followed by a write, so without the lock two supervisors -- or one
    double-clicked button -- both read "no live job" and both insert, which is
    the leak this file exists for. The complaint is what every raise on it has
    in common, so the complaint is what is locked."""
    text = flat()

    lock = text.index(
        "select * into v_complaint from public.complaints "
        "where id = p_complaint_id for update;"
    )
    guard = text.index("if exists ( select 1 from public.work_orders w")
    insert = text.index("insert into public.work_orders (")

    assert lock < guard < insert
    # The lock is on the complaint, not on the jobs -- locking the empty set the
    # guard is checking would lock nothing at all.
    assert "from public.work_orders w where w.complaint_id" in text
    assert "public.work_orders w where w.complaint_id = v_complaint.id for update" \
        not in text


def test_the_guard_stands_in_front_of_every_write() -> None:
    """Before the `work_orders` insert, before the `complaint_events` insert and
    before the notification. A refusal raised after a row was written would roll
    back inside this transaction, but a guard placed by accident rather than by
    design is one refactor away from not doing that."""
    text = flat()
    guard = text.index("if exists ( select 1 from public.work_orders w")

    for write in (
        "insert into public.work_orders (",
        "insert into public.complaint_events",
        "perform public.notify_member(",
    ):
        assert guard < text.index(write), write


# ---------------------------------------------------------------------------
# The refusal, frozen
# ---------------------------------------------------------------------------


def test_the_refusal_sentence_is_the_frozen_one() -> None:
    """Section 2 of the spec, word for word. `HB409` maps to a 409 with envelope
    `code: "conflict"` (`app/core/pg_errors.py`) and the message travels to the
    screen verbatim, so this string is user-facing copy and not a log line."""
    text = flat()

    assert f"raise exception '{REFUSAL}' using errcode = 'HB409';" in text
    assert REFUSAL in MIGRATION.read_text(encoding="utf-8")


def test_it_signals_with_hb409_and_invents_no_new_code() -> None:
    """No new envelope code: "you already have one of these" is the answer
    `HB409` has meant since `0012`. The only custom SQLSTATEs in the file are
    the ones `20260823180000` already raised."""
    text = flat()

    assert "using errcode = 'HB409'" in text
    codes = set(re.findall(r"errcode = '(\w+)'", text))
    assert codes == {"HB403", "HB404", "HB409", "22004"}, codes


# ---------------------------------------------------------------------------
# The live set is `_OPEN_STATES`
# ---------------------------------------------------------------------------


def test_the_live_set_is_the_five_states_the_service_calls_open() -> None:
    """Derived from `work_orders_service._OPEN_STATES`, so the SQL list and the
    Python tuple cannot drift. The migration's own comment names that tuple; if
    somebody adds a sixth open state in Python and not here, a raise would be
    allowed against a job the API still considers answerable."""
    predicate = guard_predicate()
    states = open_states()

    assert states == (
        "draft",
        "awaiting_resident",
        "offered",
        "scheduled",
        "in_progress",
    ), states
    for state in states:
        assert f"'{state}'" in predicate, state
    assert "_OPEN_STATES" in MIGRATION.read_text(encoding="utf-8")


def test_a_terminal_job_does_not_block_a_new_one() -> None:
    """The other half of the rule, and the half that makes the feature usable: a
    failed visit's replacement and a reopened complaint's new job are exactly
    what `create_work_order` is for. `completed`, `failed` and `cancelled` are
    absent from the guard's list."""
    predicate = guard_predicate()

    for state in TERMINAL_STATES:
        assert f"'{state}'" not in predicate, state


def test_the_guard_is_scoped_to_one_complaint_and_reads_nothing_else() -> None:
    """`complaint_id`, not department and not community. A supervisor with two
    complaints in flight raises against both."""
    predicate = guard_predicate()

    assert "w.complaint_id = v_complaint.id" in predicate
    assert "department" not in predicate
    assert "community" not in predicate
    assert "supervisor" not in predicate


# ---------------------------------------------------------------------------
# It touches nothing else
# ---------------------------------------------------------------------------


def test_it_declares_one_function_and_alters_no_object() -> None:
    """A `create or replace function` and its comment. No table, no policy, no
    constraint, no trigger, and no second function -- a file that carries one
    body forward has no business carrying a neighbour's."""
    text = flat().lower()

    assert len(re.findall(r"create or replace function", text)) == 1
    assert "create_work_order" in text

    for forbidden in (
        "create table", "alter table", "drop table", "drop function",
        "create policy", "drop policy", "create trigger", "drop trigger",
        "alter type", "add constraint", "drop constraint", "truncate",
        "delete from", "insert into public.complaints",
    ):
        assert forbidden not in text, forbidden


def test_it_writes_no_row_and_cancels_no_existing_duplicate() -> None:
    """The guard refuses NEW raises; it does not reach back. The leak complaint
    already holds two live jobs, and cancelling one is a lifecycle decision that
    belongs to a person -- the owner does it in the UI (runbook 32). A migration
    that did it by hand would be inventing that decision."""
    text = flat().lower()

    assert "update public.work_orders" not in text
    assert "'cancelled'" not in text


def test_it_does_not_touch_the_complaint_lifecycle() -> None:
    """The ruling guards `work_orders` liveness and nothing else.
    `complaints.status` has its own writers and its own projection
    (`project_complaint_from_jobs`), and a guard that also moved a complaint
    would be answering a question nobody asked it."""
    text = flat().lower()

    assert "update public.complaints" not in text
    assert "project_complaint_from_jobs" not in text
    assert "complaints set" not in text


# ---------------------------------------------------------------------------
# The file proves its own work
# ---------------------------------------------------------------------------


def test_it_reads_back_the_function_it_installed() -> None:
    """`create or replace function` succeeds against a body with no guard in it
    just as happily as against this one, so the only proof the apply did what
    the header claims is to ask the database for the definition it now holds.
    The signature is spelled out in the probe because replacing the wrong
    overload would leave the leak open with every other check passing."""
    text = flat()

    assert "to_regprocedure(" in text
    assert "pg_get_functiondef(v_oid)" in text
    assert "position('for update' in v_def)" in text
    assert "position('A job is already live on this complaint.' in v_def)" in text
    assert "position('HB409' in v_def)" in text
    assert "position('w.complaint_id = v_complaint.id' in v_def)" in text
    assert text.count("raise exception") >= 5
    # Every one of the five live states is looked for in the installed body.
    for state in open_states():
        assert f"'{state}'" in text, state


# ---------------------------------------------------------------------------
# The API says the same thing the database does
# ---------------------------------------------------------------------------


def test_the_route_docstring_carries_the_new_409_and_the_corrected_prose() -> None:
    """The docstring is the source of the OpenAPI description and of
    `docs/API.md`. A database that refuses and a document that promises are the
    same defect from the caller's side."""
    text = ROUTER.read_text(encoding="utf-8")

    assert "| 409 | `conflict` | A job on this complaint is still live |" in text
    assert "several work orders over its life, one live at a time" in text
    # The old sentence claimed multiplicity with no bound at all.
    assert "A complaint may carry several work orders." not in text
