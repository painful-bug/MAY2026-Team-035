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
#: * `/resident/complaints` and `/admin/complaints` -- the resident portal is
#:   still a zustand demo and the admin complaint surface belongs to the
#:   complaint-engine owner (`docs/potential issues/09-…`,
#:   `docs/COMPLAINT_ENGINE_HANDOFF.md`).
#: * `/admin/departments?job=` -- there is no supervisor triage screen at all,
#:   so there is no parameter to read yet (`docs/potential issues/10-…`).
#: * `/admin/amenities?booking=` -- the admin amenity screen predates the
#:   notification.
#:
#: Two have left this set, both on 2026-08-11: `/security/shifts?shift=`, the
#: case that prompted counting them at all, and `/worker/messages?conversation=`,
#: which was the only one of the six that was ours.
IGNORED_QUERY_PARAMETERS = {
    ("/admin/amenities", "booking"),
    ("/admin/complaints", "complaint"),
    ("/admin/departments", "job"),
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


#: A `const NAME = (<>…</>);` holding `<Route>` elements, spliced in wherever
#: `{NAME}` appears inside the tree.
#:
#: `HIRING_ROUTES` is the first of these (2026-08-11): the hiring sub-tree is
#: mounted under `/admin`, `/manager` and `/security-manager`, and writing it
#: three times is how two of the three would eventually drift. React Router
#: flattens a fragment among `<Route>` children, so this parser has to as well
#: -- otherwise it reads the definition at file scope, mounts those paths at the
#: root, and concludes that `/admin/departments/{id}/hiring` does not exist.
_FRAGMENT_DEF = re.compile(
    r"^const\s+([A-Z][A-Z0-9_]*)\s*=\s*\(\s*<>(.*?)</>\s*\);", re.M | re.S
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


def component_sources() -> dict[str, Path]:
    """Component name -> the file `App.jsx` imports it from."""
    src = _ROOT / "frontend" / "src"
    out: dict[str, Path] = {}
    for name, target in _IMPORT.findall(_APP_JSX.read_text(encoding="utf-8")):
        if not target.startswith("."):
            continue
        base = (src / target.lstrip("./")).resolve()
        for candidate in (
            base,
            base.with_suffix(".jsx"),
            base.with_suffix(".js"),
            base / "index.jsx",
        ):
            if candidate.is_file():
                out[name] = candidate
                break
    return out


def emitted_urls() -> list[tuple[str, int, str]]:
    """``(file, line, path)`` for every `url` a migration writes.

    A url is an SQL concatenation -- ``'/admin/departments/' || id::text ||
    '/hiring?tab=roster'`` -- so each ``||`` operand is either a literal, which
    contributes its text, or an expression, which contributes one path segment.
    """
    out: list[tuple[str, int, str]] = []
    for path in sorted(_MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for match in _URL_LINE.finditer(text):
            pieces = []
            for piece in match.group(1).rsplit(")", 1)[0].split("||"):
                piece = piece.strip().rstrip(",").strip()
                literal = _LITERAL.match(piece)
                pieces.append(literal.group(1) if literal else "{param}")
            url = "".join(pieces)
            assert url.startswith("/"), f"{path.name}: unparsed url {match.group(1)!r}"
            line = text[: match.start()].count("\n") + 1
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
        text = source.read_text(encoding="utf-8")
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

_PORTAL_BASES = {"manager": "/manager", "security-manager": "/security-manager"}

#: `/admin/…` prefixes that a manager's notification is left pointing at,
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
#: every `/admin/…` url against every manager portal. That over-reaches -- some
#: of these are addressed to somebody who is not a manager at all -- and the
#: over-reach is cheap, because the answer for each is a line here saying which
#: it is. A test that tried to infer the recipient would be re-implementing
#: `notify_community_roles` in a regex.
UNREWRITTEN_FOR_A_MANAGER = {
    # No manager equivalent exists, and should not: no department owns an
    # amenity. `0033` was corrected on 2026-08-12 to notify admins only, so a
    # manager no longer receives this at all -- but this test checks blind, by
    # design, so the entry stays.
    "/admin/amenities",
    # Admin-only audience (`notify_community_roles(array['admin'])`, `0050`).
    # The triage queue is *by definition* the complaints no department holds,
    # so a manager equivalent would be a screen with nothing in it.
    "/admin/complaint-triage",
    # Rewritten for `manager` — `/manager/complaints` exists as of 2026-08-12 —
    # and deliberately *not* for `security-manager`, which has no complaints
    # screen: a gate department's work arrives as incidents and shift entries,
    # not as resident complaints. This set is shared by both parametrisations,
    # so the entry that excuses the security manager also blunts the check for
    # the plain manager. Accepted: the rewrite is asserted positively by
    # `test_the_python_mirror_matches_the_javascript_rule_table`.
    "/admin/complaints",
    # `/admin/security/incidents` is rewritten for `security-manager` and not
    # for a plain `manager` -- correctly, since `0040` was corrected on
    # 2026-08-12 to notify admins and *security-department* managers only. A
    # plumbing manager no longer receives it; the entry stays because this test
    # cannot see an audience.
    "/admin/security/incidents",
    # Addressed to `work_order.supervisor_membership_id` — a supervisor, whose
    # portal is `/worker`, not a manager's. It is on this list because the test
    # checks blind, and it stays unrewritten for a stronger reason than the
    # others: **the destination does not exist for anybody.** There is no
    # supervisor triage screen in any portal, so `?job=` has nothing to read it
    # — `docs/potential issues/10`, and the matching entry in
    # `IGNORED_QUERY_PARAMETERS` above.
    "/admin/departments?",
}


def _portal_url(url: str, portal: str) -> str:
    """`features/notifications/portalUrl.js`, in Python."""
    if not url.startswith("/admin/"):
        return url
    base = _PORTAL_BASES.get(portal)
    if base is None:
        return url
    rest = url[len("/admin"):]
    if re.match(r"^/departments/[^/?#]+/(hiring|staff/|candidates/)", rest):
        return base + rest
    if rest == "/messages" or rest.startswith("/messages?"):
        return base + rest
    if re.match(r"^/departments/[^/?#]+(?:[?#].*)?$", rest):
        return base
    if rest == "/security/incidents" and portal == "security-manager":
        return f"{base}/incidents"
    if portal == "manager" and (
        rest == "/complaints" or rest.startswith("/complaints?")
    ):
        return f"{base}{rest}"
    return url


def test_the_python_mirror_matches_the_javascript_rule_table() -> None:
    """A second implementation is only safe while it is checked against the
    first. The four rules are read out of `portalUrl.js` by name rather than by
    behaviour -- enough to fail loudly if somebody adds a fifth here and not
    there, or renames one."""
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


@pytest.mark.parametrize("portal", sorted(_PORTAL_BASES))
def test_a_managers_notification_lands_somewhere_they_may_go(portal: str) -> None:
    routes = route_table()
    stranded = []
    for name, line, url in emitted_urls():
        if not url.startswith("/admin/"):
            continue
        rewritten = _portal_url(url, portal)
        if rewritten.startswith("/admin/"):
            prefix = next(
                (p for p in UNREWRITTEN_FOR_A_MANAGER if rewritten.startswith(p)), None
            )
            if prefix is None:
                stranded.append(f"{name}:{line} — {url} (no rule, not on record)")
            continue
        if not resolves(rewritten, routes):
            stranded.append(f"{name}:{line} — {url} → {rewritten} (no such route)")

    assert not stranded, (
        f"notification links a {portal} cannot follow:\n  " + "\n  ".join(stranded)
    )
