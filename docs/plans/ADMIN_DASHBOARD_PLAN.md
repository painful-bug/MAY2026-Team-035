# Admin Dashboard — backend plan

**Status:** plan of record, 2026-07-29. Authentication is assumed done (OAuth, Supabase-managed);
this document starts from *"an admin has a valid session and has landed on `/admin`"*.
**Audience:** backend team.
**Method:** derived by reading the ten admin surfaces in `frontend/src/`, then checking each against
`erd/homebandhu.dbml`, both `.puml` files and `design-of-components.md`.

**Artifact ownership note.** The ERD, class diagrams and component design are being maintained by
other teammates. Nothing in this plan edits them. Where a change to those artifacts is required, it
is *listed here as a request* (§7) rather than applied.

---

## 1. The surface

`AdminLayout` defines ten nav items. Everything the admin dashboard does hangs off these:

| # | Nav item | Route | Reads | Writes |
|---|---|---|---|---|
| 1 | Dashboard | `/admin` | `users`, `pendingRequests`, `complaints`, `payments`, `activities` | — |
| 2 | Pending Registrations | `/admin/pending` | `pendingRequests` | `acceptRequest`, `rejectRequest` |
| 3 | Residents | `/admin/residents` | `users`, `invitations` | `addResident`, `editResident`, `removeResident`, `issueInvite` |
| 4 | Admins | `/admin/admins` | `users` | `addAdmin` |
| 5 | Departments | `/admin/departments` | `departments`, `complaints` | `createDepartment`, `updateDepartment`, `setDepartmentStatus`, `deleteDepartment` |
| 5b | Department detail | `/admin/departments/:id` | `departments`, `complaints` | `updateComplaint`, `addComplaintComment` |
| 6 | Amenities Management | `/admin/amenities` | its own 4 stores | its own 4 services |
| 7 | Notices Board | `/admin/notices` | `notices` | `addNotice` |
| 8 | Complaints | `/admin/complaints` | `complaints` | `updateComplaint`, `addComplaintComment` |
| 9 | Maintenance Payments | `/admin/maintenance` | `payments`, `users` | — (read-only today) |
| 10 | Settings | `/admin/settings` | — | — (see §6.5) |

Amenities is not one surface among ten — it is a subsystem of its own with six pages, four stores
and four service modules. It is scoped separately in §5.

---

## 2. Cross-cutting decisions

These apply to every endpoint below and should be settled before any of them is written.

### 2.1 The dashboard aggregate is a server concern

`AdminHome` computes every headline number client-side by downloading whole collections and counting
them — residents, pending requests, active complaints, and a collection percentage summed across all
payments. That is fine for seeded arrays and untenable for a real community.

**Decision:** `GET /api/v1/dashboard/admin` returns the counts and the collection summary
pre-computed. The client stops holding `users`, `payments` and `complaints` just to produce four
integers.

### 2.2 Every list endpoint is paginated and filtered server-side

Residents, complaints, payments and notices are all filtered and searched client-side over the full
array today. Each needs `?cursor=&limit=&q=&status=` with opaque cursors, per `BACKEND_PLAN.md`.
The admin search box in the layout maps to `GET /search`.

### 2.3 Send timestamps, never relative strings

`complaints[].timeAgo` (`"2h ago"`) and `notices[].timeAgo` (`"Today"`) are pre-rendered display
strings, and `notices[].date` is `"July 8, 2026"` — a formatted string, not a date. The API sends
ISO-8601 instants; the client formats. Otherwise the value is wrong the moment it is cached.

### 2.4 Money crosses the wire as integer minor units

`payments[].amount` is `4250` meaning ₹4,250 — a plain number in major units. Per `BACKEND_PLAN.md`
§3.5 the DB stores `numeric(12,2)` and the DTO boundary converts to integer minor units. This is a
conversion at the serialiser, and the frontend will need to divide; flag it early because it silently
looks like a 100× bug if discovered late.

### 2.5 Labels are not identifiers

