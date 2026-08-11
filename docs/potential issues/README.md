# Potential issues

Findings that are real, are nobody's current task, and would otherwise be forgotten. Each is written
so it can be **pasted straight into a new GitHub issue** — copy the title, the labels, and everything
under *Body*.

Nothing here is a guess. Every claim names the file and line it came from, and every entry carries a
**How to confirm** step you can run yourself rather than take on trust.

## Index

| # | Title | Kind | Urgency |
|---|---|---|---|
| 1 | [OAuth callback never checks which provider started the sign-in](#1-oauth-callback-never-checks-which-provider-started-the-sign-in) | Security (latent) | Before a second provider is enabled |
| 2 | [`roles.py` documents an RBAC model the code no longer uses](#2-rolespy-documents-an-rbac-model-the-code-no-longer-uses) | Correctness trap | **Resolved 2026-08-10** — see the note under its body |
| 3 | [No rate limiting on the guessable or mail-sending endpoints](#3-no-rate-limiting-on-the-guessable-or-mail-sending-endpoints) | Security | Before public launch |
| 4 | [No migration has ever been applied to any database](#4-no-migration-has-ever-been-applied-to-any-database) | Deployment blocker | Now |
| 5 | [Supabase email templates do not match our own setup document](#5-supabase-email-templates-do-not-match-our-own-setup-document) | Configuration | Now — it is half of #22 |
| 6 | [149 lint violations make a CI lint gate impossible](#6-149-lint-violations-make-a-ci-lint-gate-impossible) | Tech debt | Whenever the auth work settles |
| 7 | [Design docs outside `API.md` still describe phone/SMS OTP](#7-design-docs-outside-apimd-still-describe-phonesms-otp) | Doc drift | Low |
| 8 | [`/auth/*` speaks `snake_case`, everything else speaks `camelCase`](#8-auth-speaks-snake_case-everything-else-speaks-camelcase) | Consistency | Superseded in scope by 11 |
| 9 | [The resident portal is still a demo](09-resident-portal-is-still-a-demo.md) | Unfinished wiring | Before any demo involving a resident |
| 10 | [51 API operations have no frontend consumer](10-api-operations-with-no-frontend-consumer.md) | Inventory | Low as a defect, high as a planning input |
| 11 | [The naming contract in `API.md` §1.3 is wrong](11-snake-case-in-the-published-contract.md) | Doc defect | Low, but it is a contract giving a wrong answer |
| 12 | [Four notification parameters that no screen reads](12-notification-parameters-no-screen-reads.md) | Silent UX defect | Low each; they share a failure mode with no alarm on it |
| 13 | [Dead code in files this workstream does not own](13-dead-code-in-files-this-workstream-does-not-own.md) | Tech debt | Low — written down because nothing else will |
| 14 | [The manager has hiring permission and no hiring screen](14-the-manager-has-hiring-permission-and-no-hiring-screen.md) | Unreachable capability | **Resolved 2026-08-11** — the file records what the fix turned up, and the one part still open |

## Three vintages, and why they are stored differently

**1–8** came out of fixing [#22](https://github.com/painful-bug/MAY2026-Team-035/issues/22) and live
inline below, in the order they were written.

**9–11** came out of the end-to-end compatibility sweep of 2026-08-11 — a check of every persona's
path from auth through the resident, admin, guard, security-manager and worker portals — and each has
a file of its own, because each needed more than a screenful: an inventory, the contract it says is
wrong, and a link to that contract.

**12–13** came out of fixing something else on the same day, which is the usual way: correcting one
notification's deep link raised the question of how many others were half-corrected, and deleting one
dead function raised the question of how much else nothing reaches. Both are inventories with a
script behind them — `backend/tests/test_notification_links.py` and
`backend/scripts/dead_code_sweep.py` — so both can be re-derived rather than believed. Both also
stop at the ownership line: the entries are findings in other people's code, recorded rather than
changed.

**Two more findings from the same sweep are not here, because they were fixed instead.** They are
recorded in [`docs/CHANGE_LOG.md`](../CHANGE_LOG.md) and named here so the sweep's output can be
traced in full:

| Finding | What it was | Where the fix is |
|---|---|---|
| `/security-manager` was unreachable by any user the system can create | the portal predicate in `auth_service.py` required a `manager` membership, and nothing mints one — `gate_admin_community_for` (`0040:589`) had defined a security manager as a *ranked security* membership since the day it was written | `backend/app/services/auth_service.py` (`_portal_for`), `backend/tests/test_session_portal.py`, and [`docs/design/AUTH_AND_SESSION_DESIGN.md`](../design/AUTH_AND_SESSION_DESIGN.md) §5.4 |
| Four notification deep links resolved to the landing page | migrations `0032`, `0036`, `0037` and `0043` emitted `url` values naming routes that do not exist | the four migrations, plus `backend/tests/test_notification_links.py`, which now checks every emitted `url` against `App.jsx`'s route table |

---

## 1. OAuth callback never checks which provider started the sign-in

**Labels:** `security`, `backend`, `auth`

### Body

`GET /api/v1/auth/oauth/{provider}/callback` takes the provider from the **URL path**, but the signed
transaction cookie planted at the start of the flow carries only the PKCE verifier — not the provider
it was issued for. The callback then unconditionally exchanges the code through Google's exchange
function, whatever `{provider}` said.

```python
# backend/app/api/v1/routers/auth.py:117
async def oauth_callback(request: Request, provider: str, code: str | None = None):
    _require_enabled(provider)
    transaction = verify_payload(request.cookies.get(OAUTH_COOKIE))   # {"verifier": ...} only
    ...
    session = await _run_provider_operation(
        auth_service.exchange_google_code, code, str(transaction["verifier"])
    )
```

```python
# backend/app/services/auth_service.py:60
def start_oauth(provider: str) -> tuple[str, dict[str, str]]:
    if provider != "google":
        raise ValidationError("Unsupported authentication provider.", ...)
    return start_google_oauth()          # returns {"verifier": verifier}
```

**Why it matters.** Nothing is exploitable *today*, and that is exactly the problem — the reason it is
safe is an accident of configuration, not a check. `start_oauth` refuses every provider except
`google`, so path and cookie cannot currently disagree. The day someone adds a second provider to
`AUTH_ENABLED_METHODS`, a transaction begun at one provider can be completed at the URL of another,
and the code that would have caught it does not exist. A latent hole that opens on an unrelated
config change is worse than a visible one, because nobody will be looking at this file that day.

**How to confirm.** Read the two snippets above. `start_google_oauth` (`auth_service.py:35`) returns
`{"verifier": verifier}` and nothing else, so there is no provider for the callback to compare
against.

**Suggested fix.** Put the provider in the signed transaction and reject a mismatch:

```python
# start
set_transaction_cookie(response, OAUTH_COOKIE,
    sign_payload({**transaction, "provider": provider, "next": return_path}, ttl_seconds=300))

# callback
if transaction.get("provider") != provider:
    raise AuthenticationError("This sign-in did not start here.", code="oauth_provider_mismatch")
```

Then dispatch the exchange on the recorded provider rather than calling the Google one directly.
Add a route test that starts at one provider and calls back at another.

---

## 2. `roles.py` documents an RBAC model the code no longer uses

**Labels:** `backend`, `tech-debt`, `documentation`

> **Resolved 2026-08-10** (Phase 2 Step 2 dead-code sweep): the first suggested
> fix, with one amendment discovered while doing it — `Role` itself is **not**
> dead. `memberships_repository.py` and `invitations_repository.py` import it
> as the typed name for the enum values, so the sweep deleted the hierarchy
> (`_IMPLIED_ROLES`, `effective_roles`, `role_satisfies`, `satisfies_any`,
> `parse_role`) and `tests/test_roles.py`, kept `Role` and `display_role`, and
> rewrote the docstring to say what the guards actually are. Original text kept
> below for the record.

### Body

`backend/app/domain/roles.py` opens by describing itself as live infrastructure:

> The five roles mirror the `user_role` Postgres enum (see `supabase/migrations/0001_init.sql`) and
> the `user_role` claim injected into every access token by the custom access-token hook.
> […] `role_satisfies` is the single source of truth for "does this role meet this requirement" and
> is used by both the API guards and the tests.

**Every clause of that is now false:**

| Claim | Reality |
|---|---|
| `supabase/migrations/0001_init.sql` | Does not exist. The baseline is `0001_baseline.sql` |
| the `user_role` Postgres enum | The string `user_role` appears **zero** times in the baseline |
| the claim injected into every access token | `decode_token` (`core/security.py:26`) reads no role claim at all |
| used by both the API guards and the tests | Used by `tests/test_roles.py` and nothing else |

Authorization actually resolves from the caller's active `community_memberships` row, via
`get_active_membership` and `require_membership_role` in `backend/app/api/deps.py`, and those match
role strings **exactly** — an `ADMIN` does *not* satisfy a `resident` guard, despite what
`role_satisfies` says.

**Why it matters.** This is a trap, not just dead code. It is the file you would open to answer "can
an admin use a resident endpoint?", and it gives a confident, wrong answer, complete with a
hierarchy diagram. Someone will eventually wire `role_satisfies` back into a guard on the strength of
that docstring and quietly widen access.

**How to confirm.**

```bash
grep -rn "role_satisfies\|effective_roles\|satisfies_any" backend --include=*.py
ls backend/supabase/migrations/0001_init.sql
grep -c user_role backend/supabase/migrations/0001_baseline.sql
```

**Suggested fix.** Pick one and commit to it:

- **Delete** `Role`, `_IMPLIED_ROLES`, `effective_roles`, `role_satisfies`, `satisfies_any` and
  `parse_role` along with `test_roles.py`, keeping only `display_role` (the one function with real
  callers, in `people_service.py:64`); **or**
- **Keep and correct**, if the hierarchy is still the intended model — rewrite the docstring to say
  it is a proposal that no guard consults, and open a separate issue to actually adopt it.

Either way `docs/API.md` §1.2 now describes the real behaviour and should stay the reference.

---

## 3. No rate limiting on the guessable or mail-sending endpoints

**Labels:** `security`, `backend`

### Body

No endpoint in the service is rate-limited. Four unauthenticated ones deserve it most:

| Endpoint | Why |
|---|---|
| `POST /api/v1/auth/password/sign-in` | Password guessing |
| `POST /api/v1/invitations/prepare` | Takes an invite token **and** a short code — both guessable in principle, and a hit grants community access |
| `POST /api/v1/auth/email/resend` | Sends mail on every call |
| `POST /api/v1/auth/password/reset/request` | Sends mail on every call |

The last two are the cheapest abuse available: each request costs the project a real email, and both
deliberately answer identically whether or not the address exists, so there is no natural brake.

**Why it matters.** Supabase applies its own limits to the underlying GoTrue calls, which is a
backstop, not a design — it protects Supabase's quota, not this service, and it cannot see the
`/invitations/prepare` guessing loop at all because that never reaches GoTrue.

**How to confirm.**

```bash
grep -rniE "ratelimit|rate_limit|slowapi|Retry-After" backend/app --include=*.py
```

Returns nothing. (Search for `limiter` alone and you will match the word *delimiters* in three
repository comments — there is no limiter.)

**Suggested fix.** Per-IP and per-target-address limits on those four routes, returning `429` with
`Retry-After` in the standard error envelope. `docs/API.md` §1.8 already documents the intended
response shape, so the contract is settled — only the implementation is missing.

---

## 4. No migration has ever been applied to any database

**Labels:** `blocker`, `database`, `deployment`

### Body

`backend/supabase/migrations/` holds **37 files** — `0001_baseline.sql` through
`0047_security_roster.sql`, plus six timestamped ones from the auth workstream. **None of them has
been run against any environment, including `0001`.**

> **Recounted 2026-08-11.** This said 22 files, `0001` through `0032`, when it was written on
> 2026-08-10. Fifteen have landed since: the resident money and home surfaces, service providers,
> hiring, work orders, the dispatch engine, conversations, gate operations, person-addressed
> notifications, departures, direct messages and the security roster. Every one of them is unapplied
> too, so the finding did not change — only its size did. Which is the argument for the finding: the
> longer this stays open the more there is to go wrong on the first run, and it goes wrong all at once.

**Why it matters.** Every "this endpoint works" claim in the repository currently means "the SQL it
needs exists in a file". A static check confirms every RPC and column the repositories reference is
created by *some* migration, which catches typos and nothing else. Ordering conflicts, permission
errors, failed constraint validation on existing rows and RLS mistakes are all invisible until the
first real `supabase db push` — and they will surface as a wall of failures at once, in whatever
environment goes first.

**Why it is still open.** Applying migrations needs Supabase credentials, which is a deliberate
human step and not one that should be automated from a dev machine.

**Suggested fix.** Apply them to a scratch project first, in order, capturing the output; run the
Supabase database advisors afterwards; then repeat against staging. Record the result — the honest
outcome of that first run is more valuable than any further static checking.

---

## 5. Supabase email templates do not match our own setup document

**Labels:** `configuration`, `auth`, `blocker`

### Body

This is the configuration half of #22, split out because it is nobody's code change.

`docs/SUPABASE_AUTH_SETUP.md` step 3 already specifies the required confirmation template:

```
https://<frontend>/auth/confirm-email?token_hash={{ .TokenHash }}&type=signup
```

The project is still on GoTrue's default `{{ .ConfirmationURL }}`, which routes through
`/auth/v1/verify` and lands on the confirmation page with **no `token_hash` to spend** — which is why
the **Confirm email** button appeared disabled. Recovery (`/auth/reset-password`, `type=recovery`)
needs the same treatment.

**Why it matters.** The document is right and the project does not match it. Any future reader
comparing the two will believe the flow works.

**Where to change it.** Supabase dashboard → **Authentication → Email Templates**, then verify
**Authentication → URL Configuration** lists both frontend redirect URLs exactly.

**How to confirm afterwards.** Register a fresh account, open the email, and check the link's query
string contains `token_hash=`. The confirmation page should show an active button.

> The frontend no longer fails silently if this is wrong — it now explains the missing token and
> offers to resend — but that is a safety net, not a substitute for the correct template.

---

## 6. 149 lint violations make a CI lint gate impossible

**Labels:** `tech-debt`, `backend`, `tooling`

> **Recounted 2026-08-11: 153.** The figures below are as of the day this was written and the
> distribution has not changed shape — the growth is `E501` in files added since. The point is the
> same at either number, and it is the point rather than the count that decides anything: the
> baseline is non-zero, so no *new* violation can be caught either.

### Body

`ruff check .` in `backend/` reports **149 errors**:

| Rule | Count | Meaning |
|---|---|---|
| `E501` | 136 | Line longer than 88 characters |
| `I001` | 8 | Unsorted import block |
| `N815` | 4 | mixedCase attribute in a class scope |
| `F401` | 1 | `get_user_client` imported but unused in `auth_service.py` |

They are concentrated in seven files, all from the authentication and registration workstream:

```
48  app/api/v1/routers/auth.py
24  app/services/auth_service.py
15  app/services/invitation_service.py
15  app/core/web_session.py
11  app/api/v1/routers/invitations.py
10  app/services/access_request_service.py
 7  tests/test_registration_contracts.py
```

**Why it matters.** Not the line lengths themselves — it is that nobody can add `ruff check` to CI
while the baseline is non-zero, so no *new* violation can ever be caught either. `I001` and `F401`
are auto-fixable and the `N815` cases are deliberate (they mirror the frontend's camelCase wire
format), so the real decision is only about `E501`.

**How to confirm.**

```bash
cd backend && ruff check --statistics .
```

**Suggested fix.** One mechanical commit, no behaviour change: `ruff check --fix` for the 9 fixable
ones, wrap the long lines, add `# noqa: N815` with a one-line reason to the four intentional ones,
then add `ruff check .` to CI so the count cannot climb back. Best done when the auth workstream is
between changes, since it touches their files broadly.

---

## 7. Design docs outside `API.md` still describe phone/SMS OTP

**Labels:** `documentation`

### Body

`docs/API.md` has been brought in line with what the code does — Google OAuth plus email/password,
no OTP anywhere. Other documents were not, and still describe the abandoned design as current:

- `docs/plans/BACKEND_PLAN.md` — lines 79, 747, 759 and 902 describe `sign_in_with_otp` / `verify_otp`, a
  `POST /auth/otp/verify` endpoint, and a `SupabaseOtpProvider` marked **default**
- `docs/diagrams/HomeBandhu-Architecture-Classes.puml:220` — a `verify_otp()` method on a class

**Why it matters.** Lower stakes than the rest of this list: these are planning documents, and a
reader who reaches `API.md` or `openapi.yaml` gets the truth. But `BACKEND_PLAN.md` reads as a
current design rather than a historical one, and the class diagram is a submitted artifact.

**Suggested fix.** Cheapest honest option is a dated banner at the top of `BACKEND_PLAN.md` marking
the OTP sections superseded, with a pointer to `API.md` §3 — rewriting a long planning document to
match a design it predates has little value. The `.puml` method should just be renamed, since the
diagram is meant to reflect the built system.

---

## 8. `/auth/*` speaks `snake_case`, everything else speaks `camelCase`

**Labels:** `consistency`, `api`

> **Scope widened 2026-08-11.** The premise below — that the seam is auth-shaped — is wrong. The
> compatibility sweep counted **48** snake_case properties in the generated spec, and **28 of them
> are on surfaces that have nothing to do with auth**: community onboarding, access requests and the
> amenity admin write. The boundary is chronological, not functional.
> [Issue 11](11-snake-case-in-the-published-contract.md) has the full list and supersedes this
> entry's scope. The decision it asks for is still the decision below, taken across five surfaces
> rather than one.

### Body

| Endpoint group | Case | Example |
|---|---|---|
| `/auth/*`, `/admin/invitations` | `snake_case` | `token_hash`, `invitee_email`, `intended_unit_id` |
| Everything else | `camelCase` | `pageSize`, `timeAgo`, `unitId` |

Documented in `docs/API.md` §1.3 and known, but recorded here because it is a real cost every time
someone writes a client: the same request can need both conventions.

**Why it has not been fixed.** The React app reads camelCase throughout its seeded data and cannot
change; the auth DTOs predate that constraint and the frontend already reads *them* as snake_case. So
this is a coordinated two-sided change, not a rename — small, but not a drive-by.

**Suggested fix.** Decide deliberately, then do it in one commit across both sides: give the auth
schemas the same camelCase-emitting base model the rest use, and update the four frontend call sites
in `frontend/src/lib/auth/authService.js`. Or write down that the seam is permanent, and stop
re-litigating it.
