# Schema reconciliation plan — our dashboard work vs. `origin/main`

**Raised:** 2026-07-30 · **From:** backend (admin dashboard workstream)
**Compared:** our working tree (`backend/planning/1`, uncommitted) against
`C:\Users\serve\Documents\GitHub\MAY2026-Team-035` at `32dbb49`
**Status:** plan only. **Nothing has been changed yet.**

---

## 0. The headline: this is not an auth change

The repo was handed over as *"changes made by the backend team with regard to login and
authentication."* It is much larger than that. Commit `0fffb68` ships **1,831 lines of new SQL** across
two migrations that implement **the entire application domain** — 48 tables, RLS for all of them, and
three workflow RPCs — plus a new 868-line ERD that matches it.

**Sixteen of those tables are tables we also built**, under the same names, with different columns.

| | Ours (uncommitted) | Theirs (`origin/main`) |
|---|---|---|
| Migrations | `0010`–`0017`, 7,568 lines | `0004`–`0005`, 1,831 lines |
| Tables created | 28 | 48 |
| **Table names in both** | **16** | **16** |
| Applied to a database | no | no |
| Committed | **no** | **yes, merged to `main`** |

So the job is not "adapt to a new auth flow". It is **reconciling two independent implementations of
the same domain**, where theirs is merged and ours is not. That changes the shape of the work, and it
is the reason this document exists before any code moves.

**One piece of good news up front, and it is the load-bearing fact in this plan:** our API layer talks
to the database almost entirely through **our own views and RPCs**, not through raw tables. Across
`app/`, there are only **11 references** to any table the rename touched. The blast radius is
concentrated in SQL, where we control both sides — not spread through 70 endpoints.

---

## 1. What they shipped, and what it closes for us

Genuinely good work, and it resolves seven of our open items. **These are wins, not conflicts.**

| Our item | Status now | How |
|---|---|---|
| **§1.1** privilege escalation via signup metadata (critical) | ✅ **fixed** | `handle_new_user()` no longer reads `raw_user_meta_data ->> 'role'` at all. Role comes only from `community_memberships`, resolved by `custom_access_token_hook`. |
| **§1.2** unscoped `is_admin()` (high) | ✅ **closed differently** | `is_admin()` still exists and is still global — **but it is used by zero policies.** All 50 read policies use new per-community helpers (`current_user_has_community_role(community_id, roles[])` and friends). The old global `associations_admin_write` policies are explicitly dropped (`0005:284-292`). |
| **C1** add `email` to `handle_new_user()` | ✅ **done, different column** | They added `profiles.display_email citext`, maintained in the trigger and backfilled from `auth.users`. **We added `profiles.email` in `0012` — that is now a duplicate column.** |
| **C2** migrations `0004`–`0009` reserved for auth | ✅ **honoured** | They took exactly `0004` and `0005`. Our `0010`+ numbering was correct. |
| **C3** `current_association_id()` is theirs | ✅ **resolved better** | They did not write it. They wrote a family of *community-scoped* helpers instead — the same conclusion we reached, arrived at independently. |
| **C6 / F5** `backend/.venv` committed | ✅ **removed** | `0fffb68` deletes it and fixes `.gitignore`. |
| **D1** `associations`/`units`/`apartments` renamed "later" | ✅ **done now** | `associations`→`communities`, `units`→`buildings`, `apartments`→`units`, `invitations`→`resident_invites`. The rename we deferred has happened. |

Two more things they added that we should simply adopt rather than duplicate:
`communities.timezone` (which **answers A10 in the schema**, one migration before we did), and Storage
policies on `storage.objects`.

**Their JWT contract is compatible with ours.** `custom_access_token_hook` emits `user_role` in
**uppercase** (`upper(cm.role::text)`), which is exactly what our `deps.py` and `roles.py` already
parse. No change needed to the auth seam.

---

## 2. The conflicts, worst first

### C-1 🔴 `get_caller_community_id()` — one function, 70 endpoints, currently broken

