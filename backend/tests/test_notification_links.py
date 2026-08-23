"""Every notification `url` a migration emits must be a route the app has.

`SECURITY_PORTAL_DESIGN.md` states the contract and, until this file, the
consequence too: *"a notification whose `url` 404s is a defect that no test
catches."* It does not 404, which is what makes it expensive --
`NotificationBell.jsx:72` calls `navigate(item.url)` with whatever the row says,
and `App.jsx`'s catch-all sends anything unmatched to `/`. The user taps a real
notification, arrives at the marketing page, and there is no error anywhere: not
in the browser console, not in the API log, not in a test run.

Four of them were wrong when this file was written, in three different ways --
a route that was deleted, a route that never existed, and a route belonging to a
portal other than the recipient's. All three are the same mistake: the URL was
written from memory of the navigation rather than from the navigation.

**How the route table is derived.** From `App.jsx` itself, by walking the nested
`<Route>` elements and joining each one to its parents, with `AUTH_ROUTES`
resolved out of `routes/authRoutes.js`. Keeping a copy of the table here would
reproduce the original defect one layer down: a second list of routes that is
right on the day it is written.

**What a match means.** That the path resolves to a mounted route. Query
parameters are dropped before matching, deliberately, because an ignored
parameter is a missing feature and an unroutable path is a broken link -- two
different defects that deserve two different answers.

The second one is answered further down, by `test_the_ignored_query_parameters_
are_the_ones_on_record`. Ten notification links carry a parameter; some of the
screens they land on do not read it, which lands the user on the right page
looking at the wrong row. That set is written down rather than asserted empty:
several of those screens belong to other workstreams and are already filed under
`docs/potential issues/`. Recording it keeps the list from growing quietly, and
makes a screen that starts honouring its parameter a test change rather than a
silent improvement nobody notices.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_APP_JSX = _ROOT / "frontend" / "src" / "App.jsx"
_AUTH_ROUTES_JS = _ROOT / "frontend" / "src" / "routes" / "authRoutes.js"
_MIGRATIONS = _ROOT / "backend" / "supabase" / "migrations"

_CONST = re.compile(r"^\s*([A-Z0-9_]+):\s*'([^']+)'", re.MULTILINE)
_ROUTE_OPEN = re.compile(r"<Route(?=[\s>])")
_ROUTE_CLOSE = "</Route>"
_PATH_ATTR = re.compile(r"""path=(?:"([^"]*)"|\{AUTH_ROUTES\.([A-Z0-9_]+)\})""")
_ELEMENT_ATTR = re.compile(r"element=\{<([A-Za-z_][A-Za-z0-9_]*)")
_IMPORT = re.compile(r"^import\s+([A-Za-z_][A-Za-z0-9_]*)\s+from\s+'([^']+)'", re.M)
_URL_LINE = re.compile(r"'url',\s*(.+)$", re.MULTILINE)
_LITERAL = re.compile(r"^'([^']*)'$")

#: `(path, parameter)` pairs a notification emits that the screen serving that
#: path does not read. **Not an allow-list of acceptable defects** -- an entry
#: here means a user arrives at the right screen and cannot see the thing they
#: were told about. Each of the four is written up, with the migration line that
#: emits it and the owner it belongs to, in
#: `docs/potential issues/12-notification-parameters-no-screen-reads.md`; none of
#: the four is this workstream's code to change:
#:
#: * `/resident/complaints` -- the resident portal is still a zustand demo
#:   (`docs/potential issues/09-…`), so the row a link points at may not be one
#:   the reader can see at all.
#: * `/admin/amenities?booking=` -- the admin amenity screen predates the
#:   notification.
#:
#: Two have left this set, both on 2026-08-11: `/security/shifts?shift=`, the
#: case that prompted counting them at all, and `/worker/messages?conversation=`,
#: which was the only one of the six that was ours.
#:
#: A third left on 2026-08-12: `/admin/departments?job=`. It was on record for
#: the strongest reason of the four -- *there was no triage screen in any
#: portal*, so there was nothing that could read the parameter --  and
#: `20260812120000_work_order_notification_urls` repointed all seven emissions
#: at `departments/{id}/work-orders`, which does read `job`.
#:
#: **One arrived the same day, and it is not new behaviour**: it is what
#: `emitted_urls` saw once it started following a concatenation onto its second
#: line. `0045:899` and `0045:1077` send a manager to the employee page to
#: decide a departure, carrying `?departure=`; `EmployeeDetail.jsx` reads no
#: query parameter at all, so the manager lands on the right person and finds
#: the departure themselves. Not fixed here -- the fix is in a shared admin
#: screen, and this file is the record, not the repair.
#:
#: `0043:534` carries the same parameter to the hiring screen and is *not* on
#: this list, because `0045` re-declared that function: only the surviving
#: definition of a function is read. See `emitted_urls`.
#:
#: **This set is keyed on the url the migration emits, not on the per-reader
#: rewrite**, which is worth saying out loud because for one day it mattered.
#: On 2026-08-21 `portalUrl.js` started sending a supervisor's
#: `/admin/complaints?complaint=` to `/worker/complaints`, and
#: `WorkerDashboard/Complaints.jsx` read no query parameter -- so that reader
#: landed on the right screen and the wrong row, the same defect this set
#: exists to count, invisibly, because `matching_route` resolves the emitted
#: `/admin/complaints` and never looks at the rewrite. It was not papered over
#: with a second entry (the assertion below is equality, and an entry the check
#: cannot produce would fail it) but recorded in `docs/potential issues/14-…`.
#:
#: **`("/admin/complaints", "complaint")` left this set later the same day**,
#: and it is the reason the mechanism is worth its keep. The product owner
#: ruled that the deep link must highlight on the admin *and* worker screens;
#: `AdminDashboard/Complaints.jsx` now reads `?complaint=` and rings the card,
#: which is what this check detects, and both halves of the defect above closed
#: in one change because the emitted url and the rewrite target are the same
#: screen's two names. `/resident/complaints` stays: that portal is still a
#: zustand demo and highlighting a row in dummy data is not a fix.
IGNORED_QUERY_PARAMETERS = {
    ("/admin/amenities", "booking"),
    ("/admin/departments/:departmentId/staff/:staffId", "departure"),
    ("/resident/complaints", "complaint"),
}


