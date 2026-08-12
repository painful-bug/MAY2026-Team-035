"""Find the code and the links nothing reaches, on both sides of the repo.

Run from ``backend/``::

    python scripts/dead_code_sweep.py

**Why this exists.** Two dead-code sweeps have been done here by hand
(`docs/CHANGE_LOG.md`, Phase 2 Step 2 and this one), and both found the same
kind of thing: an accessor whose last caller went away, a constant superseded by
a helper that computes the same name, a document pointing at a file that was
deleted in the change that made the document true. None of it is caught by
`pytest`, `ruff`, `oxlint` or `vite build` -- unreferenced is not an error in
either language, and a Markdown link is not checked by anything at all. A sweep
done by hand is a sweep done once; this is the same four questions, repeatable.

**What each section means, and what it does not.**

*Frontend modules nothing imports* resolves every relative specifier in
``frontend/src`` to a real file, including the extension-less and ``index``
forms. ``main.jsx`` is the entry point and is excluded. A file here is genuinely
unreachable: there is no dynamic-import-by-string anywhere in this project, and
if one is ever added this paragraph is what has to change.

*Frontend exports nothing outside the file mentions* is deliberately a **word
search**, not an import graph -- a name re-exported through a barrel, or reached
by ``import * as x``, still counts as mentioned. That makes it conservative in
the right direction: it under-reports rather than accusing live code.

*Backend names nothing references* counts occurrences of each module-level name
across ``app``, ``tests`` and ``scripts`` and reports the ones that appear
exactly once -- their own definition. **Decorated functions are excluded**: a
route handler is reached through ``@router.get`` and a cached factory through
``@lru_cache``, so every one of them would otherwise be reported as dead.
Underscore-private names are excluded for the same reason a linter excludes
them: they are the file's own business.

*Documentation links that point at nothing* resolves every relative Markdown
link in ``docs/`` against the filesystem. External and anchor-only links are not
followed -- this checks for rot inside the repository, which is the kind that
happens silently when a file is renamed.

**The standing blind spot.** Nothing here proves the *reverse*: a name with one
caller that is itself dead is still reported as live. Dead code arrives in
clusters, so it is worth re-running after acting on the output.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from urllib.parse import unquote

_BACKEND = Path(__file__).resolve().parent.parent
_ROOT = _BACKEND.parent
_FRONTEND = _ROOT / "frontend" / "src"
_DOCS = _ROOT / "docs"

_SPECIFIER = re.compile(r"""(?:from|import)\s*\(?\s*['"](\.[^'"]+)['"]""")
_NAMED_EXPORT = re.compile(
    r"^export\s+(?:async\s+)?(?:function|const|let|class)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_JS_SUFFIXES = {".js", ".jsx", ".mjs"}


def _js_sources() -> dict[Path, str]:
    return {
        path: path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(_FRONTEND.rglob("*"))
        if path.suffix in _JS_SUFFIXES and "node_modules" not in path.parts
    }


def _resolve(base: Path) -> Path | None:
    """The file a relative specifier names, trying every form Vite accepts."""
    candidates = (
        base,
        Path(f"{base}.js"),
        Path(f"{base}.jsx"),
        base / "index.js",
        base / "index.jsx",
    )
    return next((c.resolve() for c in candidates if c.is_file()), None)


def _entry_points(sources: dict[Path, str]) -> set[Path]:
    """Files that are run rather than imported, so nothing importing them is fine.

    ``main.jsx`` is the app, and each ``*.test.mjs`` is a node test-runner entry
    named directly in ``package.json``'s test script.
    """
    return {(_FRONTEND / "main.jsx").resolve()} | {
        path for path in sources if path.name.endswith(".test.mjs")
    }


def orphan_modules(sources: dict[Path, str]) -> list[Path]:
    """Frontend files no other file imports, entry point excluded."""
    imported: set[Path] = set()
    for path, text in sources.items():
        for specifier in _SPECIFIER.findall(text):
            target = _resolve((path.parent / specifier).resolve())
            if target is not None:
                imported.add(target)
    return sorted(set(sources) - imported - _entry_points(sources))


def unused_exports(sources: dict[Path, str]) -> list[tuple[Path, int, str]]:
    """``(file, line, name)`` for each named export no other file mentions."""
    out: list[tuple[Path, int, str]] = []
    for path, text in sources.items():
        for match in _NAMED_EXPORT.finditer(text):
            name = match.group(1)
            word = re.compile(rf"\b{re.escape(name)}\b")
            if any(word.search(other) for p, other in sources.items() if p != path):
                continue
            out.append((path, text[: match.start()].count("\n") + 1, name))
    return sorted(out)


def _python_sources() -> dict[Path, str]:
    out: dict[Path, str] = {}
    for base in (_BACKEND / "app", _BACKEND / "tests", _BACKEND / "scripts"):
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            out[path] = path.read_text(encoding="utf-8", errors="ignore")
    return out


def _is_decorated(node: ast.stmt) -> bool:
    return isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef)
    ) and bool(node.decorator_list)


def unreferenced_names(sources: dict[Path, str]) -> list[tuple[Path, int, str]]:
    """Public module-level names in ``app`` that occur exactly once."""
    out: list[tuple[Path, int, str]] = []
    for path, text in sources.items():
        if (_BACKEND / "app") not in path.parents:
            continue
        for node in ast.parse(text).body:
            names: list[tuple[str, int]] = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not _is_decorated(node):
                    names.append((node.name, node.lineno))
            elif isinstance(node, ast.Assign):
                names.extend(
                    (t.id, node.lineno)
                    for t in node.targets
                    if isinstance(t, ast.Name) and t.id.isupper()
                )
            for name, line in names:
                if name.startswith("_"):
                    continue
                word = re.compile(rf"\b{re.escape(name)}\b")
                if sum(len(word.findall(t)) for t in sources.values()) == 1:
                    out.append((path, line, name))
    return sorted(out)


def dangling_links() -> list[tuple[Path, str]]:
    """``(document, target)`` for every relative link resolving to nothing."""
    out: list[tuple[Path, str]] = []
    for document in sorted(_DOCS.rglob("*.md")):
        text = document.read_text(encoding="utf-8", errors="ignore")
        for target in _LINK.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative = unquote(target.split("#")[0])
            if not relative:
                continue
            if not (document.parent / relative).resolve().exists():
                out.append((document, target))
    return out


def _where(path: Path) -> str:
    return path.relative_to(_ROOT).as_posix()


def _section(title: str, rows: list[str]) -> None:
    print(f"\n=== {title} ({len(rows)}) ===")
    for row in rows or ["none"]:
        print(f"  {row}")


def main() -> int:
    js = _js_sources()
    py = _python_sources()

    orphans = orphan_modules(js)
    exports = unused_exports(js)
    names = unreferenced_names(py)
    links = dangling_links()

    print(f"frontend modules: {len(js)}   backend modules: {len(py)}")

    _section("frontend modules nothing imports", [_where(p) for p in orphans])
    _section(
        "frontend exports nothing outside the file mentions",
        [f"{_where(p)}:{line}   {name}" for p, line, name in exports],
    )
    _section(
        "backend names nothing references",
        [f"{_where(p)}:{line}   {name}" for p, line, name in names],
    )
    _section(
        "documentation links that point at nothing",
        [f"{_where(d)} -> {target}" for d, target in links],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
