# HomeBandhu — backend implementation plan

**Date:** 2026-07-29
**Supersedes:** the compromises in [`CONFLICT_RESOLUTIONS.md`](../CONFLICT_RESOLUTIONS.md) §8 that were
made on the assumption the frontend was a shipped product. See §1.
**Governing constraint:** the demo must run at the end of every phase.

---

## 1. What the demo framing changes

The frontend was built to run on seeded dummy data so the team could demonstrate progress. That makes
the operative constraint **"never break the demo"**, not **"never change the frontend"** — and those
are very different rules. Three of my earlier compromises existed only because I had the second one.

| Earlier position | Now | Why it changes |
|---|---|---|
| **R24** — ship `timeAgo: "2h ago"` beside the ISO instant, accepting an un-cacheable response class | **Dropped.** The API emits instants only; the frontend formats. | `timeAgo` is demo scaffolding, not a requirement. Keeping it forced `Cache-Control: no-store` on a whole response class and put the server's clock and locale into a client concern. That cost was only worth paying for an unchangeable frontend. |
| **R23** — every entity carries label *and* id, permanently | **Transition measure only.** Views emit both while a domain migrates; the duplication is removed in Phase 8. | `assignee: "Ramesh - Plumber"` and `apartmentId: "B-1204"` are seed conveniences. Freezing them into the API would make the demo's shortcuts permanent product debt. |
| **C1** — accept a nullable FK plus `assignee_label`, indefinitely | **Interim only.** Shadow accounts via `auth.admin.createUser` land in Phase 6 and the FK becomes real. | The blocker was that department staff have no accounts. Supabase can create an account for someone who never signs in, which turns a permanent retreat from referential integrity into a two-phase migration. |

**One position gets *stronger*, not weaker.** Never change `frontend/src/` without the frontend team.
Everything below that touches the frontend is written as a **work package** for them (§7), specified
precisely enough to hand over, and not something we do.

**And one earlier recommendation is reversed on the merits** — see C2 in §6.

---

## 2. Architecture: two seams, no bespoke API server

Everything the resolutions needed a "server layer" for is available in Supabase. The shape is:

```
React ─► repository module ─┬─► [mock]     seeded arrays  (demo mode, today)
                            └─► [supabase] supabase-js
                                              ├─► VIEWS  (security_invoker)  ── all reads
                                              └─► RPC    (security definer)  ── all writes
                                                     └─► tables + RLS + constraints
```

**Seam 1 — the repository module (client).** One module per domain, exporting the function signatures
the Zustand slices already call. Two implementations behind `VITE_DATA_SOURCE=mock|supabase`. This is
not a new idea imposed on the frontend: the component design §10 already commits to *"service
boundaries that can later be connected to backend APIs and a database without redesigning the
frontend pages"*, and `onboardingRegistrationService.js` is the first one. We are completing a pattern
the frontend already chose.

**Seam 2 — views and RPC (server).** Reads go through `security_invoker` views, which is where
`displayRole`, joined labels and computed fields live while RLS still evaluates as the caller. Writes
go through `SECURITY DEFINER` functions, which is where multi-table transactions, find-or-create and
string→id resolution live.

**No custom API server.** This resolves C3 — the resolutions that appeared to need one need a view or
a function instead.

### Supabase feature map

| Need | Supabase feature | Replaces / resolves |
|---|---|---|
| Authentication | Auth, OAuth + PKCE | `otp_challenges`, custom sessions |
| Tenant isolation | RLS with `auth.uid()` | app-layer filtering |
| `displayRole`, joined labels | `security_invoker` views | R17a, R23, C3 |
| Community registration as one transaction | `SECURITY DEFINER` RPC | R21, C3 |
| Optimistic concurrency | `PATCH ?id=eq.X&updated_at=eq.Y` → 0 rows = 409 | R3; no `version` columns |
| Cross-tab sync | Realtime `postgres_changes` | `store/sync.js` storage events |
| Attachments and avatars | Storage private buckets + signed URLs | `media_assets` already models it |
| Resident invitations | `auth.admin.inviteUserByEmail` | custom token mail |
| Staff without sign-in | `auth.admin.createUser` | **C1** |
| Recurring invoices, invite expiry | `pg_cron` | a cron server |
| Notification fan-out | Database Webhooks → Edge Function | polling |
| No double-booking | exclusion constraints (`btree_gist`) | app-side checks; **R14** |
| Migrations | Supabase CLI `supabase/migrations/` | ad-hoc SQL |
| Demo and local seeding | `supabase/seed.sql` + `db reset` | `frontend/src/data/*.js` |
| Client types | `supabase gen types typescript` | hand-written types |