def _auth_routes() -> dict[str, str]:
    return dict(
        (name, value)
        for name, value in _CONST.findall(_AUTH_ROUTES_JS.read_text(encoding="utf-8"))
    )


def _tag_end(text: str, start: int) -> int:
    """Index just past the ``>`` closing the tag that opens at ``start``.

    Attribute values are JSX expressions holding their own elements, so the
    first ``>`` is usually inside ``element={<ProtectedRoute …>}``. Braces and
    quotes are balanced past instead.
    """
    depth, index = 0, start
    while index < len(text):
        char = text[index]
        if char in "\"'":
            index += 1
            while index < len(text) and text[index] != char:
                index += 1
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == ">" and depth == 0:
            return index + 1
        index += 1
    raise AssertionError(f"unterminated tag at {start}")


def _join(parent: str, segment: str) -> str:
    if segment.startswith("/"):
        return segment.rstrip("/") or "/"
    if not segment:
        return parent
    return f"{parent.rstrip('/')}/{segment}"


#: A `const NAME = (…);` holding `<Route>` elements, spliced in wherever
#: `{NAME}` appears inside the tree.
#:
#: `HIRING_ROUTES` is the first of these (2026-08-11): the hiring sub-tree is
#: mounted under `/admin`, `/manager` and `/security-manager`, and writing it
#: three times is how two of the three would eventually drift. React Router
#: flattens a fragment among `<Route>` children, so this parser has to as well
#: -- otherwise it reads the definition at file scope, mounts those paths at the
#: root, and concludes that `/admin/departments/{id}/hiring` does not exist.
#:
#: **The body is no longer required to be a `<>…</>` fragment** (2026-08-12).
#: `WORK_ORDER_ROUTES` is one `<Route>` with no wrapper -- a fragment around a
#: single element is what a linter removes -- and the pattern that insisted on
#: `<>` did exactly what the paragraph above warns about: it left
#: `/departments/:departmentId/work-orders` mounted at the *root*, so
#: `/admin/departments/{id}/work-orders` was absent from the table and the
#: triage notifications would have been reported as landing on the catch-all.
#: The body now runs to the `);` in the first column, which is the only place
#: that sequence appears in a JSX definition indented like these two.
_FRAGMENT_DEF = re.compile(
    r"^const\s+([A-Z][A-Z0-9_]*)\s*=\s*\(\s*(<.*?)\n\);", re.M | re.S
)
_FRAGMENT_REF = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
#: Stands in for "whatever this fragment ends up nested under" while its own
#: paths are being resolved. Never appears in a result.
_FRAGMENT_BASE = "/\x00frag"


def _walk_routes(
    text: str,
    constants: dict[str, str],
    fragments: dict[str, list[tuple[str, str]]],
    base: str = "",
) -> dict[str, str]:
    """The shared walk. Returns ``{full path: component}``."""
    routes: dict[str, str] = {}
    stack: list[str] = [base] if base else []
    index = 0

    while index < len(text):
        opened = _ROUTE_OPEN.search(text, index)
        closed = text.find(_ROUTE_CLOSE, index)
        reference = _FRAGMENT_REF.search(text, index) if fragments else None

        # A fragment reference before the next tag: splice its routes in,
        # relative to whatever is currently open.
        if reference is not None and reference.group(1) in fragments:
            before_open = opened is None or reference.start() < opened.start()
            before_close = closed == -1 or reference.start() < closed
            if before_open and before_close:
                parent = stack[-1] if stack else ""
                for segment, element in fragments[reference.group(1)]:
                    routes.setdefault(_join(parent, segment), element)
                index = reference.end()
                continue

        if opened is None and closed == -1:
            break
        if closed != -1 and (opened is None or closed < opened.start()):
            assert stack, "</Route> with no open element"
            stack.pop()
            index = closed + len(_ROUTE_CLOSE)
            continue

        end = _tag_end(text, opened.start())
        tag = text[opened.start() : end]
        found = _PATH_ATTR.search(tag)
        if found is None:
            segment = ""  # an index route: it is its parent's path
        elif found.group(1) is not None:
            segment = found.group(1)
        else:
            segment = constants[found.group(2)]
        full = _join(stack[-1] if stack else "", segment)
        leaf = tag.rstrip().endswith("/>")
        element = _ELEMENT_ATTR.search(tag)
        if segment != "*" and (leaf or full not in routes):
            routes[full] = element.group(1) if element else ""
        if leaf:
            index = end
        else:
            stack.append(full)
            index = end
    return routes


