# Reconciliation addendum — everything outside `backend/`

**Status:** draft for approval. Extends [SCHEMA_RECONCILIATION_PLAN.md](SCHEMA_RECONCILIATION_PLAN.md); does not replace it.
**Written against:** `origin/main` @ `94556e5`. Date: 2026-07-30.

---

## 0. Scope correction

The reconciliation plan was written after reviewing `backend/` and `docs/homebandhu_submission_erd.dbml`. That was
half the handover. The commit range `3116027..94556e5` changes **166 files outside `backend/`**:

| Area | Files | Insertions | Deletions |
|---|---|---|---|
| `frontend/` | 93 | 1 168 | 5 907 |
| `docs/` + root | 14 | 3 296 | 4 402 |
| `graphify-out/` (generated) | 59 | ~37 000 | 0 |

The frontend deletions are the story. **They rewrote the frontend.** This addendum covers what that means for us.

> A second reminder of plan §0: the folder we were handed is `32dbb49`, one commit behind. Almost every document
> named below — `FRONTEND_CHANGES.md`, `BACKEND_CHANGES.md`, `AUTH_REGISTRATION_IMPLEMENTATION_PLAN.md` — exists
> **only in `94556e5`** and is absent from the folder we were told to refer to. The folder's own `AGENTS.md` still
> asserts *"There is **no backend**"*. Read nothing from that folder as current.

---

## 1. The headline: the frontend is no longer a dummy-data demo

Verified from `docs/FRONTEND_CHANGES.md` and the source at `94556e5`:

- **Every fixture in `frontend/src/data/` is deleted** — `users.js`, `complaints.js`, `payments.js`, `visitors.js`,
  `amenities.js`, `amenitiesManagement.js`, `amenityBookings.js`, `amenityLedger.js`, `departments.js`, `notices.js`,
  `admins.js`, `pendingRequests.js`, `invitations.js`, `authentication.js`. Only onboarding metadata, admin
  designation options and resident FAQs survive, as configuration rather than tenant records.
- **`appStore.js` is now a render cache.** Their words: *"its domain collections begin empty and only the snapshot
  hydrator supplies records."* `partialize` no longer persists tenant data.
- **The whole dashboard reads from one endpoint.** `DashboardDataBootstrap.jsx`, mounted once in `App.jsx`, calls
  `GET /api/v1/dashboard/snapshot`, writes it through `hydrateDashboard`, then opens an `EventSource` on
  `GET /api/v1/dashboard/events` and re-snapshots (debounced) on every `dashboard.refresh`.
- **Auth is Google-only and cookie-based.** `ResidentLoginPage.jsx` (325 lines), `OtpVerificationPage.jsx`,
  `OnboardingOtpPage.jsx`, `OtpInput.jsx`, `PhoneNumberField.jsx`, `adminAuthService.js`, `AuthFlowRoute.jsx`,
  `lib/tokens.js`, `lib/invites.js`, `createInvitationsSlice.js` are all deleted.
- **`vite.config.js` proxies `/api` → `http://localhost:8000`**, so the client is same-origin by construction.

This retires the `homebandhu-demo-frontend` memory, which says the frontend is a dummy-data demo whose shapes we
should not preserve. Half of that is now wrong: there is no dummy data, and the shapes are now **contractual**,
because a real serializer has to produce them. I will update that memory once this plan is approved.

### 1.1 The frontend's actual endpoint contract

Nineteen paths, enumerated from `git grep "api('/…')"` at `94556e5`:

| Group | Paths |
|---|---|
| Auth | `GET /auth/session`, `GET /auth/methods`, `POST /auth/logout`, `POST /auth/refresh`, `GET /auth/google/start`, `GET /auth/google/callback` |
| Invitations | `POST /invitations/prepare`, `POST /invitations/redeem`, `POST /admin/invitations` |
| Registration | `GET /communities/search`, `GET /communities/admin/units`, `POST /access-requests`, `GET /access-requests/mine`, `POST /access-requests/{id}/withdraw`, `GET /admin/access-requests`, `POST /admin/access-requests/{id}/approve`, `POST /admin/access-requests/{id}/reject` |
| Onboarding | `POST /onboarding/community` |
| Dashboard | `GET /dashboard/snapshot`, `GET /dashboard/events`, `POST /dashboard/amenities`, `PUT /dashboard/amenities/{id}`, `DELETE /dashboard/amenities/{id}` |