**Edge Functions are used only where an external system is involved** — sending mail, a payment
gateway later. Business rules stay in the database where RLS can see them.

---

## 3. Demo continuity — the thing most likely to be forgotten

Two demo mechanisms break silently under a real backend. Both need a decision **before Phase 5**, not
after someone loses a demo.

1. **The hardcoded demo logins die.** `login(phone, otp)` matches `9876543210` → resident and
   `9999988888` → admin, and does not check the OTP. Under OAuth neither exists.
   **Plan:** `supabase/seed.sql` creates a demo community with the same content as
   `frontend/src/data/*.js`, and the presenter's real Google account is seeded as its admin. The demo
   becomes *more* impressive, not less — it is a real backend with real auth.
2. **`mock` mode stays shippable indefinitely.** `VITE_DATA_SOURCE=mock` remains a supported build,
   not a scaffold to delete. It is the offline demo, the fallback when the Supabase project is down
   mid-presentation, and the thing that keeps the seam honest — a repository interface with one
   implementation drifts.

---

## 4. Phases

Each phase ends with the demo working. Phases 0–2 do not touch the frontend at all.

### Phase 0 — Decide and scaffold *(no behaviour change)*

1. Settle the six product decisions in §8 and the two architecture decisions (C3 seam — agreed above;
   C4 destination — agreed below).
2. Resolve **C4**: fold the useful parts of the 63-table `homebandhu.dbml` draft into the v1 ERD as
   **v1.1**, then delete the draft. One schema description, not three. The v1 file is the base because
   the team owns it and continuity beats our draft's head start.
3. `supabase init`; commit `supabase/migrations/`, `supabase/seed.sql`, `config.toml`.
4. CI: `supabase db reset` on every PR, so a migration that does not apply from scratch fails fast.

**Gates —** Frontend: none. ERD: v1.1 becomes the single target. Class diagram: none yet.
Component design: none. Supabase: CLI and migration discipline established first, deliberately.

### Phase 1 — Schema v1.1 *(migrations only, nothing reads it)*

Apply the accepted resolutions as ordered migrations. **R1 must precede R21's code** — find-or-create
keys on `(building, label)`, and under the old community-scoped index the second block's "101"
collides with the first block's.

1. **R1** two partial unique indexes on `units`.
2. **R19** relax the four `communities` address columns; **R2** invite digests; **R28** + **C6** staff
   invites with the second partial index that closes the NULL-distinctness hole.
3. **R5** + **C2** `complaint_categories`; **R8** department columns and `staff_assignments.rank`;
   **R9** complaint columns and the three small tables — with `assigned_to_membership_id` **nullable
   plus `assignee_label`** for now (C1 interim).
4. **R17b** `departments.kind`; **R18** `community_memberships.title`; **R20** `map_x`/`map_y`;
   **R10** `community_modules`; **R13** amenity settings.
5. **R14** maintenance blocks — **and the exclusion constraint's predicate in the same migration**
   (C7). Split across two migrations, the feature ships looking complete and blocking nothing.
6. **R4** composite foreign keys on the six directly-read child tables.
7. **R3** one `set_updated_at()` trigger applied to every table.
8. **R16** phase-2 notes on the 12 orphans and on `community_registration_requests`.

**Gates —** Frontend: untouched, demo unaffected. ERD: this *is* the ERD change; +6 tables, ~33
columns, 0 deletions. Class diagram: update in the same PR — **R29** collapses five
`CommunityMembership` subclasses into one class with a `role` attribute, **R30** adds the attributes
that `reopen()`/`escalate()`/`resolve()` were missing. Component design: R32–R35 edits — strike the
non-existent `notifications` slice, mark per-tab sessions prototype-only, mark the separate-login-flows
and OTP lines superseded. Supabase: all schema arrives as CLI migrations from day one.

### Phase 2 — Tenancy, constraints, seed *(server-only, testable without a UI)*

1. `current_communities()` and `current_membership(community_id)` as `STABLE SECURITY DEFINER` helpers.
2. RLS on every table. Resident capability keys on an active `unit_residencies` row (**R17c**), not on
   `role = 'resident'`.
3. **R12** the `community_activity` view over `audit_events` — allow-list plus redacted projection,
   `security_invoker = true`.
4. `supabase/seed.sql` reproducing the demo dataset.
5. Tenant-isolation tests: for each table, a second community's user must read zero rows.