def route_elements() -> dict[str, str]:
    """Every full path `App.jsx` mounts, and the component it renders there.

    A path can be claimed twice -- a layout `<Route>` with children and the
    index `<Route>` inside it resolve to the same string -- and the second is
    the one that answers a notification. The leaf wins, which here means the
    self-closing tag wins, because a layout is never self-closing.

    Route fragments are lifted out first and spliced back in at each `{NAME}`,
    which is what React Router does with them.
    """
    text = _APP_JSX.read_text(encoding="utf-8")
    constants = _auth_routes()

    # Walked against a sentinel base, then stripped back off. Walking with an
    # empty base would return `/departments/…` — an *absolute* path, which
    # `_join` then refuses to nest under `/admin`, and every hiring route would
    # silently mount at the root. The sentinel keeps a child a child.
    fragments: dict[str, list[tuple[str, str]]] = {}
    for name, body in _FRAGMENT_DEF.findall(text):
        walked = _walk_routes(body, constants, {}, base=_FRAGMENT_BASE)
        fragments[name] = sorted(
            (path[len(_FRAGMENT_BASE):].lstrip("/"), element)
            for path, element in walked.items()
        )
    # Removed from the tree text so the definition is not also walked at file
    # scope, which would mount every fragment path at the root.
    tree = _FRAGMENT_DEF.sub("", text)

    return _walk_routes(tree, constants, fragments)


def route_table() -> set[str]:
    """Every full path `App.jsx` mounts."""
    return set(route_elements())


def _resolve_module(from_dir: Path, target: str) -> Path | None:
    """A relative import specifier -> the file it names, if there is one."""
    base = (from_dir / target).resolve()
    for candidate in (
        base,
        base.with_suffix(".jsx"),
        base.with_suffix(".js"),
        base / "index.jsx",
    ):
        if candidate.is_file():
            return candidate
    return None


def component_sources() -> dict[str, Path]:
    """Component name -> the file `App.jsx` imports it from."""
    src = _ROOT / "frontend" / "src"
    out: dict[str, Path] = {}
    for name, target in _IMPORT.findall(_APP_JSX.read_text(encoding="utf-8")):
        if not target.startswith("."):
            continue
        resolved = _resolve_module(src, target.lstrip("./"))
        if resolved is not None:
            out[name] = resolved
    return out


#: ``return <Name`` -- a component whose whole body is *choosing which page this
#: route is*, rather than being the page.
_DELEGATE = re.compile(r"return\s*\(?\s*<([A-Z][A-Za-z0-9_]*)")


def screen_source(component: Path) -> str:
    """A route's source, following one hop through a page-picking component.

    **Why the hop exists.** `/worker` stopped being a page on 2026-08-22 and
    became a fork: `WorkerLanding` is four lines that return `<WorkerHome />` for
    a technician and `<SupervisorDashboard />` for a supervisor. The parameter
    check below reads the route's component file for `.get('job')`, so a
    dispatcher of that shape reports every parameter as ignored -- and
    `?job=` is in fact read, one file down, by exactly the page it lands a
    technician on.

    **Why it is one hop and only through a `return <Name`.** Following every
    component a page renders would fold half the component tree into the search
    and let an unrelated child's `searchParams.get('job')` vouch for a screen
    that ignores it -- which would turn this check into one that cannot fail.
    A capitalised component returned *directly* is a delegation and not a child:
    real pages return a `<div>` or a fragment.
    """
    text = component.read_text(encoding="utf-8")
    delegates = set(_DELEGATE.findall(text))
    if not delegates:
        return text

    imports = dict(_IMPORT.findall(text))
    parts = [text]
    for name in sorted(delegates):
        target = imports.get(name)
        if not target or not target.startswith("."):
            continue
        resolved = _resolve_module(component.parent, target)
        if resolved is not None:
            parts.append(resolved.read_text(encoding="utf-8"))
    return "\n".join(parts)