**None of our 70 operations appear in that list.** See C-8.

---

## 2. New conflicts (continuing the plan's numbering)

### C-8 🔴 The frontend is a client of *their* API, not ours

Their amenity mutations are `POST/PUT/DELETE /dashboard/amenities`. Ours are `POST/PUT/DELETE /amenities` — one of
22 amenity operations from build step 8. Same domain, two URL namespaces, and the shipping frontend calls theirs.

Worse for the other eight steps: the admin pages no longer fetch per-domain at all. `Residents.jsx` lost 464 lines
and now renders from the snapshot. `PendingRegistrations.jsx` was rewired to `registrationApi.js`. So our
`GET /residents`, `GET /complaints`, `GET /invoices` and the rest have **no caller**.

This does not make our work waste, and I want to be precise about why rather than optimistic. The snapshot is a
whole-community projection with no `limit`, `cursor`, `status=` or `q=` parameter, and their own
`FRONTEND_CHANGES.md` concedes the follow-up: *"Booking and ledger mutation endpoints remain a follow-up
integration boundary."* A snapshot cannot serve a 400-unit community's resident table, a filtered complaint
queue, or an invoice ledger. Our endpoints are what that boundary needs. But the honest statement of status is:

> Our 70 operations are now a **proposed** API surface with no frontend caller, not the implementation of an
> existing one. Until the frontend team agrees to call them, they are speculative.

That is a meeting item, not a code change. It is the single most important thing to put in front of both teams.

**Recommendation:** keep our paths, do **not** renamespace under `/dashboard`. Their `/dashboard/amenities` is
three endpoints inside a router named for a snapshot; ours is a documented 22-operation resource surface. Offer
theirs as the deprecation target once ours is wired.

### C-9 🔴 All 47 of our write endpoints will 403 against the shipping client

`grep -c require_csrf` across our nine routers returns **0 for every file**. Their client sets `X-CSRF-Token` on
every non-GET/HEAD/OPTIONS request and their routers enforce it with `dependencies=[Depends(require_csrf)]`.

Two consequences, in opposite directions:

1. Our writes do not *validate* CSRF, so once the app is same-origin and cookie-authenticated, **every one of our
   47 write endpoints is a CSRF hole**. This is a security defect introduced by their auth change, not by us, but
   it lands in our files.
2. Their `require_csrf` rejects requests lacking the header. Any of our endpoints called by their client is fine
   (the client always sends it); anything called by a test or a bearer-token integration is not.

**Fix:** add `dependencies=[Depends(require_csrf)]` at the router level for all nine routers, in Phase 1 alongside
the `require_role` → `require_membership_role` swap. Mechanical, nine lines, and it closes the hole.

This is auth-adjacent, but it is *consuming* their primitive in our routers, not editing theirs — so it stays
inside the standing "leave auth to its owner" boundary. I will not touch `require_csrf` itself.

### C-10 🔴 They deleted a five-gate source of truth

`docs/frontend-documentation.md` — **3 305 lines, deleted.** Our five-gate check runs every proposal past the
frontend documentation. That artifact no longer exists on `main`.

Also deleted: `docs/AGENTS.md` (485), `docs/CLAUDE.md` (55), `docs/plan.md` (192). **We have local modifications to
`docs/CLAUDE.md`**, so the merge produces a delete/modify conflict there. Our copies of all four survive in our
tree, and our `docs/` additionally holds 16 documents `main` has never seen.

**Recommendation:** keep our copies (`git checkout --ours`), and replace gate 1's source with the pair that
supersedes it — `docs/FRONTEND_CHANGES.md` plus the live `frontend/src/`. Record the substitution in the build
plan's five-gate table so the gate stays meaningful instead of pointing at a deleted file.

### C-11 🟡 Step 9's module catalogue duplicates a table they already shipped

Their baseline has `feature_catalog(code, name, description, default_enabled, is_active)` +
`community_features(community_id, feature_code, is_enabled, updated_by_membership_id, updated_at)`.
Step 9 shipped `module_catalogue(module_key, display_name, description, sort_order, default_enabled,
backend_status, backend_note)` + `community_modules(community_id, module_key, enabled)`.

