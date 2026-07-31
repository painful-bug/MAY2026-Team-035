# Reconciliation plan — our dashboard work vs. `origin/main`

**Raised:** 2026-07-30 · **From:** backend (admin dashboard workstream)
**Revised:** 2026-07-30, **after fetching `origin/main` and finding the handed-over folder is stale.**
**Baseline compared against:** `origin/main` @ `94556e5` *"feat: complete Google auth and realtime dashboards"*
**Status:** plan only. Our work is committed (`8729782`); **no merge has been performed.**

> **Scope limit — read [RECONCILIATION_ADDENDUM.md](RECONCILIATION_ADDENDUM.md) with this file.**
> This plan was written from `backend/` and the ERD. The same commit range also changes **166 files outside
> `backend/`**, including a rewrite of the frontend from a dummy-data demo into a real API client. The addendum
> covers that, adds conflicts **C-8 – C-16**, amends the phases in its §3, and corrects one claim here in our
> favour (the realtime outbox needs no work from us — **since amended in the addendum's own C-13: it needed
> migration `0024` and a rewritten reader**). Two of its findings — the frontend contract (C-8) and CSRF
> on our writes (C-9) — rank alongside C-1 in importance.

---

## 0. Two corrections to what we were told

**First: the handover was described as *"changes with regard to login and authentication."* It is not.**
It is a complete parallel implementation of the application domain **and** a competing dashboard API.

**Second: the folder handed over (`Documents\GitHub\...`, at `32dbb49`) is one commit behind
`origin/main`, and that one commit changes almost everything the first draft of this plan analysed.**
`94556e5` **deletes migrations `0001`–`0005` and replaces them with a single 263-line
`0001_baseline.sql`**, whose header reads *"Apply only to a new Supabase project."* Table names and
shapes changed again in the process.

So there have been **three** versions of their schema in two days:

| | `0001`–`0003` | `+ 0004`–`0005` (the folder we were given) | `0001_baseline` + `0006` + `0007` (**actual `main`**) |
|---|---|---|---|
| Tables | 5 | 48 | 46, **renamed and reshaped again** |
| Amenity bookings | — | `amenity_booking_series` + `_occurrences` | **`amenity_bookings`**, one table |
| Amenity config | — | `amenity_rules` (6 fields) | **`amenities.booking_rules jsonb`** |
| Invoices attach to | — | `liable_unit_id` | **`membership_id`** |
| Complaint read state | — | — | `complaint_read_state` |
| RLS | global admin policies | 50 SELECT policies + per-community helpers | **6 tables, 7 policies** |

**This plan is written against `94556e5` only.** Anything in the given folder that `94556e5` deleted is
treated as history. Note the corollary: **their schema has been rewritten twice in two days, so a
plan that hard-codes its details will go stale again.** That is an argument for putting our
translation in views we own, which §5 does.

---

## 1. What their work closes for us — re-verified against `94556e5`

Real wins, and they are the reason adopting their base is right.

| Our item | Status | How |
|---|---|---|
| **§1.1** privilege escalation via signup metadata (critical) | ✅ **gone entirely** | There is no role in signup metadata any more. `BACKEND_CHANGES.md`: *"no browser-supplied role or JWT role claims authorize a request."* |
| **§1.2** unscoped `is_admin()` (high) | ✅ **gone entirely** | `is_admin()`, `jwt_role()` and `custom_access_token_hook()` appear **zero times** in `0001_baseline` or `0006`. Authorization is `require_membership_role(...)` over a membership row read from Postgres. |
| **C1** `email` on profiles | ✅ | `profiles.display_email citext`, unique where not null. |
| **C2** migrations `0004`–`0009` reserved | ✅ | They used `0001`, `0006`, `0007`. |
| **C3** `current_association_id()` | ✅ **resolved better than either of us proposed** | `get_active_membership()` returns a `MembershipContext` carrying `community_id`, `role` and `department_id`, ordered by `is_default_community`. This is our `get_caller_community_id()` done properly, including the multi-community case ours had no answer for. |
| **C5** what identifies an invitee under OAuth | ✅ **answered** | `resident_invites.invitee_email citext not null` — email, with phone optional. Google is the sole identity provider. |
| **C6 / F5** `.venv` committed | ✅ | Removed and ignored. |
| **D1** `associations`/`units`/`apartments` naming | ✅ **moot** | The baseline starts with `communities` / `buildings` / `units`. Nothing to rename. |
| **A10** community timezone | ✅ **theirs** | `communities.timezone not null default 'Asia/Kolkata'`. Our `community_settings.timezone` is now a duplicate. |
| **F3** rate limiting | 🟡 **table exists** | `rate_limit_buckets`. Nothing enforces it yet, but the storage is there. |
| **F4** optimistic concurrency | 🟡 **partly** | `complaints.aggregate_version` and `amenity_bookings.aggregate_version`. Not on the other edit surfaces. |
| **E14** payment idempotency | ✅ **theirs too** | `payments.idempotency_key` with `unique (community_id, idempotency_key)`, plus a general `idempotency_records` table. Same conclusion, reached independently. |