#: ``create [or replace] function public.name(`` -- the start of a definition.
#: Matched by name only, not by signature: two overloads of one name would be
#: conflated, and none of the url-emitting functions has an overload. If one
#: ever does, this is the line that has to learn about argument lists.
_FUNCTION_DEF = re.compile(
    r"^create\s+(?:or\s+replace\s+)?function\s+(public\.\w+)\s*\(", re.M
)


def _surviving_definitions() -> dict[str, str]:
    """Function name -> the migration file whose definition Postgres keeps.

    Filename order is apply order, so the last file to declare a name is the
    one that is installed. Nothing here parses bodies: a name is claimed by the
    file it was last written in, which is all "whose text is live" needs.
    """
    latest: dict[str, str] = {}
    for path in sorted(_MIGRATIONS.glob("*.sql")):
        for match in _FUNCTION_DEF.finditer(path.read_text(encoding="utf-8")):
            latest[match.group(1)] = path.name
    return latest


def _enclosing_function(text: str, position: int) -> str | None:
    """The function whose body ``position`` falls inside, or ``None``.

    The nearest preceding definition wins. A url outside every function -- none
    exist today -- belongs to no definition and is always read.
    """
    found = None
    for match in _FUNCTION_DEF.finditer(text, 0, position):
        found = match.group(1)
    return found


