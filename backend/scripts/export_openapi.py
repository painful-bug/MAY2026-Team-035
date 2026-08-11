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
    "COOKIE_SIGNING_SECRET": "placeholder-cookie-signing-secret-0123456789",
}
for _key, _value in _PLACEHOLDERS.items():
    os.environ.setdefault(_key, _value)

sys.path.insert(0, str(_BACKEND))

import yaml  # noqa: E402

from app.main import app  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_annotations import (  # noqa: E402
    ERROR_RESPONSES,
    ERROR_SCHEMA_DOCS,
    NO_STORY_STATUS,
    OPERATIONS,
    PARAMETER_DESCRIPTIONS,
    PARAMETER_OVERRIDES,
    STATUS_TO_RESPONSE,
    STORIES,
)

_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

_INFO_DESCRIPTION = """\
Admin-dashboard backend for HomeBandhu, a FastAPI service over Supabase.

## Reading this document

Every operation carries four things beyond its request and response schemas:

* a **summary** and a **description** saying what it does and what is
  surprising about it;
* the **error responses it can actually return**, derived by walking each
  handler into its services and repositories rather than assumed;
* **`x-user-stories`**, tracing the operation back to the team's requirements;
* **`security`**, or its deliberate absence on the pre-authentication routes.

## Errors

Every failure returns one envelope, `ErrorResponse`:

```json
{"error": {"code": "not_found", "message": "Department not found.", "details": []}}
```

Branch on `error.code`, never on `error.message`, which is prose and may be
reworded. `details[]` appears only on `request_validation_error` and lists the
offending fields. This shape is emitted by all four handlers registered in
`app/core/exceptions.py`, including the catch-all, so a client needs exactly one
error path. Note that this is **not** FastAPI's stock `{"detail": [...]}`: the
default handlers are replaced.

`404` is returned both for a resource that does not exist and for one the caller
may not see. That ambiguity is deliberate -- a 404 must never confirm that
another community's data exists.

## User stories

`x-user-stories` links an operation to the stories in
`docs/product/USER_STORIES.md`, with the role it plays in each and whether that
story is `served` or `partial`.

An operation that serves none carries `x-no-user-story` instead, which states
`Not covered by user story` and then classifies what the operation is --
`Feature`, `Functional`, `Configuration`, `Master data` or `Non-functional` --
with the reason. Absence of a story is therefore a recorded verdict rather than
an omission, and says what the operation *is* instead of only what it is not.

`docs/API.md` section 16 is the prose matrix, and is the only one of the two
that also names the stories **nothing** serves yet -- a spec can only describe
endpoints that exist.

## Scope

This describes the admin-dashboard build. `docs/product/USER_IDENTIFICATION.md`
records one consequence worth knowing before reading the traceability: staff
have no login, so every story written for a Facility or Security Manager is
either an administrator acting on their behalf or has no home here.
"""

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


def _operations(spec: dict):
    """Yield ((method, path), operation) for every real operation in the spec."""
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method in _METHODS:
                yield (method, path), operation


