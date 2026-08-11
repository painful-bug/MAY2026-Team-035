"""Check the live routes against ``openapi.yaml``, ``API.md`` and the mapper.

Run from ``backend/``::

    python scripts/api_map_scan.py            # report
    python scripts/api_map_scan.py --strict   # exit 1 on any finding
    python scripts/api_map_scan.py --max-findings 20  # reject baseline growth

``export_openapi.py --check`` proves the yaml matches what FastAPI *declares*.
It cannot prove the declaration matches what the handler *does* -- a handler
returning a raw ``Response``, or annotated ``-> dict``, satisfies that check
while documenting its body as ``{}``. This script covers the rest of the
distance, and is the scan ``docs/api_yaml_mapper.md`` §6.2 asks for after every
pull, when somebody else's endpoints arrive without our documentation.

Five questions, in the order they matter:

1. Does every live operation appear in the spec, and vice versa?
2. Does every operation describe its success body with a named component?
3. Does ``API.md`` document it?
4. Is it listed in ``docs/api_yaml_mapper.md``?
5. Do the three places that record a user story's verdict agree?

Question 5 is here because the answer was no. The verdict for each of the 24
stories is written in ``docs/product/USER_STORIES.md``, in ``API.md`` §16, and
in ``api_annotations.py`` (from where it reaches the spec as ``x-user-stories``
``coverage``). The exporter guards the mapping in one direction only -- every
*operation* must declare which stories it serves -- so six story lines reported
work as unfinished for four days after it shipped, and one story carried a
verdict no operation backed at all. Nothing mechanical could see either.

Findings are *not* automatically defects -- the SSE streams answer "no" to
question 2 on purpose. The mapper's §5 carries the verdict for each known one;
anything reported here that is not in §5 is new and needs one.
"""

from __future__ import annotations

import argparse
import inspect
import os
import re
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_DOCS = _BACKEND.parent / "docs"
_SPEC = _DOCS / "openapi.yaml"
_API_MD = _DOCS / "API.md"
_MAPPER = _DOCS / "api_yaml_mapper.md"
_USER_STORIES = _DOCS / "product" / "USER_STORIES.md"

# Set before importing the app, and only when absent, so a real .env still wins.
_PLACEHOLDERS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
    "SUPABASE_JWT_SECRET": "placeholder-jwt-secret",
    "COOKIE_SIGNING_SECRET": "placeholder-cookie-signing-secret-0123456789",
}
for _key, _value in _PLACEHOLDERS.items():
    os.environ.setdefault(_key, _value)

sys.path.insert(0, str(_BACKEND))

import yaml  # noqa: E402

from app.main import app  # noqa: E402

_METHODS = {"get", "post", "put", "patch", "delete"}

# FastAPI's own documentation endpoints. Not ours to document.
_BUILTIN = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}


def _leaves(obj):
    """Flatten FastAPI 0.139's lazy ``_IncludedRouter`` into concrete routes.

    ``include_router`` no longer copies prefixed routes onto ``app.routes``; a
    naive walk sees five entries instead of a hundred.
    """
    if type(obj).__name__ == "_IncludedRouter":
        for candidate in obj.effective_candidates():
            yield from _leaves(candidate)
    else:
        yield obj


def live_operations() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for registered in app.routes:
        for leaf in _leaves(registered):
            path = getattr(leaf, "path", None)
            route = getattr(leaf, "route", leaf)
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None or path is None or path in _BUILTIN:
                continue
            try:
                source = Path(inspect.getsourcefile(endpoint))
                rel = source.relative_to(_BACKEND).as_posix()
                line = inspect.getsourcelines(endpoint)[1]
            except (OSError, TypeError, ValueError):
                rel, line = "?", 0
            for method in getattr(route, "methods", None) or set():
                if method.lower() not in _METHODS:
                    continue
                out.setdefault(
                    (method.lower(), path),
                    {"file": rel, "line": line, "handler": endpoint.__name__},
                )
    return out


def documented_operations(spec: dict) -> dict[tuple[str, str], dict]:
    return {
        (method, path): operation
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in _METHODS
    }


def _concrete_success(operation: dict) -> bool:
    """Does at least one 2xx/3xx response name a schema a client can use?"""
    for code, response in operation.get("responses", {}).items():
        if code[0] not in "23":
            continue
        content = response.get("content")
        if not content:
            continue  # a declared empty body is a description, not a gap
        for content_type, body in content.items():
            if content_type != "application/json":
                return True  # streams and redirects describe themselves
            schema = body.get("schema", {})
            if not schema or schema.get("additionalProperties") is True:
                return False
            return True
    return True


def _camel(path: str) -> str:
    def one(match: re.Match[str]) -> str:
        name = re.sub(r"_(\w)", lambda c: c.group(1).upper(), match.group(1))
        return "{" + name + "}"

    return re.sub(r"\{([a-z_]+)\}", one, path)


def _spellings(path: str) -> set[str]:
    """Every way this path is written across the docs.

    ``API.md`` uses camelCase parameters and often drops the ``/api/v1`` prefix;
    the mapper quotes the route exactly as the code declares it.
    """
    out = set()
    for spelling in (path, _camel(path)):
        out.add(spelling)
        if spelling.startswith("/api/v1"):
            short = spelling[len("/api/v1") :]
            if len(short) > 1:
                out.add(short)
    return out