`dashboard_repository.get_caller_community_id()` reads **`profiles.association_id`**. Their `0004`
renames that column to `legacy_community_id` and stops maintaining it — membership is the source of
truth now. **Every one of our 70 operations calls this function**, directly or transitively.

It is also a **one-function fix**: resolve the community from `community_memberships` instead. Their
`memberships_repository.py` already demonstrates the query. This is the single highest
impact-to-effort item in the whole reconciliation.

### C-2 🔴 Sixteen colliding tables, all structurally different

Not name clashes to be renamed around — the same concept modelled differently. The four that matter:

| Table | Ours | Theirs | Consequence |
|---|---|---|---|
| `community_memberships` | `public.user_role` enum (UPPERCASE), `status text`, **`unique (id, community_id)`** | `membership_role` enum (lowercase), `membership_status` enum incl. `pending`/`ended`, `department_id`, `is_default_community` | Two role vocabularies **and** two status vocabularies. Their table has no `(id, community_id)` unique constraint, which **every composite FK in our `0011`–`0017` depends on.** |
| `unit_residencies` | has `community_id`, composite FKs to unit and membership | **no `community_id`** — tenancy flows through `unit_id` | Our whole "a child row cannot point at another community's parent" strategy (R4) has no anchor. |
| `amenity_booking_occurrences` | `booking_date date` + `starts_at time` + `ends_at time`, exclusion constraint scoped `where is_exclusive`, plus an advisory-lock trigger | `starts_at`/`ends_at timestamptz`, **blanket** `exclude using gist (amenity_id with =, tstzrange &&)` | See C-3 — this is a live bug in their schema. |
| `complaints` | `department_id`, `category_id`, `due_at`, `assignee_label`, SLA engine | no department, no category table, no `due_at`, no assignee; routing goes complaint → `work_orders` → `work_order_assignments` | **Our entire SLA design (A1, A2, A3, `complaint_due_at()`) has nowhere to live.** Their model is arguably better — it has real work orders — but it answers none of the SLA questions. |

Also colliding with different columns: `departments` (theirs has no `sla_hours`, no
`department_kind`, no category claims), `invoices` (`due_at timestamptz`, `total_amount`, and
`overdue` **as a stored enum value** — the thing our D6 deliberately derives), `payments` (enum
status, `provider_reference`), `notices`, `staff_assignments`, `complaint_events`,
`amenity_booking_series`, `amenity_booking_charges`, `amenity_financial_events`, `invoice_line_items`.

### C-3 🔴 Their exclusion constraint reproduces the bug we filed as A18

Their occurrence table carries a **blanket** overlap exclusion on `amenity_id`. Their `amenities`
table carries a `capacity` column and a `booking_mode`. **Those two facts cannot both be honoured:**
a blanket exclusion means one booking at a time per amenity, so `capacity` is a number nothing can
ever reach.

This is precisely the frontend bug we documented as `DECISIONS_NEEDED.md` **A18** and **E17** — the
cleaning buffer making shared capacity unreachable — now reproduced in the database, and for the same
reason the ERD note originally gave. Our `0016` solved it with a **scoped** exclusion plus an
advisory-lock trigger, because an `EXCLUDE` predicate is per-row and cannot express "conflict if
*either* side is exclusive", nor count.

**Whatever else is decided, this one needs fixing in their schema, not worked around in ours.**

### C-4 🟡 No admin write policy exists on any domain table

Their `0005` has **50 SELECT policies, 3 resident INSERT policies, 1 UPDATE policy** (notifications)
and 2 Storage policies. That is all. There is **no admin write path through RLS at all** — every
admin mutation must go through a `SECURITY DEFINER` RPC or the service-role key.

Our design mostly agrees: **32 of our 41 write paths are already RPCs.** But **9 are direct
PostgREST `.insert()`/`.update()`/`.delete()` calls** which currently rely on the admin write
policies *our* migrations create. Under their schema those 9 will fail silently (empty result) or as
`42501`. They must become RPCs or gain policies.