**Their auth seam is compatible with our routers, which is better news than their own notes imply.**
`deps.py` keeps `get_current_user` and `get_request_client` with identical signatures, and
`_extract_token` accepts **either** an `Authorization: Bearer` header **or** the new session cookie. So
our documented bearer contract still works and every `Depends(get_current_user)` in our seven routers
is unaffected.

---

## 2. The conflicts, worst first

### C-1 🔴 We disagree about *where authorization lives*, and that is architectural

This is the biggest item and it is not about tables.

|  | Ours | Theirs (`94556e5`) |
|---|---|---|
| Client used for domain reads | user-scoped (`get_request_client`) | **service-role** (`get_service_client`) |
| Tenant boundary | **RLS in Postgres**, on every table | **Python**, in `get_active_membership` / `require_membership_role` |
| Tables with RLS enabled | all of ours | **6 of 46** (`profiles`, `communities`, `community_memberships`, `units`, `resident_invites`, `access_requests`) |
| Policies | ~40 read + admin write | **7, all SELECT** |

Our build plan's Supabase gate commits us to *"RLS as the enforcement boundary."* Their baseline
leaves **~40 tables with no RLS at all** — including `complaints`, `invoices`, `payments`,
`amenity_bookings` and `notices`. That is safe **only** while every query goes through the service-role
key and a Python guard. The moment anything reaches those tables with a user token — which is exactly
what our `get_request_client()` does — there is no boundary left.

**So this must be decided before any of our repositories are re-pointed**, because the answer changes
every one of them:

- **(a) Add RLS for the tables we use** (~14 tables, policies modelled on their 7). Keeps our design
  and our tests' meaning, keeps defence in depth, and is work they will benefit from.
- **(b) Adopt their service-role + Python-guard model.** Less SQL, but it deletes the boundary our
  cross-tenant regression test exists to prove, and one forgotten guard becomes a tenant leak.

**Recommendation: (a).** It is additive, it does not ask them to change anything, and "an admin of
community A reads zero rows of community B" stops being a claim about our Python and goes back to being
a claim about the database.

### C-2 🔴 There are now two dashboard APIs, in files with the same names

They built `GET /dashboard/snapshot` (one payload transformed *"into the existing frontend shape"*),
`GET /dashboard/events` (SSE), and admin-guarded amenity create/update/delete. We built 70 endpoints
across eight surfaces.

**Three files were authored by both teams under the same path** — git will report them as
*both-added* conflicts:

- `app/api/v1/routers/dashboard.py`
- `app/services/dashboard_service.py`
- `app/repositories/dashboard_repository.py`

This is a genuine product question, not a merge mechanic: **one snapshot endpoint plus SSE, or a
resource-per-surface REST API?** They are not equivalent — theirs refreshes a whole dashboard in one
round trip and pairs with realtime; ours pages, filters and writes per resource, which a snapshot
cannot do. My reading is that **they are complementary and both should live**: keep their
`/dashboard/snapshot` and `/dashboard/events` for the read-heavy home screen, keep our resource
endpoints for everything that lists, filters, pages or writes. That requires renaming our three files
so both survive.

### C-3 🔴 Sixteen-plus colliding tables, reshaped *again* in `94556e5`

The collisions from the first draft still exist, but several changed shape. The ones that cost us:

