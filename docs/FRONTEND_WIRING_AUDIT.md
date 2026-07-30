# Frontend wiring audit — what our API surface is cut down to

**Date:** 2026-07-30 · **Against:** merge of `origin/main` @ `94556e5` into `backend/planning/1`
**Purpose:** PO instruction — *"all the other conflicts about the apis that we have implemented for which there
are no front end calls should be edited or removed such that there is all relevant connections and calls made
appropriately."* This is the evidence behind every removal.

---

## 1. The organising principle

After the merge there are two read paths and they overlap. Rather than judge each endpoint on its own, one rule
settles all of them:

> **Their snapshot is the read path. Our endpoints are the write path, plus the reads the snapshot cannot serve.**

This is coherent because of the SSE outbox (addendum C-13): every write of ours fires an
`AFTER INSERT/UPDATE/DELETE` trigger, which writes `sse_events`, which pushes `dashboard.refresh`, which makes the
frontend re-snapshot. So a write through our API updates the UI **without our API needing a matching read.**

Two exceptions, both verified rather than assumed:

- **`GET /dashboard/snapshot` stubs department staff.** `dashboard_service.py:203` builds every department as
  `{"staff": [], "categories": []}` — hardcoded empty lists. `Departments.jsx` (1 095 lines) and
  `DepartmentDetail.jsx` (713 lines) are built around staff rosters and per-department complaint queues. Our
  department reads are the only source, so they stay.
- **The snapshot has no `limit`, `cursor`, `q=` or `status=`.** It is a whole-community projection. Anything
  aggregated or filtered server-side (amenity ledger, amenity reports) stays.

## 2. Admin dashboard interaction audit

Method: for each page, which store actions it destructures, and whether the corresponding slice calls an API.
**Only `createOnboardingCompletionSlice.js` calls an API** — every other domain slice mutates local state only.
Since `appStore` no longer persists tenant data, those writes are lost on refresh today.

| Page | Interaction | Served by | Our endpoint |
|---|---|---|---|
| AdminHome | stat tiles, activity feed | snapshot | — *(ours removed)* |
| Residents | create invitation, list units | **their API** | — *(ours removed)* |
| PendingRegistrations | list / approve / reject | **their API** | — *(ours removed)* |
| Amenities — management | create / update / delete amenity | **their API** `/dashboard/amenities` | — *(ours removed)* |
| Amenities — bookings | 17 service fns, **0 API calls** | ✗ dead | **kept** (step 8) |
| Amenities — ledger | 5 service fns, **0 API calls** | ✗ dead | **kept** (step 8) |
| Amenities — reports | `amenityReportsService`, 0 API calls | ✗ dead | **kept** (step 8) |
| Admins | `addAdmin` | ✗ dead, **no endpoint existed** | **added** `POST /admins` |
| Complaints | `updateComplaint`, `addComplaintComment` | ✗ dead | **kept** (step 5) |
| Departments | `createDepartment`, `updateDepartment`, `deleteDepartment`, `setDepartmentStatus`, `removeStaffMember` | ✗ dead | **kept** (step 6) |
| DepartmentDetail | `assignTechnician`, `updateComplaint` | ✗ dead | **kept** (steps 5/6) |
| Notices | `addNotice` | ✗ dead, **no endpoint existed** | **added** `POST /notices` |
| Maintenance | filter only — read-only | snapshot | — *(ours removed)* |
| Settings | 4 toggles, `handleSave` only toasts | ✗ dead | **kept** (step 9) |

Resident side, for completeness: `payInvoice` (Payments) and `addPhoneToApartment` (Profile) are also dead.

**`payInvoice` must not be wired to `POST /invoices/{id}/payments`.** That endpoint marks money as *received* and
settles the invoice, so exposing it to the payer would let a resident clear their own dues by asserting they had
paid. It stays admin-only. Resident self-service needs a payment gateway whose webhook calls it — unbuilt, though
the baseline's `payments.provider` and `unique(community_id, idempotency_key)` now support it.

## 3. What was removed, and why

| Removed | Reason |
|---|---|
| `GET /dashboard/admin` | Their `/dashboard/snapshot` serves AdminHome. This was conflict C-2; resolved by deleting ours. |
| `GET /communities/current` | `GET /auth/session` already returns identity + membership + community. |
| `GET /residents` | `Residents.jsx` was rewritten into an invite-only form and no longer lists residents. |
| `GET /admins` | Snapshot `users[]` carries `role`; the page filters client-side. |
| `PATCH`/`DELETE /residents/{id}` | No edit or remove control survives on any admin screen. |
| `GET /registrations`, `POST /registrations/{id}/approve\|reject` | Duplicated their `/admin/access-requests` trio, which the frontend already calls. |
| `GET /notices` | Snapshot `notices[]`. |
| `GET /complaints`, `GET /complaints/{id}` | Snapshot `complaints[]`, with comments and history embedded. |
| `GET /complaint-categories` | `CreateDepartment.jsx` collects categories as **free-text inputs** (`useState([''])`), not from a vocabulary, and `Departments.jsx` reads `department.categories` off the department. Nothing fetches a category list. |
| `POST /complaints/{id}/attachments` | No upload control on any admin screen, and the Storage bucket is still unbuilt (F2). |
| `POST /complaints/{id}/read` | No read-receipt UI exists. |
| `GET /amenities`, `GET /amenities/{id}` | Snapshot `amenities[]`. |
| `POST`/`PATCH`/`DELETE /amenities`, `PATCH /amenities/{id}/status` | Their `/dashboard/amenities` already serves amenity CRUD and `amenitiesService.js` calls it. |
| `GET /invoices`, `GET /invoices/{id}`, `GET /payments` | Snapshot `payments[]` merges invoices and payments. |
| `GET /invoices/summary` | `Maintenance.jsx` computes its totals client-side. |
| `POST /invoices/{id}/void` | No void control on any screen. |
| `POST /maintenance-runs` | No caller and no scheduler. See the warning in §5. |
| `GET`/`PUT /settings/modules`, `PATCH /settings/modules/{moduleKey}` | Module selection exists only in onboarding, which writes their `community_features`. Ours duplicated it (C-11). |

