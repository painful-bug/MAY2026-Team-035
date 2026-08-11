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
# Endpoints that are unauthenticated on purpose. Everything here is reachable
# *before* the caller has a session, which is why none of them can require one.
# Adding a path to this set is a security decision: it says "anyone on the
# internet may call this", so it belongs in review, not in a quick fix to make
# the test below go green.
_PUBLIC_PATHS = {
    "/health",
    "/api/v1/auth/methods",
    # Issues the CSRF token that the sign-in POST must carry, so it necessarily
    # precedes any session.
    "/api/v1/auth/csrf",
    # OAuth redirect handshake. `google/*` is the original pair; `oauth/{provider}/*`
    # generalised it in the unified-auth work and both are still routed.
    "/api/v1/auth/google/start",
    "/api/v1/auth/google/callback",
    "/api/v1/auth/oauth/{provider}/start",
    "/api/v1/auth/oauth/{provider}/callback",
    # Password and email-confirmation flows. Every one of these is either how a
    # session is obtained or how an account is recovered when the user cannot
    # sign in, so requiring a session would make them unusable.
    "/api/v1/auth/password/sign-up",
    "/api/v1/auth/password/sign-in",
    "/api/v1/auth/password/reset/request",
    "/api/v1/auth/password/reset/verify",
    "/api/v1/auth/password/reset/complete",
    "/api/v1/auth/email/verify",
    "/api/v1/auth/email/resend",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    # Anonymous launch-funnel events are bound to a random HTTP-only visitor
    # cookie and still require the pre-auth CSRF pair; no account is required.
    "/api/v1/telemetry/service-signup",
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
        # The service-operations aggregate. Nine routers behind one
        # `include_router` in `service_api.py`, which is exactly the arrangement
        # this test exists to catch: dropping that one line would delete sixty
        # operations and raise nothing anywhere.
        #
        # `worker/snapshot`, `worker/calendar` and `security/posts` were added on
        # 2026-08-10, and their absence is worth naming rather than quietly
        # fixing: this list said "four routers" while eight were mounted, so the
        # three newest were covered only by the aggregate's own line. A
        # parametrised list is only as good as its last update.
        "/api/v1/service-providers/me",
        "/api/v1/worker/communities",
        "/api/v1/worker/snapshot",
        "/api/v1/worker/calendar",
        "/api/v1/departments/{department_id}/candidates",
        "/api/v1/conversations",
        "/api/v1/work-orders/{work_order_id}",
        "/api/v1/complaints/{complaint_id}/schedule-request",
        "/api/v1/security/posts",
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
        # `/api/v1/complaints` was on this list and came back in `0031`. The
        # retirement was correct for what it retired: an *admin* complaint list,
        # duplicating what `GET /dashboard/snapshot` already projects. The
        # resident has no snapshot to read it from -- which is finding 3.1 in a
        # second table -- so the path now serves a projection that never existed
        # rather than the one that was removed. Deleting this line is the
        # decision the docstring below asks for.
        #
        # `/api/v1/complaint-categories` came back in `0048`, and this is that
        # decision made a second time. Its retirement reason (audit line 72) was
        # a statement about two screens: "CreateDepartment.jsx collects
        # categories as free-text inputs, not from a vocabulary, and
        # Departments.jsx reads department.categories off the department.
        # Nothing fetches a category list." **Both halves have since expired.**
        # CreateDepartment.jsx was deleted in 38927e5, and the department form's
        # category box is now a combobox whose whole job is to stop somebody
        # inventing "Plumbling" beside "Plumbing" -- which it cannot do without
        # the list. The new path is also not the old one: it carries each
        # category's linked skill, so the form can show the categories that
        # match no trade and therefore reach no service person in any hiring
        # search. That projection never existed before.
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