| Table | Ours | Theirs @ `94556e5` | Cost |
|---|---|---|---|
| `amenities` | 30-field `amenity_settings` table | **`booking_rules jsonb`**, no `capacity`, no `booking_mode` | Our settings tab has ~30 typed fields; a jsonb blob cannot be constrained or queried the same way. Our D7 argument now applies to a blob. |
| `amenity_bookings` | series + occurrences, wall-clock `date`+`time`, scoped exclusion + advisory lock | one table, `timestamptz`, exclusion scoped `where status in ('requested','approved')` | Their exclusion is **better than `0004`'s** (status-scoped) but still blanket across booking modes. With `capacity` gone there is no contradiction left — but **shared//multi-occupancy booking is now unrepresentable**, and the gym's capacity of 24 was a product fact. |
| `invoices` | attach to the **unit**, `invoice_number`, derived `isOverdue` | attach to **`membership_id`**, no `invoice_number`, `overdue` **stored** in the enum | Reverses their own `0004`. Our E15 privacy rule (a new tenant must not see the previous occupant's arrears) was built on unit liability; membership liability changes who owes what when someone moves out — that is F6, still unanswered. |
| `complaints` | `department_id`, `category_id`, `due_at`, assignee, SLA | `category text`, no department, no `due_at`; routing via `work_orders` | **Our SLA engine (A1/A2/A3) has no home.** Their `aggregate_version` is a genuine improvement we should adopt. |
| `departments` | `sla_hours`, `department_kind`, category claims | `category text`, `hours jsonb`, `manager_membership_id` | A1's tie-break question becomes unanswerable — there is nothing to tie-break. |
| `complaint_read_state` | `complaint_read_receipts` | `complaint_read_state` | Same concept, rename only. |
| `feature_catalog` / `community_features` | `module_catalogue` / `community_modules` | theirs | Rename, **plus** ours carries `sort_order`, `backend_status`, `backend_note` and per-key `updated_by`, which theirs lacks and the settings screen needs. |

Ours-only and still needed, so still additive: `community_billing_settings` (A13 — **the maintenance
amount still does not exist anywhere in their schema either**), `complaint_categories`,
`department_categories`, `community_settings` (minus `timezone`), `complaint_attachments`.

### C-4 🟡 `roles.py` is the one true two-sided Python conflict

They renamed `Role.TECHNICIAN` → `Role.WORKER` and added a `parse_role` normaliser; we added
`_DISPLAY_ROLE` / `display_role()` whose table still says `"TECHNICIAN"`. Both wanted; the merge is
mechanical.

Everything else in Python is clean: our `exceptions.py` work is purely additive (it unified the error
envelope, which their new `code=`-carrying errors will slot straight into), and every other shared file
was **identical modulo line endings** before `94556e5`.

### C-5 🟡 `require_role` no longer exists — all seven of our routers call it

Replaced by `require_membership_role(*roles: str)` taking lowercase strings and checking a **membership
row**, not a JWT claim. This is strictly better, and adopting it also lets us delete
`get_caller_community_id()` in favour of the injected `MembershipContext.community_id` — which removes
our worst single point of failure rather than fixing it.

### C-6 🟡 Our `API.md` §4 documents an invitation shape that no longer exists

Now `{ community_id, intended_unit_id, invitee_email, ... }`, email-keyed, Google-only. Our §4 predates
all of it. §1.2 (Authentication) also needs the cookie option documented beside the bearer token, and
`require_csrf` needs a mention for unsafe cookie-authenticated calls.

### C-7 🟢 Their own artifacts disagree with each other

`docs/homebandhu_submission_erd.dbml` still describes the **`0004`** schema — `amenity_booking_series`,
`amenity_booking_occurrences`, `liable_unit_id`, `visitor_access_requests` — none of which exist in
`0001_baseline`. It also omits `feature_catalog`/`community_features`, which the baseline creates. So
**their ERD documents a schema that was deleted.** Worth telling them; it is the same drift our
D-section exists to catch.

---

## 3. Decisions needed before implementation

1. **C-1, the enforcement boundary** — add RLS for the tables we touch *(recommended)*, or adopt their
   service-role + Python-guard model? **This gates all repository work.**
2. **C-2, the two dashboards** — keep both *(recommended)*, or drop ours in favour of their snapshot?
3. **Which of our four contested designs to preserve as additive work**, and which to concede:
   SLA/`due_at`, unit-vs-membership invoice liability, typed `amenity_settings` vs `booking_rules jsonb`,
   derived vs stored `overdue`. My recommendation is to preserve all four and raise the two that touch
   *their* tables with them — but each is a product call, not a technical one.

---

## 4. Revised implementation plan

### Phase 0 — Merge *(mechanical, ~1 sitting)*

1. ✅ **Done:** our work committed as `8729782` on `backend/planning/1`, with compiled Python untracked
   so the reconciliation is a readable diff.
2. Merge `origin/main` (`94556e5`). Expect **both-added** conflicts in the three dashboard files (C-2)
   and a content conflict in `roles.py` (C-4); take theirs for `.gitignore`, `config.toml`, and every
   auth file we never touched.
3. Rename our three dashboard files to `admin_dashboard.*` so both APIs survive, pending decision 2.
4. Keep our `0010`–`0017` in the tree, unapplied. They are the specification for Phase 3, not
   migrations to run — **and they must not be applied to a project holding the new baseline.**

### Phase 1 — Auth seam *(small, unblocks everything)*

5. Merge `roles.py` by hand (C-4).
6. Replace `require_role(Role.ADMIN)` with `require_membership_role("admin")` across the seven routers.
7. **Delete `get_caller_community_id()`**; inject `MembershipContext` instead. This is the single
   highest-leverage change in the whole reconciliation — it removes the linchpin rather than repairing it.
8. Add the vocabulary layer for their two enums (lowercase `membership_role`, `membership_status` with
   `pending`/`ended`) in `vocabularies.py`, where every other translation already lives.

### Phase 2 — Decide *(gate — §3)*

### Phase 3 — Our views, rebuilt on their tables

Our 12 views are the seam. Rewrite them and most of `services/` and all of `domain/` survives — and,
given their schema has moved twice in two days, a view we own is the right place for that risk to sit.

9. `department_overview`, `department_staff_overview` → their `departments` + `staff_assignments` + `skills`.
10. `complaint_overview` → their `complaints` + `complaint_events` + `complaint_comments` (+ `work_orders`).
11. `invoice_overview`, `payment_overview`, `collection_summary` → their `invoices`/`payments`.
12. The four amenity views → their `amenities` + `amenity_bookings` + `booking_charges`/`booking_refunds`.
13. `community_settings_overview`, `community_module_overview` → `communities.timezone` +
    `feature_catalog`/`community_features` + our additive columns.
14. If decision 1 is (a): `0018_dashboard_rls.sql`, RLS for the ~14 tables we read, modelled on their 7.

### Phase 4 — Additive migrations `0018`+

15. `community_billing_settings` + the maintenance amount (A13) — **still missing from their schema too.**
16. `complaint_categories`, `department_categories`, `sla_hours`, `due_at`, `complaint_due_at()`.
17. `amenity_settings` as a typed superset beside `booking_rules jsonb`.
18. Module metadata columns on `feature_catalog` / `community_features`.
19. `community_settings` minus `timezone`; `complaint_attachments`.

### Phase 5 — Writes

20. Re-point our 32 RPCs at their table and column names.
21. Convert the 9 direct PostgREST writes per decision 1.
22. Delete our `assert_community_admin` in favour of one admin check, wherever decision 1 puts it.

### Phase 6 — Verify and re-document

23. Run the suite; expect real failures in the mapping tests wherever a vocabulary moved.
24. Regenerate `openapi.yaml`. Their six routers plus our seven will change the operation count.
25. Update `API.md` (§1.2 auth, §4 invitations, every changed field), `DECISIONS_NEEDED.md` (close §1.1,
    §1.2, C1, C2, C3, C5, C6, D1, A10, E14; add the C-items above; **rewrite D6/D7/D8 against a baseline
    that has replaced the ERD they were written against**), `CHANGE_LOG.md`, the build plan's five-gate
    table, and the agenda if a wire shape moved.

---

## 5. What this costs

**Survives unchanged:** all nine DTO modules, `vocabularies.py`, `formatting.py`, `pg_errors.py`,
`common_schemas.py`, the error-envelope work, and the bulk of `services/`. Our bearer contract still
works because their `_extract_token` accepts both.

**Rewritten:** 12 views, 32 RPCs, 9 direct writes, the seven routers' auth dependency, and the parts of
seven repositories that name a table. **The SQL layer and a thin slice above it.**

**At risk without a product answer:** the SLA engine, unit-vs-membership invoice liability (and with it
E15's privacy rule and F6), typed amenity settings, derived `overdue`, and multi-occupancy amenity
booking — which their single-table model cannot currently express.

**Still open and untouched by any of this:** F1 — **now worse.** There are two schemas' worth of unrun
SQL, they are mutually exclusive (`0001_baseline` says *"apply only to a new Supabase project"*, our
`0010`–`0017` assume `0001`–`0003`), and **applying the wrong set first is now a way to lose a
database.** F2 (Storage bucket) is partly answered by their `media` table and Storage policies.
