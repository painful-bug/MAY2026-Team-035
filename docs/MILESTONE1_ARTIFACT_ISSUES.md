# Milestone-1 artifacts — issue audit

**Date:** 2026-07-29.
**Sources audited** (all as-submitted, no edits applied by this audit):

| Artifact | File | Provenance |
|---|---|---|
| ERD / DBML | [`erd/homebandhu-v1-milestone1.dbml`](erd/homebandhu-v1-milestone1.dbml) | **byte-identical** to the supplied `er-dbml.txt` — verified with `diff` |
| Design of components | [`design-of-components.md`](design-of-components.md) | **byte-identical** to the supplied `design-of-component.txt` — verified with `diff` |
| Class diagrams | [`class-diagram/homebandhu-domain.puml`](class-diagram/homebandhu-domain.puml), [`homebandhu-architecture.puml`](class-diagram/homebandhu-architecture.puml) | restored from the git index — the teammates' staged versions |
| Frontend | `frontend/src/` | working tree, unmodified |

**Scale:** the v1 ERD defines **48 tables**.

---

## 0. The headline

The ERD and the class diagram are **consistent with each other** and were clearly written together —
same five-value role enum, same table set, same omissions. The problem is not that they disagree.
It is that **both describe a different product from the one the component design specifies and the
frontend implements.**

Three separate mismatches, in increasing order of cost:

1. **The schema is email-first; the product is phone-first.** `auth.users` has no phone column at
   all, `resident_invites.recipient_email` and `access_requests.applicant_email` are `not null`,
   while `profiles.phone_e164` is merely nullable-unique. Every implemented screen authenticates by
   phone. (Now partly overtaken by the OAuth decision, which makes email the identity again — but
   the invite and access-request paths are still phone in the UI.)
2. **The component design specifies features the schema has no columns for** — most acutely in
   complaints and departments, where the count of missing fields is 9 and 6 respectively.
3. **The schema specifies subsystems no requirement asks for and no screen uses** — 12 tables, a
   quarter of the ERD.

---

## 1. ERD / DBML

### 1.1 Internal defects — wrong regardless of any other document

| # | Issue | Consequence |
|---|---|---|
| 1 | **`units_community_label_uq` is `(community_id, unit_label)`** | "Flat 101" can exist **once per community**. A second block can never have a Flat 101. For any real apartment complex the schema is unusable as written. Should be scoped by `building_id`. |
| 2 | **`resident_invites` says *"do not store plaintext invitation tokens"* and provides no digest column** | The invitation cannot be verified at all. The note forbids the only mechanism the table offers. Self-contradicting. |
| 3 | **No `version` column on any table** | No optimistic concurrency anywhere. Two admins editing the same department silently last-write-wins. |
| 4 | **Child and event tables carry no `community_id`** — `complaint_events`, `visitor_events`, `payment_events`, `invoice_line_items`, `amenity_rules`, `amenity_booking_occurrences`, `booking_guests`, `amenity_booking_charges`, `amenity_financial_events`, `policy_revisions`, `notification_deliveries`, `work_order_*`, `worker_*` | Every RLS policy on those tables needs a join to the parent, on every row, for every query. This is both a performance problem and a correctness risk — a missed join is a tenant leak. |
| 5 | **`complaints.category` is free text** | §6 of the component design requires categories to be *"connected with the appropriate department and its service-level target."* Free text cannot carry a relationship. |
| 6 | **`visitor_access_requests` has no `guest_count`** | §5 requires recording *"number of guests"* and the frontend issues group passes. The group concept is unrepresentable. |
| 7 | **`visitor_access_requests` has `access_code_digest` only** | §5 requires *"a structured QR pass **and** a short access code."* One of the two credentials has nowhere to live. |
| 8 | **No link from `departments` to `complaints`** | §3 requires *"Prevent a department from being deleted while it is responsible for unresolved complaints."* The only department↔complaint path runs through `work_orders`, which has no UI, so the rule is unenforceable in practice. |

### 1.2 Requirements in the component design with no schema behind them