**Gates —** Frontend: none. ERD: policies annotated, no structural change. Class diagram: none.
Component design: none. Supabase: RLS is the entire authorization layer — no app-side filtering
anywhere, so a missing policy fails closed.

### Phase 3 — The seam *(frontend work package #1 — demo behaviour identical)*

Introduce `frontend/src/repositories/<domain>.js` with the mock implementation only, and switch the
Zustand slices to call it. **Zero behaviour change; every screen still runs on seeded arrays.**

This phase exists on its own precisely so that the refactor and the first real network call are never
in the same change — when the pilot domain misbehaves in Phase 4, the seam is already known-good.

**Gates —** Frontend: significant but behaviour-preserving; handed to the frontend team as §7-A.
ERD: none. Class diagram: none. Component design: §10's service-boundary commitment is finally
honoured — worth recording as met, not changed. Supabase: none yet.

### Phase 4 — Pilot domain: Notices *(first real data)*

Notices are the simplest domain — title, body, category, urgency, published_at, no cross-table
writes — which makes them the right place to prove views, RPC, RLS and types end to end.

1. `v_notices` view with joined author label.
2. `create_notice()` / `update_notice()` RPC.
3. `supabaseNoticesRepository`; `VITE_DATA_SOURCE` switches modes.
4. Run the demo in both modes and diff the screens.

**Exit criterion:** both modes render identically. If they do not, the seam is wrong and every later
domain would inherit it.

**Gates —** Frontend: repository implementation only, no page edits. ERD: none. Class diagram: none.
Component design: §7 unchanged in substance. Supabase: first view + RPC + generated types.

### Phase 5 — Registration and the authenticated entry flow

The one flow that cannot stay mock, because the OAuth session is what everything else is scoped by.

1. `register_community()` RPC — community, buildings, modules, admin membership, **R21
   find-or-create** for the founding admin's unit, all in one transaction. Idempotent on the
   authenticated account id.
2. The post-auth registration check: active membership → dashboard; none → `/get-started`.
3. Seed the demo admin's OAuth identity.

**Gates —** Frontend: `onboardingRegistrationService.js` gets its real implementation — the file's own
comment anticipates this, so it is completion, not conflict. ERD: none beyond Phase 1. Class diagram:
none. Component design: §2's *"after OTP confirmation"* already struck in Phase 1. Supabase: Auth,
RPC, RLS all load-bearing together for the first time.

### Phase 6 — Core domains, in dependency order

Residents and invites → departments and staff → complaints → visitors → amenities and bookings →
payments and invoices. One domain per PR, demo green after each.

**C1 closes here.** When an admin adds department staff, the backend creates a shadow account with
`auth.admin.createUser`, so `assigned_to_membership_id` becomes a real FK and `assignee_label` is
dropped. The free-text assignee input becomes a select over department staff (§7-B).

**Gates —** Frontend: per-domain repository implementations plus the §7-B edits. ERD: none beyond
Phase 1 — if a domain needs a column here, Phase 1 missed something and that is worth noticing.
Class diagram: none. Component design: none. Supabase: `auth.admin.createUser`, Storage for complaint
and visitor attachments, `pg_cron` for invoice generation and invite expiry.

### Phase 7 — Realtime and Storage

Replace `store/sync.js` with Realtime `postgres_changes` subscriptions. The component design §10
describes *"listen for browser storage events and rehydrate"*; the same sentence describes Realtime
with the transport swapped, and it starts working **across devices**, not just across tabs — which is
what the requirement always meant.

**Gates —** Frontend: `sync.js` replaced, §7-C. ERD: none. Class diagram: none. Component design: §10
transport sentence updated. Supabase: Realtime, Storage signed URLs.

### Phase 8 — Retire the scaffolding

1. Drop `assignee_label` and the R23 label duplication from the views once the frontend reads ids.
2. Remove `timeAgo` and every other pre-formatted date from responses (§7-D).
3. Empty states (**R27**) — a real founding admin sees zero of everything, and the dashboard has never
   once rendered that.
4. Keep `mock` mode. Delete nothing that the offline demo needs.

---

## 5. Order of the first five PRs

1. `supabase init` + CI `db reset` *(Phase 0)*
2. ERD v1.1 as migrations 001–00n, class diagram and component design edits in the same PR *(Phase 1)*
3. RLS, helpers, `seed.sql`, isolation tests *(Phase 2)*
4. Repository seam, mock only *(Phase 3 — frontend team)*
5. Notices end to end *(Phase 4)*