The frontend joins on human labels throughout: `complaints[].flat` is `"B-1204"`,
`departments[].head` is `"Ramesh Kumar"`, `complaints[].assignee` is `"Ramesh - Plumber"`,
`payments[].tower` is `"B"`. Every one of these is an FK in the schema. The API returns **both** —
the id for correctness and a denormalised label for display — so the UI keeps rendering what it
renders without a lookup table.

### 2.6 RLS is the enforcement boundary, not the router

Every admin endpoint is scoped by `community_id` from the token claim. `ProtectedRoute` checking
`role === 'Admin'` is a UI convenience and must never be the only thing standing between a resident
and `/admin/residents`. Management-only fields (`complaints.management_notes`,
`amenity_booking_series.internal_notes`, `complaint_comments.visibility = 'internal'`) are excluded
by policy, not by the serialiser.

### 2.7 Optimistic concurrency

Every mutable aggregate in the ERD carries a `version` column. Admin edits (`editResident`,
`updateDepartment`, `updateComplaint`) send `If-Match`/`version` and get `409 VERSION_CONFLICT`.
Two admins editing the same department is an ordinary occurrence, not an edge case.

### 2.8 Activity feed

`addActivity()` currently writes to localStorage. It maps to `activity_events`, which is deliberately
**not** `audit_events` — one is a product surface that can be filtered and redacted, the other is an
append-only compliance log. Mutating endpoints write both.

---

## 3. Phasing

Ordered by dependency, then by how much of the dashboard each phase lights up.

| Phase | Scope | Done when |
|---|---|---|
| **A. Read-only shell** | `GET /dashboard/admin`, `GET /communities/current`, `GET /auth/me`; residents list; notices list | The dashboard renders real numbers for a real community; a resident's token on any of these returns 403 |
| **B. People** | Residents CRUD + invitations; pending registration requests approve/reject; admins list | Approving a request creates the resident **and** the first invoice in one transaction; a double-approve is rejected |
| **C. Complaints** | Categories, list, detail, status transitions, comments, assignment, read-state | SLA computed server-side at submission; internal comments invisible to a resident token; assignment routes by category → department |
| **D. Departments + staff** | Department CRUD, staff assignment, the provisioning path that turns a staff record into a login | A department cannot be archived while it owns unresolved complaints; a staff member can actually sign in |
| **E. Money** | Invoices, payment recording, the maintenance view | Invoice liability attaches to the unit; a replayed provider webhook is a no-op |
| **F. Amenities** | The whole subsystem — §5 | Overlapping bookings rejected by the exclusion constraint, not app code; refund cannot exceed remaining deposit |
| **G. Settings** | Whatever §6.5 resolves to | — |

A, B and C are the spine. D unblocks the staff dashboards. E and F are independent of each other
once B lands — that is where the team parallelises.

---

## 4. Per-surface contracts

### 4.1 Dashboard home

```
GET /api/v1/dashboard/admin
→ { residentsCount, pendingRequestsCount, activeComplaintsCount,
    collection: { currentMinor, targetMinor, percent, currencyCode },
    recentActivity: [ { id, message, activityType, actor, occurredAt } ],
    recentPendingRequests: [ … ]  // the home page shows the first three
  }
```

The page also renders a hardcoded `"+2 this week"` trend next to the resident count. Either compute a
real week-over-week delta or drop it — a fabricated trend beside three real numbers is worse than no
trend. **Recommend computing it**; `community_memberships.activated_at` already supports it.

### 4.2 Pending registrations

Backed by `access_requests`. Approval is the interesting operation: per `design-of-components.md` §3
it must create the resident account **and** an initial maintenance invoice in the same transaction —
which is exactly what `acceptRequest` does today in one `set` across three slices.

```
GET  /api/v1/registration-requests?status=pending
POST /api/v1/registration-requests/{id}/approve   → { residency, invoice }
POST /api/v1/registration-requests/{id}/reject    { reason }
```

`access_requests.resulting_invite_id` and `.resulting_invoice_id` already exist for this. Approve is
a compare-and-set on `status` so two admins clicking at once cannot both win.

### 4.3 Residents

