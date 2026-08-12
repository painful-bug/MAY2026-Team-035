# 15. The service-professional intent dies in the confirmation email

**Labels:** `auth`, `configuration`, `telemetry`
**Found:** 2026-08-12, auditing the merged service-professional auth commits (`fc69d3f`)
**Urgency:** The dead end is fixed; the funnel metric stays wrong until the template decision

---

## Body

A professional who signs up with **email and password** loses their `intent=service-provider` on the
way through the confirmation email, because the email's link is a **fixed URL** configured in the
Supabase dashboard (`docs/SUPABASE_AUTH_SETUP.md` step 3: `…/auth/confirm-email?token_hash={{ .TokenHash }}&type=signup`).
`sign_up_with_password` dutifully sets `email_redirect_to` with the intent attached
(`backend/app/services/auth_service.py:135`) and the template never interpolates it. The OAuth path
is unaffected — its intent rides the redirect the whole way.

**Two consequences, one fixed, one open:**

1. ~~The user dead-ends~~ **Fixed 2026-08-12.** `/get-started` offered only *Create a Community* /
   *Join a Community*; an email-path professional landed there with no route on. It now has a third
   door whose destination is **computed** from `destinationAfterAuth(context, SERVICE_PROVIDER_INTENT)`
   rather than hardcoded, so it cannot drift from the OAuth path
   (`frontend/src/pages/GetStarted/GetStartedPage.jsx`, with `GetStartedPage.test.jsx` pinning the
   parity). `/worker` is the right landing because `WorkerDashboardHome` renders the registration
   form for anyone whose snapshot lacks coordinates or skills — bare `/worker` *is* the continuation
   point.
2. **Still open: the funnel undercounts.** `auth_completed` — one of the two metrics the rollout
   plan names — is never recorded for the entire email path, so the primary metric's numerator is
   structurally low relative to `cta_impression`, and nothing in the numbers says so.

## The trap next to the obvious fix

"Switch the template to `{{ .RedirectTo }}`" **was** dangerous when this was found:
`confirmation_redirect_url` built its query with a bare `?`, so the template change would have
produced `…?intent=service-provider?token_hash=…` — `token_hash` parses as `null` and confirmation
breaks for every service-provider signup, which is strictly worse than the misroute. That
concatenation is fixed (2026-08-12, `auth_service.py:109` — `&` when the base already carries `?`,
value urlencoded, test pinning both parameters' survival), so the template option is now *safe* —
but it is still a **dashboard configuration plus an allowlist entry**, not a code change, and it is
half of issue **5** (the templates already do not match the setup document).

## How to confirm

Sign up at `/register?intent=service-provider` with email and password, open the confirmation mail,
and read the link's query string: no `intent`. After confirming, the funnel table has no
`auth_completed` row for that visitor id.

Aishik's own E2E does not catch it — `frontend/e2e/service-professional-full-stack.spec.js:88-95`
uses a pre-confirmed user who signs **in** on the intent-carrying page, so the email round trip is
never exercised.

## Suggested fix

Decide between:

- **Template carries the intent** — amend the dashboard template (and
  `docs/SUPABASE_AUTH_SETUP.md`, and the URL allowlist) to interpolate `{{ .RedirectTo }}` or to
  append `&intent={{ … }}` to the fixed URL. One configuration change, closes both the routing and
  the metric. Requires issue 5 to be done at the same time, by whoever holds the dashboard.
- **Client-side carry** — stash the intent in `localStorage` at sign-up, consume-on-read at
  confirmation. No dashboard dependency, but introduces a cross-tab, cross-session identity hint
  with a TTL, and can misroute a *later* signup in the same browser. Only worth it if the dashboard
  stays out of reach.

Either way, record `auth_completed` at the point the confirmed session first resolves with a
provider registration, not at the redirect — then the metric stops depending on which path carried
the intent.

## Related

- [5 — Supabase email templates do not match our own setup document](README.md#5-supabase-email-templates-do-not-match-our-own-setup-document) —
  the same dashboard visit fixes both
- `docs/CHANGE_LOG.md` Session 67 — the audit this came out of
