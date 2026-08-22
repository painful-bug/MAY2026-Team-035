# Phase 1 session-restoration evidence

Date: 2026-08-21
Branch: `performance/phase-1-session-restoration`

## Scope

This phase does not cache authentication, sessions, memberships, capabilities,
profiles, or authorization decisions. It reduces the authoritative session read
path and adds privacy-safe timing.

## Teammate reconciliation

- Fetched and pruned all remotes before implementation.
- Incorporated `origin/live-app-fixes@95a4ec9` (idle-session CSRF refresh) and
  added a regression test.
- Kept PR #36 (`services-and-security`) out of this branch. Its new 9,831-line
  remote-schema snapshot is unrelated to session restoration and its database
  CI is failing; bundling it would couple two independent review decisions.

## Local measurements

Disposable local Supabase and FastAPI, one confirmed resident account:

| Metric | Result |
|---|---:|
| First `/auth/session` wall time | 31.50 ms |
| Warm samples | 20 |
| Warm wall p50 | 11.82 ms |
| Warm wall p95 | 13.20 ms |
| Warm `Server-Timing` p95 | 12.46 ms |
| Missing access + valid refresh | `401 token_expired` |
| Refresh | `200` |
| Retried session | `200` |

The structured logs contained only normalized route, status, duration, and the
`profile`/`membership` step names. They contained no token, email, profile,
community, cookie, query value, or response body.

The exact PostgREST nested projection returned `200` with the expected
`unit_residencies`, `departments`, and `staff_assignments` relationships.
Established members now perform two PostgREST reads after local JWT validation:
one profile read and one nested membership read. The reads run concurrently.

## Query-plan decision

Local `EXPLAIN (ANALYZE, BUFFERS)` completed in 0.141 ms. Membership,
residency, unit, building, and department joins used indexes. The only
sequential scan covered five local `staff_assignments` rows. This does not prove
an index benefit, so Phase 1 adds no speculative migration.

## Automated verification

- Backend: 1,047 passed, 4 skipped.
- Frontend: 96 passed.
- Frontend lint and production build passed.
- Focused Ruff `F`/`I` checks and Python compileall passed.
- Exact local PostgREST projection and expired-session refresh sequence passed.
- Clean-reset local Supabase integration suite: 4 passed.
- Full-stack Chromium/Pixel 7 Playwright suite: 10 passed, 2 intentionally
  skipped because the stateful full-stack flow runs once on Chromium.
- OpenAPI export check passed; the API mapper remained at its known 20
  documentation verdicts and reported no route-count drift.

## Evidence still required outside this checkout

- Twenty cold and twenty warm samples against the deployed/staging backend.
- Role-by-role browser timing for admin, resident, worker, security,
  security-manager, manager, and onboarding identities.
- Hosting cold-start and backend/Supabase region comparison.
- Human verification of valid, expired, revoked, logged-out, offline, and
  backend-unavailable states.

These require the staging URL, disposable role accounts, and the Chrome
DevTools performance connector. Local timings must not be presented as deployed
p95 evidence.
