"""Test-wide setup and opt-in test-document generation.

``Settings`` is constructed at import time and requires the Supabase values plus,
since the Google-OAuth work landed, a cookie signing secret -- so without these
the whole app module raises before a single test runs.

The values are placeholders and nothing here opens a connection: the tests that
import the app inspect its *shape* -- which routes exist, what the generated
OpenAPI document says -- and never make a request to Supabase.

Test documentation is generated only when pytest receives
``--generate-test-docs``. Normal collection and test runs must leave tracked
README files unchanged.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

# `setdefault`, not assignment: a developer with a real .env in their environment
# keeps it, and these only fill the gaps.
for _key, _value in {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
    "SUPABASE_JWT_SECRET": "placeholder-jwt-secret",
    # Long enough to satisfy the minimum-length check in `Settings`.
    "COOKIE_SIGNING_SECRET": "placeholder-cookie-signing-secret-0123456789",
}.items():
    os.environ.setdefault(_key, _value)


@pytest.fixture(autouse=True)
def _reset_reference_read_caches():
    """Empty the process-local TTL caches (Phase B2) around every test.

    These caches are module-level singletons -- deliberately, so every request
    in one worker shares them -- which means every test in this session shares
    them too unless something clears them. Different tests reuse the same
    fixture community/department ids, monkeypatching the repository to return
    different rows each time; without this, the second test to call, say,
    `GET /departments` for "the" test community could be served the first
    test's cached response instead of hitting its own monkeypatched repo.
    Cleared both before and after so a test that fails partway through a
    mutation cannot leave a poisoned entry for the next one.
    """
    from app.services import departments_service, settings_service, skills_service

    def _clear() -> None:
        departments_service.reset_cache()
        skills_service.reset_cache()
        settings_service.reset_cache()

    _clear()
    yield
    _clear()


def pytest_addoption(parser):
    """Register the explicit switch for regenerating test documentation."""
    parser.addoption(
        "--generate-test-docs",
        action="store_true",
        default=False,
        help="Regenerate tests/README.md and tests/api/README.md during collection.",
    )


def pytest_collection_modifyitems(session, config, items):
    """Generate README files only when explicitly requested by the caller."""
    if not config.getoption("--generate-test-docs"):
        return

    api_tests = {}
    core_tests = {}

    for item in items:
        # Avoid issues with non-function items
        if not hasattr(item, "module") or not hasattr(item, "obj"):
            continue

        path_str = str(item.path) if hasattr(item, "path") else str(item.fspath)
        is_api = "tests\\api" in path_str or "tests/api" in path_str
        target_dict = api_tests if is_api else core_tests

        mod_name = Path(path_str).name

        if mod_name not in target_dict:
            mod_doc = (
                getattr(item.module, "__doc__", None) or "No description provided."
            )
            target_dict[mod_name] = {
                "doc": textwrap.dedent(mod_doc).strip(),
                "tests": [],
            }

        test_doc = getattr(item.obj, "__doc__", None) or "No description provided."
        target_dict[mod_name]["tests"].append(
            {
                "name": item.name,
                "doc": textwrap.dedent(test_doc).strip(),
            }
        )

    def write_readme(out_path, title, test_dict):
        lines = [
            f"# {title}",
            "",
            "> **Note:** This file is generated from test docstrings by running "
            "`uv run pytest --collect-only --generate-test-docs` from `backend`.",
            "",
        ]

        for mod_name, data in sorted(test_dict.items()):
            lines.append(f"## `{mod_name}`")
            if data["doc"]:
                lines.append(f"{data['doc']}")
            lines.append(f"\n*Total tests in this file: {len(data['tests'])}*\n")

            lines.append("| Test Function | Description |")
            lines.append("|---------------|-------------|")
            for t in data["tests"]:
                # Clean doc for table formatting
                doc_clean = " ".join(t["doc"].split("\n")).strip()
                doc_clean = doc_clean.replace("|", "\\|")
                lines.append(f"| `{t['name']}` | {doc_clean} |")
            lines.append("\n")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    base_dir = Path(__file__).parent
    try:
        write_readme(
            base_dir / "api" / "README.md", "API Tests Documentation", api_tests
        )
        write_readme(base_dir / "README.md", "Core Tests Documentation", core_tests)
    except Exception as e:
        print(f"Failed to generate READMEs: {e}")
