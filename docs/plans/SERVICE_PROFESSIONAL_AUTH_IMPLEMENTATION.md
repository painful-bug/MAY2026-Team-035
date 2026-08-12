# Service-professional authentication implementation

Implemented on 2026-08-11 as a service-signup intent over the existing BFF auth,
provider, hiring, notification and PostGIS modules.

## Locked contracts

- `/register?intent=service-provider` reuses the existing Google/email page.
  Intent changes navigation only; session membership remains authoritative.
- Existing resident/admin/manager identities are told to use a separate account.
  **Bidirectional since `20260812113000` (PO ruling 2026-08-12):** the reverse path is refused
  too — `enforce_professional_membership_mode` raises `HBSEP` (409
  `professional_account_separate`) when a registered professional's profile is offered a
  resident/manager/admin membership. The database is the enforcement point; the
  `authRoutes.js` guard is one of two halves.
- `POST /service-providers` atomically writes the profile, mandatory coordinates,
  1–500 km radius and at least one active skill. Legacy partial profiles render
  the same form as a repair path.
- Community and candidate searches return at most 20 rows inside the
  professional-controlled radius, ordered by distance, case-folded name and id.
- Applications target one department. Its active manager decides; active
  community admins are the fallback only when it has no manager. Supervisors do
  not decide.
- Acceptance atomically writes membership, staff assignment and decision.
  Security departments issue `security`; other departments issue `worker`; the
  two modes cannot coexist on one professional account.
- Funnel telemetry stores only random visitor id, one of five event names and
  occurrence time, deduplicated per event and deleted after 30 days.

## Manager-portal integration contract

The teammate-owned portal keeps the existing department hiring endpoints. Its
candidate result never includes exact provider coordinates, is capped at 20 and
may return 403 for an admin when the selected department has an active manager.
Roster-ranked managers are accepted. Invitation terms are immutable when the
professional accepts. Shared E2E approval, fallback and candidate-distance
scenarios remain a release gate; this branch does not change manager layouts or
navigation.

## Production data and rollout gate

Before exposing the CTA in production:

1. Apply both `20260811…` forward migrations after a dry run.
2. Backfill and verify coordinates for all three hosted communities.
3. Verify active departments, category-to-skill mappings and manager/fallback
   ownership, including security categories under security departments.
4. Run rollback-only radius-boundary and candidate queries on hosted PostGIS.
5. Smoke-test real Google OAuth, real confirmation email, manager acceptance and
   next-login worker/security routing on staging.
6. Deploy migrations/backend before the frontend CTA.

No live A/B variant ships. A future presentation-only variant needs an approved
traffic estimate, minimum detectable effect, sample size and stopping rule. Its
primary metric is unique `first_application_submitted` / unique
`cta_impression`; auth failures, profile completion, existing signup regression
and support/error volume are guardrails.

## Verification automation

The fast CI job runs backend HTTP/unit tests, frontend component tests, lint,
build, Python compilation, migration parsing, OpenAPI freshness and the recorded
20-finding API-map baseline. The database/browser job resets local Supabase,
uses real user JWTs for registration, radius boundaries, manager/fallback
authorization, invitations, concurrent writes, mixed-mode refusal and telemetry
retention, and fails if a representative PostGIS `EXPLAIN` stops using the
provider-location GiST index.

Playwright keeps small deterministic OAuth, dedicated-account and telemetry
failure tests on desktop and mobile. Its CI-only full-stack cases use real
FastAPI cookies and local Supabase for email login, atomic registration,
nearest-community application, manager approval, logout/login worker routing,
and security-department routing. Failure traces, screenshots, video and network
evidence are retained only on failure.

Local mocks and CI do not replace the production rollout gates above: real
provider email delivery, real Google OAuth, the hosted-data backfill and the
teammate-owned manager portal must still be evidenced on staging.
