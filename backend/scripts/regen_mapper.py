"""Regenerate the operation tables in ``docs/api_yaml_mapper.md``.

Run from ``backend/``::

    python scripts/regen_mapper.py           # rewrite the tables
    python scripts/regen_mapper.py --check   # exit 1 if a rewrite would change it

**Why this exists.** The mapper's tables carry four mechanical facts per
operation -- the route, the handler and its line, the ``operationId``, and the
success schema -- plus one editorial one, which section of ``API.md`` covers it.
The mechanical four were maintained by hand, and by 2026-08-11 the *line
numbers* had drifted by roughly seventy across the file: ``API.md`` grows above
a heading and every reference below it moves. Nothing caught that, because
``api_map_scan.py`` checks whether an operation is *mentioned* in the mapper,
not whether the row is still true.

**The split this script keeps.** It regenerates what can be derived and
preserves what cannot:

* *Derived, every run* -- the route, ``handler :line``, the ``operationId``, and
  the success schema. These come from the live app and the generated spec, so
  they cannot disagree with the code.
* *Preserved* -- the choice of which ``API.md`` section covers an operation.
  For an operation with its own ``###`` heading that is mechanical too; but the
  ``mention only -- § 3.4 Password recovery`` cells are somebody deciding which
  prose paragraph is the right answer, and no script can rederive that. The
  label is kept verbatim and only its **line number** is re-resolved.
* *Preserved* -- bold. ``**200 free-form object**`` marks a §5 defect and
  ``200 free-form object`` does not; the difference is a judgment about whether
  the untyped body matters. When a derived cell matches an existing one apart
  from its ``**``, the existing one wins.

Everything outside the tables -- the layer chains, the notes, the blockquotes,
§1, §2, §4 through §7 -- is untouched, byte for byte.

**When a heading a cell points at no longer exists**, the line number is dropped
and the label kept, rather than being silently repointed at whatever is nearest.
A missing reference is a finding; a confidently wrong one is a trap.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_DOCS = _BACKEND.parent / "docs"
_API_MD = _DOCS / "API.md"
_MAPPER = _DOCS / "api_yaml_mapper.md"

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from api_map_scan import _camel, _spellings, live_operations  # noqa: E402

_SPEC = _DOCS / "openapi.yaml"

_HEADER = (
    "| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |"
)
_RULE = "|---|---|---|---|---|"

# The order the tables have always used: by path, then by method within a path.
_METHOD_ORDER = {"get": 0, "post": 1, "put": 2, "patch": 3, "delete": 4}


def _success_cell(operation: dict) -> str:
    """``201 BookingSummary`` / ``200 free-form object`` / ``200 `text/csv``` …

    The first 2xx or 3xx response wins, which is the one a client codegen would
    bind to.
    """
    for code, response in sorted(operation.get("responses", {}).items()):
        if code[0] not in "23":
            continue
        content = response.get("content")
        if not content:
            return f"{code} no body"
        content_type, body = next(iter(content.items()))
        if content_type != "application/json":
            return f"{code} `{content_type}`"
        schema = body.get("schema", {})
        ref = schema.get("$ref")
        if ref:
            return f"{code} {ref.rsplit('/', 1)[-1]}"
        if schema.get("type") == "array":
            item = schema.get("items", {}).get("$ref")
            name = item.rsplit("/", 1)[-1] if item else "inline"
            return f"{code} array of {name}"
        if not schema or schema.get("additionalProperties") is True:
            return f"{code} free-form object"
        return f"{code} inline"
    return "—"


def _headings(api_md: str) -> list[tuple[int, str, str]]:
    """``(line number, hashes, text)`` for every heading in ``API.md``."""
    out = []
    for number, line in enumerate(api_md.splitlines(), start=1):
        match = re.match(r"^(#{2,4}) (.+?)\s*$", line)
        if match:
            out.append((number, match.group(1), match.group(2)))
    return out


def _resolve(label: str, headings: list[tuple[int, str, str]]) -> int | None:
    """The line of the heading a preserved ``API.md`` cell label refers to.

    Labels come in two shapes -- a quoted route (``` `GET /api/v1/x` ```) which
    matches a heading exactly, and a section reference (``3.4 Password
    recovery``, ``16.6``) which is a prefix of one.
    """
    clean = label.strip().strip("`").strip()
    for number, _, text in headings:
        if text.strip().strip("`") == clean:
            return number
    for number, _, text in headings:
        if text.startswith(clean) or clean.startswith(text):
            return number
    # `16.6` against `### 16.6 Endpoints that serve no story, and why that is fine`
    lead = clean.split()[0] if clean.split() else ""
    if re.fullmatch(r"\d+(\.\d+)?\.?", lead):
        for number, _, text in headings:
            if text.startswith(lead.rstrip(".")):
                return number
    return None


def _api_md_cell(existing: str | None, path: str, headings) -> str:
    """Keep the editorial choice; refresh only the line number."""
    if existing is not None and existing.strip():
        cell = existing.strip()
        if "**missing**" in cell:
            return cell
        label = re.sub(r"\s*\(API\.md:\d+\)\s*$", "", cell)
        bare = re.sub(r"^(?:mention only\s*[—-]\s*)?§\s*", "", label).strip()
        line = _resolve(bare, headings)
        return f"{label} (API.md:{line})" if line else label

    for number, hashes, text in headings:
        if hashes != "###":
            continue
        stripped = text.strip().strip("`")
        for spelling in _spellings(path):
            if stripped.endswith(spelling) or stripped.endswith(f"{spelling}`"):
                return f"§ `{stripped}` (API.md:{number})"
    return "**missing**"


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _previous(
    old: dict[tuple[str, str], list[str]],
    key: tuple[str, str],
    matched: set[tuple[str, str]],
) -> list[str] | None:
    """The row this operation had before, under either spelling of its path.

    Some rows quote the route in camelCase, against §1's own rule that the
    mapper writes it as the code declares it. Matching both keeps a normalised
    row's ``API.md`` cell instead of making it look newly added.
    """
    for candidate in (key, (key[0], _camel(key[1]))):
        if candidate in old:
            matched.add(candidate)
            return old[candidate]
    return None


def _keep_bold(derived: str, existing: str | None) -> str:
    """``**200 free-form object**`` is a verdict; ``200 free-form object`` is not."""
    if existing and existing.replace("**", "").strip() == derived:
        return existing.strip()
    return derived


def build(spec: dict) -> tuple[dict[str, list[tuple[str, str]]], dict]:
    """``{router file: [(sort key, row key)]}`` and the derived cells per key."""
    live = live_operations()
    by_file: dict[str, list] = {}
    derived: dict[tuple[str, str], dict] = {}
    for (method, path), where in live.items():
        operation = spec["paths"].get(path, {}).get(method)
        if operation is None:
            continue
        section = f"backend/{where['file']}"
        entry = (path, _METHOD_ORDER[method], (method, path))
        by_file.setdefault(section, []).append(entry)
        derived[(method, path)] = {
            "operation": f"`{method.upper()} {path}`",
            "handler": f"`{where['handler']}` :{where['line']}",
            "anchor": f"`{operation['operationId']}`",
            "success": _success_cell(operation),
            "path": path,
        }
    return {k: [v[2] for v in sorted(vs)] for k, vs in by_file.items()}, derived


def rewrite(text: str, api_md: str, spec: dict) -> tuple[str, list[str]]:
    by_file, derived = build(spec)
    headings = _headings(api_md)
    lines = text.splitlines()
    out: list[str] = []
    notes: list[str] = []
    index = 0
    section: str | None = None

    while index < len(lines):
        line = lines[index]
        heading = re.match(r"^### `(backend/[^`]+)`\s*$", line)
        if heading:
            section = heading.group(1)
        if line.strip() != _HEADER:
            out.append(line)
            index += 1
            continue

        # A table: the header, its rule, and every row until a non-`|` line.
        start = index
        index += 1
        if index < len(lines) and lines[index].strip() == _RULE:
            index += 1
        old: dict[tuple[str, str], list[str]] = {}
        order: list[tuple[str, str]] = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            cells = _cells(lines[index])
            match = re.match(r"`(\w+) (\S+)`", cells[0]) if cells else None
            if match:
                key = (match.group(1).lower(), match.group(2))
                old[key] = cells
                order.append(key)
            index += 1

        keys = by_file.get(section or "", [])
        if not keys:
            notes.append(f"  no live operations for {section}; table left as written")
            out.extend(lines[start:index])
            continue

        matched: set[tuple[str, str]] = set()
        out.append(_HEADER)
        out.append(_RULE)
        for key in keys:
            fields = derived[key]
            was = _previous(old, key, matched)
            out.append(
                _row(
                    [
                        fields["operation"],
                        fields["handler"],
                        fields["anchor"],
                        _keep_bold(fields["success"], was[3] if was else None),
                        _api_md_cell(was[4] if was else None, fields["path"], headings),
                    ]
                )
            )
        for gone in order:
            if gone not in matched:
                notes.append(
                    f"  dropped {gone[0].upper()} {gone[1]} — no longer a live route"
                )
        for added in keys:
            if added not in old and (added[0], _camel(added[1])) not in old:
                notes.append(f"  added {added[0].upper()} {added[1]}")
        section = None

    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if the file would change"
    )
    args = parser.parse_args()

    spec = yaml.safe_load(_SPEC.read_text(encoding="utf-8"))
    text = _MAPPER.read_text(encoding="utf-8")
    api_md = _API_MD.read_text(encoding="utf-8")

    fresh, notes = rewrite(text, api_md, spec)
    for note in notes:
        print(note)

    if fresh == text:
        print(f"{_MAPPER} is up to date.")
        return 0
    if args.check:
        print(f"{_MAPPER} is stale — run scripts/regen_mapper.py")
        return 1
    _MAPPER.write_text(fresh, encoding="utf-8")
    changed = sum(
        1
        for a, b in zip(text.splitlines(), fresh.splitlines(), strict=False)
        if a != b
    )
    print(f"rewrote {_MAPPER} ({changed} row(s) differ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