# A tag with no entry here still groups its operations in Swagger UI, but the
# group arrives unlabelled -- a reader sees `resident-money` and has to open the
# operations to find out what it separates from `money`. The order below is the
# order the groups render in, so it runs outward: the caller's own session,
# joining a community, then the admin surface, then the resident surface.
_TAGS: tuple[tuple[str, str], ...] = (
    ("auth", "Sign-in, token refresh and the caller's own profile."),
    ("onboarding", "Founding a community -- once per community, by its first admin."),
    ("communities", "Finding a community to join, and reading its unit list."),
    (
        "access requests",
        "A resident asking to join a community, and the admin queue that answers.",
    ),
    ("invitations", "Admin-issued invites and their redemption."),
    ("dashboard", "Admin dashboard tiles, community profile and residents."),
    ("people", "Admins and the registration review queue."),
    ("complaints", "Complaints, their timeline, comments and attachments."),
    ("departments", "Departments, staff rosters and complaint categories."),
    ("amenities", "The amenity catalogue, its bookings, approvals and ledger."),
    ("money", "Community-side billing: invoices raised, payments recorded."),
    ("settings", "Community and billing configuration."),
    ("notices", "Society notices."),
    ("resident-home", "A resident's own home screen, household and directory."),
    ("visitors", "Visitor passes: pre-approval, approval at the gate, cancellation."),
    ("resident-money", "A resident's own invoices and bookings, and paying them."),
    ("notifications", "The resident's in-app notification feed and its read state."),
    ("push", "Web Push plumbing: the application server key and its subscriptions."),
    ("realtime", "The server-sent event stream."),
    (
        "department-hiring",
        "Applications, invitations, candidate search, removal and blacklisting, "
        "from the department's side. The router guard asks whether the caller "
        "manages anything; the database asks whether they manage this.",
    ),
    (
        "service-providers",
        "A service person's own registration and the global catalogue of trades. "
        "The only surface here whose callers hold no community membership.",
    ),
    (
        "worker-communities",
        "Finding work and tracking applications, from the service person's side. "
        "Scoped to the caller's own provider row, never to a community id they "
        "supply.",
    ),
    (
        "worker-jobs",
        "A service person's own jobs and the five things they can do to one. "
        "Authenticated only and cross-community by design: a role guard here "
        "would read the wrong one of a worker's four memberships.",
    ),
    (
        "worker-schedule",
        "A service person's calendar, leave and working week -- all of it "
        "global across every community that employs them, which is what the "
        "dispatch sweep reads before offering anybody a job.",
    ),
    (
        "conversations",
        "The chat between a department and a service person. One thread per "
        "pair, and the only surface here with no role guard at all -- "
        "participation is a property of the thread, so the database decides it.",
    ),
    (
        "messages",
        "Direct messages between people (0046): the chat dock on every "
        "portal. One thread per pair per community; a resident and a "
        "serviceman share only the work-order thread, which locks when the "
        "job ends. Identity-only guard for the conversations reason -- "
        "participation is a property of the thread.",
    ),
    (
        "complaint-routing",
        "Which department owns a complaint. Decided when it is raised -- the "
        "category first, the resident's own guess second, the admin's triage "
        "queue third -- and corrected afterwards by an admin allotting, a "
        "manager moving, or a supervisor asking their manager to.",
    ),
    (
        "work-orders",
        "Turning a triaged complaint into a scheduled visit by a named person. "
        "The role guard is coarse because a supervisor is a rank on a roster "
        "and not a membership role; the department check is in the database.",
    ),
    (
        "resident-scheduling",
        "The resident's answer to a proposed visit. Two routes, neither of "
        "which takes a work-order id -- the job is resolved from the complaint, "
        "so naming somebody else's is not expressible.",
    ),
    (
        "security-operations",
        "The gate: posts, shifts, the two registers, incidents, credential "
        "verification and the CSV exports. The one surface in this feature "
        "scoped to a single community, because a gate belongs to one society.",
    ),
    (
        "skills",
        "Authoring the global trade catalogue, and saying which trades a "
        "department needs. Reading the catalogue is `service-providers`' "
        "`GET /skills`, because that endpoint exists for the registration "
        "screen and any signed-in person may call it; everything here is "
        "admin-or-manager only. The catalogue is global and a department's "
        "claim on it is not.",
    ),
    ("system", "Liveness."),
)


