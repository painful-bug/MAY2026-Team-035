"""Regenerate ``docs/openapi.yaml`` from the live FastAPI app.

Run from ``backend/``::

    python scripts/export_openapi.py           # write the spec
    python scripts/export_openapi.py --check   # fail if it is out of date

**Generated, never hand-edited.** A hand-maintained spec drifts from the code
the first time a field is renamed, and a spec that lies is worse than no spec:
clients generate types from it. ``docs/API.md`` stays hand-written because it
carries the reasoning -- why a delete is really a deactivation, which guard
returns 409 -- which no generator can produce. The two are complementary, and
`--check` in CI is what keeps this half honest.

Placeholder Supabase settings are injected below because importing ``app.main``
constructs ``Settings``, which requires them. They are never used: nothing here
opens a connection, and the emitted document contains no secret.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_OUTPUT = _BACKEND.parent / "docs" / "openapi.yaml"

# Set before importing the app, and only when absent, so a real .env still wins.
_PLACEHOLDERS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
    "SUPABASE_JWT_SECRET": "placeholder-jwt-secret",
}
for _key, _value in _PLACEHOLDERS.items():
    os.environ.setdefault(_key, _value)

sys.path.insert(0, str(_BACKEND))

import yaml  # noqa: E402

from app.main import app  # noqa: E402

_HEADER = """# HomeBandhu API — OpenAPI 3.1 description
#
# GENERATED FILE. Do not edit by hand; your changes will be overwritten.
# Regenerate from backend/ with:
#
#     python scripts/export_openapi.py
#
# Verify it is current with `--check`. The prose companion, with the reasoning
# behind each endpoint and its status codes, is docs/API.md.
"""


def build_spec() -> dict:
    """Return the OpenAPI document, with the descriptions a generator cannot infer."""
    spec = app.openapi()

    # Servers are a deployment fact, not a code fact, so FastAPI does not emit
    # them. Without at least one, generated clients default to the host serving
    # the spec -- which for a file checked into docs/ is nothing at all.
    spec["servers"] = [
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "https://{host}", "description": "Deployed", "variables": {
            "host": {"default": "api.homebandhu.example", "description": "API host"}
        }},
    ]

    spec.setdefault("tags", [])
    known = {tag["name"] for tag in spec["tags"]}
    for name, description in (
        ("auth", "Sign-in, token refresh and the caller's own profile."),
        ("invitations", "Admin-issued invites and their redemption."),
        ("dashboard", "Admin dashboard tiles, community profile and residents."),
        ("people", "Admins and the registration review queue."),
        ("complaints", "Complaints, their timeline, comments and attachments."),
        ("departments", "Departments, staff rosters and complaint categories."),
    ):
        if name not in known:
            spec["tags"].append({"name": name, "description": description})

    return spec


def render(spec: dict) -> str:
    """Serialise deterministically, so an unchanged API produces an identical file."""
    body = yaml.safe_dump(
        spec,
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    return _HEADER + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the checked-in spec differs from the code.",
    )
    args = parser.parse_args()

    spec = build_spec()
    rendered = render(spec)

    if args.check:
        if not _OUTPUT.exists():
            print(f"{_OUTPUT} is missing. Run: python scripts/export_openapi.py")
            return 1
        if _OUTPUT.read_text(encoding="utf-8") != rendered:
            print(
                f"{_OUTPUT} is out of date. Run: python scripts/export_openapi.py"
            )
            return 1
        print(f"{_OUTPUT} is up to date.")
        return 0

    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(rendered, encoding="utf-8")
    operations = sum(
        1
        for item in spec["paths"].values()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    )
    # ASCII only: the Windows console this project is developed on is cp1252 and
    # mangles an em dash in `print`.
    print(f"Wrote {_OUTPUT} - {len(spec['paths'])} paths, {operations} operations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