### C-5 🟡 Duplicate columns and tables we would be adding twice

| Ours | Theirs | Action |
|---|---|---|
| `profiles.email` (`0012`) | `profiles.display_email` (`0004`) | Drop ours, read theirs |
| `community_settings.timezone` (`0017`) | `communities.timezone` (`0004`) | Drop ours, read theirs |
| `module_catalogue` + `community_modules` (`0011`, `0017`) | `feature_catalog` + `community_features` (`0004`) | Same ten keys, same concept. Theirs wins on name; **ours carries `sort_order`, `backend_status`, `backend_note`, and per-key `updated_at`/`updated_by`, which theirs lacks** — add those as columns on theirs. |
| `registration_requests` (`0012`) | `community_registration_requests` (`0004`) | Theirs wins on name; check column coverage |

Note their `feature_catalog` defaults differ from ours on one key: they seed
`maintenance-billing` **enabled**, we seed it from `onboardingModules.js` — worth one line of
verification against the frontend when we get there.

### C-6 🟡 `roles.py` is a true two-sided merge conflict

The only Python file where both sides edited the same lines.

- **They** renamed `Role.TECHNICIAN` → `Role.WORKER` and added a `parse_role` normaliser mapping
  `TECHNICIAN`/`SERVICEMAN` → `WORKER`.
- **We** added `_DISPLAY_ROLE` and `display_role()` — whose table still contains `"TECHNICIAN"`.

Both changes are wanted. The merge is small and mechanical: take their rename and normaliser, keep
our `display_role`, re-key the display table to `WORKER`.

`core/exceptions.py` also differs but **only because we extended it** (three extra handlers unifying
the error envelope). That is a clean fast-forward, no conflict. Every other shared Python file is
**identical modulo line endings** — the auth team did not touch them.

### C-7 🟡 Our API.md documents an invitation shape that no longer exists

`POST /admin/invitations` in `API.md` §4 documents `{ phone, apartment_id, full_name, role }`. Their
`schemas.py` now requires `{ community_id, intended_unit_id, phone, full_name, email }` — no
`apartment_id`, no `role`. Their `invitation_service.py` and `invitations_repository.py` changed with
it. **Our §4 is now wrong**, and it is the one section of `API.md` we did not write.

### C-8 🟢 Their own ERD and their own migration disagree

`docs/homebandhu_submission_erd.dbml` has 48 tables and **does not include `feature_catalog` or
`community_features`**, which `0004` creates and `0005` writes policies for. Minor, but it is exactly
the class of drift our D-section exists to catch, and worth telling them rather than silently
absorbing.

---

## 3. The decision this plan hangs on

Three of the sixteen collisions are not "rename and move on" — they are **different answers to the
same design question**, and only one can be in the database:

1. **Amenity occurrences** — wall-clock `date`+`time` (ours) vs `timestamptz` (theirs)
2. **Overlap and capacity** — scoped exclusion + advisory lock (ours) vs blanket exclusion (theirs)
3. **Complaint routing and SLA** — category/department/`due_at` (ours) vs work orders (theirs)

**Recommendation: their schema is the base; ours becomes additive on top of it.**

Reasons, in order of weight:

- **Theirs is merged to `main` and ours is not.** Reversing that means asking another team to drop
  1,831 lines of shipped work; making ours additive costs us rewriting SQL that has never run.
- **Neither has been applied to a database**, so both are equally unproven — but theirs is the one
  the rest of the team, the new ERD and the frontend documentation now describe.
- **Their model is broader where it overlaps least with us** — work orders, visitors, notifications,
  audit events, media assets, policies are all things we never built and the product needs.
- **Our value survives the move.** What we actually contributed is the **API layer** — 70
  documented operations, 275 tests, the DTO/vocabulary translation to the frontend's exact shapes —
  plus the surfaces they have no answer for: billing settings and the maintenance amount (A13),
  complaint categories and SLA, amenity settings beyond their 6-field `amenity_rules`, module
  metadata, and the settings screen. Those become **additive migrations `0018`+**.

