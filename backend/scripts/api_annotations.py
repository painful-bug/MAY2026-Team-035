"""Per-operation annotations applied to the generated OpenAPI document.

FastAPI infers everything it can from the code: paths, schemas, status codes on
success. Three things it cannot infer, and which the submission requires, live
here instead:

1. **Error responses.** Handlers raise :class:`~app.core.exceptions.AppError`
   subclasses from deep inside the service layer, so no signature carries them.
2. **User-story traceability.** ``docs/product/USER_STORIES.md`` is a document,
   not a type.
3. **Descriptions for handlers with no docstring.**

Why a table rather than ``responses=`` on each route
----------------------------------------------------
Roughly half these operations belong to the other workstream's routers -- auth,
access requests, communities, onboarding, invitations, and the amenity CRUD in
``dashboard.py``. Editing those files is not ours to do. A single table keeps
every operation annotated the same way, in one reviewable place, instead of
half-decorated routes and half-something-else.

The cost is that the table can drift from the code. ``export_openapi.py``
removes the risk by refusing to build if a key here does not match a live
operation, or if a live operation is missing from ``OPERATIONS``. Adding an
endpoint therefore fails the export until its stories and errors are declared,
which is the behaviour we want: the traceability matrix cannot silently rot.

Error codes were derived by walking each handler into its services and
repositories and collecting every ``raise`` reachable from it, then verified by
hand. Two corrections came out of that pass and are marked ``# verified`` below.
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------
# The error envelope. Documented here; *defined* in app/core/exceptions.py.
# --------------------------------------------------------------------------
# ``ErrorResponse``/``ErrorBody``/``ErrorDetail`` are real pydantic models as of
# cfe803c, so FastAPI generates the schemas and this file must not restate them:
# a second, hand-written definition is exactly the kind of thing that drifts.
# What a model cannot carry is prose, so only descriptions are contributed, and
# only where the generated schema has none.
#
# Every handler registered by ``register_exception_handlers`` -- AppError,
# RequestValidationError, StarletteHTTPException and the bare Exception
# catch-all -- returns this one shape.

ERROR_SCHEMA_DOCS: dict[str, dict[str, Any]] = {
    "ErrorResponse": {
        "": (
            "The single error envelope for this API. Every failure -- expected, "
            "framework-raised or unhandled -- arrives in this shape, so a client "
            "can parse errors with one branch."
        ),
    },
    "ErrorBody": {
        "code": (
            "Stable, machine-readable identifier. Clients should branch on this, "
            "never on `message`, which is prose and may be reworded."
        ),
        "message": "Human-readable and safe to show to the caller.",
        "details": "Field-level failures. Only `request_validation_error` sets this.",
    },
    "ErrorDetail": {
        "": "One field-level failure, present only on validation errors.",
        "field": "Dotted path to the offending field, e.g. `body.email`.",
        "message": "What is wrong with it.",
    },
}


def _response(description: str, code: str, message: str, details: bool = False) -> dict:
    example: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        example["error"]["details"] = [
            {"field": "body.email", "message": "value is not a valid email address"}
        ]
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                "example": example,
            }
        },
    }


ERROR_RESPONSES: dict[str, dict] = {
    "Unauthorized": _response(
        "No credentials, or credentials that no longer verify. The caller should "
        "refresh the session and retry once, then sign in again.",
        "authentication_error",
        "Missing bearer token.",
    ),
    "Forbidden": _response(
        "Authenticated, but not permitted. Three distinct causes share this "
        "status: the community role is insufficient (`community_role_required`), "
        "there is no active membership (`active_membership_required`), or the "
        "CSRF pair failed (`csrf_invalid`, `csrf_origin_invalid`). Retrying "
        "helps only in the last case, and only after re-fetching `GET /auth/csrf`.",
        "community_role_required",
        "You do not have permission for this community action.",
    ),
    "NotFound": _response(
        "The addressed resource does not exist, or is not visible to this caller "
        "-- the two are deliberately indistinguishable, so that a 404 never "
        "confirms the existence of another community's data.",
        "not_found",
        "Department not found.",
    ),
    "Conflict": _response(
        "The request is well-formed but disagrees with current state: a duplicate, "
        "or a transition the resource's status does not allow. Retrying without "
        "changing something will fail identically.",
        "conflict",
        "That member is already an administrator.",
    ),
    "UnprocessableEntity": _response(
        "The request could not be validated. `request_validation_error` is a "
        "schema failure and carries `details[]`; every other code here is a "
        "business rule that a well-typed request can still break.",
        "request_validation_error",
        "The request could not be validated.",
        details=True,
    ),
    "InternalServerError": _response(
        "An unhandled exception. Logged in full server-side and deliberately "
        "opaque here: no message, stack or query ever reaches the caller.",
        "internal_error",
        "An unexpected error occurred.",
    ),
    "ServiceUnavailable": _response(
        "A dependency this call needs -- Supabase Auth, or a Postgres object that "
        "has not been provisioned -- did not answer. Transient; retry with backoff.",
        "service_unavailable",
        "The authentication provider did not respond in time. Please try again.",
    ),
}

STATUS_TO_RESPONSE = {
    "401": "Unauthorized",
    "403": "Forbidden",
    "404": "NotFound",
    "409": "Conflict",
    "422": "UnprocessableEntity",
    "500": "InternalServerError",
    "503": "ServiceUnavailable",
}

# --------------------------------------------------------------------------
# User stories. Titles and coverage verdicts come from docs/API.md section 14,
# which is the working copy; docs/product/USER_STORIES.md is the team's source.
# --------------------------------------------------------------------------

STORIES: dict[str, tuple[str, str]] = {
    "US-1.1": ("Partial cancellation of multi-day bookings", "served"),
    "US-1.2": ("Auto-sync cancellations to accounts", "served"),
    "US-1.3": ("Real-time sync across modules", "partial"),
    "US-1.4": ("Streamlined resident information update", "partial"),
    "US-1.5": ("Simplified booking management workflow", "served"),
    "US-1.6": ("Automated administrative reports", "partial"),
    "US-2.1": ("Reliable visitor approval notifications", "partial"),
    "US-2.2": ("Fast visitor pre-approval", "partial"),
    "US-2.4": ("Reliable notifications for society notices", "partial"),
    "US-2.6": ("Complaint status tracking with history", "partial"),
    "US-2.7": ("Complaint lifecycle notifications", "partial"),
    "US-2.8": ("Complaint accountability", "partial"),
    "US-2.9": ("Verified management contact directory", "partial"),
    "US-2.12": ("Reliable booking payment confirmation", "partial"),
}

# Operations that trace to no story, by group, as ``(api type, rationale)``.
#
# The classification answers "what sort of API is this, if not a story?", which
# is the question an untraced row otherwise leaves open. The vocabulary is
# deliberately small:
#
#   Feature        -- user-facing capability somebody asked for, just not in a
#                     written story.
#   Functional     -- required for the product to function at all; no user would
#                     think to request it.
#   Configuration  -- sets behaviour other operations then obey.
#   Master data    -- maintains the reference data features operate on.
#   Non-functional -- serves operators and infrastructure, not users.
#
# Section 14.6 of docs/API.md argues why untraced operations are expected rather
# than a defect: the team wrote stories about pain points in an existing
# product, not about the plumbing every product needs.
NO_STORY = {
    "auth": (
        "Functional",
        "Authentication and session management. Nobody writes a user story about"
        " signing in until it breaks.",
    ),
    "join": (
        "Feature",
        "Joining a community, and the admin review of those requests; the"
        " interviews were with people already in one.",
    ),
    "found": (
        "Feature",
        "Founding a community and finding one to found against -- a"
        " once-per-community act no resident story reaches.",
    ),
    "config": (
        "Configuration",
        "Sets behaviour other features then obey, rather than being a feature the"
        " stories name.",
    ),
    "catalogue": (
        "Master data",
        "Amenity catalogue upkeep. The booking stories assume amenities already"
        " exist; something still has to create them.",
    ),
    "platform": (
        "Non-functional",
        "Platform liveness for operators and orchestrators, deliberately outside"
        " /api/v1.",
    ),
}

# The exact phrase required on every untraced operation.
NO_STORY_STATUS = "Not covered by user story"


def op(
    *,
    errors: list[str],
    stories: list[tuple[str, str]] | None = None,
    no_story: tuple[str, str] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """One row of the table.

    ``errors`` are status codes reachable on this operation. ``stories`` pairs a
    story id with the role this specific operation plays in it -- the pairing is
    what makes the extension worth reading; a bare list of ids would not say why.
    ``no_story`` is the ``(api type, rationale)`` pair required of an operation
    that traces to nothing; see :data:`NO_STORY`.
    """
    return {
        "errors": errors,
        "stories": stories or [],
        "no_story": no_story,
        "description": description,
    }


# --------------------------------------------------------------------------
# Parameters. Keyed by name, because these names mean the same thing wherever
# they appear; the few that do not are listed in PARAMETER_OVERRIDES. A
# parameter that already carries a description from its `Query(...)` keeps it.
# --------------------------------------------------------------------------

PARAMETER_DESCRIPTIONS: dict[str, str] = {
    # path
    "amenity_id": (
        "Amenity id. Must belong to the caller's community, or the answer is 404."
    ),
    "complaint_id": "Complaint id, scoped to the caller's community.",
    "department_id": "Department id, scoped to the caller's community.",
    "invoice_id": "Invoice id, scoped to the caller's community.",
    "occurrence_id": (
        "A single booked day. Not the booking -- see `seriesId` for the whole "
        "request."
    ),
    "provider": (
        "OAuth provider key. Must be in the deployment's enabled set, or the answer "
        "is 422."
    ),
    "request_id": "Access-request id.",
    "series_id": (
        "Booking request id, covering every day the resident asked for at once."
    ),
    "staff_id": (
        "Staff assignment id. Must belong to `departmentId`, or the answer is 422."
    ),
    # query
    "page": "1-based page number.",
    "pageSize": "Rows per page. The maximum differs per endpoint; see the schema.",
    "q": "Free-text search. Matching is case-insensitive and substring-based.",
    "date": (
        "Restrict to a single day (`YYYY-MM-DD`). Mutually exclusive with "
        "`from`/`to`."
    ),
    "from": "Start of an inclusive date range (`YYYY-MM-DD`).",
    "to": "End of an inclusive date range (`YYYY-MM-DD`).",
    "startDate": "Start of the reporting window (`YYYY-MM-DD`), inclusive.",
    "endDate": "End of the reporting window (`YYYY-MM-DD`), inclusive.",
    "amenityId": "Restrict the report to one amenity. Omit for all of them.",
    "bookingStatus": "Restrict the report to one booking status. Omit for all of them.",
    "next": (
        "Path to return to after sign-in. Validated, not sanitised: anything "
        "absolute or off-site is rejected outright, so this cannot be used as "
        "an open redirect."
    ),
    "code": (
        "Authorization code returned by the provider. Absent means the user declined."
    ),
}

PARAMETER_OVERRIDES: dict[tuple[str, str, str], str] = {
    ("get", "/api/v1/admin/access-requests", "status"): (
        "Queue to show: `pending`, `approved`, `rejected` or `withdrawn`. "
        "Anything else is 422 rather than an empty page."
    ),
    ("get", "/api/v1/admin/access-requests", "limit"): (
        "Maximum rows to return (1-100)."
    ),
    ("get", "/api/v1/communities/search", "limit"): "Maximum matches to return (1-20).",
    ("get", "/api/v1/communities/search", "q"): (
        "Community name fragment, 2-100 characters. Shorter than two is 422: "
        "a one-character search would return most of the directory."
    ),
}


# --------------------------------------------------------------------------
# The table. Keyed (method, path) on the full path as mounted.
# --------------------------------------------------------------------------

OPERATIONS: dict[tuple[str, str], dict[str, Any]] = {
    # -- system ------------------------------------------------------------
    ("get", "/health"): op(
        errors=["500"],
        no_story=NO_STORY["platform"],
    ),
    # -- auth --------------------------------------------------------------
    ("get", "/api/v1/auth/methods"): op(
        errors=["500"],
        no_story=NO_STORY["auth"],
        description=(
            "List the sign-in methods this deployment has enabled.\n\n"
            "Unauthenticated, and the only cacheable endpoint in the API: it "
            "returns an `ETag` with `Cache-Control: public, max-age=300`, and "
            "answers **304** to a matching `If-None-Match`. The sign-in screen "
            "calls this before rendering, so that a disabled provider is never "
            "offered as a button that cannot work."
        ),
    ),
    ("get", "/api/v1/auth/csrf"): op(
        errors=["500"],
        no_story=NO_STORY["auth"],
        description=(
            "Issue the pre-authentication CSRF cookie.\n\n"
            "Call once before any unauthenticated write. Sign-up, sign-in, "
            "password reset and invitation preparation all reject a request "
            "whose `X-CSRF-Token` header does not match this cookie, so skipping "
            "this step turns every one of them into a **403**."
        ),
    ),
    ("get", "/api/v1/auth/oauth/{provider}/start"): op(
        errors=["422", "500"],
        no_story=NO_STORY["auth"],
        description=(
            "Begin an OAuth sign-in. Answers **307** to the provider's consent "
            "screen.\n\n"
            "A signed, five-minute transaction cookie carries the PKCE verifier "
            "and the return path across the round trip. `next` is validated "
            "before it is stored -- an absolute or off-site value is rejected "
            "rather than sanitised, so this cannot be turned into an open "
            "redirect. A provider not in the enabled set is **422**, not 404: "
            "the route exists, the configuration does not permit it."
        ),
    ),
    ("get", "/api/v1/auth/oauth/{provider}/callback"): op(
        errors=["401", "404", "422", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Complete an OAuth sign-in and answer **307** to the stored return "
            "path.\n\n"
            "Exchanges the authorization code against the verifier from the "
            "transaction cookie, establishes the session cookies, and clears the "
            "transaction. A missing code, an expired transaction cookie or a "
            "verifier mismatch is **401** -- the exchange is the authentication."
        ),
    ),
    ("get", "/api/v1/auth/google/start"): op(
        errors=["422", "500"],
        no_story=NO_STORY["auth"],
        description=(
            "Compatibility alias for `GET /auth/oauth/google/start`.\n\n"
            "Kept because it is registered as a redirect URI with Google and "
            "exists in shipped bookmarks; it delegates to the generic route and "
            "behaves identically. Prefer the generic form in new clients."
        ),
    ),
    ("get", "/api/v1/auth/google/callback"): op(
        errors=["401", "404", "422", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Compatibility alias for `GET /auth/oauth/google/callback`.\n\n"
            "Registered with Google as a redirect URI, which is why it cannot "
            "simply be removed. Delegates to the generic route."
        ),
    ),
    ("post", "/api/v1/auth/password/sign-up"): op(
        errors=["401", "403", "422", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Create an email and password account.\n\n"
            "The response is **deliberately identical** whether or not the "
            "address is already registered -- *\"If the account can be created, "
            "check your email\"* -- so this endpoint cannot be used to enumerate "
            "accounts. A CAPTCHA token is required when `AUTH_CAPTCHA_ENABLED`. "
            "No session is established; the address must be confirmed first."
        ),
    ),
    ("post", "/api/v1/auth/password/sign-in"): op(
        errors=["401", "403", "404", "422", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Sign in with email and password, establishing the session cookies.\n\n"
            "Wrong password and unknown address both answer **401** with the same "
            "message, for the same anti-enumeration reason as sign-up. The access "
            "and refresh tokens are set as `HttpOnly` cookies and are never "
            "returned in the body."
        ),
    ),
    ("post", "/api/v1/auth/email/verify"): op(
        errors=["401", "403", "404", "422", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Exchange a token from a confirmation email for a session.\n\n"
            "`verificationType` must be `email` or `signup`; anything else is "
            "**422** before the provider is called. A consumed or expired token "
            "is **401**. On success the session cookies are established, so a "
            "confirmed user lands signed in."
        ),
    ),
    ("post", "/api/v1/auth/email/resend"): op(
        errors=["403", "500"],
        no_story=NO_STORY["auth"],
        description=(
            "Accepted, and always answered identically.\n\n"
            "**This endpoint does not currently send anything.** Supabase exposes "
            "no standalone resend primitive that is safe to call through this "
            "backend-for-frontend, so rather than leak whether an unconfirmed "
            "account exists, it returns the neutral message unconditionally. "
            "Retrying sign-up re-sends the confirmation. Documented as-is because "
            "a client that believes this delivers mail will wait forever."
        ),
    ),
    ("post", "/api/v1/auth/password/reset/request"): op(
        errors=["403", "422", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Send a password recovery email.\n\n"
            "Answers the same neutral message for a known and an unknown address. "
            "A CAPTCHA token is required when `AUTH_CAPTCHA_ENABLED`."
        ),
    ),
    ("post", "/api/v1/auth/password/reset/verify"): op(
        errors=["401", "403", "404", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Exchange a recovery token for a short-lived **recovery** session.\n\n"
            "The cookies this sets are separate from the normal session pair and "
            "authorise exactly one thing: `POST /auth/password/reset/complete`. "
            "Verifying a recovery link therefore does not sign the caller in."
        ),
    ),
    ("post", "/api/v1/auth/password/reset/complete"): op(
        errors=["401", "403", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Set a new password using the recovery session, then clear it.\n\n"
            "Requires the recovery cookies from `reset/verify`; without them the "
            "answer is **401** and the caller must request a fresh link. On "
            "success every session cookie is cleared, so the user signs in again "
            "with the new password -- a password change should not leave an old "
            "session alive."
        ),
    ),
    ("get", "/api/v1/auth/session"): op(
        errors=["401", "404", "500"],
        no_story=NO_STORY["auth"],
        description=(
            "Return the caller's profile, memberships and active community.\n\n"
            "The first call a signed-in client makes: it decides which community "
            "context the rest of the API will resolve, and whether the caller has "
            "a membership at all. A verified token whose profile row is missing "
            "is **404**, not 401 -- the credential is good, the record is not."
        ),
    ),
    ("post", "/api/v1/auth/refresh"): op(
        errors=["401", "403", "404", "500", "503"],
        no_story=NO_STORY["auth"],
        description=(
            "Rotate the session from the refresh cookie.\n\n"
            "Takes no body: the refresh token is read from its `HttpOnly` cookie "
            "and never travels through JavaScript. Absent or rejected, the answer "
            "is **401** and the client must sign in again."
        ),
    ),
    ("post", "/api/v1/auth/logout"): op(
        # verified: the handler catches AuthenticationError and
        # ServiceUnavailableError from revoke_session and proceeds, so neither
        # 401 nor 503 can reach the caller. The static walk reported 503.
        errors=["403", "500"],
        no_story=NO_STORY["auth"],
        description=(
            "Revoke the session and clear every session cookie.\n\n"
            "**Cannot fail because the provider failed.** Revocation is attempted "
            "and its errors are swallowed, then the cookies are cleared "
            "regardless -- a logout that leaves the browser holding a session "
            "because Supabase timed out is worse than an unrevoked server-side "
            "token. Only the CSRF guard can refuse this call."
        ),
    ),
    # -- access requests ---------------------------------------------------
    ("post", "/api/v1/access-requests"): op(
        errors=["401", "403", "404", "409", "422", "500"],
        no_story=NO_STORY["join"],
        description=(
            "Apply to join a community. Answers **201**.\n\n"
            "Four distinct refusals, deliberately separated: an unknown community "
            "is **404**; already being a member, or already having a request "
            "pending, is **409**; a rejected application inside the cool-off "
            "window is **409**; and a unit that belongs to a different community "
            "is **422**, because the request is coherent but the pairing is not."
        ),
    ),
    ("get", "/api/v1/access-requests/mine"): op(
        errors=["401", "500"],
        no_story=NO_STORY["join"],
        description=(
            "List the caller's own join requests and their current status.\n\n"
            "Scoped to the caller by identity rather than by a parameter, so "
            "there is nothing here to tamper with."
        ),
    ),
    ("post", "/api/v1/access-requests/{request_id}/withdraw"): op(
        errors=["401", "403", "409", "500"],
        no_story=NO_STORY["join"],
        description=(
            "Withdraw a pending request.\n\n"
            "Only a request still pending can be withdrawn; anything already "
            "decided is **409**. Withdrawal is a status transition, not a "
            "deletion, so the community's audit trail keeps the attempt."
        ),
    ),
    ("get", "/api/v1/admin/access-requests"): op(
        errors=["401", "403", "500"],
        no_story=NO_STORY["join"],
        description=(
            "The administrator's review queue for the caller's community.\n\n"
            "`status` defaults to `pending`, which is the screen's default view; "
            "`limit` is capped at 100. Both are validated by pattern and range, "
            "so a bad filter is **422** rather than a silent empty page."
        ),
    ),
    ("post", "/api/v1/admin/access-requests/{request_id}/approve"): op(
        errors=["401", "403", "404", "409", "500"],
        no_story=NO_STORY["join"],
        description=(
            "Approve a join request, creating the membership.\n\n"
            "Approving a request that is not pending is **409** -- which is what "
            "two administrators clicking the same row a second apart will get, "
            "and the reason the second one is not silently ignored."
        ),
    ),
    ("post", "/api/v1/admin/access-requests/{request_id}/reject"): op(
        errors=["401", "403", "404", "409", "500"],
        no_story=NO_STORY["join"],
        description=(
            "Reject a join request, with a reason recorded against it.\n\n"
            "The applicant may apply again after the cool-off window; see "
            "`POST /access-requests`, which enforces it."
        ),
    ),
    ("post", "/api/v1/admin/access-requests/{request_id}/blacklist"): op(
        errors=["401", "403", "404", "409", "500"],
        no_story=NO_STORY["join"],
        description=(
            "Reject a request and bar the applicant from re-applying.\n\n"
            "The difference from `reject` is only the cool-off: a blacklisted "
            "applicant has no expiry to wait out."
        ),
    ),
    # -- invitations -------------------------------------------------------
    ("post", "/api/v1/admin/invitations"): op(
        errors=["401", "403", "422", "500"],
        no_story=NO_STORY["join"],
        description=(
            "Issue a resident invitation, returning its code and link.\n\n"
            "The invite is bound to the email address given here. Redemption "
            "later checks that the Google identity signing in matches it, which "
            "is why the address is required rather than optional."
        ),
    ),
    ("post", "/api/v1/invitations/prepare"): op(
        errors=["403", "422", "500"],
        no_story=NO_STORY["join"],
        description=(
            "Resolve an invitation link or code and stage it for redemption.\n\n"
            "Unauthenticated by design -- the recipient has not signed in yet. "
            "Accepts exactly one of `token` or `code`; both or neither is "
            "**422**. On success the invitation id is stored in a signed "
            "five-minute cookie, so the id never crosses the browser in a form "
            "the recipient could edit before `redeem`."
        ),
    ),
    ("post", "/api/v1/invitations/redeem"): op(
        errors=["401", "403", "409", "422", "500"],
        no_story=NO_STORY["join"],
        description=(
            "Redeem the staged invitation for the signed-in Google identity.\n\n"
            "Requires **both** factors: the signed cookie from `prepare` and a "
            "verified access token. The invitation token is a mandatory second "
            "factor and there is no path that redeems on identity alone. An "
            "invitation already used or revoked is **409**."
        ),
    ),
    # -- communities and onboarding ---------------------------------------
    ("get", "/api/v1/communities/search"): op(
        errors=["401", "422", "500", "503"],
        no_story=NO_STORY["found"],
        description=(
            "Search the public community directory by name.\n\n"
            "For a signed-in user who does not belong anywhere yet, so it is the "
            "one read that works without a membership. `q` must be 2-100 "
            "characters. **503** means the directory's search index is rebuilding "
            "-- transient, and distinguished from a genuine failure so the client "
            "can retry rather than report an error."
        ),
    ),
    ("get", "/api/v1/communities/admin/units"): op(
        errors=["401", "403", "500"],
        no_story=NO_STORY["found"],
        description=(
            "List the units in the caller's community, for pickers.\n\n"
            "Feeds the unit selector on the join-request and invitation screens; "
            "the ids returned here are the ones `POST /access-requests` accepts."
        ),
    ),
    ("post", "/api/v1/onboarding/community"): op(
        errors=["401", "403", "409", "500", "503"],
        no_story=NO_STORY["found"],
        description=(
            "Found a community and make the caller its first administrator.\n\n"
            "The bootstrap case: the only write that does not require an existing "
            "membership, because it creates one. Requires a verified Google "
            "identity. **409** if the community could not be created -- almost "
            "always a name collision; **503** if the registration path itself has "
            "not been provisioned."
        ),
    ),
    # -- dashboard ---------------------------------------------------------
    ("get", "/api/v1/dashboard/snapshot"): op(
        errors=["401", "403", "500"],
        stories=[
            (
                "US-1.3",
                "The authoritative re-read every SSE event asks the client to perform"
            ),
            (
                "US-1.4",
                "users[], complaints[], bookings[] and payments[] in one response -- "
                "the single-screen read"
            ),
            (
                "US-2.1",
                "visitors[], already scoped to the caller's own for a non-admin"
            ),
            (
                "US-2.2",
                "The read half of visitor pre-approval; no write endpoint exists yet"
            ),
            (
                "US-2.6",
                "complaints[] carries status, comments[] and history[], filtered to "
                "the caller's own"
            ),
        ],
    ),
    ("get", "/api/v1/dashboard/events"): op(
        errors=["401", "403", "500"],
        stories=[
            (
                "US-1.3",
                "Server-sent events; dashboard.refresh fires on writes to 12 tables"
            ),
        ],
    ),
    ("post", "/api/v1/dashboard/amenities"): op(
        errors=["401", "403", "404", "500"],
        no_story=NO_STORY["catalogue"],
        description=(
            "Create an amenity in the caller's community.\n\n"
            "Catalogue upkeep, not booking: this defines the thing that later "
            "gets booked through `/amenities/{amenityId}/bookings`."
        ),
    ),
    ("put", "/api/v1/dashboard/amenities/{amenity_id}"): op(
        errors=["401", "403", "404", "500"],
        no_story=NO_STORY["catalogue"],
        description=(
            "Replace an amenity's definition.\n\n"
            "A full replace, not a patch: every field the body omits is reset to "
            "its default. **404** if the amenity is not in the caller's community."
        ),
    ),
    ("delete", "/api/v1/dashboard/amenities/{amenity_id}"): op(
        errors=["401", "403", "404", "500"],
        no_story=NO_STORY["catalogue"],
        description=(
            "Remove an amenity from the catalogue.\n\n"
            "Returns the id that was removed. Existing bookings keep their "
            "ledger rows -- history stays attributable after the amenity itself "
            "is gone."
        ),
    ),
    # -- people ------------------------------------------------------------
    ("post", "/api/v1/admins"): op(
        errors=["401", "403", "404", "409", "500"],
        stories=[
            (
                "US-2.9",
                "Promotes an existing member, so the directory reflects who is "
                "actually in charge"
            ),
        ],
    ),
    # -- complaints --------------------------------------------------------
    ("patch", "/api/v1/complaints/{complaint_id}"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-2.6",
                "Writes the status and its timeline entries in one transaction, so a "
                "status cannot change without a trace"
            ),
            (
                "US-2.7",
                "Every transition the story names -- acknowledged, updated, "
                "reassigned, resolved -- writes a complaint_events row"
            ),
            (
                "US-2.8",
                "Accepts assignee and expectedResolutionAt; both are stored, and both "
                "are dropped by the snapshot projection before a resident sees them"
            ),
        ],
    ),
    ("post", "/api/v1/complaints/{complaint_id}/comments"): op(
        errors=["401", "403", "404", "500"],
        stories=[
            (
                "US-2.6",
                "A resident-visible comment joins the timeline; an internal one never "
                "does"
            ),
        ],
    ),
    # -- notices -----------------------------------------------------------
    ("post", "/api/v1/notices"): op(
        errors=["401", "403", "422", "500"],
        stories=[
            (
                "US-2.4",
                "Publishes immediately and fires the notices SSE trigger; nothing "
                "carries it to a resident who has not opened the app"
            ),
        ],
    ),
    # -- departments -------------------------------------------------------
    ("get", "/api/v1/departments"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-2.9",
                "The directory itself, with contact details, hours and the head"
            ),
        ],
    ),
    ("post", "/api/v1/departments"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[("US-2.9", "Keeping the directory current")],
    ),
    ("get", "/api/v1/departments/{department_id}"): op(
        errors=["401", "403", "404", "500"],
        stories=[("US-2.9", "One directory entry in full")],
    ),
    ("patch", "/api/v1/departments/{department_id}"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-2.9",
                "Designates the head, and corrects contact details as they change"
            ),
        ],
    ),
    ("delete", "/api/v1/departments/{department_id}"): op(
        errors=["401", "403", "404", "500"],
        stories=[
            (
                "US-2.9",
                "Deactivation rather than deletion, so past assignments stay "
                "attributable"
            ),
        ],
    ),
    ("put", "/api/v1/departments/{department_id}/staff"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[("US-2.9", "Replaces the roster wholesale")],
    ),
    ("post", "/api/v1/departments/{department_id}/staff"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-2.9",
                "Adds one person; membership_id stays null because staff have no "
                "login"
            ),
        ],
    ),
    ("patch", "/api/v1/departments/{department_id}/staff/{staff_id}"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[("US-2.9", "Corrects a roster entry's role or contact details")],
    ),
    ("delete", "/api/v1/departments/{department_id}/staff/{staff_id}"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[("US-2.9", "Removes a person from the roster")],
    ),
    # -- money -------------------------------------------------------------
    ("get", "/api/v1/billing-settings"): op(
        errors=["401", "403", "404", "500"],
        stories=[("US-1.6", "The rates every reported figure is derived from")],
    ),
    ("put", "/api/v1/billing-settings"): op(
        errors=["401", "403", "404", "422", "500"],
        no_story=NO_STORY["config"],
    ),
    ("post", "/api/v1/invoices"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-1.6",
                "Creates the maintenance billing rows the reports aggregate"
            ),
        ],
    ),
    ("post", "/api/v1/invoices/{invoice_id}/payments"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-2.12",
                "Payment and confirmation are one transaction, so money cannot be "
                "taken without the record moving with it"
            ),
        ],
    ),
    # -- amenities ---------------------------------------------------------
    ("get", "/api/v1/amenities/{amenity_id}/bookings"): op(
        errors=["401", "403", "404", "500"],
        stories=[("US-1.1", "The individual days an administrator chooses between")],
    ),
    ("post", "/api/v1/amenities/{amenity_id}/bookings"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-1.5",
                "An administrator books on a resident's behalf in one call, with no "
                "impersonation"
            ),
        ],
    ),
    ("post", "/api/v1/amenities/{amenity_id}/bookings/request"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-1.5",
                "The resident-initiated path into the same approval queue"
            ),
        ],
    ),
    ("post", "/api/v1/amenities/{amenity_id}/blocks"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-1.5",
                "Takes a slot out of circulation without inventing a fake booking"
            ),
        ],
    ),
    ("get", "/api/v1/amenities/{amenity_id}/approvals"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[("US-1.5", "The approval queue")],
    ),
    ("post", "/api/v1/amenity-bookings/{series_id}/approve"): op(
        errors=["401", "403", "404", "500"],
        stories=[
            (
                "US-1.5",
                "One decision per request rather than per day -- the redundant step "
                "the story asks to remove"
            ),
        ],
    ),
    ("post", "/api/v1/amenity-bookings/{series_id}/reject"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[("US-1.5", "The other half of one decision per request")],
    ),
    ("post", "/api/v1/amenity-bookings/cancel"): op(
        errors=["401", "403", "422", "500"],
        stories=[
            (
                "US-1.1",
                "Takes a list of occurrence ids rather than a booking id -- this "
                "story is the reason for that signature"
            ),
        ],
    ),
    ("post", "/api/v1/amenity-bookings/{occurrence_id}/force-cancel"): op(
        errors=["401", "403", "404", "500"],
        stories=[
            (
                "US-1.1",
                "The administrator override when the resident objects; the ledger "
                "records who"
            ),
        ],
    ),
    ("get", "/api/v1/amenities/{amenity_id}/ledger"): op(
        errors=["401", "403", "404", "500"],
        stories=[
            (
                "US-1.2",
                "cancellationHistory, refundHistory, auditTrail and paymentStatus, "
                "all derived from the event stream rather than stored"
            ),
            ("US-1.6", "Amenity billing, per booking"),
        ],
    ),
    ("get", "/api/v1/amenities/{amenity_id}/ledger/summary"): op(
        errors=["401", "403", "404", "500"],
        stories=[("US-1.2", "The money totals, derived the same way")],
    ),
    ("post", "/api/v1/amenity-bookings/{occurrence_id}/payments"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-2.12",
                "Records the payment against the booking in one transaction; "
                "paymentStatus is derived from the rows, never set alongside them"
            ),
        ],
    ),
    ("post", "/api/v1/amenity-bookings/{occurrence_id}/refund"): op(
        errors=["401", "403", "404", "500"],
        stories=[
            (
                "US-1.2",
                "Returns the deposit, and moves the booking off refund_pending"
            ),
        ],
    ),
    ("post", "/api/v1/amenity-bookings/{occurrence_id}/damage"): op(
        errors=["401", "403", "404", "500"],
        stories=[
            (
                "US-1.2",
                "Deducts damage from the deposit, on the same ledger the cancellation "
                "wrote to"
            ),
        ],
    ),
    ("post", "/api/v1/amenity-bookings/{occurrence_id}/charges"): op(
        errors=["401", "403", "404", "422", "500"],
        stories=[
            (
                "US-1.2",
                "Additional and late-cancellation charges, so the ledger reflects the "
                "full cost of a change"
            ),
        ],
    ),
    ("get", "/api/v1/amenity-reports"): op(
        errors=["401", "403", "404", "500"],
        stories=[
            (
                "US-1.6",
                "Rows plus six KPIs aggregated over every matching row, not the "
                "current page -- the whole reason this endpoint exists"
            ),
        ],
    ),
    # -- settings ----------------------------------------------------------
    ("get", "/api/v1/settings"): op(
        errors=["401", "403", "404", "500"],
        no_story=(
            NO_STORY["config"][0],
            NO_STORY["config"][1]
            + " Worth one exception, though: modules[].backendStatus reports which"
            " features are unimplemented, which makes it the only endpoint that"
            " describes this matrix's gaps in machine-readable form.",
        ),
    ),
    ("put", "/api/v1/settings"): op(
        errors=["401", "403", "404", "500"],
        no_story=NO_STORY["config"],
    ),
}