def _mentioned_in(text: str, path: str) -> bool:
    """Is this path written out anywhere in ``text``?

    The match is anchored on the left, and that is not a detail. A plain
    substring test says ``GET /communities/search`` is documented because
    ``§18`` documents ``GET /worker/communities/search`` -- a *different*
    endpoint that happens to end the same way. That hid a genuinely
    undocumented operation until the mapper was regenerated on 2026-08-11 and
    its row disagreed with the scan. Nothing may precede a spelling except a
    boundary: a longer path is not a mention of the shorter one.
    """
    return any(
        re.search(rf"(?<![\w/-]){re.escape(spelling)}", text)
        for spelling in _spellings(path)
    )


def _documented_in_api_md(text: str, path: str) -> bool:
    if _mentioned_in(text, path):
        return True
    # `### POST /x/{id}/approve` · `/reject` -- one heading, two operations.
    for spelling in _spellings(path):
        parent, _, last = spelling.rpartition("/")
        if not parent or not last:
            continue
        for line in text.splitlines():
            if f"{parent}/" in line and f"`/{last}`" in line:
                return True
    return False


def _story_verdicts_in_user_stories(text: str) -> dict[str, str]:
    """``**Backend:** **Served**`` under each ``### US-x.y`` heading."""
    out: dict[str, str] = {}
    for block in re.finditer(
        r"^### (US-\d+\.\d+) —(.*?)(?=^### |\Z)", text, re.M | re.S
    ):
        verdict = re.search(r"\*\*Backend:\*\* \*\*(\w+)\.?\*\*", block.group(2))
        out[block.group(1)] = verdict.group(1).lower() if verdict else "unreadable"
    return out


def _story_verdicts_in_api_md(text: str) -> dict[str, str]:
    """§16's own headings and, for the security manager, its summary table."""
    out: dict[str, str] = {}
    section = text[text.index("## 16. User stories") :]
    verdict = r"\*\*(served|partial|none)\*\*"
    # One heading can carry two stories: `#### US-2.1 — … · US-2.2 — … — **served**`.
    for line in re.findall(r"^#### US-.*$", section, re.M):
        for part in line.split("·"):
            found = re.search(rf"(US-\d+\.\d+).*?{verdict}", part)
            if found:
                out[found.group(1)] = found.group(2)
    for row in re.finditer(rf"^\| (US-\d+\.\d+) .*?\| {verdict}", section, re.M):
        out.setdefault(row.group(1), row.group(2))
    return out


def _check_stories(spec: dict, findings: list[str]) -> None:
    from api_annotations import STORIES  # noqa: PLC0415 -- optional, and local

    declared = _story_verdicts_in_user_stories(
        _USER_STORIES.read_text(encoding="utf-8")
    )
    matrix = _story_verdicts_in_api_md(_API_MD.read_text(encoding="utf-8"))

    served_by: dict[str, int] = {}
    for item in spec["paths"].values():
        for method, operation in item.items():
            if method not in _METHODS:
                continue
            for story in operation.get("x-user-stories") or []:
                served_by[story["id"]] = served_by.get(story["id"], 0) + 1

    print(f"\nuser stories: {len(declared)}")
    for story_id in sorted(declared, key=lambda s: [int(p) for p in s[3:].split(".")]):
        seen = {
            "USER_STORIES.md": declared[story_id],
            "API.md §16": matrix.get(story_id, "absent"),
            "api_annotations": STORIES.get(story_id, (None, "absent"))[1],
        }
        # A story no operation serves is legitimately absent from the code-side
        # table; "none" and "absent" are the same claim there.
        if seen["api_annotations"] == "absent" and declared[story_id] == "none":
            seen.pop("api_annotations")
        if len(set(seen.values())) > 1:
            findings.append(
                f"  STORY VERDICT   {story_id}  "
                + ", ".join(f"{where}={what}" for where, what in seen.items())
            )
        if declared[story_id] in {"served", "partial"} and not served_by.get(story_id):
            findings.append(
                f"  STORY UNBACKED  {story_id}  verdict "
                f"'{declared[story_id]}' and no operation declares it"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict", action="store_true", help="exit 1 when anything is reported"
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        help="exit 1 only when findings exceed this recorded baseline",
    )
    args = parser.parse_args()

    spec = yaml.safe_load(_SPEC.read_text(encoding="utf-8"))
    live = live_operations()
    documented = documented_operations(spec)
    api_md = _API_MD.read_text(encoding="utf-8")
    mapper = _MAPPER.read_text(encoding="utf-8")

    findings: list[str] = []

    print(f"live operations: {len(live)}   documented: {len(documented)}")

    for key in sorted(set(live) - set(documented)):
        method, path = key
        where = live[key]
        findings.append(
            f"  NOT IN SPEC     {method.upper():6} {path}"
            f"  ({where['file']}:{where['line']})"
        )
    for method, path in sorted(set(documented) - set(live)):
        findings.append(f"  NOT IN CODE     {method.upper():6} {path}")

    for key in sorted(live):
        operation = documented.get(key)
        if operation is None:
            continue
        method, path = key
        where = live[key]
        if not _concrete_success(operation):
            findings.append(
                f"  UNTYPED BODY    {method.upper():6} {path}"
                f"  ({where['file']}:{where['line']})"
            )
        if not _documented_in_api_md(api_md, path):
            findings.append(f"  NOT IN API.md   {method.upper():6} {path}")
        if not _mentioned_in(mapper, path):
            findings.append(f"  NOT IN MAPPER   {method.upper():6} {path}")

    operation_findings = len(findings)
    for line in findings:
        print(line)

    _check_stories(spec, findings)
    for line in findings[operation_findings:]:
        print(line)

    if findings:
        print(
            f"\n{len(findings)} finding(s). Each one is either a gap to document "
            "or a verdict to record in api_yaml_mapper.md §5."
        )
    else:
        print("\nno findings.")
    if args.max_findings is not None and len(findings) > args.max_findings:
        return 1
    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