Nothing after PR 5 should start before PR 5 is green in both modes.

---

## 6. Disposition of every conflict

| ID | Disposition | Phase |
|---|---|---|
| R1, R2, R4, R5, R8–R10, R13, R14, R16–R20, R28 | As written | 1 |
| R3 | As written — native PostgREST filtered PATCH, no `version` columns | 1 |
| R6, R7, R11, R15, R22 | As written; R11/R15/R22 cost nothing | 1 |
| R12 | As written — view over `audit_events` | 2 |
| R21 | As written; **must follow R1** | 5 |
| R23 | **Downgraded to a transition measure**, removed in Phase 8 | 4–8 |
| R24 | **Dropped.** ISO instants only; frontend formats | 8 / §7-D |
| R25, R26, R27 | R26 by `community_modules`; R25 and R27 in §7 and §8 | 6–8 |
| R29–R31 | Class diagram edits alongside Phase 1 | 1 |
| R32–R35 | Component design edits alongside Phase 1 | 1 |
| **C1** | Interim nullable FK + label in Phase 1; **closed** by shadow accounts | 1 → 6 |
| **C2** | **Recommendation reversed — see below** | 0 (decision), 1 |
| **C3** | Resolved by views + RPC | 2–4 |
| **C4** | Resolved by folding the draft into v1.1 and deleting it | 0 |
| **C5** | Re-run the frontend checks at the head of each phase | ongoing |
| **C6, C7** | Folded into the Phase 1 migrations that create the problem | 1 |
| **C8** | Product decision — §8 | 0 |
| **C9** | Accepted; reparentable later | 5 |

### C2 — I am reversing my own recommendation

I proposed a `department_categories` join table because the UI's multi-select permits two departments
to claim "Plumbing". Having thought about what that means rather than only what it permits: **with
many-to-many, "which department's SLA applies to this complaint?" has no answer.** The routing rule
and the SLA both need exactly one owner, and the join table would push that ambiguity into every
complaint the system ever files.

**Recommend one-to-many** — `complaint_categories.department_id` stays single-valued — with the UI
disabling categories another department already claims. That is a smaller schema *and* a smaller
frontend change than the join table, and the demo's multi-select is most likely scaffolding rather
than a considered decision.

**It is still a product decision, not mine.** If a category genuinely needs two departments, the join
table is in §8 waiting, and the SLA question has to be answered before it is built.

---

## 7. Frontend work packages

Specified for the frontend team. **None of this is ours to implement.** Ordered by phase; each is
independently takeable.

**A — the repository seam** *(Phase 3, largest)*. `repositories/<domain>.js`, mock implementation from
the existing seeds, slices call it, `VITE_DATA_SOURCE` flag. Behaviour must be bit-identical.

**B — assignee becomes a select** *(Phase 6)*. `Complaints.jsx:175` is a free-text input; make it a
select over department staff. Also `DepartmentDetail.jsx:217` recovers a name with
`assignee.split(' - ')[0]` — that string parsing goes away when the id is available, which it must,
because Phase 1 splits the frontend's mixed `staff[].role` into `rank` and `job_title` and the
reconstructed string would otherwise stop matching.

**C — Realtime replaces `sync.js`** *(Phase 7)*. Same rehydrate call, different transport.

**D — dates and ids** *(Phase 8)*. Format relative times client-side from ISO instants; read
`assigneeId` / `unitId` instead of display strings.

**E — empty states** *(Phase 8)*. Every list needs a zero-rows rendering. This is the first thing a
real founding admin sees.

---

## 8. Decisions needed before Phase 1

Each will otherwise be decided by default, which is the worst way to decide any of them.

1. **C2** — one department per complaint category, or many? *(Recommend one; blocks R5.)*
2. **C8** — do staff invitations need a second factor, like the resident invite token? *(Currently
   email-match at first sign-in, weaker than residents, and only by side effect.)*
3. **R19** — add an address step to onboarding, or accept invoices with no issuer address?
4. **R31** — may one person hold active residencies in two communities?
5. **R16** — work orders and workforce: confirm phase 2, or cut the 10 tables?
6. **R16** — policies: no requirement references them at all. Keep or cut?
7. **R25** — Settings' billing and late-fee toggles: build, or mark coming soon? *(They currently look
   functional and silently discard the user's intent.)*
8. **C4** — confirm v1.1 as the single schema, and that `homebandhu.dbml` gets deleted.
