"""Seven work-order notifications, repointed at the screen that now exists.

`20260812120000_work_order_notification_urls.sql` moves every supervisor-facing
work-order notification in `0037` and `0039` off `/admin/departments?job=<id>`
-- the department *list*, which reads no `job` parameter -- and onto
`departments/{id}/work-orders?job=<id>`, the triage screen. `docs/potential
issues/12` item 4 deferred this until such a screen existed; it does.

These are static checks. Whether Postgres installs these bodies is the local
Supabase CI job's question, and whether the link lands is
`test_notification_links.py`'s -- which reads the same files and checks every
surviving url against `App.jsx`'s route tree, including the per-portal rewrite.
What is left for this file is the part neither can see: that the seven bodies
are the applied text with seven url lines changed and nothing else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pglast import parse_sql

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
REPOINT = MIGRATIONS / "20260812120000_work_order_notification_urls.sql"
DISPATCH = MIGRATIONS / "0037_dispatch_engine.sql"
WORKER = MIGRATIONS / "0039_worker_actions.sql"

#: Every function the repoint re-declares, and the file it was extracted from.
EXTRACTED = {
    "dispatch_ping_candidates": DISPATCH,
    "dispatch_auto_assign": DISPATCH,
    "dispatch_failed_visit_escalation": DISPATCH,
    "accept_work_order_offer": WORKER,
    "complete_work_order": WORKER,
    "report_work_order_failure": WORKER,
}

def statements(sql: str) -> str:
    """``sql`` with whole-line `--` comments dropped.

    This file's header discusses the dead url, the grants it does not restate
    and the discipline it follows, all in prose. A check that read the prose
    would be asserting against its own explanation.
    """
    return "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )


def body(sql: str, function: str) -> str:
    """The `create … function public.<function>` block, up to its `$$;`."""
    start = re.search(
        r"^create or replace function public\." + function + r"\(", sql, re.M
    )
    assert start, f"{function} is not declared here"
    end = sql.index("\n$$;", start.start())
    return sql[start.start() : end]


def test_the_migration_parses_as_postgresql() -> None:
    parse_sql(REPOINT.read_text(encoding="utf-8"))


def test_it_sorts_after_every_migration_it_supersedes() -> None:
    """Filename order is apply order: last declaration of a name wins."""
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names[-1] == REPOINT.name
    assert REPOINT.name > DISPATCH.name
    assert REPOINT.name > WORKER.name


def test_every_emission_of_the_dead_url_is_accounted_for() -> None:
    """Seven, counted from the applied files rather than from memory.

    The count is the point of this test: a repoint that reaches six of seven
    leaves one notification pointing at a department list, and it would be the
    one nobody clicks in testing.
    """
    emissions = [
        (path.name, line)
        for path in (DISPATCH, WORKER)
        for line, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "/admin/departments?job=" in text
    ]
    assert len(emissions) == 7, emissions
    assert {name for name, _ in emissions} == {DISPATCH.name, WORKER.name}

    sql = statements(REPOINT.read_text(encoding="utf-8"))
    assert sql.count("/work-orders?job=") == 7
    assert "/admin/departments?job=" not in sql


@pytest.mark.parametrize("function", sorted(EXTRACTED))
def test_each_body_is_the_applied_text_with_only_the_url_changed(
    function: str,
) -> None:
    """Whole-body extraction, checked line by line against its source.

    The copy is mandatory -- both source files are applied and immutable -- and
    a copy that quietly drops a status check while it is repointing a link is
    the failure mode the discipline exists to prevent. Every line of the applied
    body must appear in the new one unless it is a url line.
    """
    applied = body(EXTRACTED[function].read_text(encoding="utf-8"), function)
    rewritten = body(REPOINT.read_text(encoding="utf-8"), function)

    missing = [
        line.strip()
        for line in applied.splitlines()
        if line.strip()
        and "/admin/departments?job=" not in line
        and line.strip() not in rewritten
    ]
    assert not missing, f"{function} lost lines from the applied body:\n  " + (
        "\n  ".join(missing)
    )


@pytest.mark.parametrize("function", sorted(EXTRACTED))
def test_each_changed_line_is_marked_and_is_the_only_change(function: str) -> None:
    """House discipline: an extracted body marks every departure `-- CHANGED`."""
    applied = body(EXTRACTED[function].read_text(encoding="utf-8"), function)
    rewritten = body(REPOINT.read_text(encoding="utf-8"), function)

    changed = applied.count("/admin/departments?job=")
    assert changed >= 1
    assert rewritten.count("-- CHANGED") == changed
    assert rewritten.count("/work-orders?job=") == changed
    assert "/admin/departments?job=" not in rewritten

    # Comment lines are exempt: the `-- CHANGED` markers and the reasons beside
    # them are the whole point of the discipline, and they have nowhere to come
    # from but this file. Statements are not exempt.
    added = [
        line.strip()
        for line in statements(rewritten).splitlines()
        if line.strip()
        and "work-orders?job=" not in line
        and "v_order.department_id::text" not in line
        and line.strip() not in applied
    ]
    assert not added, f"{function} gained lines beyond the url:\n  " + (
        "\n  ".join(added)
    )


def test_the_url_carries_the_department_the_screen_is_scoped_to() -> None:
    """`:departmentId` is in the path under all three portal bases.

    A url that named only the job would resolve to no route at all -- there is
    no `/admin/work-orders` -- so the department is not decoration.
    """
    sql = statements(REPOINT.read_text(encoding="utf-8"))
    assert sql.count("'/admin/departments/' || v_order.department_id::text") == 7
    assert sql.count("|| '/work-orders?job=' || v_order.id::text") == 7


def test_no_acl_or_comment_is_restated_from_memory() -> None:
    """`create or replace` keeps the oid, so both survive on their own.

    Restating them would mean writing out two opposite postures by hand:
    `0037`'s three are service_role only and `0039`'s three are granted to
    `authenticated`. A copy that gets one backwards is a privilege change
    wearing the clothes of a link fix.
    """
    sql = statements(REPOINT.read_text(encoding="utf-8")).lower()
    assert "grant execute" not in sql
    assert "revoke" not in sql
    assert "comment on function" not in sql


def test_the_worker_and_resident_links_in_these_bodies_are_untouched() -> None:
    """Only the supervisor's link moves. The worker's and the resident's do not.

    Both were corrected once already (`0036`'s header records `/worker/jobs…`
    twice), and a body-wide search-and-replace on `?job=` is exactly how they
    would be broken a third time.
    """
    sql = statements(REPOINT.read_text(encoding="utf-8"))
    assert sql.count("'/worker?job=' || v_order.id::text") == 2
    assert sql.count("'/resident/complaints?complaint=' ||") == 4