| Component-design requirement | Schema status |
|---|---|
| §2 *"select the functional modules required by the association"* | **No table.** Nowhere to persist the answer to onboarding step 3. |
| §3 departments with *"contact details, department heads, staff members, operating hours, complaint categories, and service-level targets"* | `departments` has `name`, `description`, `status`. **6 of 6 requirements missing.** |
| §6 complaints tracking *"status, progress, assignee, management notes, unread updates"*, plus comments, reopen, rating, feedback, SLA | `complaints` has none of these. **9 requirements, 0 columns.** No `complaint_comments`, no read-state table. |
| §6 *"supporting attachments"* on complaints | No `complaint_attachments`. |
| §3 *"invitations that residents can redeem using a link **or code**"* | No code column (and no token digest — see 1.1 #2). |
| §4 *"Present management contact information"* | No `emergency_contacts`. |
| §7 / §10 *"a shared activity feed"* | Only `audit_events`, which is an append-only compliance log. A feed that can be filtered and redacted is a different thing; collapsing them yields either a leaky feed or a useless audit trail. |
| §8 *"block maintenance periods"* | No `amenity_blocked_slots`. Without it a blocked window cannot participate in the overlap exclusion, so a booking can be created inside one. |
| §8 *"cleaning buffers, resident booking limits, private bookings"* | `amenities` has `capacity` and `approval_required`. Cleaning buffer, per-resident booking cap, `allow_private_booking` and maintenance mode are all absent. |
| §9 *"forced booking cancellations"* | `amenity_financial_events.event_type` can carry the event, but there is no `force_cancelled_by` on the occurrence. |
| Security dashboard incident logging | No `security_incidents` table. |

### 1.3 Schema with no requirement and no UI — 12 tables

Neither mentioned in the component design (0 keyword hits) nor referenced anywhere in
`frontend/src/`:

- **Work orders (5):** `work_orders`, `work_order_assignments`, `work_order_proposals`,
  `work_order_views`, `work_order_completion_verifications`
- **Workforce (5):** `vendors`, `skills`, `staff_skills`, `worker_availability_rules`,
  `worker_unavailability`
- **Policies (2):** `policies`, `policy_revisions`

That is a quarter of the ERD. This is not necessarily wrong — a schema may legitimately run ahead of
the UI — but it should be a deliberate decision with a phase attached, not an unexamined surface.
The `refundPolicy` strings found in the frontend are amenity settings and unrelated to the
`policies` tables.

### 1.4 Contradictions with the frontend

| Issue | Detail |
|---|---|
| **Role vocabulary** | ERD: `resident \| worker \| security \| manager \| admin`. Frontend routes on `Admin \| Resident \| Security \| SecurityManager`. `worker` has **no UI whatsoever**; the ERD's generic `manager` is specifically a *security* manager in the UI. |
| **A security supervisor is unrepresentable** | `security` is a role and `manager` is a role, so "supervisor within the security department" has no expression. The frontend's `departments[].staff[].role` already contains `"Supervisor"`. |
| **A committee member is unrepresentable** | The founding admin collects a `designation` (President, Secretary, Treasurer…) at onboarding. No table stores it. |
| **Address is `not null`, never collected** | `communities.address_line_1/city/state/postal_code/country_code` are all `not null`. The onboarding flow asks for none of them. |
| **Coordinates are `latitude`/`longitude`** | The frontend produces `{x, y}` percentages of a static image. `numeric(9,6)` accepts them silently. |
| **No flat inventory** | Onboarding creates blocks or villas only. `unit_residencies.unit_id` is `not null`, so the founding admin's own residency has nothing to reference in an apartment community. |
| **Money** | `numeric(12,2)` in the schema; plain major-unit integers in the frontend (`amount: 4250`). |

---

## 2. Class diagrams

The domain diagram is faithful to the v1 ERD, so it inherits §1.2 and §1.3 wholesale — `Department`
carries only `name`/`description`/`status`, `Complaint` carries no progress, assignee, rating or SLA.
Beyond that, three modelling issues of its own:

1. **Role is modelled as inheritance.** `CommunityMembership` is abstract with five subclasses
   (`ResidentMembership`, `WorkerMembership`, `SecurityMembership`, `ManagerMembership`,
   `AdminMembership`). Role is *state*, not *type*: promoting a resident to admin would require
   changing an object's class, which no ORM and no table can do. It also makes the person who is
   both a resident and the security supervisor unrepresentable without multiple inheritance.

2. **Behaviour without state.** `Complaint` exposes `reopen(reason)` and `escalate()` but has no
   `reopenCount`, no escalation flag and no assignee — the methods have nothing to record their
   effect in. Same for `resolve()` with no rating or feedback to capture.

3. **The scope invariant is split by subclass** — *"RESIDENT/ADMIN: one active membership across all
   communities. WORKER/SECURITY/MANAGER: multi-community."* An invariant that differs per subclass
   cannot be expressed as one partial unique index, and the diagram does not say how it is enforced.

The architecture diagram was not found to have issues in this pass.

---

## 3. Design of components

Mostly accurate as a description of the prototype. Four issues:

1. **§10 claims a `notifications` collection that does not exist.** It lists the domain slices as
   including *"…activities, and notifications."* There is no notifications slice in
   `frontend/src/store/slices/`. Verified by directory listing.

2. **§1 *"Maintain the authenticated user session separately in each browser tab"* cannot survive a
   backend.** It is true of the prototype (sessionStorage) and impossible once sessions are
   server-issued, because cookies are scoped to an origin, not a tab. There is no workaround. This
   needs to be marked as prototype behaviour or it will read as a broken requirement.

3. **§1 *"Provide separate entry and login flows for residents and association administrators"* is
   now superseded** by the OAuth single-entry decision. Not a defect at the time of writing;
   flagged so it is not treated as a live requirement.

4. **§2 collects an administrator's *"unit number"* while configuring only blocks and villas.** The
   document does not notice that it never creates the flat that unit number refers to. This is the
   origin of the missing-inventory problem in §1.4.

Also worth noting: §2 *"Create a simulated association and administrator record after OTP
confirmation"* is superseded by the OAuth decision.

---

## 4. Frontend

Issues visible only when the frontend is read against these documents:

1. **Labels used as foreign keys throughout.** `apartmentId` is `` `${tower}-${flatNumber}` ``,
   `complaints[].assignee` is `"Ramesh - Plumber"`, `departments[].head` is a person's name,
   `complaints[].flat` is `"B-1204"`. Every one is an FK in the schema.

2. **`departments[].staff[].role` mixes two axes** — `"Supervisor"` is a rank, `"Technician"` is a
   job title. The ERD has `job_title` and no rank, so the distinction has nowhere to land.

3. **Department staff are records with no account.** Nothing in the frontend turns a staff entry into
   a login, and the ERD has no provisioning path either. Every staff dashboard is unreachable by
   design.

4. **Display strings where instants belong** — `timeAgo: "2h ago"`, `date: "July 8, 2026"`. Wrong the
   moment they are cached.

5. **Settings is a stub** — four `useState` toggles and a toast. Its labels promise automated monthly
   billing and late-payment fines, which exist in no table and no requirement.

6. **Onboarding promises module editing that does not exist.** Step 3 says features *"can be changed
   later from the Admin Settings page."* No such control exists, and there is no table behind it.

7. **The dashboard has never rendered an empty state.** Every count is derived from seeded arrays.

---

## 5. What to fix first

Ranked by cost-of-delay, not by effort.

| Priority | Item | Why first |
|---|---|---|
| **1** | `units` unique constraint scoped by building (§1.1 #1) | It is a correctness bug that blocks the most common deployment — a multi-block apartment complex. Everything else can be added later; this one is baked into the primary key story. |
| **2** | Invite token/code digest columns (§1.1 #2) | The invitation flow cannot be implemented at all without them. |
| **3** | Decide the flat-inventory question (§1.4) | The founding admin's residency depends on it, so it blocks registration, which blocks everything. |
| **4** | Complaints and departments column sets (§1.2) | Two of the ten admin surfaces cannot be built. Largest gap by volume. |
| **5** | `community_id` on child tables (§1.1 #4) | Cheap now, invasive later — it changes every RLS policy already written. |
| **6** | `version` columns (§1.1 #3) | Same argument: adding optimistic concurrency after endpoints exist means revisiting all of them. |
| **7** | Decide the fate of the 12 orphan tables (§1.3) | Not urgent, but leaving them unexamined means nobody knows whether they are a plan or an accident. |

---

## 6. Note on file layout

`docs/erd/` holds two files and they must not be confused:

- **`homebandhu-v1-milestone1.dbml`** — the milestone-1 submission, verified identical to the
  supplied source. **This is the artifact the teammates own.**
- **`homebandhu.dbml`** — a 63-table v2 draft produced during backend planning, which resolves many
  of the issues above. It is *our working draft*, not an agreed artifact, and it should not be
  treated as authoritative while the ERD is being maintained elsewhere.