def _apply_tags(spec: dict) -> None:
    """Describe every tag group, and refuse to build if one is undescribed.

    Same bargain as ``_check_coverage``: the check is what keeps the list from
    silently going stale. A new router introduces a new tag, and without this it
    would ship as an unlabelled group that nobody notices is unlabelled.
    """
    in_use = {
        tag
        for _, operation in _operations(spec)
        for tag in operation.get("tags", [])
    }
    described = {name for name, _ in _TAGS}
    if missing := sorted(in_use - described):
        raise SystemExit(
            "These tags group operations but have no description in "
            "scripts/export_openapi.py:\n  " + "\n  ".join(missing)
        )
    if stale := sorted(described - in_use):
        raise SystemExit(
            "scripts/export_openapi.py describes tags nothing uses:\n  "
            + "\n  ".join(stale)
        )
    spec["tags"] = [{"name": name, "description": text} for name, text in _TAGS]


def _check_request_bodies(spec: dict) -> None:
    """No operation may carry content on a method that gives it no meaning.

    RFC 9110 leaves content on `GET`, `HEAD` and `DELETE` undefined: clients may
    decline to send it, intermediaries may strip it, and OpenAPI tooling warns.
    A body that reaches the server in development and vanishes behind a proxy in
    production is the worst failure available, so this is a build error rather
    than a review note. The remedy is a `POST` to a sub-path, as
    `/push/subscriptions/unregister` does.
    """
    offenders = [
        f"{method.upper():6} {path}"
        for (method, path), operation in _operations(spec)
        if method in {"get", "head", "delete"} and "requestBody" in operation
    ]
    if offenders:
        raise SystemExit(
            "These operations put a body on a method with no defined body "
            "semantics:\n  " + "\n  ".join(offenders)
        )


def _check_coverage(spec: dict) -> None:
    """Refuse to build if the annotation table and the code disagree.

    This is what makes a side table safe. Without it, renaming a route silently
    drops its error responses and its traceability, and the spec keeps claiming
    coverage it no longer has. Adding an endpoint fails here until somebody
    declares which stories it serves -- including declaring that it serves none.
    """
    live = {key for key, _ in _operations(spec)}
    declared = set(OPERATIONS)
    problems: list[str] = []

    # Both halves are reported together: a renamed route produces one of each,
    # and seeing them side by side is what identifies it as a rename rather
    # than an addition and an unrelated deletion.
    if missing := sorted(live - declared):
        problems.append(
            "These operations have no entry in scripts/api_annotations.py:\n  "
            + "\n  ".join(f"{m.upper():6} {p}" for m, p in missing)
            + "\n  Add one, with its error codes and either its user stories"
            " or a no_story reason."
        )
    if stale := sorted(declared - live):
        problems.append(
            "scripts/api_annotations.py annotates operations that do not exist:\n  "
            + "\n  ".join(f"{m.upper():6} {p}" for m, p in stale)
            + "\n  Remove them, or fix the path if the route was renamed."
        )
    if problems:
        raise SystemExit("\n\n".join(problems))

    for key, entry in OPERATIONS.items():
        if not entry["stories"] and not entry["no_story"]:
            raise SystemExit(
                f"{key[0].upper()} {key[1]} declares neither stories nor a"
                " no_story reason. Silence is not a verdict."
            )
        for story_id, _role in entry["stories"]:
            if story_id not in STORIES:
                raise SystemExit(
                    f"{key[0].upper()} {key[1]} cites unknown story {story_id}."
                )


