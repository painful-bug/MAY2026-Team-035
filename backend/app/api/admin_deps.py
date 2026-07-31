"""Admin-dashboard dependencies, layered on top of ``app.api.deps``.

The admin workstream needs one thing the shared dependencies do not express:
"this caller must be the community's admin". Rather than edit ``app.api.deps``
— which the auth workstream owns — the guard is composed here from their
``require_membership_role``.

Why this replaced our own ``require_role``:

``require_role`` checked a ``role`` claim inside the identity JWT, which relied
on ``0003_access_token_hook.sql`` installing a ``custom_access_token_hook``.
That migration is gone from the baseline and the hook is never installed, so the
claim no longer exists and the check would have passed for everybody. Their
``require_membership_role`` resolves the role from ``community_memberships`` in
Postgres instead, which cannot be forged by a stale token.

Role values are the lowercase ``public.membership_role`` vocabulary
(``admin``/``resident``/…), not the uppercase ``Role`` enum our schemas render.
"""

from __future__ import annotations

from fastapi import Request

from app.api.deps import require_csrf, require_membership_role

#: Guard for endpoints only a community admin may call. Built once at import
#: time because ``require_membership_role`` returns a new closure per call and
#: FastAPI caches dependencies by identity.
require_admin = require_membership_role("admin")

#: Guard for endpoints an admin or a department manager may call.
require_admin_or_manager = require_membership_role("admin", "manager")


def require_csrf_unsafe(request: Request) -> None:
    """Apply ``require_csrf``, but only to state-changing methods.

    Needed because ``require_csrf`` rejects any request whose ``Origin`` (or
    ``Referer``) does not equal the configured frontend origin -- and **browsers do
    not send ``Origin`` on same-origin GET requests**. Declaring the raw guard at
    router level would therefore 403 every read on a mixed router.

    Gating on the method lets a whole router declare CSRF once and stay correct,
    and it matches what the frontend actually sends: ``lib/api/client.js`` attaches
    ``X-CSRF-Token`` for everything except GET, HEAD and OPTIONS.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    require_csrf(request)
