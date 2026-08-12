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
| Amenities — bookings | 17 service fns, **0 API calls** | ✗ dead | **wired 2026-08-12** (phase 7b) — `amenitiesApi.js`; 14 demo fns and 4 modules deleted, Edit Booking removed (no endpoint exists) |
| Amenities — ledger | 5 service fns, **0 API calls** | ✗ dead | **wired 2026-08-12** — ledger + summary + all five money writes |
| Amenities — reports | `amenityReportsService`, 0 API calls | ✗ dead | **wired 2026-08-12** — `GET /amenity-reports`, service deleted |
| Admins | `addAdmin` | ✗ dead, **no endpoint existed** | **added** `POST /admins` |
| Complaints | `updateComplaint`, `addComplaintComment` | ✗ dead | **kept** (step 5) |
| Departments | `createDepartment`, `updateDepartment`, `deleteDepartment`, `setDepartmentStatus`, `removeStaffMember` | ✗ dead | **kept** (step 6) |
| DepartmentDetail | `assignTechnician`, `updateComplaint` | ✗ dead | **kept** (steps 5/6) |
| Notices | `addNotice` | ✗ dead, **no endpoint existed** | **added** `POST /notices` |
| Maintenance | filter only — read-only | snapshot | — *(ours removed)* |
| Settings | 4 toggles, `handleSave` only toasts | ✗ dead | **kept** (step 9) |

Resident side, for completeness: `payInvoice` (Payments) and `addPhoneToApartment` (Profile) were also dead.
**Closed 2026-08-12 by phase 6**: the whole resident portal — home, complaints, visitors, payments, notices,
profile, and the amenities browse list — now reads and writes the API through
`frontend/src/features/resident/residentApi.js`; the demo slices' resident data writes are deleted. Issue 09
carries the page-by-page record; the one residual (the Amenities "Your Bookings" table) is named there.

**`payInvoice` must not be wired to `POST /invoices/{id}/payments`** — and it was not: the resident pages use
`POST /invoices/{id}/pay`, the resident-scoped simulator. The admin-side endpoint marks money as *received* and
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
| ~~`GET /complaint-categories`~~ | ~~`CreateDepartment.jsx` collects categories as **free-text inputs** (`useState([''])`), not from a vocabulary, and `Departments.jsx` reads `department.categories` off the department. Nothing fetches a category list.~~ **Reinstated 2026-08-11 by `skills_and_categories`** — both premises expired. `CreateDepartment.jsx` was deleted in `38927e5`, and the department form's category field is now a combobox that exists to prevent duplicate categories, which it cannot do without the list. The reinstated path is not the retired one: it carries each category's linked skill, so the form can warn about categories that match no trade and therefore reach no service person in any hiring search. |
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

> **Half of that expired on 2026-08-12.** `Maintenance.jsx:46` calls `POST /invoices` and `:201` calls
> `POST /invoices/{id}/payments`, so one bill at a time is now a thing a screen does rather than a thing only the
> resident path implies. What has *not* improved is the sentence's actual subject: nothing runs a **cycle**, and
> *"Automated Monthly Maintenance"* still switches a flag no scheduler reads. A22 stands unchanged.

**The admin write surface is not reachable from the UI yet.** Every endpoint kept in §2 exists because a frontend
handler wants it, but that handler currently calls a Zustand action instead. Wiring them up is frontend work that
we are not permitted to do. Until then these endpoints are correct, tested, and uncalled — which is the honest
status, and the first item for the joint meeting.

> **Overtaken between 2026-08-11 and 2026-08-12, and the freeze it rests on was lifted.** Phases 6 and 7 wired the
> resident portal, the amenity admin surface, the money writes and the work-order triage screen — §2's table above
> carries the per-row dates. `frontend_api_sweep.py` now reports **186 of 195 live operations reached by a call
> site**, and the nine it does not reach are the four OAuth redirects, `POST /auth/refresh`, the two SSE streams,
> `GET /worker/unavailability` and `/health` — none of them a screen's missing call. "Correct, tested and
> uncalled" is no longer the honest status; it was for two weeks, and this paragraph is why the wiring happened.

**The schema they need now exists.** An earlier draft of this section reported that 3 of our 35 endpoints could
run, because `0018_settings_on_baseline.sql` had rebuilt the settings *tables* but neither the views nor the RPCs.
Migrations `0019`–`0023` have since rebuilt the rest of the quarantined `0013`–`0017` onto the baseline:

| Migration | Replaces | Serves |
|---|---|---|
| `0019_departments_on_baseline.sql` | `0014` | the 9 department/staff endpoints |
| `0020_complaint_events_on_baseline.sql` | `0013` | `PATCH /complaints/{id}`, `POST …/comments` |
| `0021_money_on_baseline.sql` | `0015` | `POST /invoices`, `POST …/payments`, `PUT /billing-settings` |
| `0022_settings_views_on_baseline.sql` | `0017` views | `GET`/`PUT /settings` |
| `0023_amenities_on_baseline.sql` | `0016` | the 16 amenity endpoints |