**Three exceptions where I recommend we push back rather than adopt:**

- **C-3, the blanket exclusion constraint, must be fixed.** Not our preference — their `capacity`
  column is unreachable as written. This is a bug report with a patch attached.
- **`community_memberships` needs `unique (id, community_id)`** added. One line, no behaviour change,
  and it is what lets any cross-tenant composite FK exist at all.
- **`amenity_booking_occurrences` should keep a wall-clock representation** (or a generated one), for
  the reason in D7: "07:00" must survive somebody correcting the community timezone. Now that
  `communities.timezone` exists, a generated column can bridge both.

---

## 4. Implementation plan

Seven phases. Each ends somewhere the suite is green, so the work can stop between any two.

### Phase 0 — Get the two trees into one repo *(no code changes)*

1. `git fetch origin` in our working tree; confirm `0fffb68`/`32dbb49` are reachable.
2. Commit our current work on `backend/planning/1` **first**, so the reconciliation is a reviewable
   diff and not an unrecoverable mix of two teams' edits. *(Nothing has been committed this whole
   workstream — this is the moment that stops being safe.)*
3. Merge `origin/main`. Expect conflicts in exactly three files: `app/domain/roles.py` (C-6),
   `.gitignore`, and `backend/pyproject.toml`. Take theirs for the venv/gitignore changes.
4. **Do not** delete our `0010`–`0017` yet. They are the specification for phases 3–5.

### Phase 1 — The auth seam *(small, unblocks everything)*

5. Merge `roles.py` by hand: their `WORKER` + normaliser, our `display_role`, display table re-keyed.
6. Rewrite `get_caller_community_id()` against `community_memberships` (C-1). Add the multi-community
   case explicitly — their `is_default_community` flag is the right tiebreak, and our current
   single-value read has no answer for a person in two communities.
7. Add a role/status vocabulary layer for their two enums (lowercase `membership_role`,
   `membership_status` with `pending`/`ended`) alongside our existing `Role`. `vocabularies.py` is
   already the home for exactly this.
8. Fix `API.md` §4 to their invitation shape (C-7).

### Phase 2 — Decide and confirm the base *(gate)*

9. Take §3's decision. If it lands as recommended, the three push-backs go to the auth team as a
   short patch proposal — ideally a `0006` they own, not a `0018` we own, because
   `community_memberships` and `amenity_booking_occurrences` are theirs now.

### Phase 3 — Rewrite our views onto their tables

**This is where the leverage is.** Our 12 views are the seam between their schema and our API. Rewrite
the views, and most of `services/` and all of `domain/` survive untouched.

10. `department_overview`, `department_staff_overview` → their `departments` + `staff_assignments` +
    `skills`.
11. `complaint_overview` → their `complaints` + `complaint_events` (+ `work_orders` for assignment).
12. `invoice_overview`, `payment_overview`, `collection_summary` → their `invoices`/`payments`,
    deriving `isOverdue` rather than reading their stored `overdue` enum value (D6 still stands).
13. `amenity_overview`, `amenity_booking_overview`, `amenity_ledger_overview`,
    `amenity_ledger_summary` → their amenity tables.
14. `community_settings_overview`, `community_module_overview` → their `communities.timezone` +
    `feature_catalog`/`community_features`, plus our additive columns.

### Phase 4 — Additive migrations `0018`+ for what they have no answer for

15. `0018_billing_settings.sql` — `community_billing_settings` and the maintenance amount (A13),
    unchanged in substance from `0015`'s section.
16. `0019_complaint_taxonomy.sql` — `complaint_categories`, `department_categories`, `sla_hours`,
    `due_at` and `complaint_due_at()`, attached to **their** `complaints` and `departments`.
17. `0020_amenity_settings.sql` — our ~30-field `amenity_settings`, as a superset beside their
    6-field `amenity_rules` (D7 point 1 argument is unchanged and now applies to a real table).