**The ten keys are byte-identical** — `resident-management`, `visitor-management`, `complaint-management`,
`maintenance-billing`, `notice-board`, `amenities-booking`, `security-gate-management`, `parking-management`,
`staff-management`, `community-marketplace` — with identical `default_enabled` values, because both were derived
from `onboardingModules.js`. Independent derivation, same answer. And their onboarding RPC already writes
`community_features` and projects `enabledModules` from it.

**Recommendation — cheapest resolution in the whole reconciliation:** drop our two tables, add our three columns
(`sort_order`, `backend_status`, `backend_note`) to their `feature_catalog` in an additive migration, and re-point
`GET /settings` and `PATCH /settings/modules` at `community_features`. Every word of step 9's documentation
survives; only the table name changes. This also removes decision A24's awkwardness: `backend_status` is exactly
the honesty column their catalogue lacks.

### C-12 🟡 Three of our migrations were deleted upstream

Our `backend/supabase/migrations/` holds `0001_init.sql`, `0002_rls.sql`, `0003_access_token_hook.sql` — all three
**deleted** by `94556e5` in favour of `0001_baseline.sql` — plus our `0010`–`0017`, which upstream has never seen.
Their tree has `0001_baseline.sql`, `0006_legacy_founder_onboarding_bridge.sql`, `0007_dashboard_realtime_outbox.sql`.

Good news: the directory is the same, so there is no path move. Bad news: `git merge` will present the three
deletions against our unmodified copies, and our `0010`–`0017` assume `0001`–`0003` ran.

**Recommendation:** accept the deletions. Retire `0003_access_token_hook.sql` outright — the plan already verified
that `is_admin`, `jwt_role` and `custom_access_token_hook` appear **zero** times in their baseline, so the JWT-claim
hook it installs is dead under `require_membership_role`. Rebase `0010`–`0017` onto the baseline as `0018`+ per the
plan's Phase 4.

### C-13 🟢 Their realtime outbox works on our writes for free

I expected to have to emit outbox rows from all 47 of our writes. I was wrong, and in our favour.
`0007_dashboard_realtime_outbox.sql` implements it as `AFTER INSERT OR UPDATE OR DELETE … FOR EACH ROW` triggers
installed by a `to_regclass`-guarded loop over twelve tables, calling `emit_dashboard_sse_event()`, which reads
`community_id` off the row and inserts `('dashboard.refresh', {table})` into `sse_events`.

I checked all twelve against the baseline: `community_memberships`, `complaints`, `visitor_requests`, `amenities`,
`amenity_bookings`, `invoices`, `payments`, `notices`, `departments`, `access_requests` all carry a `community_id`
column (`visitor_access_requests` and `amenity_booking_series` are the older names, skipped by the `to_regclass`
guard). So **any write of ours to those tables refreshes every connected client's UI, including writes made inside
our RPCs** — triggers fire regardless of the calling layer.

Two gaps worth one additive migration: the trigger list omits the tables step 9 and step 5 added
(`community_settings`, `community_billing_settings`, `complaint_comments`), and it skips rows whose table has no
`community_id`. Extending the loop is a five-line migration.

> **Amended 2026-07-30, after building the live-update path.** The heading above is too generous and the word
> "free" is wrong twice over. The outbox does fire on our writes, but (a) a `dashboard.refresh` carrying only
> `{"table": …}` cannot *notify* — it cannot distinguish a new join request from a rejected one, which is what
> the admin badge needed, so `0024` adds specific `access_request.created` / `.decided` topics; and (b) the
> reader on the other end could not have scaled, independently of the trigger design. See
> [FRONTEND_WIRING_AUDIT.md](../FRONTEND_WIRING_AUDIT.md) §7 and the *Live updates* section of
> [ARCHITECTURE.md](../ARCHITECTURE.md). The two trigger gaps named in this paragraph are **still open** — `0024`
> did not extend the loop — and are now recorded under *Guarantees and limits* in `ARCHITECTURE.md`.

### C-14 🟢 Their baseline closes three of our long-standing open items

| Our item | Status before | What their baseline provides |
|---|---|---|
| **F2** Storage bucket for attachments | open | `media(community_id, storage_path unique, mime_type, byte_size, uploaded_by_membership_id)` |
| **F3** Rate limiting | open | `rate_limit_buckets(bucket pk, count, window_ends_at)` |
| **F4** Concurrency / lost updates | open | `idempotency_records(community_id, key, request_hash, response)` + `aggregate_version` on `complaints` and `amenity_bookings` |