Between them: 10 views, 24 write RPCs, and columns on 11 baseline tables. Every one of the 28 RPCs our
repositories call now exists in some migration, and every column they select exists on the table or view they
select it from — both verified statically with `pglast`, the real PostgreSQL parser, rather than by eye.

**That is not the same as "runnable", and the difference matters.** No migration has been applied to any database,
including `0001` itself. Nothing here has ever executed. The honest claim is that the SQL is complete, parses, and
matches the code's expectations — applying it is F1, and it is now the only thing between these endpoints and
working.

The rebuild also surfaced a bug that had nothing to do with migrations: `status_to_storage` mapped `Pending` and
`Reopened` onto values absent from the baseline's `complaint_status` enum, so every `PATCH /complaints/{id}`
carrying either would have failed with `22P02`. Its tests passed because they never reach a database. Fixed, with
a test that asserts every mapped value is a member of the enum.

**C-11 is closed.** `community_module_overview` is now a view over their `feature_catalog` and
`community_features` rather than module tables of ours, so there is exactly one place a module's enabled state
lives and the onboarding workstream owns the writer. `0017`'s module tables are permanently superseded rather than
pending a rebuild.

**The amenities design question is also settled**, and not the way this document previously implied. The updated
submission ERD (`db85c04`) removed `amenity_booking_series` and `amenity_booking_occurrences`, siding with the
baseline. `0023` keeps their single `amenity_bookings` as the only booking table and adds one nullable
`booking_group_id` column — which preserves atomic approval of a multi-date request without reintroducing the
tables upstream deleted. Reasoning in the header of `0023_amenities_on_baseline.sql`.

## 6. Two things the dashboard workstream should change

Neither was edited here, because both are in files that workstream owns.

1. **`dashboard_service.py` stubs department staff** as `{"staff": [], "categories": []}`. Either fill it, or
   treat `GET /departments` as the supported source and drop the empty keys so the frontend cannot mistake them for
   "this department has no staff".
2. **`dashboard_service.py` drops `category` and `urgency` from notices.** `POST /notices` now stores both
   (migration 0018), so adding them to that projection is a one-line change that makes the Notices screen's two
   selects mean something.

## 7. Join-request notifications: two bugs, not one missing feature

The dashboard was supposed to show a badge when someone asks to join, and did not. The cause turned out to be
two independent faults, on opposite sides of the "SSE outbox" assumption §1 is built on.

**The notification was never sent.** `AdminLayout.jsx` renders the sidebar badge from `pendingRequests.length`,
and `appStore.js` reads `snapshot.pendingRequests ?? []`. `DashboardSnapshot` had no such field. The frontend was
correct and complete; the key simply never appeared in the payload, so the badge could never render under any
conditions. Fixed by adding the field, the `pending_access_request_overview` view behind it, and the repository
read — **admin-only**, because those rows carry a third party's name, email and phone.

**The transport could not have scaled.** `event_stream` was a *synchronous* generator calling `time.sleep(5)`.
Starlette iterates sync generators in the anyio worker threadpool, so each connected admin pinned one of that
pool's 40 threads for the whole life of the stream — and since the pool is shared with all other synchronous
work, the 41st open dashboard would starve unrelated requests process-wide rather than merely lag. It also
polled once per client rather than once per process, and wrote the payload dict into the `data:` field as a
Python repr, which is not JSON and would have thrown in any client that tried to parse it.

`app/core/realtime.py` replaces the reader with one shared poller on a global cursor. Cost is one indexed query
per tick for the entire process regardless of viewer count, no connection holds a thread, and latency is 500ms
rather than 5s. Migration `0024` adds specific `access_request.created` / `.decided` topics carrying the live
pending count, so a client can *notify* instead of only re-fetching.

**One frontend change was needed and was made by explicit exception to the freeze.** `PendingRegistrations.jsx`
reads React Query (`['admin-access-requests']`), not the snapshot, so the SSE-driven re-snapshot never reached
it — the badge would have ticked up while the page behind it went stale. It now invalidates that key on the
`homebandhu:dashboard-refresh` window event `DashboardDataBootstrap` already dispatched. Four lines, no second
`EventSource`. This is the only frontend file this branch has touched.

**Also closed while in there:** `sse_events` had no RLS despite being reachable through PostgREST, so any
authenticated user could read every community's event stream — table names and community ids for tenants they
have no membership in. `0024` enables RLS with no policy, which denies everything except `service_role`, the
only role the backend ever uses to read it. It also bounds retention: twelve tables feed that outbox on every
row change and nothing had ever deleted from it.