18. `0021_module_metadata.sql` — `sort_order`, `backend_status`, `backend_note`, `updated_by` on
    **their** `feature_catalog`/`community_features`.
19. `0022_settings.sql` — what is left of `community_settings` once `timezone` moves out:
    `unit_label_singular`, `invite_ttl_hours`, `visitor_code_ttl_minutes`, the two policy toggles,
    `version`.
20. Re-add our complaint side-tables (`complaint_comments`, `complaint_attachments`,
    `complaint_read_receipts`, `amenity_booking_guests` → check against their `booking_guests` first).

### Phase 5 — Rewrite the 9 direct writes, and re-home the RPCs

21. Convert the 9 direct `.insert()`/`.update()`/`.delete()` calls to RPCs (C-4), since their RLS
    grants no admin write anywhere.
22. Re-point our 32 RPCs at the renamed tables and their column names. Mechanical but broad.
23. Replace our `assert_community_admin` with their
    `current_user_has_community_role(community_id, array['admin'])` so there is **one** admin check in
    the database, not two.

### Phase 6 — Verify, and re-document

24. Run the suite. Expect real failures in `test_settings_mapping.py`, the department and money
    mapping tests, and anything asserting a vocabulary we have just changed.
25. Regenerate `openapi.yaml`; confirm 70 operations still stand or record deliberately dropped ones.
26. Update, in this order: `API.md` (§4 invitation shape, plus any changed field), `DECISIONS_NEEDED.md`
    (close §1.1, §1.2, C1, C2, C3, C6, D1, A10; **add** the new C-items for the three push-backs;
    rewrite D6/D7/D8 against the new ERD), `CHANGE_LOG.md` (Session 16), the build plan's five-gate
    table, and `FRONTEND_MEETING_AGENDA.md` if any wire shape moved.

---

## 5. What this costs, honestly

**Survives unchanged:** all 9 DTO modules (`domain/*_schemas.py`), `vocabularies.py`,
`formatting.py`, `pg_errors.py`, `common_schemas.py`, the 7 routers, most of `services/`, and the
error-envelope work in `exceptions.py`. That is the bulk of the 70 documented operations.

**Needs rewriting:** 12 views, 32 RPCs, 9 direct writes, `get_caller_community_id`, and the parts of
7 `repositories/` modules that name a renamed table. Call it **the SQL layer and a thin slice of the
repositories.**

**At risk of being lost, and needing a product answer:**

- **Our SLA engine** (A1/A2/A3) — their model has no `due_at`. Phase 4 step 16 preserves it, but if
  they intend work-order due dates to replace complaint SLAs, that is a real product decision and
  three of our documented questions change meaning.
- **`isOverdue` derived vs stored** (D6) — their `invoice_status` enum contains `overdue`. Ours
  derives it. Both cannot be true; ours is right for the reason D6 gives, but theirs is in the ERD.
- **Amenity wall-clock times** (D7) — see §3.

**Not addressed by any of this, still open:** F1 (nothing applied to any database — now **more**
urgent, because there are two schemas' worth of unrun SQL), F2 (the Storage bucket — note they added
`storage.objects` policies for `community_media`, which may or may not cover our
`complaint-attachments`), F3 (rate limiting), F4 (concurrency).

---

## 6. What I need before implementing

1. **Confirm §3's direction** — their schema as the base, ours additive. If you would rather keep our
   amenity/complaint models and ask them to adapt, the plan inverts and phases 3–5 change completely.
2. **Confirm Phase 0 step 2** — may I commit our work on `backend/planning/1` before merging? Nothing
   has been committed this entire workstream, and merging 1,831 lines of someone else's SQL into an
   uncommitted tree of ours is the one step here that could lose work irrecoverably.
3. **Who takes the three push-backs to the auth team** — the blanket exclusion constraint (a real bug),
   the `(id, community_id)` unique constraint, and the wall-clock question. These are their tables now.