def _apply_annotations(spec: dict) -> None:
    """Attach error responses, user stories and missing descriptions."""
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    _document_error_schemas(schemas)
    spec["components"]["responses"] = dict(ERROR_RESPONSES)

    for key, operation in _operations(spec):
        entry = OPERATIONS[key]

        if entry["description"] and not operation.get("description"):
            operation["description"] = entry["description"]

        for parameter in operation.get("parameters", []) or []:
            if (parameter.get("description") or "").strip():
                continue  # an explicit Query(description=...) wins
            name = parameter["name"]
            parameter["description"] = PARAMETER_OVERRIDES.get(
                (key[0], key[1], name)
            ) or PARAMETER_DESCRIPTIONS.get(name) or parameter.get("schema", {}).get(
                "description", ""
            )
            if not parameter["description"]:
                del parameter["description"]

        responses = operation.setdefault("responses", {})
        # Union, never subtraction. The declared set is what this table derived
        # plus anything the app itself declares -- `include_router(...,
        # responses={422: ErrorResponse})` in app/main.py, and the explicit
        # 401/403 on the SSE route. Narrowing a claim the code makes is not the
        # exporter's call; every one of them is rendered through the same
        # component so the document reads consistently either way.
        declared = set(entry["errors"]) | {
            status
            for status in responses
            if status.startswith(("4", "5")) and status in STATUS_TO_RESPONSE
        }
        for status in sorted(declared):
            responses[status] = {
                "$ref": f"#/components/responses/{STATUS_TO_RESPONSE[status]}"
            }

        if entry["stories"]:
            operation["x-user-stories"] = [
                {
                    "id": story_id,
                    "title": STORIES[story_id][0],
                    "coverage": STORIES[story_id][1],
                    "role": role,
                }
                for story_id, role in entry["stories"]
            ]
        else:
            api_type, rationale = entry["no_story"]
            operation["x-user-stories"] = []
            operation["x-no-user-story"] = {
                "status": NO_STORY_STATUS,
                "api-type": api_type,
                "rationale": rationale,
            }

    _drop_unreferenced(spec, {"HTTPValidationError", "ValidationError"})


def _document_error_schemas(schemas: dict) -> None:
    """Add prose to the generated error models, without redefining them.

    ``ErrorResponse`` and friends are pydantic models in
    ``app/core/exceptions.py`` as of cfe803c, so their shape is generated. Only
    descriptions are contributed, and only where the generator produced none --
    an explicit ``Field(description=...)`` upstream always wins.
    """
    for name, fields in ERROR_SCHEMA_DOCS.items():
        schema = schemas.get(name)
        if schema is None:  # the models were removed or renamed upstream
            continue
        for field, text in fields.items():
            target = schema if field == "" else schema.get("properties", {}).get(field)
            if target is not None and not (target.get("description") or "").strip():
                target["description"] = text


def _drop_unreferenced(spec: dict, candidates: set[str]) -> None:
    """Remove FastAPI's default error schemas once nothing points at them.

    Leaving them in would keep advertising `{"detail": [...]}` as a response
    shape, which is precisely the claim this pass exists to remove.
    """
    schemas = spec["components"]["schemas"]
    changed = True
    while changed:  # HTTPValidationError refs ValidationError; drop in waves.
        changed = False
        for name in sorted(candidates & set(schemas)):
            others = {k: v for k, v in spec.items() if k != "components"}
            others["_schemas"] = {k: v for k, v in schemas.items() if k != name}
            others["_responses"] = spec["components"].get("responses", {})
            if f"#/components/schemas/{name}" not in yaml.safe_dump(
                others, sort_keys=True
            ):
                del schemas[name]
                changed = True


def build_spec() -> dict:
    """Return the OpenAPI document, with the descriptions a generator cannot infer."""
    spec = app.openapi()
    spec["info"]["description"] = _INFO_DESCRIPTION
    spec["info"]["contact"] = {
        "name": "HomeBandhu backend workstream, Team 035",
        "url": "https://github.com/painful-bug/MAY2026-Team-035",
    }
    spec["info"]["license"] = {
        "name": "UNLICENSED",
        "identifier": "LicenseRef-coursework",
    }
    _check_coverage(spec)
    _check_request_bodies(spec)
    _apply_annotations(spec)

    # Servers are a deployment fact, not a code fact, so FastAPI does not emit
    # them. Without at least one, generated clients default to the host serving
    # the spec -- which for a file checked into docs/ is nothing at all.
    spec["servers"] = [
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "https://{host}", "description": "Deployed", "variables": {
            "host": {"default": "api.homebandhu.example", "description": "API host"}
        }},
    ]

    _apply_tags(spec)

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