```
GET    /api/v1/residents?cursor=&limit=&q=&status=
POST   /api/v1/resident-invitations      { name, email, unitId, phones[] }
PATCH  /api/v1/residents/{id}            { … , version }
DELETE /api/v1/residents/{id}
GET    /api/v1/invitations
POST   /api/v1/invitations/{id}/renew
POST   /api/v1/invitations/{id}/revoke
```

Two behaviours in `addResident` need a decision rather than a translation:

- It builds `apartmentId` as `` `${tower}-${flatNumber}` `` — a **string key**, and creates the flat
  implicitly by naming it. Server-side the unit must exist or be created deliberately. This is the
  same create-on-first-reference question the registration flow raised.
- It creates **one user record per phone** and mints **one invite covering all of them**. The ERD
  already decided against this (`resident_invites`: *"one membership per redemption"*). The admin UI
  therefore needs to either issue N invites or accept that only the primary contact is activated.
  **Recommend N invites**, one per phone, grouped in the response so the UI can still show them
  together.

### 4.4 Admins

`addAdmin` appends a user with `role: 'Admin'`. Note this creates a **record, not a login** — the
same provisioning gap as department staff (§4.5).

**This surface conflicts with the schema.** The ERD carries a partial unique constraint of one
active admin per community, and `communities.active_admin_membership_id` is singular; the class
diagram states the invariant as *"every ACTIVE community has exactly one"*. But the frontend has an
Admins **list** page that adds unlimited admins.

Both are defensible; they are answering different questions. The resolution is to separate them:

- `communities.active_admin_membership_id` = **the owner** — one, transferable, the account
  ultimately responsible for the community.
- `community_memberships.role = 'admin'` = **an administrator** — many, each with the admin shell.

Under that reading the singular constraint stays (on the owner) and the plural page is legal. It
needs the "one active admin per community" partial UQ to be dropped from `community_memberships`.
Logged as a request in §7.

### 4.5 Departments and staff

The largest structural gap in the dashboard.

Frontend shape:

```js
{ id, name, description, categories: ['Plumbing'], head: 'Ramesh Kumar',
  email, phone, operatingHours: { start: '08:00', end: '20:00' }, slaHours, status,
  staff: [ { id, name, phone, role: 'Supervisor' | 'Technician' } ],
  createdAt, updatedAt }
```

Four translations:

1. **`staff[]` is embedded; the schema has `staff_assignments`** joined to `community_memberships`.
   The API returns it nested so the UI is unchanged, but it is a join.
2. **`staff[].role` mixes two axes.** `"Supervisor"` is a **rank**; `"Technician"` is a
   **job_title**. `BACKEND_PLAN.md` §3.10 already separates these. The DTO must emit both and the
   admin UI eventually needs two fields — until then, derive: known ranks map to `rank`, everything
   else is `job_title` with `rank = 'worker'`.
3. **`head` is a name string**, not an FK. Return `headMembershipId` plus `headName`.
4. **`categories[]` are strings**; the schema has `complaint_categories` as rows, because they are
   admin-editable and therefore cannot be an enum. Routing is category → department → SLA.

```
GET    /api/v1/departments
POST   /api/v1/departments
GET    /api/v1/departments/{id}
PATCH  /api/v1/departments/{id}
DELETE /api/v1/departments/{id}
PATCH  /api/v1/departments/{id}/status
POST   /api/v1/departments/{id}/staff
PATCH  /api/v1/departments/{id}/staff/{staffId}
DELETE /api/v1/departments/{id}/staff/{staffId}
```

Rules the endpoints enforce, not the UI: a department cannot be archived while it owns unresolved
complaints; the §3.10 rank cardinality (one manager per department; a manager or supervisor serves
exactly one department; a worker may serve several); and any change to someone's department or rank
bumps `claims_version` so a demoted supervisor does not keep their access until token expiry.

**The provisioning gap.** Adding staff here creates a record with a phone and no account. Nothing
turns it into a login. That is the missing half of every staff dashboard, and it belongs to this
surface because this is where staff are created. **Recommend:** `POST /departments/{id}/staff`
creates the membership with `role = 'staff'` plus the assignment, and issues an invitation through
the same mechanism as residents. Until that exists, phase D is not done.

### 4.6 Notices