That is **32 operations removed** — 87 total down to 59, of which 35 are ours and 24 theirs. It deletes conflict
C-2 outright.

Two survived on a judgement call rather than a caller, and both are flagged rather than buried. `POST /invoices`
and `POST /invoices/{id}/payments` have no UI caller, because the Maintenance screen is read-only. They are kept
because `GET`/`PUT /billing-settings` *is* called by the Settings screen, and settings that govern late fees and
maintenance amounts over a system with no way to issue or settle an invoice configure nothing at all. Deleting them
would have left the money domain with two config endpoints and no verbs.

## 4. What was added

Two dead frontend interactions had no endpoint anywhere. Both are small.

- **`POST /notices`** — `Notices.jsx` calls `addNotice({title, body, …})`. `notices` is a baseline table; step 3
  created it but never gave it a write path.
- **`POST /admins`** — `Admins.jsx` calls `addAdmin({name, email, phone, tower, flat})`.

`POST /admins` needs explaining, because the obvious implementation is wrong. Their invitation flow hardcodes
`intended_role = 'resident'` (`invitations_repository.py:40`) and `CreateInvitationRequest` has no role field, so
there is no way to invite an admin. Minting an admin-bound invite ourselves would duplicate their token machinery,
which is off-limits.

So `POST /admins` **promotes an existing member** — it matches the email to an active membership in the caller's
community and sets `role = 'admin'`. This is the flow `roles.md` actually describes (*"Resident -> Committee
members -> Admin"*), it needs no token minting, and it respects their `community_admin_one_active` index by
touching `community_memberships.role` rather than `community_admin_terms`.

Consequence to flag: it returns **404** when the email is not already a member, and the frontend's form invites you
to type any address. The fix belongs on the frontend — either pre-filter the field to existing members, or surface
the 404 as *"invite them first"*. Added to the meeting agenda.

## 5. Two consequences worth stating plainly

**Nothing creates a maintenance bill.** With `POST /maintenance-runs` removed, invoices only appear one at a time
via `POST /invoices`, and no screen calls that either — it survives solely so the resident `payInvoice` path has
something to pay. The Settings toggle *"Automated Monthly Maintenance"* therefore still switches a flag that no
code reads. That was already logged as A22 and it has not improved.

**The admin write surface is not reachable from the UI yet.** Every endpoint kept in §2 exists because a frontend
handler wants it, but that handler currently calls a Zustand action instead. Wiring them up is frontend work that
we are not permitted to do. Until then these endpoints are correct, tested, and uncalled — which is the honest
status, and the first item for the joint meeting.

**And almost none of them are runnable yet.** Migrations `0010`–`0017` targeted the schema the baseline replaced,
so they were quarantined to `backend/supabase/migrations/legacy-preauth/`. `0018_settings_on_baseline.sql` rebuilt
`community_settings`, `community_billing_settings` and the two `notices` columns — **tables only, no views and no
RPCs**. Counting honestly against a real baseline database, **3 of our 35 endpoints would run**:

| Runs today | Needs a rebuild first |
|---|---|
| `POST /notices` (0018 added the columns) | `GET`/`PUT /settings` — the two `community_*_overview` views live in `0017` |
| `POST /admins` (`community_memberships` is a baseline table) | `PUT /billing-settings` — needs the `update_billing_settings` RPC from `0015` |
| `GET /billing-settings` (reads the 0018 table directly) | the 9 department, 2 complaint, 2 remaining money and 16 amenity endpoints |

An earlier draft of this section claimed 0018 covered `GET`/`PUT /settings`; it does not, and 30 was an undercount.
The rebuild order and the one open design question (our booking series/occurrences versus their single
`amenity_bookings`) are in `legacy-preauth/README.md`.

**One piece of C-11 is still open.** `GET /settings` reports the module collection from *our*
`community_module_overview`, not from their `community_features`, so the duplication the module endpoints were
deleted to remove survives on the read side. Repointing that read finishes the job and removes `0017`'s module
tables from the rebuild entirely — left undone here because it changes which table is authoritative and the
onboarding workstream owns the writer.

## 6. Two things the dashboard workstream should change

Neither was edited here, because both are in files that workstream owns.

1. **`dashboard_service.py:203` stubs department staff** as `{"staff": [], "categories": []}`. Either fill it, or
   treat `GET /departments` as the supported source and drop the empty keys so the frontend cannot mistake them for
   "this department has no staff".
2. **`dashboard_service.py:202` drops `category` and `urgency` from notices.** `POST /notices` now stores both
   (migration 0018), so adding them to that projection is a one-line change that makes the Notices screen's two
   selects mean something.
