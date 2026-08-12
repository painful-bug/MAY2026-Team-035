"""Cross-check every frontend API call against the routes FastAPI serves.

Run from ``backend/``::

    python scripts/frontend_api_sweep.py

**What it answers.** Two questions that nothing else in the repository asks, and
that no test can ask, because the two sides never meet in one process:

1. *Does every call the browser makes name a route that exists?* A typo, a
   renamed path or a method that drifted from ``POST`` to ``PATCH`` produces a
   404 or a 405 at runtime and nothing at all at build time. `npm run build`
   does not know what a route is, and `pytest` never sees the client.
2. *Which routes does nothing call?* Not a defect on its own -- an endpoint may
   legitimately precede its screen -- but the shape of that list is a real
   finding. `docs/potential issues/10-api-operations-with-no-frontend-consumer.md`
   is written from this output, and re-running it is how that document is kept
   honest rather than believed.

**How call sites are found.** Every ``api(…)``, ``download(…)`` and local
``post``/``patch``/``put``/``del`` wrapper in ``frontend/src`` whose first
argument is a string or template literal. Template substitutions are classified
rather than blindly replaced: an interpolation that builds a query string
(``${query(params)}``, ``${range(a, b)}``, anything holding ``?``, ``=`` or
``&``) contributes nothing, and everything else becomes one path segment.

**What it cannot see, stated rather than hidden.** A call whose first argument is
an expression -- ``api(a && b ? x : y)`` -- has no literal to read, so the sweep
skips it. Those are counted and listed under *unanalysable* instead of quietly
inflating the "nothing calls this" list, because an unreported blind spot in a
coverage tool is worse than a reported gap.

**Consumption paths it deliberately does not model.** ``EventSource`` for the two
SSE streams, ``window.location.assign`` for the OAuth start, the provider's own
redirect to the OAuth callback, and the bare ``fetch`` inside ``client.js`` that
refreshes the session. Those five operations are reached by mechanisms that are
not a function call with a path argument, and they will always appear unreached.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_ROOT = _BACKEND.parent
_FRONTEND = _ROOT / "frontend" / "src"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_map_scan import live_operations  # noqa: E402

_OPEN = re.compile(r"\b(api|download|post|patch|put|del)\(\s*(['\"`])")
_UNANALYSABLE = re.compile(r"\b(api|download)\(\s*(?!['\"`])([^,)\n]{0,60})")
_QUERYISH = re.compile(r"query\(|range\(|[?=&]")
_METHOD = re.compile(r"method:\s*['\"]([A-Za-z]+)['\"]")
_NAMED_METHOD = {"post": "post", "put": "put", "patch": "patch", "del": "delete"}


def _read_literal(text: str, start: int, quote: str) -> tuple[str | None, int]:
    """The literal beginning at ``start``, which is just past its opening quote."""
    out: list[str] = []
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return "".join(out), index + 1
        if char == "$" and quote == "`" and text[index + 1 : index + 2] == "{":
            depth = 1
            cursor = index + 2
            while cursor < len(text) and depth:
                if text[cursor] == "{":
                    depth += 1
                elif text[cursor] == "}":
                    depth -= 1
                cursor += 1
            expression = text[index + 2 : cursor - 1]
            out.append("" if _QUERYISH.search(expression) else "{param}")
            index = cursor
            continue
        out.append(char)
        index += 1
    return None, index


def _call_end(text: str, open_paren: int) -> int:
    """Index just past the ``)`` closing the call opened at ``open_paren``.

    Without this the ``method:`` search runs on into the *next* property of the
    surrounding object literal, and a plain ``api('/skills')`` inherits the
    ``PATCH`` of the arrow function two lines below it. That is not theoretical:
    it produced nine false "broken call site" reports the first time this ran.
    """
    depth, index = 0, open_paren
    while index < len(text):
        char = text[index]
        if char in "\"'`":
            _, index = _read_literal(text, index + 1, char)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(text)


def _method_of(text: str, open_paren: int, fn: str) -> str:
    if fn in _NAMED_METHOD:
        return _NAMED_METHOD[fn]
    found = _METHOD.search(text[open_paren : _call_end(text, open_paren)])
    return found.group(1).lower() if found else "get"


def _normalise(path: str) -> str:
    path = path.split("?")[0].rstrip("/")
    if not path.startswith("/api/v1"):
        path = "/api/v1" + path
    return path or "/"


def _matches(call: str, route: str) -> bool:
    call_parts = call.strip("/").split("/")
    route_parts = route.strip("/").split("/")
    if len(call_parts) != len(route_parts):
        return False
    return all(
        r.startswith("{") or c in ("{param}", r)
        for c, r in zip(call_parts, route_parts, strict=True)
    )


def _sources() -> list[Path]:
    files = sorted(_FRONTEND.rglob("*.js")) + sorted(_FRONTEND.rglob("*.jsx"))
    return [f for f in files if not f.name.endswith(".test.mjs")]


def call_sites() -> tuple[list[tuple[str, str, str, int]], list[tuple[str, int, str]]]:
    """``(method, path, file, line)`` per call, plus the sites with no literal.

    Most of the second list is uninteresting by construction -- the body of
    ``api()`` itself, and the one-line ``post``/``patch`` wrappers each feature
    module defines, all of which forward a ``path`` argument that some *other*
    call site supplied as a literal. The expression is printed so that a reader
    can tell those apart from the one entry that is a real blind spot.
    """
    calls: list[tuple[str, str, str, int]] = []
    unanalysable: list[tuple[str, int, str]] = []
    for file in _sources():
        text = file.read_text(encoding="utf-8")
        where = file.relative_to(_ROOT).as_posix()
        for match in _OPEN.finditer(text):
            literal, _ = _read_literal(text, match.end(), match.group(2))
            if literal is None or not literal.startswith("/"):
                continue
            open_paren = text.index("(", match.start())
            calls.append(
                (
                    _method_of(text, open_paren, match.group(1)),
                    _normalise(literal),
                    where,
                    text[: match.start()].count("\n") + 1,
                )
            )
        for match in _UNANALYSABLE.finditer(text):
            line = text[: match.start()].count("\n") + 1
            unanalysable.append((where, line, match.group(2).strip()))
    return calls, unanalysable


def main() -> int:
    live = live_operations()
    routes = sorted(live)
    calls, unanalysable = call_sites()

    unmatched, consumed = [], set()
    for method, path, file, line in calls:
        hit = [r for r in routes if r[0] == method and _matches(path, r[1])]
        if hit:
            consumed.update(hit)
        else:
            loose = sorted({r[0].upper() for r in routes if _matches(path, r[1])})
            unmatched.append((method, path, file, line, loose))

    print(f"frontend call sites: {len(calls)}   live operations: {len(routes)}")
    print(f"operations reached by a call site: {len(consumed)}")

    print("\n=== call sites with no matching live route ===")
    for method, path, file, line, loose in unmatched:
        note = f"   [path exists for {'/'.join(loose)}]" if loose else ""
        print(f"  {method.upper():6} {path:52} {file}:{line}{note}")
    if not unmatched:
        print("  none")

    print("\n=== unanalysable call sites (first argument is not a literal) ===")
    for file, line, expression in unanalysable:
        print(f"  {file}:{line}   {expression}")
    if not unanalysable:
        print("  none")

    print("\n=== live operations no call site reaches ===")
    by_file: dict[str, list[str]] = {}
    for key in routes:
        if key not in consumed:
            row = f"{key[0].upper():6} {key[1]}"
            by_file.setdefault(live[key]["file"], []).append(row)
    print(f"  ({sum(len(rows) for rows in by_file.values())} operations)")
    for file in sorted(by_file):
        print(f"  {file}")
        for row in sorted(by_file[file]):
            print(f"      {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