The simplest surface, and the one with a hidden requirement. Frontend `addNotice` takes
`{ title, description, urgency, category }` and shows every notice to everyone. The ERD carries
`audience_type` (`all | building | role`) with `audience_building_id` and `audience_role`, and the
requirement that **a notice targeted at one building is invisible to the others at the RLS layer,
not filtered in the client.**

So the table is ahead of the UI. Ship the audience columns, default `audience_type = 'all'`, and the
current UI keeps working unchanged while the policy is already correct for when targeting arrives.

```
GET  /api/v1/notices?cursor=&limit=
POST /api/v1/notices   { title, body, category, urgency, audienceType='all', publishedAt, expiresAt }
```

### 4.7 Complaints

The richest read surface. Frontend fields: `title`, `description`, `raisedBy` (name), `userId`,
`flat` (label), `date`, `timeAgo`, `category` (string), `status`, `assignee` (free text
`"Ramesh - Plumber"`), `progress` (0–100), `urgency`.

```
GET   /api/v1/complaints?cursor=&limit=&status=&departmentId=&categoryId=&q=
GET   /api/v1/complaints/{id}
PATCH /api/v1/complaints/{id}          { status?, progress?, assignedToMembershipId?, managementNotes?, version }
POST  /api/v1/complaints/{id}/comments { body, visibility }
PUT   /api/v1/complaints/{id}/read-state
```

Notes:

- **`assignee` is free text and must become an FK.** Return `assignedToMembershipId` +
  `assigneeName` + `assigneeJobTitle` so the existing `"Ramesh - Plumber"` string can be composed
  client-side without losing the reference.
- **`sla_due_at` is computed server-side** at submission from urgency + category SLA, never
  client-supplied.
- **`management_notes` and internal comments are staff-only** — enforced by policy.
- `progress` is a smallint the admin sets directly; the department detail page is where it moves.
- The department detail page shows a complaint timeline — that is `complaint_events`, which the
  schema already has.

### 4.8 Maintenance payments

Read-only in the UI today, which makes it the cheapest real surface to ship — but the semantics
differ from the frontend's model in one important way.

Frontend `payments[]` rows carry `userId`, i.e. **a person owes the money**. The ERD attaches
invoices to `unit_id` — *"invoice liability belongs to the unit, not to a person, so a resident who
moves out does not take the debt with them."* The schema is right and the DTO adapts: return
`unitId` + `unitLabel` + the current primary contact as `payerName`, so the table renders as it does
now while the debt stays attached to the flat.

Also: one frontend `payment` row conflates three schema concepts — `invoices`,
`invoice_line_items` and `payments`. The list endpoint returns invoices with a computed
`outstandingAmountMinor`; the payment records hang off them.

```
GET /api/v1/invoices?cursor=&limit=&status=&unitId=
GET /api/v1/invoices/{id}
```

---

## 5. Amenities (phase F)

Six pages, four Zustand stores and **four service modules that already exist as async boundaries** —
`amenitiesService`, `amenityBookingsService`, `amenityLedgerService`, `amenityReportsService`. That
is the cleanest seam in the whole frontend and it maps almost directly onto four endpoint groups:
catalog, bookings/approvals, ledger, reports.

The schema work is already done and is unusually careful — it is worth not undoing it:

- `booking_mode` (granularity) and `exclusivity` (sharing policy) are **separate axes**. Collapsing
  them is what created the "two amenity models" problem in the first place.
- Overlapping occurrences are prevented by a **gist exclusion constraint**, not application code —
  and the check must also cover `amenity_blocked_slots`, or a booking can be created inside a
  maintenance window.
- The remaining refundable deposit is **derived** from `amenity_financial_events` and never stored,
  so it cannot drift. A refund can never exceed it.
- `internal_notes` is management-only and must not be selectable by a resident policy.

Because of its size, treat amenities as its own mini-plan rather than a section of this one. It
should not block C or D.

---

## 6. Things with no backing anywhere

Found by looking for the reverse mismatch — UI that implies a data model that does not exist.

### 6.1 Settings is a stub