Schema only — no Python reads any of them yet. But the design decisions are made, which turns three open questions
into implementation tasks. `payments` also carries `unique(community_id, idempotency_key)`.

### C-15 🟢 Our error envelope already matches their client, exactly

Their `client.js` reads `payload.error.code`, `.message`, `.details`. Our `exceptions.py` emits
`{"error": {"code", "message", "details"}}` for all four error classes, deliberately unified so *"a client cannot
parse errors generically against three shapes."* Independent convergence — no change needed. Our 401s also work
correctly with their one-shot `POST /auth/refresh` retry.

### C-16 🟡 Their ERD is stale against their own baseline — and it agrees with *us*

Set comparison of `docs/homebandhu_submission_erd.dbml` (49 tables) against `0001_baseline.sql` (46):

- **20 tables in the ERD do not exist in the baseline**, including `amenity_booking_series`,
  `amenity_booking_occurrences`, `amenity_rules`, `amenity_booking_charges`, `amenity_financial_events`,
  `visitor_access_requests`, `policies`, `policy_revisions`, `work_order_proposals`, `media_assets`.
- **15 baseline tables are absent from the ERD**, including `feature_catalog`, `community_features`, `sse_events`,
  `amenity_bookings`, `complaint_comments`, `idempotency_records`, `rate_limit_buckets`.
- The ERD gives `communities.active_admin_membership_id`; the baseline uses `community_admin_terms` with a partial
  unique index.

Note what this does to plan §3's third decision. The contested designs are ours-vs-baseline, and on amenities the
ERD sides with **us**: it models a booking *series* with separate *occurrences* and a typed `amenity_rules` table,
which is our step-8 design, not the baseline's single `amenity_bookings` with `booking_rules jsonb`. Their baseline
is the deviation from their own submitted ERD.

That is the strongest argument available for preserving our typed amenity design, and it should be made from their
artifact rather than our preference.

---

## 3. Changes to the plan's phases

| Phase | Addendum change |
|---|---|
| **0 Merge** | Add the `docs/CLAUDE.md` delete/modify conflict and the three deleted migrations (C-10, C-12). Resolve `graphify-out/` by taking theirs wholesale — it is generated. |
| **1 Auth seam** | Add CSRF to all nine routers (C-9). Same sitting as the `require_role` swap. |
| **2 Decide** | Add decisions 4 and 5 below. |
| **3 Views** | Unchanged. |
| **4 Migrations `0018`+** | Add: `feature_catalog` gains three columns and `module_catalogue`/`community_modules` are dropped (C-11); the SSE trigger loop is extended over our step-5/step-9 tables (C-13). |
| **5 Writes** | Reduced — no outbox emission needed (C-13). |
| **6 Verify/re-document** | Add: repoint gate 1 to `FRONTEND_CHANGES.md` + live source; rewrite `API.md` §11's module section onto `community_features`; update the `homebandhu-demo-frontend` memory. |
| **7 — new — Frontend contract** | Take C-8 to the joint meeting. No code until both teams agree who calls what. |

### Two decisions this adds

4. **C-8, the frontend contract.** Keep our paths and pitch them as the pagination/filtering boundary
   *(recommended)*, or renamespace under `/dashboard` to match what ships? This is the one that decides whether
   nine build steps get wired up or sit as a proposal.
5. **C-11, the module catalogue.** Fold our three columns into their `feature_catalog` *(recommended)*, or keep two
   parallel catalogues of the same ten keys?

Decision 1 from the plan — the RLS enforcement boundary — still gates Phases 3 and 5 and is still the most
consequential. C-9 sharpens it: their model is service-role plus a Python guard plus CSRF, and we now have direct
evidence the CSRF half was never applied to our routers.

---

## 4. What this addendum adds to the cost

The plan's estimate stands for the SQL and repository work. On top:

- **Small:** CSRF on nine routers; migration folding `module_catalogue` into `feature_catalog`; extending the SSE
  trigger loop; docs-conflict resolution.
- **Removed:** outbox emission from 47 writes (C-13) — was in Phase 5, no longer needed.
- **Unbounded, and not ours to schedule:** C-8. If the frontend team wants our 70 operations, someone rewrites the
  admin pages to call them. If they do not, our endpoints stay a proposal. Either way it is a decision for the
  joint meeting, and it should be the first agenda item.
