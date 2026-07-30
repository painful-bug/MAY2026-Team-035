"""Guards on the API surface itself.

``docs/openapi.yaml`` is generated from the code, which makes it trustworthy
right up until someone changes a route and forgets to regenerate. This module is
what stops that: a stale spec fails the build rather than quietly shipping a lie
to whoever generates a client from it.

The other two tests catch failure modes that have no other alarm -- a router
written but never mounted (nothing errors; the endpoints simply do not exist),
and an endpoint that forgets its auth dependency (it works perfectly, for
everyone).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.main import app

_SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.yaml"

#: Everything reachable without a token. Adding to this list is a security
#: decision, so it is written out here rather than inferred.
#:
#: The OTP and redeem entries are gone: Google-only OAuth replaced them and the
#: routes no longer exist. What replaced them is cookie-based, and a cookie is not
#: an OpenAPI security scheme the generator can see -- so the sign-in handshake and
#: logout legitimately declare none. Each is listed individually rather than
#: skipping the whole ``/auth`` prefix, so a new authenticated auth route cannot
#: inherit an exemption by sitting next to a public one.
_PUBLIC_PATHS = {
    "/health",
    "/api/v1/auth/methods",
    "/api/v1/auth/google/start",
    "/api/v1/auth/google/callback",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    # Exchanges an invite token+code for a short-lived signed cookie. Called
    # before the user has signed in -- that is the point of it.
    "/api/v1/invitations/prepare",
}


def _spec() -> dict:
    return app.openapi()


def test_checked_in_spec_matches_the_code():
    """docs/openapi.yaml must be what `scripts/export_openapi.py` produces now."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.export_openapi import build_spec, render

    assert _SPEC_PATH.exists(), (
        "docs/openapi.yaml is missing. Run: python scripts/export_openapi.py"
    )
    assert _SPEC_PATH.read_text(encoding="utf-8") == render(build_spec()), (
        "docs/openapi.yaml is out of date. "
        "Run: python scripts/export_openapi.py"
    )


@pytest.mark.parametrize(
    "path",
    [
        # Ours, one per surviving router.
        "/api/v1/admins",
        "/api/v1/notices",
        "/api/v1/complaints/{complaint_id}",
        "/api/v1/departments",
        "/api/v1/invoices",
        "/api/v1/billing-settings",
        "/api/v1/amenity-reports",
        "/api/v1/settings",
        # Theirs. Listed because our admin_router is mounted from the same
        # aggregator, so a mistake there could drop their routes instead of ours.
        "/api/v1/dashboard/snapshot",
        "/api/v1/auth/session",
        "/api/v1/admin/access-requests",
        "/api/v1/communities/search",
        "/api/v1/onboarding/community",
    ],
)
def test_every_router_is_mounted(path):
    """One representative path per router.

    A router that is written but never added to ``api_router`` raises nothing at
    all -- its endpoints just silently do not exist, and the first person to
    notice is whoever calls them.
    """
    assert path in _spec()["paths"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/dashboard/admin",
        "/api/v1/residents",
        "/api/v1/registrations",
        "/api/v1/complaints",
        "/api/v1/complaint-categories",
        "/api/v1/payments",
        "/api/v1/amenities",
        "/api/v1/settings/modules",
    ],
)
def test_retired_endpoints_stay_retired(path):
    """Paths deliberately removed by the frontend wiring audit.

    Each was either duplicating an endpoint the frontend already calls or serving
    a read the shared dashboard snapshot serves. Re-adding one is a decision, not
    an accident, so it should have to delete a line here first. See
    ``docs/FRONTEND_WIRING_AUDIT.md``.
    """
    assert path not in _spec()["paths"]


def test_no_protected_endpoint_is_missing_its_auth_dependency():
    """An endpoint that forgets `Depends(get_current_user)` still works -- for
    everyone. Nothing else in the stack notices."""
    unprotected = []
    for path, item in _spec()["paths"].items():
        if path in _PUBLIC_PATHS:
            continue
        for method, operation in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not operation.get("security"):
                unprotected.append(f"{method.upper()} {path}")

    assert not unprotected, (
        "These endpoints declare no security scheme: " + ", ".join(sorted(unprotected))
    )