Four `useState` toggles and a `showToast`. Nothing persists, nothing is read. The toggles imply
features that exist in no table: **automated monthly maintenance generation** (₹4,250 on the 1st),
**late-payment fines** (₹100 weekly after 10 days), gate-security rules, notice alerts.

Automated billing and fines are real features with real schema implications — a scheduled job, a
fine line-item type, a per-community rate. They are not settings toggles; they are a phase.

**Recommend:** ship Settings against `community_settings` with only what exists — timezone,
currency, invite TTL, visitor-code TTL, and the **enabled modules**. Everything else stays inert
until scoped.

### 6.2 Enabled modules are never editable

Onboarding step 3 tells the founder *"These features can be changed later from the Admin Settings
page."* No such control exists. `community_settings.enabled_modules` is written once at registration
and never again. Either build the control or remove the promise — this is a small, visible broken
promise on the first day of use.

### 6.3 The dashboard has no empty state

Every count comes from seeded arrays, so the dashboard has never rendered zeros. A genuinely new
community has no residents, no complaints, no payments and no activity. Not a backend obligation, but
the first admin will see it, so it belongs on someone's list.

---

## 7. Requests for the artifact owners

Not applied here — the ERD, class diagrams and component design are maintained elsewhere.

1. **Drop the "one active admin per community" partial UQ** on `community_memberships`, keeping
   `communities.active_admin_membership_id` as the singular *owner*. Reason: §4.4 — the frontend has
   a multi-admin page, and owner and administrator are different concepts.
2. **Add the staff-provisioning path** to the component design: creating a department staff member
   must be able to create their login, or no staff dashboard can ever be reached (§4.5).
3. **Confirm `complaints.assignee` → `assigned_to_membership_id`** is the intended direction, and
   that free-text assignment is not retained.
4. **Confirm invoice liability attaches to `unit_id`, not to a person** (§4.8) — the schema says so,
   the frontend assumes otherwise, and this is a semantic decision, not a mapping detail.
5. **Decide the resident-invite cardinality**: N invites for N phones, versus one invite activating a
   whole flat (§4.3). The ERD has already chosen N; the frontend has not.
6. **Scope or drop automated billing and late fines** (§6.1) before Settings is built.

---

## 8. Source files

| Surface | File |
|---|---|
| Shell, nav, search | [`layouts/AdminLayout.jsx`](../../frontend/src/layouts/AdminLayout.jsx) |
| Dashboard home | [`pages/AdminDashboard/AdminHome.jsx`](../../frontend/src/pages/AdminDashboard/AdminHome.jsx) |
| Pending registrations | [`pages/AdminDashboard/PendingRegistrations.jsx`](../../frontend/src/pages/AdminDashboard/PendingRegistrations.jsx) |
| Residents | [`pages/AdminDashboard/Residents.jsx`](../../frontend/src/pages/AdminDashboard/Residents.jsx) |
| Admins | [`pages/AdminDashboard/Admins.jsx`](../../frontend/src/pages/AdminDashboard/Admins.jsx) |
| Departments | [`pages/AdminDashboard/Departments.jsx`](../../frontend/src/pages/AdminDashboard/Departments.jsx), [`DepartmentDetail.jsx`](../../frontend/src/pages/AdminDashboard/DepartmentDetail.jsx) |
| Notices | [`pages/AdminDashboard/Notices.jsx`](../../frontend/src/pages/AdminDashboard/Notices.jsx) |
| Complaints | [`pages/AdminDashboard/Complaints.jsx`](../../frontend/src/pages/AdminDashboard/Complaints.jsx) |
| Maintenance | [`pages/AdminDashboard/Maintenance.jsx`](../../frontend/src/pages/AdminDashboard/Maintenance.jsx) |
| Settings | [`pages/AdminDashboard/Settings.jsx`](../../frontend/src/pages/AdminDashboard/Settings.jsx) |
| Amenities subsystem | [`features/amenities/`](../../frontend/src/features/amenities/) — 6 pages, 4 stores, 4 services |
| Store slices (the write surface) | [`store/slices/`](../../frontend/src/store/slices/) |
| Seed shapes (the DTO reference) | [`data/`](../../frontend/src/data/) |