def emitted_urls() -> list[tuple[str, int, str]]:
    """``(file, line, path)`` for every `url` a migration writes.

    A url is an SQL concatenation -- ``'/admin/departments/' || id::text ||
    '/hiring?tab=roster'`` -- so each ``||`` operand is either a literal, which
    contributes its text, or an expression, which contributes one path segment.

    **A concatenation that runs onto the next line is followed** (2026-08-12).
    Reading only the first line was a silent hole rather than a missing feature:
    three urls in `0043` and `0045` wrap at 80 columns, and each was being read
    as the prefix ``/admin/departments/{param}`` -- a real route, so the check
    passed, with the half of the path that could be wrong never looked at and
    the query parameters after the wrap invisible to the parameter check below.
    Every one of the seven work-order urls repointed by
    `20260812120000_work_order_notification_urls` wraps the same way, so
    without this the migration that gave them a screen would have been
    "verified" against the department list they were being moved off.

    The continuation rule is the one the migrations actually use: a following
    line whose first token is ``||``. Nothing wider, because a wider rule would
    start consuming the next `jsonb_build_object` key.

    **Only the surviving definition of a function counts** (2026-08-12). Every
    correction before the deployment boundary was an edit in place, so the file
    and the database always agreed and reading all of them was reading the
    truth. Forward-only changes that; `20260812120000` re-declares six functions
    from `0037` and `0039`, and the superseded url text stays in those two files
    forever because they are applied and immutable. A scanner that reads them
    reports seven links that no longer exist, and -- worse in the other
    direction -- would go on passing a file whose *current* definition was
    broken as long as some older one was fine. `_surviving_definitions` below is
    the same rule Postgres applies: last `create or replace` in filename order
    wins.
    """
    surviving = _surviving_definitions()
    out: list[tuple[str, int, str]] = []
    for path in sorted(_MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for match in _URL_LINE.finditer(text):
            line = text[: match.start()].count("\n") + 1
            function = _enclosing_function(text, match.start())
            if function is not None and surviving.get(function) != path.name:
                continue  # a later migration re-declared this function
            expression = match.group(1)
            index = line  # 0-based index of the line *after* the match
            while index < len(lines) and lines[index].lstrip().startswith("||"):
                expression += " " + lines[index].strip()
                index += 1
            pieces = []
            for piece in expression.rsplit(")", 1)[0].split("||"):
                piece = piece.strip().rstrip(",").strip()
                literal = _LITERAL.match(piece)
                pieces.append(literal.group(1) if literal else "{param}")
            url = "".join(pieces)
            assert url.startswith("/"), f"{path.name}: unparsed url {expression!r}"
            out.append((path.name, line, url))
    return out


def matching_route(url: str, routes: set[str]) -> str | None:
    """The mounted path this url lands on, or `None` for the catch-all."""
    wanted = url.split("?")[0].split("#")[0].rstrip("/") or "/"
    parts = wanted.strip("/").split("/")
    for route in routes:
        candidate = route.strip("/").split("/")
        if len(candidate) != len(parts):
            continue
        if all(
            r.startswith(":") or p == "{param}" or p == r
            for p, r in zip(parts, candidate, strict=True)
        ):
            return route
    return None


def resolves(url: str, routes: set[str]) -> bool:
    return matching_route(url, routes) is not None


def query_parameters(url: str) -> list[str]:
    """The parameter names a url carries, in order, values discarded."""
    if "?" not in url:
        return []
    query = url.split("?", 1)[1].split("#")[0]
    return [pair.split("=")[0] for pair in query.split("&") if pair.split("=")[0]]


def test_the_route_table_is_actually_parsed() -> None:
    """If the walker silently produced nothing, everything below would pass."""
    routes = route_table()
    assert len(routes) > 40
    for expected in (
        "/security/shifts",
        "/worker",
        "/admin/departments/:departmentId/hiring",
        # A `const` holding one bare `<Route>` rather than a `<>…</>` fragment.
        # Until the lifter learned that shape these mounted at the root, and a
        # notification pointing at the triage screen would have been reported
        # as landing on the catch-all.
        "/admin/departments/:departmentId/work-orders",
        "/manager/departments/:departmentId/work-orders",
        "/security-manager/departments/:departmentId/work-orders",
        "/resident/complaints",
    ):
        assert expected in routes, f"{expected} missing from the parsed table"


@pytest.mark.parametrize(
    "gone",
    [
        "/security/visitors?pass={param}",  # 0032 — a route that never existed
        "/worker/jobs/{param}",  # 0036 — the worker portal has no jobs route
        "/worker/jobs?job={param}",  # 0037 — the same, spelled differently
        "/security-manager/shifts?shift={param}",  # 0043 — the wrong portal
    ],
)
def test_the_matcher_rejects_the_four_urls_this_file_was_written_for(gone: str) -> None:
    """Proof the check has teeth.

    A link checker that cannot fail is worth nothing, and this one is only ever
    exercised by a passing suite. These are the four values that were in the
    migrations on 2026-08-11; each must still be judged unroutable.
    """
    assert not resolves(gone, route_table())


def test_the_component_behind_every_linked_route_can_be_read() -> None:
    """The parameter check below is only worth as much as this resolution.

    If a path stopped resolving to a file -- renamed folder, re-exported
    component, a route whose element is an inline expression -- the checks that
    follow would quietly pass by having nothing to look at.
    """
    routes = route_elements()
    sources = component_sources()
    unresolved = []
    for _, _, url in emitted_urls():
        if not query_parameters(url):
            continue
        path = matching_route(url, set(routes))
        assert path is not None, f"{url} resolves to no route"
        element = routes[path]
        if element not in sources:
            unresolved.append(f"{path} -> {element or '(no element)'}")
    assert not unresolved, "routes whose component file was not found:\n  " + (
        "\n  ".join(sorted(set(unresolved)))
    )


def test_the_ignored_query_parameters_are_the_ones_on_record() -> None:
    """A link that lands on the right screen and shows the wrong row.

    `/security/shifts?shift=` was the case that prompted this: the path was
    corrected on 2026-08-11 and the guard still arrived at a fortnight of rows
    with nothing marking the one they had been told about. Fixing that without
    checking the others would have left five more of the same, each invisible
    for the same reason -- the link works, so nothing reports it.

    Equality, not a subset. A screen that starts honouring its parameter must
    leave this set, so the record cannot drift into an allow-list nobody prunes.
    """
    routes = route_elements()
    sources = component_sources()
    ignored = set()
    for _, _, url in emitted_urls():
        parameters = query_parameters(url)
        if not parameters:
            continue
        path = matching_route(url, set(routes))
        assert path is not None
        source = sources.get(routes[path])
        if source is None:
            continue
        text = screen_source(source)
        for name in parameters:
            if f".get('{name}')" not in text and f'.get("{name}")' not in text:
                ignored.add((path, name))

    new = sorted(ignored - IGNORED_QUERY_PARAMETERS)
    honoured = sorted(IGNORED_QUERY_PARAMETERS - ignored)
    assert ignored == IGNORED_QUERY_PARAMETERS, (
        "the set of notification parameters no screen reads has changed.\n"
        f"  now ignored but not on record: {new}\n"
        f"  on record but now honoured:    {honoured}"
    )


def test_every_notification_url_resolves_to_a_mounted_route() -> None:
    routes = route_table()
    broken = [
        f"{name}:{line} — {url}"
        for name, line, url in emitted_urls()
        if not resolves(url, routes)
    ]
    assert not broken, "notification links that land on the catch-all:\n  " + (
        "\n  ".join(broken)
    )


# ---------------------------------------------------------------------------
# The same question, asked for the reader rather than for the URL (2026-08-11)
#
# `test_every_notification_url_resolves_to_a_mounted_route` above asks whether a
# link goes *somewhere*. It has always passed for the hiring notifications,
# because `/admin/departments/{id}/hiring` is a real route -- for an admin.
#
# Several of these notifications are addressed to `array['admin', 'manager']`,
# and for a manager `ProtectedRoute requiredRole="Admin"` does not 404 and does
# not show a 403: it redirects to their own portal. So the link resolved, the
# guard held, and the user saw a click that appeared to do nothing. Exactly the
# failure this module was written to catch, one axis over -- **resolving is not
# the same as resolving for the person who was told.**
#
# `portalNotificationUrl` (frontend) rewrites what it can. This mirrors its rule
# table in Python, which is a second implementation and is worth it here: what
# is being asserted is that the *route tree* has a destination for each rewrite,
# and only the route tree can answer that.
# ---------------------------------------------------------------------------

_PORTAL_BASES = {
    "manager": "/manager",
    "security-manager": "/security-manager",
    # 2026-08-21. A service department's supervisor holds a `worker` membership
    # -- `_portal_for` upgrades only a `security`-role membership by roster rank
    # -- so every `/admin/…` link they were sent came back unrewritten and
    # bounced them home, silently, exactly as it did for a manager before
    # 2026-08-11. Two families reach them: the five work-order kinds keyed to
    # `work_orders.supervisor_membership_id`, and the complaint staff notices
    # `notify_complaint_staff` widened to supervisor-rank roster holders.
    "worker": "/worker",
}

#: `/admin/…` paths that a manager's notification is left pointing at,
#: because their portal has no equivalent screen. **Not acceptable defects** --
#: each one is a manager receiving a link that redirects them home. Rewriting
#: them would be worse: a route that does not exist fails more confusingly than
#: one that visibly bounces. Recorded in
#: `docs/potential issues/14-…` under "What is still not fixed".
#:
#: The third is the widest: `0040` fans `/admin/security/incidents` out to
#: *every* manager in the community, so a plumbing manager is told about gate
#: incidents. That is a notification-audience question in `0040`, not a routing
#: one, and it is the honest remainder of issue 14.
#:
#: **This test does not know a notification's audience** and deliberately checks
#: every `/admin/…` url against every portal in `_PORTAL_BASES`. That
#: over-reaches -- some of these are addressed to somebody who is not a manager
#: at all -- and the over-reach is cheap, because the answer for each is a line
#: here saying which it is. A test that tried to infer the recipient would be
#: re-implementing `notify_community_roles` in a regex.
#:
#: **Entries are whole paths, matched exactly after the query string is
#: dropped** (2026-08-21). They were prefixes, matched with `startswith`, which
#: was harmless while every entry was a single flat path -- and stopped being
#: harmless the moment `UNREWRITTEN_FOR_A_WORKER` below needed to name a
#: department root *and* two sub-screens beneath it: under `startswith` the root
#: entry silently excuses both, so deleting either sub-screen line would have
#: left the test green with nothing on record. Exact paths make every line here
#: load-bearing, which is the property the rest of this file is built on.
UNREWRITTEN_FOR_A_MANAGER = {
    # No manager equivalent exists, and should not: no department owns an
    # amenity. `0033` was corrected on 2026-08-12 to notify admins only, so a
    # manager no longer receives this at all -- but this test checks blind, by
    # design, so the entry stays.
    "/admin/amenities",
    # Admin-only audience (`notify_community_roles(array['admin'])`, `complaint_department_routing`).
    # The triage queue is *by definition* the complaints no department holds,
    # so a manager equivalent would be a screen with nothing in it.
    "/admin/complaint-triage",
    # Rewritten for `manager` — `/manager/complaints` exists as of 2026-08-12 —
    # and deliberately *not* for `security-manager`, which has no complaints
    # screen: a gate department's work arrives as incidents and shift entries,
    # not as resident complaints. This set is shared by the two manager
    # parametrisations, so the entry that excuses the security manager also
    # blunts the check for the plain manager. Accepted: the rewrite is asserted
    # positively by `test_the_python_mirror_matches_the_javascript_rule_table`.
    # (`worker` reads its own record below, where this line does not appear:
    # `/worker/complaints` exists and the rewrite is checked, not excused.)
    "/admin/complaints",
    # `/admin/security/incidents` is rewritten for `security-manager` and not
    # for a plain `manager` -- correctly, since `0040` was corrected on
    # 2026-08-12 to notify admins and *security-department* managers only. A
    # plumbing manager no longer receives it; the entry stays because this test
    # cannot see an audience.
    "/admin/security/incidents",
    # `/admin/departments?job=` used to be here, for the strongest reason on the
    # list: the destination existed for nobody. The triage screen exists now,
    # mounted under all four portals (`/worker` joined on 2026-08-21, which is
    # the only one of them a supervisor ever reaches), `portalUrl.js` rewrites the path, and
    # `20260812120000_work_order_notification_urls` points the seven emissions
    # at it — so the entry is gone rather than excused.
}


#: The same record for a `worker` -- a service department's supervisor, or the
#: technician on the roster beside them. **Not acceptable defects either**: each
#: is a link that bounces its reader home. Where the manager list is mostly
#: "no such screen exists anywhere", this one is mostly "this reader is not in
#: that notification's audience", because the blind check above asks every
#: portal about every url.
#:
#: `candidates/` is the fourth department sub-screen `/worker` does not mount
#: and has no line here, for the reason an unused entry is worse than a missing
#: one under exact matching: no migration emits a `/candidates/` url today, so a
#: line for it would be a claim nothing tests. If one is ever emitted, this test
#: fails with "no rule, not on record" and the line gets written then.
UNREWRITTEN_FOR_A_WORKER = {
    # No worker equivalent, and no worker in the audience: `0033` was corrected
    # on 2026-08-12 to notify admins only.
    "/admin/amenities",
    # Admin-only audience, and by definition: the triage queue is the complaints
    # no department holds, so there is nothing in it a supervisor could act on.
    "/admin/complaint-triage",
    # `0040` notifies admins and security-department managers. A security
    # department's people reach `/security` or `/security-manager`, never
    # `/worker`, so no reader of this notification is on this parametrisation.
    "/admin/security/incidents",
    # `/admin/departments/{param}` -- the department root, from
    # `20260821170000_blocked_invitee_notice` -- **left this set later on
    # 2026-08-21**, and it was the one line here that named a live audience:
    # `notify_department_leadership` (`0043` §419-436) includes supervisor-rank
    # roster holders, who hold portal `worker`. It was on record on the grounds
    # that a worker's base is a jobs dashboard rather than a department
    # overview, so the substitution exact for a manager would be a non-sequitur.
    # The product owner's ruling is that the guard sends that reader to
    # `/worker` whatever this table says, so the substitution is not the
    # question: `worker` joined `_DEPARTMENT_ROOT_PORTALS` and the rewrite is
    # now asserted positively rather than excused here. The three lines that
    # remain are all "no such screen in this portal", which is what the rest of
    # this record is made of.
    #
    # `/worker` mounts no hiring screen. Addressed to `['admin', 'manager']`
    # (`0043`), so no worker-portal reader either.
    "/admin/departments/{param}/hiring",
    # Nor a staff screen. `0045` sends this to a manager deciding a departure.
    "/admin/departments/{param}/staff/{param}",
}

#: Which record answers for which portal. The two manager portals share one, as
#: they always have; `worker` has its own because the two lists differ in every
#: line but three.
_UNREWRITTEN = {
    "manager": UNREWRITTEN_FOR_A_MANAGER,
    "security-manager": UNREWRITTEN_FOR_A_MANAGER,
    "worker": UNREWRITTEN_FOR_A_WORKER,
}


#: The alternatives inside `portalUrl.js`'s `DEPARTMENT_SUBSCREEN` -- the
#: department sub-screens each portal mounts at the same shape `/admin` does.
#: Held as data rather than inlined in the pattern below so the mirror test can
#: compare it with the JavaScript instead of merely checking that a name still
#: appears.
#:
#: **Per-portal since 2026-08-21**, in lockstep with the JavaScript. One shared
#: tuple was true while the only readers were the two manager portals, which
#: mount the whole hiring sub-tree; `/worker` mounts `work-orders` and nothing
#: else from this list, and rewriting a supervisor's hiring link into a portal
#: with no hiring screen would be this module's own failure mode.
_SUBSCREENS = {
    "manager": ("hiring", "staff/", "candidates/", "work-orders"),
    "security-manager": ("hiring", "staff/", "candidates/", "work-orders"),
    "worker": ("work-orders",),
}

#: Portals whose base stands in for the admin's department screen -- both
#: managers, and `worker` since the product owner's ruling later on 2026-08-21.
#: The first reading of that day left `worker` out because its base is a jobs
#: dashboard rather than a department overview; the ruling is that
#: `/admin/departments/{id}` is Admin-guarded, so a worker-portal reader is
#: redirected to `/worker` either way, and the real choice is between arriving
#: there deliberately and arriving there via a click that appeared to do
#: nothing. The department-root line in `UNREWRITTEN_FOR_A_WORKER` left with it.
_DEPARTMENT_ROOT_PORTALS = ("manager", "security-manager", "worker")

#: Portals with a complaints screen. `worker` joined on 2026-08-21 with the
#: widened `notify_complaint_staff`; `security-manager` still has none, because
#: a gate department's work arrives as incidents and shift entries.
_COMPLAINTS_PORTALS = ("manager", "worker")

#: `const DEPARTMENT_SUBSCREEN = { … };` in `portalUrl.js` -- an object literal
#: since it became per-portal, so the whole body is captured and its entries
#: read out one at a time.
_JS_SUBSCREEN_TABLE = re.compile(r"DEPARTMENT_SUBSCREEN\s*=\s*\{(.*?)\n\};", re.S)
#: One `portal: /regex/,` line inside that body. The key is quoted when it
#: contains a hyphen (`'security-manager'`) and bare when it does not.
_JS_SUBSCREEN_ENTRY = re.compile(r"^\s*'?([a-z-]+)'?:\s*(/.+?/),\s*$", re.M)


def _portal_url(url: str, portal: str) -> str:
    """`features/notifications/portalUrl.js`, in Python."""
    if not url.startswith("/admin/"):
        return url
    base = _PORTAL_BASES.get(portal)
    if base is None:
        return url
    rest = url[len("/admin"):]
    subscreens = _SUBSCREENS.get(portal)
    if subscreens and re.match(
        r"^/departments/[^/?#]+/(" + "|".join(subscreens) + ")", rest
    ):
        return base + rest
    if rest == "/messages" or rest.startswith("/messages?"):
        return base + rest
    if portal in _DEPARTMENT_ROOT_PORTALS and re.match(
        r"^/departments/[^/?#]+(?:[?#].*)?$", rest
    ):
        return base
    if rest == "/security/incidents" and portal == "security-manager":
        return f"{base}/incidents"
    if portal in _COMPLAINTS_PORTALS and (
        rest == "/complaints" or rest.startswith("/complaints?")
    ):
        return f"{base}{rest}"
    return url


def test_the_python_mirror_matches_the_javascript_rule_table() -> None:
    """A second implementation is only safe while it is checked against the
    first. The four rules are read out of `portalUrl.js` by name rather than by
    behaviour -- enough to fail loudly if somebody adds a fifth here and not
    there, or renames one.

    **The sub-screen list is compared by content**, not by name. Naming was
    enough while the list was three entries nobody touched; `work-orders` joined
    it on 2026-08-12 for the work-order notification repoint, and a name check
    would have passed just as happily with the JavaScript half of that change
    reverted -- leaving every one of the seven links bouncing a department
    manager home while this file asserted they were fine.

    **And per portal, since 2026-08-21.** The comparison is now dictionary
    against dictionary rather than tuple against tuple, which keeps that
    property under the restructure: reverting the JavaScript to one shared list,
    or quietly handing `worker` the manager's four sub-screens, changes the
    parsed table and fails here. A comparison that had flattened both sides back
    into one set of names would have lost exactly the teeth the paragraph above
    is about.
    """
    source = (
        _ROOT / "frontend" / "src" / "features" / "notifications" / "portalUrl.js"
    ).read_text(encoding="utf-8")
    expected = {
        "DEPARTMENT_SUBSCREEN",
        "DEPARTMENT_ROOT",
        "/messages",
        "/security/incidents",
    }
    missing = sorted(token for token in expected if token not in source)
    assert not missing, f"portalUrl.js no longer mentions: {missing}"

    table = _JS_SUBSCREEN_TABLE.search(source)
    assert table, "DEPARTMENT_SUBSCREEN is no longer a per-portal object literal"
    entries = _JS_SUBSCREEN_ENTRY.findall(table.group(1))
    assert entries, f"no portal entries in {table.group(1)!r}"

    javascript = {}
    for portal, literal in entries:
        alternation = re.search(r"\(([^)]*)\)", literal)
        assert alternation, f"no alternation in {literal}"
        # `staff\/` there, `staff/` here: the escape is JavaScript's, not a rule.
        javascript[portal] = tuple(
            part.replace("\\", "") for part in alternation.group(1).split("|")
        )

    assert javascript == _SUBSCREENS, (
        "portalUrl.js and this file disagree about which department sub-screens "
        "each portal mounts:\n"
        f"  portalUrl.js: {javascript}\n"
        f"  this file:    {_SUBSCREENS}"
    )

    # The two portal lists that are not regular-expression literals, read the
    # same way: by content, for the same reason. `security-manager` being handed
    # a complaints screen it does not have is precisely the mistake this module
    # was written to stop, and only a content check sees it.
    for name, mirror in (
        ("DEPARTMENT_ROOT_PORTALS", _DEPARTMENT_ROOT_PORTALS),
        ("COMPLAINTS_PORTALS", _COMPLAINTS_PORTALS),
    ):
        found = re.search(rf"{name}\s*=\s*new Set\(\[([^\]]*)\]\)", source)
        assert found, f"{name} is no longer a `new Set([…])` literal"
        javascript_portals = tuple(
            part.strip().strip("'") for part in found.group(1).split(",") if part.strip()
        )
        assert javascript_portals == mirror, (
            f"portalUrl.js and this file disagree about {name}:\n"
            f"  portalUrl.js: {javascript_portals}\n"
            f"  this file:    {mirror}"
        )


@pytest.mark.parametrize("portal", sorted(_PORTAL_BASES))
def test_a_notification_lands_somewhere_its_reader_may_go(portal: str) -> None:
    """Renamed on 2026-08-21: it said `a_managers_` and `worker` is not one.

    A supervisor is the reader this parametrisation was extended for, and the
    name would have been a small lie of exactly the kind the rest of this file
    spends its comments correcting.
    """
    routes = route_table()
    record = _UNREWRITTEN[portal]
    stranded = []
    for name, line, url in emitted_urls():
        if not url.startswith("/admin/"):
            continue
        rewritten = _portal_url(url, portal)
        if rewritten.startswith("/admin/"):
            # Whole path, query dropped: see the note on
            # `UNREWRITTEN_FOR_A_MANAGER` for why this is not `startswith`.
            if rewritten.split("?")[0].split("#")[0] not in record:
                stranded.append(f"{name}:{line} — {url} (no rule, not on record)")
            continue
        if not resolves(rewritten, routes):
            stranded.append(f"{name}:{line} — {url} → {rewritten} (no such route)")

    assert not stranded, (
        f"notification links a {portal} cannot follow:\n  " + "\n  ".join(stranded)
    )
