# HomeBandhu — Backend Implementation Plan

**Status:** proposal for team review. No code is written against this yet.
**Supersedes:** `docs/plan.md` (that document is now the *auth-slice-only* plan and is stale in
several places — see §9).
**Change history:** [`docs/CHANGE_LOG.md`](CHANGE_LOG.md) — every edit to every design artifact and
the reason for it. Append there whenever this plan, the ERD, the class diagrams or the component
design change. This plan says what the design *is*; the change log says why it stopped being
something else.

---

## 0. Inputs and precedence

Three documents describe the backend, and they disagree with each other in specific,
fixable ways. This plan sets a precedence rule so we stop re-litigating:

| Source | What it is authoritative for | Where it is wrong / thin |
|---|---|---|
| `docs/class-diagram/homebandhu-domain.puml` | **Domain model + table set + enums.** 47 classes, invariants, exclusion constraints. This is the submission artifact — the DB must match it. | Missing ~14 tables the frontend needs, and its flat 5-value role enum cannot express a security supervisor or a committee member (§4.2). Email-centric identity. |
| `docs/frontend-documentation.md` | **API surface**: endpoints, request/response shapes, error codes, envelope, status semantics, authorization order. Genuinely thorough — 3,300 lines derived from `frontend/`. | Missing the staff-login mechanism, session staff scope, and several enum value sets that exist in code (§4.1). |
| `docs/plan.md` + `backend/app/**` | Historical: the auth/invitation slice already scaffolded. | Role model contradicts the class diagram. `TECHNICIAN` is not a role. Must be reworked (§9). |
| **`docs/erd/homebandhu.dbml`** (v2) | **The physical schema** — 58 tables with types, nullability, FKs, composite PKs, named uniques and invariant notes. Migrations 0002 and 0006–0013 are built from this file. | v1's 7 corrections / ~25 missing columns / 13 missing tables / 5-value role enum are all **resolved in v2**; §4.3 records why. Still cannot express partial indexes, exclusions, CHECKs or deferrable FKs — those live in Notes and are real only in the migrations. |
| **`docs/design-of-components.md`** | **Component responsibilities and workflow rules**, incl. four rules stated nowhere else (§4.3 F). | Prototype-scoped; describes browser storage as the persistence layer. |

Both were added to the repo on 2026-07-28 (the ERD as `.dbml`, not only the PNG — a PNG cannot be
diffed). Three artifacts now describe one schema: `.dbml`, `.puml`, and `supabase/migrations/`. Only
the migrations execute, so **the migrations are the source of truth and the other two are
projections** — regenerated at the end of each phase, never edited as the spec.

**Rule:** class diagram wins on *schema and domain semantics*; frontend-documentation wins on
*wire format and endpoint contracts*; where they conflict, §3 records the decision.

Fourth input, which no document captures: **`roles.md`** —
`Resident → Committee members → Admin` and `Staff → technician | supervisor | manager`, each with a
security variant. This confirms the class diagram's model (role on membership, skill separate) and
it is what the login code actually implements.

Fifth input, **product owner's domain statement** (2026-07-28) — this is authoritative over all four
documents above wherever it contradicts them:

> The main roles are resident, admin and departments. Security departments have different dashboard
> needs than plumbing or electrical. Departments have specialised views for manager, supervisor and
> worker. Committee members are residents with specialised views. The admin is a committee member and
> therefore also a resident. The app is either an apartment association **or** a standalone-homes
> residents association — never both. An apartment community may have multiple buildings, but all
> homes in it are apartment-type.

Three of those statements are unrepresentable in the current class diagram (supervisor tier,
committee members, community-type exclusivity). §3.1 and §3.8 resolve them; the `.puml` edit is
listed in §4.2.

---

## 1. Architecture: what Supabase owns vs what we write

The instruction is "use Supabase functionality as much as possible." Taken seriously, that does
**not** mean "let the browser talk to PostgREST for everything" — the frontend contract needs an
envelope, idempotency keys, `If-Match` versioning, cursor pagination and stable error codes, none of
which PostgREST provides. It means: *never reimplement something Supabase already does correctly.*

```
Browser (React/Zustand)
  │
  ├── HTTPS/JSON ──────────────►  FastAPI  /api/v1        ← the only write path
  │                                  │
  │                                  ├─ GoTrue (auth.*)   phone OTP, sessions, refresh, admin API
  │                                  ├─ PostgREST         reads/writes as the *caller* (RLS on)
  │                                  ├─ Postgres RPC      multi-table atomic commands
  │                                  └─ Storage           signed upload/download URLs
  │
  └── Supabase Realtime (direct, browser holds the Supabase JWT) ── postgres_changes, RLS-filtered
```

**Delegated to Supabase — we write no code for these:**

| Concern | Supabase feature |
|---|---|
| Phone OTP send/verify, sessions, refresh-token rotation | GoTrue `sign_in_with_otp` / `verify_otp` / `refresh_session` |
| Password-less user provisioning on invite redemption | `auth.admin.create_user(phone=…, phone_confirm=True)` |
| Role/tenant claims inside the access token | **Custom Access Token Hook** (`0003`) |
| Authorization enforcement | **RLS policies** — the real boundary |
| Atomicity across tables | Postgres functions called via `rpc()` (single statement = single txn) |
| Interval double-booking prevention | `EXCLUDE USING gist` + `btree_gist` |
| File storage, signed upload/download, private buckets | Supabase Storage |
| Realtime invalidation (replaces `store/sync.js`) | Supabase Realtime `postgres_changes`, RLS-filtered |
| Scheduled jobs (invoice generation, mark-overdue, expire proposals) | `pg_cron` |

**We write in FastAPI (Supabase has no equivalent):**
response envelope + `requestId`, `Idempotency-Key` handling, `If-Match`/version conflict → `409`,
cursor pagination, the stable error-code catalogue, DTO validation, defence-in-depth role guards,
audit/activity emission, payment-provider integration and webhook verification, and the
enumeration-safe account-discovery logic.

**Anti-goal:** business rules living *only* in FastAPI. Every tenant/ownership rule must also exist
as an RLS policy, so a leaked anon key or a missed guard is not a data breach.

---

## 2. Client trust levels

Already implemented correctly in `backend/app/core/supabase_client.py` — keep it.

- `get_user_client(jwt)` — **the default for every request-scoped read/write.** RLS runs as the
  caller. Use this unless there is a written reason not to.
- `get_service_client()` — RLS bypassed. Allowed **only** in: GoTrue admin calls, invitation
  redemption, community registration, payment-webhook reconciliation, account discovery, and cron
  jobs. Every service-client call site gets a comment naming why.
- `get_anon_client()` — public/unauthenticated reads only.

---

## 3. Conflict resolutions (decide these before writing SQL)

### 3.1 Role model — **three orthogonal axes, not one enum**

Every existing source flattens role into a single list, and every one of them is wrong, because the
domain has three independent axes. Evidence that a flat enum cannot work:

- A **security supervisor** is simultaneously "security" and "supervisor". A flat enum must either
  drop the tier or cross-multiply (`SECURITY_SUPERVISOR`, `PLUMBING_SUPERVISOR`, …).
- `frontend/src/data/departments.js` already stores `staff[].role` = `Supervisor | Technician`,
  while `CreateDepartment.jsx` offers `Technician | Manager | Supervisor` and
  `SecurityManagerDashboard.jsx` offers `Security Guard | Gate Officer | Supervisor`. Same tier,
  different job titles, per department kind.
- A **committee member** is a resident with extra views; an **admin** is a committee member and
  therefore also a resident. A flat enum makes these mutually exclusive.

| Axis | Column | Values | Decides |
|---|---|---|---|
| **Principal role** | `community_memberships.role` | `RESIDENT`, `STAFF`, `ADMIN` | which dashboard shell you land in; coarse RLS |
| **Department kind** | `departments.kind` | `SECURITY`, `MAINTENANCE`, `HOUSEKEEPING`, `FACILITIES`, `OTHER` | *which* staff dashboard (security ≠ plumbing) |
| **Rank in department** | `staff_assignments.rank` | `MANAGER`, `SUPERVISOR`, `WORKER` | which views inside that dashboard |

Plus a free-form `staff_assignments.job_title` (`Technician`, `Gate Officer`, `Security Guard`, …)
validated against a per-department-kind catalogue. This is exactly the class diagram's *"technician
is a `Skill`, not a role"* rule, generalised — `rank` is authority, `job_title`/`skills` is trade.

**Membership is one row per person per community.** The other capabilities are *possessions*, not
role values:

| Capability | Expressed as | Not as |
|---|---|---|
| is a resident of a home | a row in `unit_residencies` | `role = 'RESIDENT'` |
| is staff of a department | a row in `staff_assignments` | `role = 'WORKER'` |
| is on the committee | a row in `committee_positions` (designation from `adminDesignations.js`) | a role value |
| is the association admin | `role = 'ADMIN'` (one active per community) | — |

This makes the product owner's containment **true by construction rather than by a hardcoded
implication**: an ADMIN holds a `committee_positions` row and a `unit_residencies` row, so
`is_resident()` returns true for them without any `ADMIN ⊇ RESIDENT` special case. It also kills the
dual-membership workaround that was §10.4 in the previous draft.

**Presentation role** stays a derived string, computed server-side and returned by `/auth/me`, so the
frontend keeps the vocabulary it already uses:

```json
{
  "role": "STAFF",
  "uiRole": "SecurityManager",
  "isResident": true, "isCommittee": false,
  "staffAssignmentId": "…", "departmentId": "…",
  "departmentName": "Security", "departmentKind": "SECURITY", "rank": "MANAGER"
}
```

| `role` | `department.kind` | `rank` | `uiRole` | Frontend today |
|---|---|---|---|---|
| ADMIN | — | — | `Admin` | ✅ `/admin` |
| RESIDENT | — | — | `Resident` (+`Committee` if a position exists) | ✅ `/resident`, committee views ❌ |
| STAFF | SECURITY | MANAGER | `SecurityManager` | ✅ `SecurityManagerDashboard` |
| STAFF | SECURITY | SUPERVISOR | `SecuritySupervisor` | ⚠️ manager shell, roster read-only |
| STAFF | SECURITY | WORKER | `Security` | ✅ gate view |
| STAFF | any other | MANAGER / SUPERVISOR / WORKER | `DepartmentManager` / `DepartmentSupervisor` / `DepartmentStaff` | ❌ not built |

**DECIDED 2026-07-28 — no `UNSUPPORTED_ROLE`.** A role with no shell built yet still authenticates
normally and receives a full session; `uiRole` resolves to a value the frontend maps to a **WIP
placeholder screen** carrying a back-to-login button. Rationale: the alternative (`409` at verify)
means an admin can provision a plumbing technician who then cannot log in at all, with no way for
either of them to see why. A stub screen is a frontend-only unblock; the backend contract does not
change when the real shell lands. This supersedes `409 UNSUPPORTED_ROLE` in
`frontend-documentation.md` §"Shared Community Login" — that code is retired.

`lib/securityAccounts.js` computes precisely the SECURITY rows of this table client-side today — the
server takes that over.

**DECIDED 2026-07-28 — supervisor gets its own view.** Rank is a genuine three-level tier, not a
two-level one, because *"there will only be a single manager in a department; there will be multiple
supervisors with multiple workers under them."* So `SUPERVISOR` lands in the manager shell with staff
**editing disabled** — a read-only roster of their own workers. Today's
`lib/securityAccounts.js:22` sends only `Manager` there; that is a prototype simplification, not the
domain rule.

**DECIDED 2026-07-28 — assignment cardinality is rank-dependent.** *"Workers can also belong to
multiple departments if they have the skill for it, but supervisors and managers are only for a
single department."* This invalidates the v2 ERD's flat "one active staff assignment per membership"
and replaces it with three constraints — see §3.10.

**Consequences for the class diagram** (`MembershipRole` = RESIDENT/WORKER/SECURITY/MANAGER/ADMIN,
5 subclasses): the enum becomes 3 values, the subclass hierarchy becomes
`ResidentMembership | StaffMembership | AdminMembership`, and two new enums (`DepartmentKind`,
`StaffRank`) plus `CommitteePosition` are added. `TECHNICIAN` stays deleted. This is a real edit to a
graded artifact, made deliberately: the diagram as drawn cannot represent a security supervisor.

### 3.2 The word "unit" means three different things — **rename now**

| Concept | Class diagram | Frontend doc | `0001_init.sql` | **Canonical** |
|---|---|---|---|---|
| Block / tower / villa cluster (has map coords) | `Building` | `CommunityUnit` | `units` ❌ | **`buildings`** |
| An individual flat / villa / shop | `Unit` | `Apartment` | `apartments` | **`units`** |

**Decision:** DB and API both use `buildings` + `units`. The frontend has no API layer yet (its
services are mock stubs), so renaming is free today and expensive in three weeks.
Onboarding maps cleanly: apartment community → creates `buildings` with `location`; villa layout →
creates `units` with `unit_type = VILLA` and `location`. Both classes already carry `GeoPoint`.
The two shapes are mutually exclusive — see §3.8, which the schema must enforce.

### 3.3 Community type is exclusive and immutable — enforce it in the DB

`data/onboarding.js` already models this: `COMMUNITY_TYPES = { APARTMENT, LAYOUT_VILLA }`, and
`onboardingStore.js` clears `villas` when you pick apartment and clears `blocks` when you pick villa.
Neither the class diagram nor the frontend doc carries the constraint, so nothing stops a mixed
community from being created through the API.

**Decision:** `communities.community_type` = `APARTMENT | LAYOUT_VILLA`, `not null`, **immutable
after onboarding** (a `before update` trigger raises if it changes once any unit exists), with a
check trigger on `units`:

| | `APARTMENT` | `LAYOUT_VILLA` |
|---|---|---|
| `buildings` | ≥ 1, max 10 (`MAX_BLOCKS`) | none permitted |
| `units.building_id` | `not null` | must be `null` |
| `units.unit_type` | `FLAT` (or `SHOP`/`PARKING` for non-residential) | `VILLA`, max 50 (`MAX_VILLAS`) |
| `location` (GeoPoint) | on `buildings` | on `units` |

Expressed as one table-level check plus a per-community-type count guard, so "an apartment community
with a villa in it" is not merely a validation failure — it is unrepresentable. `unitLabel`
(`Flat` vs `Villa`) is derived from `community_type` and returned in `/communities/current` so the
frontend stops hardcoding "Flat".

### 3.4 Identity: phone, not email — **frontend wins**

Class diagram has `AuthUser.email` and `ResidentInvite.recipientEmail`; every implemented screen is
phone-OTP with Indian 10-digit normalisation (`utils/phone.js`).

**Decision:** phone (E.164) is the primary identity. Supabase phone OTP is first-class. Email stays
as an optional profile attribute. `resident_invites` carries `phone_e164` + `recipient_email` (both
nullable-ish, at least one required) so the diagram stays honest.
**Cost:** an SMS provider (MSG91 for India) must be wired in the Supabase dashboard. For dev, use
Supabase's *test phone numbers with fixed OTPs* — no SMS spend, no code branches.

### 3.5 Money — store decimal, serialise minor units

Diagram says `numeric(12,2)`; frontend doc mandates integer minor units on the wire.
**Decision:** DB `numeric(12,2)` + `currency_code`; a single `to_minor()/from_minor()` pair in
`domain/money.py` converts at the DTO boundary. Never let a float touch either side.

### 3.6 Booking-mode enum collision

`amenitiesManagement.js` uses `Shared | Hybrid | Exclusive`; the diagram uses
`SLOT | FULL_DAY | MULTI_DAY`. These describe **different axes** — sharing policy vs. granularity.

**Decision:** keep both as separate columns: `booking_mode` (`SLOT/FULL_DAY/MULTI_DAY`, from the
diagram) and `exclusivity` (`SHARED/HYBRID/EXCLUSIVE`, from the UI). Do not try to collapse them;
that is how the "two amenity models" problem started.

### 3.7 Access-token lifetime vs the doc's 10–15 min

The doc asks for a 10–15 minute access token with the refresh token in an `HttpOnly` cookie.
Supabase's default is 1 h and its JS client stores both in `localStorage`.
**Decision:** set the project JWT expiry to **900 s**; FastAPI owns `/auth/refresh` and sets the
refresh token as `Secure; HttpOnly; SameSite=Lax`. The browser never holds a refresh token, and the
access token stays a genuine Supabase JWT so RLS and Realtime keep working unchanged.

### 3.9 Work orders exist in the schema, not yet in the API

The class diagram has a full work-order subsystem (assignments, proposals, availability rules,
completion verification, gist exclusion on accepted assignments). The frontend has *none* of it —
complaints carry a free-text `assignee`.
**Decision:** create the tables in phase 5 (the diagram is a graded artifact), but expose only
`complaints.assignee_staff_id` in the v1 API. Work-order endpoints are phase 8, gated on a frontend
existing.

### 3.10 Staff assignment cardinality — rank-dependent, not flat

The v2 ERD carried a single partial unique: *one active `staff_assignment` per membership*. The
product owner's 2026-07-28 statement breaks it — **workers may serve several departments, ranked
staff may not.** Replace it with three constraints plus a trigger:

| Rule | Constraint |
|---|---|
| A department has at most one manager | partial UQ `(department_id) WHERE status='active' AND rank='manager'` |
| A manager or supervisor serves exactly one department | partial UQ `(membership_id) WHERE status='active' AND rank IN ('manager','supervisor')` |
| A worker is not assigned to the same department twice | partial UQ `(membership_id, department_id) WHERE status='active'` |
| Ranks do not mix | trigger: if a membership holds an active `manager`/`supervisor` row, it must be its **only** active row |

Stated once: **a membership has either exactly one active manager/supervisor assignment, or N active
worker assignments across distinct departments — never a mix.**

Two knock-on effects:

1. **The JWT cannot carry `department_id` as a scalar.** §6's claim set becomes
   `department_ids: uuid[]` and `department_kinds: text[]`, with `rank` still scalar (a worker's rank
   is `worker` in every department by construction, since a ranked row must be solitary). RLS
   predicates change from `department_id = claim` to `department_id = ANY(claim)`.
2. **Landing-shell resolution needs a tiebreak.** A worker in Security *and* Plumbing has two
   candidate shells. Rule: prefer the assignment whose `department.kind` has a shell built
   (`security` today), then lowest `departments.created_at`. A department switcher in the staff shell
   is the eventual fix; the tiebreak keeps login deterministic until then.

The multi-department worker is also exactly why `skills` / `staff_skills` exist in the schema —
*"if they have the skill for it"* is the assignment precondition, and phase 5's work-order routing
already reads it.

---

## 4. Gaps — what neither document covers

### 4.1 Missing from `frontend-documentation.md` (found in the code)

1. **How a staff member becomes a login account.** `lib/securityAccounts.js` authenticates
   Security/SecurityManager by matching the phone against `departments[].staff[].phone`, and infers
   manager from `staff.role === 'Manager'` *or* the phone matching `department.phone`. The doc says
   "staff records do not automatically become login accounts" but never specifies the provisioning
   flow. **Needed:** `POST /departments/{id}/staff/{staffId}/invite` → creates
   profile + `SECURITY`/`MANAGER` membership + `staff_assignment`, then the normal OTP login works.
2. **Session must carry staff scope.** The manager UI reads `currentUser.staffId`,
   `departmentId`, `departmentName`; the guard-vs-manager split and the self-removal guard
   (`member.id === currentUser.staffId`) depend on them. The doc's session payload only shows
   `apartmentId`. Add `staffAssignmentId`, `departmentId`, `departmentName` to `/auth/me`.
3. **Admin designation.** `adminDesignations.js` (President / Secretary / Treasurer / Committee
   Member / Association Manager / Other) is captured during onboarding and persisted nowhere in
   either model. Add `designation` to the admin membership.
4. **Staff `shift` and `status`** (`Day/Evening/Night`, `Active/Inactive`) are used by the manager
   dashboard's staffing-by-shift widget; the doc's `Staff` entity omits both.
5. **Complaint categories are department-owned and editable** (`departments[].categories[]`), so
   `complaint.category` cannot be a Postgres enum — it needs a `complaint_categories` table scoped
   to the community and referenced by departments for routing.
6. **Visitor credential is a 6-digit numeric code** (`lib/visitorPasses.js`, 900k space) *plus* a
   `PG-xxxx` display code. The doc says "hash it and rate-limit"; it does not say the space is
   small enough that rate-limiting is load-bearing. Needs per-community uniqueness among *active*
   passes, short TTL, and a hard attempt cap.
7. **`enabledModules` key set is never enumerated.** `onboardingModules.js` defines **ten** keys —
   `resident-management`, `visitor-management`, `complaint-management`, `maintenance-billing`,
   `notice-board`, `amenities-booking`, `security-gate-management`, `parking-management`,
   `staff-management`, `community-marketplace` — and the server must validate against that exact
   list. The frontend-doc example (`["visitors","complaints","amenities","payments"]`) uses a
   different vocabulary that exists nowhere in the code; the code's kebab-case ids win.
8. **Amenity ledger fields** the doc summarises but does not enumerate: `chargeOverride`,
   `internalNotes`, `additionalCharges`, `depositPaid`, `remainingRefund`, `auditTrail`,
   `refundHistory`, `damageHistory`, `cancellationHistory`, `forceCancelledBy`, `paymentReference`.
   All are in `data/amenityLedger.js` and drive real UI.
9. **Committee members are absent from every source.** `adminDesignations.js` exists and onboarding
   collects a designation, but no document defines what a committee member may *do* beyond a
   resident. Until the product owner scopes those views, the server ships the data
   (`committee_positions` + `isCommittee` in the session) and grants **no** extra permissions —
   so the capability can be turned on later without a migration.
10. **Non-security department dashboards are unbuilt but must exist in the model.** Only the
   security department has a staff UI today; plumbing/electrical staff have no login destination.
   The API is built for all department kinds from phase 5; ranks whose dashboard is missing still
   authenticate normally and land on a WIP placeholder (§3.1), rather than being refused or
   pretended into security staff.

### 4.2 Missing from the class diagram (needed by the frontend)

`SecurityIncident` · `EmergencyContact` · `ComplaintComment` · `ComplaintReadState` ·
`ComplaintAttachment` · `AmenityBlockedSlot` · `ActivityEvent` (distinct from `AuditEvent` — one is
a user-visible feed, the other is a compliance log) · `OtpChallenge` · `AuthSession` ·
`IdempotencyRecord` · invite `token_digest`/`code_digest` columns (the note mentions digests, the
class has no such attributes) · `Department.categories/slaHours/operatingHours/head/contact` ·
`Notice.audience` · `Amenity.location/images/maintenanceMode`.

**Plus the structural edits from §3.1 and §3.3** — these are changes to what is already drawn, not
additions, so they need a deliberate pass:

| Change | Why |
|---|---|
| `MembershipRole` 5 values → `RESIDENT, STAFF, ADMIN` | supervisor tier and committee membership are unrepresentable otherwise |
| 5 membership subclasses → `ResidentMembership`, `StaffMembership`, `AdminMembership` | follows the enum |
| new `StaffRank` enum on `StaffAssignment` (`MANAGER/SUPERVISOR/WORKER`) + `jobTitle` | the tier the department dashboards branch on |
| new `DepartmentKind` enum on `Department` (`SECURITY/MAINTENANCE/…`) | security dashboards differ from every other department |
| new `CommitteePosition` class (membership 1—0..1, `designation`, term, status) | committee members are residents with extra views |
| new `CommunityType` enum on `Community` + the exclusivity note on `Building`/`Unit` | apartment **xor** standalone homes |

Constraint notes to add: *"exactly one active ADMIN per community, who must also hold a
`CommitteePosition` and a `UnitResidency`"* and *"`Building` exists only when
`community.type = APARTMENT`; `Unit.building` is null iff `community.type = LAYOUT_VILLA`."*

#### 4.2.1 Class-diagram conflicts with the §6 auth model (audited 2026-07-28)

Seven direct contradictions, distinct from the omissions above. These are places the diagram asserts
something the auth decisions make false:

| # | Where | Conflict | Fix |
|---|---|---|---|
| 1 | `AuthUser` (`.puml:104`) | has `email {unique}` + `emailConfirmedAt` and **no phone attribute at all** — the identity column is missing from the identity class | add `phone {unique}`, `phoneConfirmedAt`; demote email to `[0..1]` |
| 2 | `ResidentInvite` (`:403`) | `recipientEmail : String {required}`, **no phone, no digests** — yet its own note says only token/code digests are stored | `recipientPhoneE164 {required}` + `tokenDigest` + `codeDigest` + `attemptCount`; email `[0..1]` |
| 3 | `AdminMembership.inviteResident(u : Unit, email : String)` (`:292`) | invites keyed by email | `inviteResident(u : Unit, phone : String)` |
| 4 | `CommunityRegistrationRequest.applicantEmail {required}` (`:134`), `AccessRequest.applicantEmail {required}` (`:426`) | email required on both intake paths | phone required, email `[0..1]` |
| 5 | **`CommunityMembership` scope note (`:259`)** | *"RESIDENT/ADMIN: one active membership across all communities. WORKER/SECURITY/MANAGER: many communities."* — contradicts §6.7 (**everyone** gets one) and misplaces multi-department-ness on the membership instead of `StaffAssignment` | rewrite: one active membership per profile, full stop; multi-**department** is a `StaffAssignment` cardinality (§3.10) |
| 6 | same note — *"Staff & non-staff not mixed"* | forbids the resident who is also the security supervisor, which §6.6 explicitly supports | delete the clause; capabilities are possessions |
| 7 | `Profile.activeMemberships() : List<>`, `membershipIn(c : Community)` (`:124`) | both presume multi-community | collapse to `activeMembership() : Optional<CommunityMembership>` |

Also: `Profile.verifyPhone(otp)` (`:122`) and `CommunityRegistrationRequest.verifyOtp(code)` (`:143`)
are **two independent OTP verifiers on two aggregates** — exactly what §6.8 forbids. Both must
delegate to the single `AuthenticationProvider`; neither aggregate should know what an OTP is.
`AdminMembership.grantRole(p, r : MembershipRole)` (`:293`) is likewise stale — granting staff-ness
now means creating a `StaffAssignment`, not setting a role value.

**Action:** extend the `.puml` in the same pass as the migrations so the diagram and the DB ship in
sync. The platform tables (`otp_challenges`, `auth_sessions`, `trusted_devices`,
`idempotency_records`) and the `AuthenticationProvider` seam belong on the *architecture* diagram,
not the domain one.

### 4.3 ERD reconciliation (`docs/erd/homebandhu.dbml`)

> **STATUS — resolved 2026-07-28.** Every delta in A–D below has been **applied** to
> `docs/erd/homebandhu.dbml` (now v2). The milestone-1 submission version is preserved verbatim as
> `docs/erd/homebandhu-v1-milestone1.dbml`, so the two are diffable. Each change in v2 is tagged
> `CHANGED:` or `NEW:` in a comment or Note. This section is kept as the rationale record — it is
> why v2 differs from v1, not an outstanding to-do list. **The diagram needs re-rendering from
> the v2 file.**

**Verdict: it works.** It is a well-formed physical schema — 45 tables, consistent
`community_id`/`created_at`/`updated_at` discipline, composite PKs where they belong
(`staff_skills`, `work_order_views`, `*_attachments`), digests rather than plaintext
(`access_code_digest`, `otp_digest`), and notes that already name the two exclusion constraints and
the one-active-admin / one-primary-contact invariants. Migrations 0002 and 0006–0013 are built
**from this file**, not from scratch. What follows are the deltas.

**A. Corrections — things that are wrong or will break a real workflow**

| # | Where | Issue | Fix |
|---|---|---|---|
| A1 | `units_community_label_uq (community_id, unit_label)` | In an apartment community, Flat 101 exists in Block A *and* Block B. The frontend stores `tower` and `flat` separately (`data/users.js`), so labels **will** collide and the second block's units will fail to insert. | `(community_id, building_id, unit_label)`, with a partial unique on `(community_id, unit_label) where building_id is null` for the villa case |
| A2 | `resident_invites.recipient_email text [not null]` + `invited_auth_user_id` + `auth_invite_sent_at` | The ERD assumes Supabase's **email magic-link invite**. Every implemented screen is phone OTP with a typable code (§3.4). | Add `phone_e164`, `token_digest`, `code_digest`, `attempt_count`; relax `recipient_email` to nullable with a check that at least one contact exists. The note says "do not store plaintext tokens" but no digest column exists to store them in. |
| A3 | `access_requests.applicant_email [not null]` | Same email assumption; the pending-requests screen collects a phone. | Nullable email, `not null` phone |
| A4 | `communities.active_admin_membership_id` → `community_memberships.id`, which FKs back to `communities.id` | A genuine cycle. A plain FK makes `register_community` impossible to write as one statement. | Declare it `deferrable initially deferred` — the RPC then inserts community → membership → update in a single transaction |
| A5 | Event/child tables carry no `community_id` (`complaint_events`, `visitor_events`, `payment_events`, `amenity_financial_events`, `amenity_rules`, `amenity_booking_occurrences`, `booking_guests`, `work_order_assignments`, `invoice_line_items`, `notification_deliveries`) | Every RLS policy on these needs a join to the parent, on every row, for every query. That is the single biggest performance and correctness risk in the design. | Denormalise `community_id` onto all of them and add composite FKs `(community_id, parent_id) → parent (community_id, id)` so it cannot drift |
| A6 | No `version` column anywhere | `frontend-documentation.md` mandates `If-Match` and a `STALE_VERSION` error on concurrent edits. There is nothing to compare against. | `version integer not null default 1` + `bump_version()` trigger on every editable table (already in §5's cross-cutting contract) |
| A7 | `community_memberships` unique is `(community_id, profile_id)` | Written as a full unique; the note says it should be partial-on-active. A resident who leaves and returns can never be re-added. | Partial unique `where status = 'ACTIVE'` |

**B. Missing columns on tables that already exist**

- `departments` — has only `name`/`description`/`status`, but `design-of-components.md` §3 requires
  "contact details, department heads, staff members, operating hours, complaint categories, and
  service-level targets", all of which exist in `data/departments.js`. Add **`kind`** (§3.1),
  `head_membership_id`, `contact_email`, `contact_phone_e164`, `opens_at`, `closes_at`, `sla_hours`.
- `staff_assignments` — has `job_title` ✅ (matches §3.1) but needs **`rank`** (`MANAGER/SUPERVISOR/WORKER`)
  and `shift` (§4.1.4). Its note *"one active staff assignment per membership"* independently
  confirms §10.13.
- `complaints` — no `assigned_to_membership_id`, `department_id`, `progress`, `sla_due_at`,
  `rating`, `feedback`, `reopen_count`. `design-of-components.md` §6 requires every one of them.
  Routing via `work_orders.department_id` alone does not work, because the frontend assigns a
  complaint directly and has no work-order UI (§3.9).
- `communities` — no `enabled_modules`. Onboarding step 3 selects ten modules
  (`onboardingModules.js`) and there is nowhere to persist the answer → `community_settings` (0002).
- `amenities` — no `exclusivity` (§3.6), `cleaning_buffer_minutes`, `max_bookings_per_resident`,
  `allow_private_booking`, `location`, `images`, `maintenance_mode`. `amenity_rules` is otherwise
  richer than I credited from the PNG — charges, deposits, guest caps and cancellation deadlines are
  all already there.
- `visitor_access_requests` — `access_code_digest` ✅, but no `attempt_count`/`locked_until` and no
  QR-token column. `design-of-components.md` §5 requires *both* a QR pass and a short code.
- `notices` — no `audience` (block/unit/role targeting).
- `profiles` — `phone_e164 [unique]` ✅ is already there, which makes A2 an inconsistency inside the
  ERD itself rather than a change of direction.

**C. Missing tables** — exactly the §4.2 list, now confirmed rather than inferred:
`committee_positions`, `community_settings`, `complaint_categories`, `complaint_comments`,
`complaint_read_state`, `complaint_attachments`, `security_incidents`, `emergency_contacts`,
`amenity_blocked_slots`, `activity_events`, `otp_challenges`, `auth_sessions`,
`idempotency_records`.

**D. The role model.** `Enum membership_role { resident worker security manager admin }` is the
5-value enum, so §3.1 is a real edit to this file: the enum becomes `resident, staff, admin`;
`departments` gains `kind`; `staff_assignments` gains `rank`; `committee_positions` is added. The
existing note — *"Technician and serviceman are worker skills, not roles"* — survives intact, and
`skills`/`staff_skills` already implement it.

**E. Two behaviours the ERD implies that nobody has confirmed**

1. ~~Platform-operator approval of new associations.~~ **DECIDED 2026-07-28: approved
   immediately.** `register_community` sets `status = approved` in the same transaction that
   creates the community; no v1 endpoint writes `review_notes`, `reviewed_by_operator_ref` or
   `reviewed_at`. The columns stay so the manual gate can be switched on later without a
   migration. Treated as a much-later optional addition — out of scope for every phase in §8.
2. `community_memberships`' note says *"staff may serve multiple communities"* while residents and
   admins may not. That is a real asymmetry with an RLS cost, and it contradicts §10.13's
   single-assignment recommendation only if the assignments are in different communities. *Recommend
   allowing the schema and deferring the multi-community login switcher past v1.*

**F. New rules found only in `design-of-components.md`** (no other source states them):
a department cannot be deleted while it owns unresolved complaints (§3); approving a registration
request must create the resident account **and an initial maintenance invoice** in the same
transaction (§3); complaint SLA is derived from urgency at submission time (§6); a resident may
cancel individual dates out of a multi-day booking without cancelling the series (§8 — the ERD's
occurrence model already supports this correctly).

### 4.4 `design-of-components.md` conflicts with the §6 auth model

Three, all in §1 "Authentication and Role-Based Access Component":

1. **"Provide separate entry and login flows for residents and association administrators."** This is
   the document-level statement of the two-portal design that the one-door rule replaces. It is the
   root of the split that also produced the four `/auth/{admin,community}/otp/*` endpoints.
2. **"Maintain the authenticated user session separately in each browser tab."** Achievable today
   because the session is just `sessionStorage`. With a real `HttpOnly` refresh cookie it is not —
   cookies are per-origin, not per-tab. **Resolved by correction, not by design** — the bullet is now
   marked as prototype behaviour; see §6.9, "cannot absorb" item 2.
3. **§2 "Create a simulated association and administrator record after OTP confirmation."** Still
   true, but the OTP now precedes onboarding rather than closing it (§6.2). Ordering only.

**No conflict, and worth recording as support:** §1's *"Allow residents to activate their accounts
using an invitation link or invitation code"* and §3's *"Generate time-limited, single-use
invitations"* both corroborate the mandatory-token decision in §6.5. §3–4's *"support multiple phone
numbers belonging to the same apartment"* is likewise consistent — each phone is its own profile with
its own invite, which is why `lib/invites.js#applyRedeem`'s "activate every phone on the flat"
behaviour does not carry over.

### 4.5 Resolution register — **applied 2026-07-28**

Everything catalogued in §4.2.1 and §4.4 is now closed. Three constraints governed how:
**no frontend conflicts**, **minimal edits to the ERD, class diagram and component design**, and no
silent reinterpretation of a decision already made.

The ordering principle that fell out of those constraints is worth stating on its own, because it
decided most of the individual cases:

> **Resolve a conflict in the layer that owns the truth, and adapt at the boundary.**
> Identity, cardinality and authorization are the backend's to own, so the diagrams change to match
> the backend. Vocabulary, screen count and route paths are the frontend's to own, so the **API**
> changes to match the frontend. Nothing meets in the middle, and nothing is resolved by asking the
> other side to move.

**Frontend — 0 changes required, 0 made.** Four compatibility rules (§6.9 C1–C4) absorb the entire
conflict set: portal prefixes are accepted and ignored, `displayRole` is emitted in the frontend's
own 4-string vocabulary, `isRegistered` keeps its shape, and `redirectTo` is optional everywhere it
appears. Three items remain that no backend rule can absorb, all additive and all listed in §6.9.

**ERD — 0 changes required.** `homebandhu.dbml` v2 already carries every column and constraint these
resolutions depend on: `staff_rank`, `department_kind`, the three partial uniques on
`staff_assignments`, `one_active_membership_per_profile_uq`, and `resident_invites`'
`token_digest`/`code_digest`/`attempt_count`/`recipient_phone_e164`. `displayRole` is **computed, not
stored** — deliberately, so that adding a shell later is an API change and not a migration.

**Class diagram — 13 edits, all local.** No package moved, no association was deleted:

| # | §4.2.1 conflict | Resolution in `homebandhu-domain.puml` |
|---|---|---|
| 1 | `AuthUser` has no phone | `phone {unique}` + `phoneConfirmedAt` added; `email` demoted to `[0..1]`; note now names phone as *the* login identifier |
| 2 | `ResidentInvite` is email-only, no digests | `recipientPhoneE164 {required}`, `tokenDigest {unique}`, `codeDigest`, `attemptCount`; `accept(p)` → `redeem(secret, v)`; note states the two factors explicitly |
| 3 | `inviteResident(u, email)` | → `inviteResident(u : Unit, phone : String)` |
| 4 | `applicantEmail {required}` ×2 | phone promoted, email `[0..1]`, on both intake classes |
| 5 | scope note claims per-role membership rules | rewritten: **one** active membership per profile, no exceptions; multi-department moved to `StaffAssignment` where it belongs |
| 6 | *"staff & non-staff not mixed"* | deleted, replaced by an explicit `{role vs capability}` clause naming the security-supervisor-who-lives-in-302 case |
| 7 | `activeMemberships() : List<>` + `membershipIn(c)` | collapsed to `activeMembership() : Optional<>` — the invariant is now visible in the signature |
| — | two independent OTP verifiers | `Profile.verifyPhone(otp)` → `markPhoneVerified(v)`; `CommunityRegistrationRequest.verifyOtp(code)` → `attachVerifiedIdentity(v)`. Neither aggregate knows what an OTP is any more |
| — | `grantRole(p, r)` | → `assignStaff(p, d, rank) : StaffAssignment` — granting staff-ness creates a row, it does not set a value |
| — | 5-value `MembershipRole`, 5 subclasses | → 3 and 3; `StaffRank`, `DepartmentKind`, `CommitteePositionStatus` added; `WorkerMembership`/`SecurityMembership`/`ManagerMembership` merged into `StaffMembership` with a guard note |
| — | `StaffAssignment` note said "one active per membership" | replaced with the rank-dependent cardinality (§3.10) and the array-claim consequence |
| — | `Department` had no `kind` | `kind`, contacts, hours, `slaHours`, `head()` added |
| — | committee membership unrepresentable | new `CommitteePosition` class + two associations |
| — | `VerifiedIdentity` existed only in prose | added as a value object, with the "no role, no membership, no community" rule in its note |

`CommunityMembership "1" -- "0..1" StaffAssignment` also becomes `"0..*"`, which the old flat
invariant had made wrong.

**design-of-components.md — 3 sentence-level edits, no restructuring.** The document describes a
prototype accurately, so it was corrected rather than rewritten: separate login *flows* became
separate *entry points sharing one flow*; the invitation bullet now says the secret is required
rather than optional; the per-tab session bullet is marked as prototype behaviour with the
server-session consequence named; and the onboarding OTP bullet notes the reordering. Its
*"time-limited, single-use invitations"* language was left untouched — it already supports the
mandatory-token rule.

**Still open, deliberately.** The `department_kind` value list is a first cut
(`security, maintenance, housekeeping, facilities, other`, §10.11) and needs the team's confirmation;
`.puml` and `.dbml` now agree on it. Adding values later is cheap — only `security` is load-bearing
in RLS. Trades like plumbing and electrical are `job_title` and `skills`, not kinds; a kind exists
only where a *dashboard* differs.

---

## 5. Database plan

Migrations live in `backend/supabase/migrations/`, applied with `supabase db push`. The existing
`0001`–`0003` are **replaced**, not amended (nothing is deployed yet). **The migrations are the
source of truth**; the ERD and the `.puml` are projections of them and get regenerated/updated at the
end of each phase, never the other way round.

The table set below is the ERD's, plus the rows the ERD is missing (marked **new**) and minus the
role-model changes from §3.1. Where a name differs from the ERD, the ERD's name wins — it is already
Postgres-shaped.

| # | File | Contents |
|---|---|---|
| 0001 | `core_extensions_enums.sql` | `pgcrypto`, `btree_gist`, `citext`; all ~38 enums from the diagram (minus `TECHNICIAN`); `set_updated_at()` and `bump_version()` triggers |
| 0002 | `identity_community.sql` | `profiles`, `communities` (+`community_type`, immutability trigger), `community_registration_requests`, `buildings`, `units` (+the §3.3 exclusivity check), `community_memberships` (role = RESIDENT/STAFF/ADMIN), `unit_residencies`, **`committee_positions`**, **`community_settings`** |
| 0003 | `rls_helpers.sql` | `auth_membership_id()`, `auth_community_id()`, `auth_role()`, `is_admin()`, `is_resident()`, `is_committee()`, `has_unit(uuid)`, `staff_rank(uuid)`, `is_staff_of_department(uuid)`, `is_security_staff()`, `manages_department(uuid)` — all `stable security definer`, the vocabulary every later policy is written in |
| 0004 | `rls_core.sql` | RLS enabled + policies on everything in 0002 |
| 0005 | `access_token_hook.sql` | `custom_access_token_hook(event jsonb)` injecting `membership_id`, `community_id`, `role`, `permissions`; grant to `supabase_auth_admin`; **register in Dashboard → Auth → Hooks** |
| 0006 | `onboarding.sql` | `resident_invites` (+`token_digest`, `code_digest`, single-use compare-and-set), `access_requests` |
| 0007 | `staff.sql` | `departments` (+`kind`, categories, SLA, hours, head/contact), `vendors`, `skills`, `staff_assignments` (+`rank`, `job_title`, `shift`, `status`), `staff_skills`, `worker_availability_rules`, `worker_unavailability` |
| 0008 | `complaints.sql` | **`complaint_categories`**, `complaints`, `complaint_events`, **`complaint_comments`**, **`complaint_read_state`**, **`complaint_attachments`** |
| 0009 | `work_orders.sql` | `work_orders`, `work_order_assignments` (**`EXCLUDE USING gist (staff_assignment_id WITH =, scheduled_range WITH &&) WHERE status='ACCEPTED'`**), `work_order_proposals`, `work_order_views`, `work_order_completion_verifications`, `work_order_attachments` |
| 0010 | `visitors.sql` | `saved_visitors`, `visitor_access_requests`, `visitor_events`, `visitor_attachments`, **`security_incidents`**, **`emergency_contacts`** |
| 0011 | `amenities.sql` | `amenities`, `amenity_rules`, **`amenity_blocked_slots`**, `amenity_booking_series`, `amenity_booking_occurrences` (**gist exclusion on active occurrences per amenity**), `booking_guests`, `amenity_booking_charges`, `amenity_financial_events` |
| 0012 | `finance.sql` | `invoices`, `invoice_line_items`, `payments`, `payment_events` |
| 0013 | `comms_media.sql` | `notices`, `policies`, `policy_revisions`, `notifications`, `notification_deliveries`, **`activity_events`**, `audit_events`, `media_assets` |
| 0014 | `platform.sql` | **`otp_challenges`**, **`auth_sessions`**, **`idempotency_records`** (all three absent from the ERD); `pg_cron` schedules (mark-overdue, expire invites/proposals, purge idempotency) |
| 0015 | `rls_all.sql` | RLS + policies for 0006–0014 |
| 0016 | `realtime_storage.sql` | `alter publication supabase_realtime add table …` for the invalidation set; storage buckets + `storage.objects` policies |
| 0017 | `seed_dev.sql` | Dev-only fixtures mirroring `frontend/src/data/*` so the UI can be pointed at a real DB early |

**Cross-cutting column contract on every tenant table:**
`id uuid pk default gen_random_uuid()`, `community_id uuid not null references communities(id)`,
`version integer not null default 1` (bumped by trigger), `created_at`, `updated_at`.
Deletes are status transitions wherever history references the row.

**RLS pattern.** Every policy is expressed with the 0003 helpers, e.g.

```sql
create policy units_resident_read on public.units for select
  using (community_id = auth_community_id() and (is_admin() or has_unit(id)));
```

**Policy matrix — written per table before any coding.** Note that the rows are *capabilities*, not
role values (§3.1), so a person can match several at once:

| Principal | Read | Write |
|---|---|---|
| holds `unit_residencies` (resident, incl. the admin) | own unit, own household, own complaints/bookings/invoices, community-wide notices | own rows only |
| holds `committee_positions` | resident scope; extra scope deferred (§4.1.9) | none extra in v1 |
| `staff_assignments.rank = WORKER` | work orders / complaints assigned to them | status + notes on those only |
| `rank = SUPERVISOR` | all work in **their** department | assign and reassign within the department |
| `rank = MANAGER` | their department incl. staff roster | department settings + staff; cannot remove self |
| department `kind = SECURITY` (any rank) | visitor passes, gate events, incidents — **plus a narrow audited RPC** for resident contact lookup; the class diagram explicitly forbids a broad resident directory here | gate events, check-in/out |
| `role = ADMIN` | whole community | whole community |

The security scope is a *department-kind* predicate (`is_security_staff()`), not a role check — that
is what lets a plumbing supervisor and a security supervisor share a rank without sharing visitor
data.

---

## 6. Auth and session design (Supabase-native)

### 6.1 One door — there is no login button and no signup button

**DECIDED 2026-07-28.** The product has a single entry point. The user types a phone number; the
backend alone decides whether that is a login, an activation, or the start of a new association. The
client never asserts which.

The four endpoints in `frontend-documentation.md` §"Endpoint Summary" collapse into one pair, because
an `admin`/`community` path prefix *is* the client asserting a privileged role before authenticating —
the exact thing `frontend-documentation.md` line 21 forbids. The document contradicts itself; we
resolve toward line 21.

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/otp/request` | phone in, challenge out — **discloses nothing** |
| `POST /api/v1/auth/otp/verify` | challenge + code in, session **and branch** out |
| `POST /api/v1/auth/refresh` | rotates the `HttpOnly` refresh cookie |
| `GET  /api/v1/auth/me` | session restore on reload |
| `POST /api/v1/auth/logout` | revoke |

#### The portal is a hint, never a claim — **RESOLVED 2026-07-28**

One door does **not** mean one screen. The two-portal design is a *presentation* choice and the
frontend may keep it indefinitely; what collapses is the *trust* model, which was never the
frontend's to hold. Both screens call the same two endpoints and get identical behaviour.

To make that concrete and to keep the documented URLs alive, the role-prefixed paths stay as **thin
aliases**:

```
POST /api/v1/auth/admin/otp/request      ─┐
POST /api/v1/auth/community/otp/request  ─┴─► the same handler; prefix parsed, then discarded
```

The prefix is accepted, logged as an analytics dimension (`entry_point`), and **never read by any
authorization decision**. An admin who types their number into the community portal signs in as an
admin; a resident who types theirs into the admin portal signs in as a resident. Neither is rejected
for using the "wrong" door, because there is no wrong door — which is exactly what
`ResidentLoginPage.jsx:69` gets wrong today, and it stops mattering the moment the branch comes from
the server.

This is the resolution that costs the frontend nothing: two screens, two URLs, one truth.

**No frontend code has been changed, and none will be without the frontend team.** §6.9 states the
compatibility contract the backend commits to, and lists the little that genuinely cannot be absorbed
server-side.

### 6.2 The request step discloses nothing

**DECIDED 2026-07-28 — reveal after OTP, not before.** Every syntactically valid phone gets an
identical `202 { challengeId, expiresIn, resendAfter }`, registered or not, and every one is sent an
SMS. We accept the cost to close the enumeration oracle.

The consequence is that the founding admin is verified at step 0, so the step-5 OTP at
`/onboarding-otp-verification` becomes redundant and `register_community` commits against an
already-verified session. An unverified stranger can no longer burn a five-step onboarding. **This
touches the onboarding screens, so it is a §6.9 item for the frontend team, not a change we make.**
If the frontend team prefers to keep the step-5 screen, the backend can serve it as a no-op confirmation —
the contract does not depend on which way they go.

Flow: service client → `sign_in_with_otp(phone, should_create_user=true)` → persist an
`otp_challenges` row for `challengeId`, purpose-binding, rate limiting and attempt counting. **We
never store or verify the code itself; that stays GoTrue's.**

`should_create_user` is now `true` for every login, not just registration, because we cannot branch
before verifying without leaking. An `auth.users` row for a phone that never completes verification
is inert — it holds no membership, so RLS grants it nothing. `pg_cron` reaps unconfirmed,
membership-less users after 24 h.

### 6.3 Rate limiting — server-side keys only

**A client-supplied token can never be a rate-limit control.** The attacker clears it, or never
stores it, or mints a fresh one per request. The frontend today holds nothing usable anyway: only
`zustand/persist` keys (`homebandhu-auth` in sessionStorage, `homebandhu-*` in localStorage), no CSRF
token, no device id, and `lib/ids.js#genId` is `Date.now()` + `Math.random()` — client-minted and
guessable.

Limits key on what the attacker cannot cheaply change. All four counters are queries over
`otp_challenges`, which already carries `phone_e164`, `requested_ip`, `attempt_count` and
`created_at`. **No Redis in v1** — Postgres is comfortable at this scale.

| Key | Limit | Protects |
|---|---|---|
| `phone_e164` | 3 sends / 15 min, 10 / day | the person being spammed — the primary control |
| `requested_ip` | 20 sends / hour | one attacker enumerating many numbers |
| IP `/24` | 60 / hour | a small botnet |
| global | circuit-breaker on sends/hour | **the SMS bill**, under a distributed attack |

Per-challenge: 5 wrong codes burns it. `429` always carries `Retry-After`.

**Trusted-device cookie (phase 2, optional).** After a successful verify, issue a server-side,
`HttpOnly`, revocable device token good for 30–90 days that skips OTP entirely on return. This is
the single largest lever on SMS spend — larger than provider price — and it is the *only* legitimate
use of a device token here. It is not, and cannot be, a rate-limit control.

### 6.4 The OTP channel is swappable

Cheap SMS is unresolved, so the delivery channel must not be load-bearing. Use Supabase's **Send SMS
Hook**: GoTrue still generates, hashes and verifies the code, but calls our function to deliver the
message. Swapping MSG91 → a WhatsApp template → a console stub becomes configuration, not a code
branch, and `verify_otp` keeps working untouched.

Rejected: generating OTPs ourselves. It buys nothing and makes us own hashing, timing-safe compare,
and minting a Supabase session by hand.

**Before shopping for providers, note the volume is smaller than it looks.** At a 900 s access token
with a 30-day rotating refresh cookie, a resident authenticates by SMS roughly once per device per
month — a 200-flat association is ~200 SMS/month, not 200/day. With §6.3's trusted-device cookie at
90 days it is a third of that.

### 6.5 What `verify` returns — the branch

`POST /auth/otp/verify` → `verify_otp(type='sms')` → resolve state → one of:

| State | Response |
|---|---|
| Active membership | `200` session + `dashboard` |
| Pending invite for this phone | `200 { nextStep: "REDEEM_INVITE" }` + activation ticket, **no session** |
| Pending `access_request` | `200 { nextStep: "AWAIT_APPROVAL" }`, no session |
| No membership, no invite | `200 { nextStep: "REGISTER_COMMUNITY" }` + a short-lived onboarding session |
| Membership suspended / ended | `403 MEMBERSHIP_SUSPENDED` |
| Community archived | `403 COMMUNITY_SUSPENDED` |
| Wrong / expired / replayed code | `401 OTP_INVALID` / `410 OTP_EXPIRED` / `409 OTP_ALREADY_USED` |

**DECIDED 2026-07-28 — the invite token is mandatory for first activation.** An earlier draft of
this plan proposed auto-redeeming a pending invite on OTP alone, treating the token as a convenience.
That is overruled: **the token is the second factor.** Redemption requires *something you have*
(the phone, proven by OTP) **and** *something you were given* (the token or code, proven by the
link or by typing it). Verifying a phone that has a pending invite therefore yields an **activation
ticket, not a session** — the caller must then present the token to
`POST /auth/invitations/redeem`, which does the compare-and-set and only then issues the session.

Consequence: OTP alone can never create a membership. The only three ways to obtain one are an
admin-issued invite redeemed with its token, an approved `access_request`, and founding a community.
This is also why an admin typo on a phone number is contained — the stranger who receives the SMS
still cannot activate without the token, which went to the same wrong number but as a distinct
artifact the admin can revoke.

`resident_invites` already supports this unchanged: `token_digest [not null, unique]`, `code_digest`,
`attempt_count`, `recipient_phone_e164 [not null]`. No schema change.

`409 MEMBERSHIP_SELECTION_REQUIRED`, the `membershipId` field in the verify body, and the selection
token are **deleted from v1** by the one-association rule (§6.7).

### 6.6 Claims and redirect resolution

The access-token hook reads `active_membership_id` from `auth.users.app_metadata` and emits
`membership_id`, `community_id`, `role`, `is_resident`, `is_committee`, `permissions`, and — because
RLS needs the other two axes without a join on every policy — `department_ids uuid[]`,
`department_kinds text[]` and `rank`. **The department claims are arrays, not scalars** (§3.10):
a worker may serve several departments, so RLS predicates read `department_id = ANY(claim)`.

FastAPI verifies with `SUPABASE_JWT_SECRET` (HS256, `aud=authenticated`) and builds a
`SecurityContext`. A change to anyone's department or rank bumps `app_metadata.claims_version`, so
the next refresh re-mints claims — without it a demoted supervisor keeps supervisor access until
token expiry.

**`role` decides the landing shell only, never the capability set.** Capabilities remain possessions
(§3.1): resident-ness is a `unit_residencies` row, staff-ness a `staff_assignments` row. This is what
makes two awkward cases fall out for free — the admin who is also a resident (already allowed at
`App.jsx:200`), and the resident who is also the security supervisor: `role = staff`, lands on the
security shell, and `is_resident = true` lets them switch to `/resident`. Neither needs a special
case.

#### The display-role projection — **RESOLVED 2026-07-28**

The three-axis model is an *internal* model. Nothing obliges the API to expose it as the thing the
router switches on, and doing so would force the frontend to rewrite
`getDashboardRouteForRole`, `ProtectedRoute`'s `requiredRole` arrays, and every `role === 'Admin'`
comparison in the tree.

So verify and `/auth/me` return **three parallel views of the same fact**:

| Field | Vocabulary | Consumed by |
|---|---|---|
| `role`, `departmentKinds`, `rank` | the honest internal triple | new code, RLS, anything that needs precision |
| **`displayRole`** | **the frontend's existing 4 strings** | `getDashboardRouteForRole`, `requiredRole`, existing `===` checks |
| `dashboard` | a stable discriminator | future routing that wants to stop guessing |

`displayRole` is computed server-side, from the triple, into the vocabulary
`frontend/src/routes/authRoutes.js` already speaks:

| `role` | kind | rank | `displayRole` | `dashboard` | Existing helper sends them to |
|---|---|---|---|---|---|
| `admin` | — | — | `Admin` | `ADMIN` | `/admin` ✅ |
| `resident` | — | — | `Resident` | `RESIDENT` | `/resident` ✅ |
| `staff` | `security` | `manager` | `SecurityManager` | `SECURITY_MANAGER` | `/security-manager` ✅ |
| `staff` | `security` | `supervisor` | `SecurityManager` | `SECURITY_SUPERVISOR` | `/security-manager` ✅, roster read-only |
| `staff` | `security` | `worker` | `Security` | `SECURITY` | `/security` ✅ |
| `staff` | any other | any | `Staff` | `PENDING_SHELL` | ⚠️ falls through to `/resident` — see §6.9, item 1 |

Five of the six rows land correctly through the helper **exactly as it is written today, with no
edit at all**. That is the whole point of the projection: the role vocabulary the frontend was built
against keeps working, while the backend keeps the model it actually needs.

Two consequences worth stating plainly:

- The supervisor sharing `displayRole = SecurityManager` with the manager is deliberate. They share
  a *shell*; what differs inside it (roster read-only) is read from `rank`, which the shell already
  receives. A distinct route for supervisors would be a new screen, not a routing fix.
- Only the last row is a real gap, and it is a gap in the **UI's** coverage, not a disagreement —
  there is no plumbing-department shell to route to yet. `Staff` is deliberately a *new* string, so
  the existing helper's fallback is visibly wrong rather than silently plausible.

Multi-department workers resolve by the §3.10 tiebreak. The backend returns a role, never a URL —
route paths stay a frontend decision.

### 6.7 One phone, one association

**DECIDED 2026-07-28.** A phone belongs to exactly one association, and this is enforced by
Postgres rather than by convention: `profiles.phone_e164` is already globally unique, and
`community_memberships`' partial UQ moves from `(community_id, profile_id)` to **`(profile_id) WHERE
status = 'active'`**.

Founding is blocked too — `register_community` rejects any phone holding an active membership
anywhere. One new error code the docs lack: **`409 ALREADY_IN_ANOTHER_COMMUNITY`**, raised both there
and when an admin invites a phone that is live elsewhere.

### 6.8 Authentication is one replaceable function — `AuthenticationProvider`

**DECIDED 2026-07-28.** How we prove someone holds a phone is unsettled (SMS pricing, possible
WhatsApp or another channel), so it must not be load-bearing. **All of it lives behind one interface
in `app/auth/provider.py`, and no other module in the backend may import `supabase.auth` or talk to
an SMS vendor.** Swapping the mechanism is then a settings change plus one new class — routing,
redirects, RLS, and every endpoint stay untouched.

```python
class AuthenticationProvider(Protocol):
    async def ensure_user(phone: E164) -> AuthUserId
    async def start_challenge(phone: E164, purpose: Purpose, ip, ua) -> Challenge
    async def verify_challenge(challenge_id: UUID, code: str) -> VerifiedIdentity
    async def issue_session(profile_id: UUID, membership_id: UUID | None) -> SessionTokens
    async def refresh_session(refresh_token: str) -> SessionTokens
    async def revoke_session(session_id: UUID, reason: str) -> None
```

**The critical design rule is what `VerifiedIdentity` carries:**

```python
@dataclass(frozen=True)
class VerifiedIdentity:
    auth_user_id: UUID
    phone_e164:   str
    purpose:      Purpose
    verified_at:  datetime
```

No role. No membership. No community. **Authentication answers only "who holds this phone."**
Everything in §6.5–§6.7 — branch resolution, membership lookup, the one-association rule, the
dashboard mapping — is *authorization*, and lives in a separate `MembershipResolver` that consumes a
`VerifiedIdentity` and knows nothing about how it was obtained. That boundary is precisely what keeps
the OTP mechanism swappable: change the left-hand side freely, the right-hand side never notices.

| Implementation | Mechanism | Use |
|---|---|---|
| `SupabaseOtpProvider` | GoTrue `sign_in_with_otp` / `verify_otp` | **default** |
| `SelfHostedOtpProvider` | we generate, hash and compare; session minted via `auth.admin` | if GoTrue's SMS path proves too costly or too rigid |
| `StubOtpProvider` | fixed code, no send | dev, demo, graded submission — zero SMS spend |

Selected by one setting, `AUTH_PROVIDER=supabase|selfhosted|stub`. A CI import-linter rule fails the
build if `supabase.auth` is referenced outside this module.

**A second, narrower seam sits inside the default provider.** `OtpDeliveryChannel.send(phone, code)`
swaps only the *carrier* (MSG91 → WhatsApp template → console stub) while GoTrue keeps generating and
verifying the code — this is Supabase's Send SMS Hook from §6.4. Two levers at two depths: change the
carrier without leaving Supabase, or change the whole mechanism without leaving the endpoint layer.

### 6.9 Frontend compatibility contract — **RESOLVED 2026-07-28**

Nothing in `frontend/` has been modified, and the target is **zero conflicts**: the backend adapts to
the UI that exists, not the other way round. Four rules make that possible, and they are binding on
the backend.

| # | Rule | Absorbs |
|---|---|---|
| C1 | **The portal prefix is accepted and ignored** (§6.1). Role-prefixed URLs stay as aliases. | Two screens, two URL families, one trust model |
| C2 | **`displayRole` is emitted in the frontend's existing vocabulary** (§6.6). | `getDashboardRouteForRole`, `requiredRole` arrays, every `role === 'Admin'` check |
| C3 | **`isRegistered` keeps its name and shape**, and is now always `true` for any well-formed number (§6.2) — it truthfully means *"a code is on its way"*. | `LoginPage.jsx:45`'s branch: everyone goes to the OTP screen, which is what disclose-nothing wants anyway |
| C4 | **Every response that causes navigation also carries `redirectTo`.** Pages may adopt it as `result.redirectTo ?? <their existing constant>`. | Hard-coded `navigate(ADMIN_DASHBOARD)` in `OtpVerificationPage.jsx:31` |

C4 has a property worth insisting on: **every frontend edit it implies is backward-compatible with
the current mocks.** `result.redirectTo ?? AUTH_ROUTES.ADMIN_DASHBOARD` behaves identically today,
when `redirectTo` is `undefined`, and correctly tomorrow, when it is not. The frontend team can
therefore take these changes whenever they like, in any order, without a coordinated cutover — which
is the difference between a compatibility contract and a migration.

`frontend/src/services/adminAuthService.js` is where the real work lands, and its own comment already
says so: *"Replacing its body with an Axios request will not require changes in the store or pages."*
That file is a mock; it was always going to be rewritten. Rewriting it is not a conflict.

**What the contract cannot absorb — three items, all additive:**

1. **A shell for staff outside the security department.** `displayRole = 'Staff'` has nowhere to go,
   so `getDashboardRouteForRole` drops it to `/resident`, which is wrong. Needs one route and one
   branch — a WIP placeholder with a back-to-login button (§3.1). This is a missing screen, not a
   disagreement.
2. **Per-tab independent sessions.** `authStore` persists to `sessionStorage`, so a resident tab and
   an admin tab stay separately logged in. An `HttpOnly` refresh cookie is shared across tabs by
   definition, so *two different users in two tabs* stops working. The in-app admin↔resident switcher
   covers the real product need, but this is how the team demos today and they should hear it early.
   No backend workaround exists — this is what "the session is real now" costs.
3. **The step-5 onboarding OTP is redundant** (§6.2), because the founder is verified at step 0. It
   can stay as a no-op confirmation screen if they prefer; the backend serves it either way.

Items 1 and 3 are the frontend team's call and cost the backend nothing. Item 2 is the only one with
no comfortable answer.

Three things that were on this list and are now **closed, requiring no frontend change**: the two
login screens merging into one (C1 — they don't), the login-vs-register branch moving (C3 — the field
keeps working), and invite redemption (§6.5 — `/join/:token` and the "registration code" step in
`ResidentLoginPage.jsx` are *exactly* the two-factor flow the mandatory-token rule needs, already
built).

### 6.10 Session claims, permissions, and the membership-creating flows

Because staff scope is now inside the token, a change to someone's department or rank must invalidate
their session: those writes bump `auth.users.app_metadata.claims_version` and the next refresh
re-mints the claims. Without this, a demoted supervisor keeps supervisor access until token expiry.

**Permissions.** `permissions[]` is derived from the *triple* `(role, department_kind, rank)` via a
static map in `domain/permissions.py` (`residents.manage`, `amenities.manage`, `amenities.finance`,
`notices.publish`, `billing.read`, `security.staff.manage`, `department.staff.manage`,
`workorders.assign`, `settings.manage`, …), with a `community_memberships.permissions jsonb`
override column present from day one but unused in v1.

**Community registration.** Per §6.2 the founder is already phone-verified at step 0, so onboarding
runs inside a short-lived onboarding session and the step-5 OTP is gone. Final submit calls a single
`register_community(payload jsonb)` Postgres
function under the service role → community (with `community_type` fixed here, permanently) +
buildings **or** villa units per §3.3 + profile + ADMIN membership + **the admin's own
`unit_residency` and `committee_position` with the designation collected in onboarding step 4** +
settings + audit, all in one transaction, guarded by the idempotency key. The residency and committee
rows are not optional extras — they are what makes "the admin is a committee member and therefore a
resident" true in the data rather than in application logic.

**Invitation redemption.** `redeem_invite(token_or_code, phone)` → Postgres function does the
compare-and-set (`update … where redeemed_at is null returning …`) so double redemption is
impossible; then `auth.admin.create_user(phone_confirm=True)`, membership activation, session issue.
**Per the doc's open question, the recommended default is one membership per redemption** — the
prototype's "activate every phone on the flat" is unsafe. Additional household members go through
the household-add flow with their own OTP.

**Staff login** works through the same single OTP endpoint once §4.1(1) provisioning exists — there
is no separate "security account" path (which is what `lib/securityAccounts.js` is today).
Provisioning a staff member creates the membership with `role = 'STAFF'` plus `staff_assignment`
row(s) carrying `department_id`, `rank` and `job_title`, subject to the §3.10 cardinality rules — one
row for a manager or supervisor, one per department for a worker. Department kind then decides the
shell.

---

## 7. Backend code layout

Extends what already exists; the mapping to `homebandhu-architecture.puml` is 1:1.

```
backend/app/
  main.py                      FastAPI factory, CORS, exception handlers, /health
  config.py                    ✅ exists
  core/
    supabase_client.py         ✅ exists — keep as-is
    security.py                JWT verify → SecurityContext          (rework: claims)
    exceptions.py              AppError hierarchy → the error-code catalogue
    envelope.py                data/meta/error response wrappers, requestId
    idempotency.py             Idempotency-Key middleware + store
    pagination.py              opaque cursor encode/decode
    logging.py                 ✅ exists
  domain/
    roles.py                   (rework: RESIDENT/STAFF/ADMIN + StaffRank + DepartmentKind,
                               no TECHNICIAN, + uiRole derivation table from §3.1)
    permissions.py             (role, department_kind, rank) → permission set
    money.py                   numeric ↔ minor units
    schemas/                   DTOs, one module per bounded context
  repositories/                one per aggregate; the ONLY layer touching Supabase
  services/                    use-case orchestration; framework-agnostic; unit-testable
  api/
    deps.py                    get_current_user, require_role, require_permission,
                               get_request_client, get_idempotency
    v1/routers/                auth, registration, communities, memberships, units,
                               invitations, access_requests, departments, staff,
                               complaints, notices, activities, uploads, dashboard,
                               visitors, security, invoices, payments, webhooks,
                               amenities, bookings, ledger, reports
supabase/migrations/           see §5
tests/                         pytest — pure logic + RLS integration tests
```

**Layer rule (from the architecture diagram):** services depend on repository interfaces, never on
the Supabase SDK. Only `repositories/` and `core/supabase_client.py` import `supabase`.

---

## 8. Build order

Each phase ends with the named verification actually run, not assumed.

| Phase | Scope | Verification |
|---|---|---|
| **1. Platform** | Migrations 0001–0005; rework `roles.py`/`security.py`; envelope, error catalogue, idempotency, pagination, `deps.py`; `/health` | Server boots; a hand-issued JWT decodes with `role` + `community_id` claims present (proves the hook is registered) |
| **2. Auth** | Admin + community OTP request/verify, `/auth/me`, `/auth/refresh` (cookie), `/auth/logout`; membership selection | Supabase *test phone numbers*; unknown phone → `register_community`; RESIDENT token on an admin route → `403`; direct PostgREST query with a resident JWT returns only own-unit rows |
| **3. Onboarding** | `register_community` RPC, uploads/Storage, `/communities/current`, settings | Full onboarding replay is atomic; replaying the idempotency key creates no second community; **an apartment community rejects a villa unit and vice-versa (§3.3), and the admin comes out with a residency + committee position** |
| **4. People** | Invitations (create/list/renew/revoke/redeem), residents, household members, admins, access requests | Concurrent double-redeem → exactly one wins; expired/used/revoked each return their documented code |
| **5. Org + complaints** | Departments (+`kind`), staff assignments (+`rank`), **staff→membership provisioning (§4.1)**, complaint categories, complaints + comments + events + read-state; work-order tables created (no endpoints) | Security guard logs in via a staff record and lands on the security dashboard; a **plumbing supervisor with the same rank cannot read a single visitor row**; SLA computed server-side; manager cannot remove self; demoting a supervisor invalidates their claims |
| **6. Visitors + security** | Passes, approvals, verify-and-check-in, check-out, gate events, incidents, emergency contacts | Concurrent check-in → one succeeds; expired pass → `410`; brute-force → `429` |
| **7. Money + amenities** | Invoices, payment orders, provider webhook, reconciliation; amenity catalog/settings/availability/booking/approvals/ledger/reports | Overlapping bookings rejected by the **gist constraint**, not by app code; replayed webhook is a no-op; refund cannot exceed remaining deposit |
| **8. Realtime, notices, dashboards, work orders** | Notices, notifications, activity feed, dashboard aggregates, Realtime channels, work-order endpoints | Resident subscription receives no other apartment's events |

Phases 5–7 are independent of each other once phase 4 lands — that is where the team parallelises.

---

## 9. What we discard from the current `backend/`

- `supabase/migrations/0001–0003` — rewritten (wrong role model, `profiles.role`, `TECHNICIAN`,
  `units`=blocks naming).
- `domain/roles.py` — `TECHNICIAN` removed; the enum becomes `RESIDENT/STAFF/ADMIN` plus separate
  `StaffRank` and `DepartmentKind`; the hardcoded `ADMIN ⊇ RESIDENT` implication map is deleted
  outright — resident-ness is a `unit_residencies` lookup (§3.1), which is both true and enforceable
  in RLS, where a Python dict is not.
- `repositories/profiles_repository.py` role read/write — role moves to memberships.
- **Kept unchanged:** `core/supabase_client.py`, `config.py`, `core/logging.py`, `core/tokens.py`,
  `core/exceptions.py`, and both test modules' structure.
- `docs/plan.md` gets a header pointing here; root `AGENTS.md` / `docs/CLAUDE.md` / `README.md`
  still describe "no backend" and need updating at the end of phase 2.

---

## 10. Decisions the team must make before phase 1

These block or expensively rework later phases. My recommendation is given for each — the point is
to confirm or overrule, not to leave them open.

1. **SMS provider + budget.** MSG91 recommended. Without it, phase 2 cannot leave test numbers.
2. **Invitation redemption scope.** *Recommend one membership per redemption.*
3. **Naming rename (`buildings`/`units`).** *Recommend yes, now.* Free today.
4. ~~**Admin-as-resident.**~~ **Resolved** by the product owner: admin ⊂ committee ⊂ resident.
   `register_community` creates the ADMIN membership *plus* a `unit_residency` and a
   `committee_position` (§6). No dual membership, no role-implication hack.
5. **Public self-registration** (`/signup` is dormant). *Recommend building `access_requests` — the
   admin `/admin/pending` screen is live and needs a source.*
6. **SecurityManager write authority.** *Recommend: read-only on visitor operations, write only on
   own-department staff.* Now generalises to every department: a MANAGER of any `kind` manages their
   own roster; only SECURITY-kind departments see visitor data at all.
7. **Payment provider.** Razorpay assumed for UPI intent + webhook signatures. Blocks phase 7.
8. **Virus scanning on uploads.** Supabase has none natively. *Recommend v1 accepts private buckets
   + MIME/size/extension validation, and records the gap explicitly.*
9. ~~**Multi-community memberships.**~~ **Resolved** by the product owner: one phone, one
   association, for every role (§6.7). Enforced by `one_active_membership_per_profile_uq`, not by
   convention. The class diagram's contrary scope note was the artifact, and is now corrected
   (§4.5).
10. **What can a committee member do that a resident cannot?** Nothing is specified anywhere. *Recommend
    shipping the data (`committee_positions`, `isCommittee` in the session) with zero extra
    permissions in v1*, so the answer can be filled in later as a permission-map change and not a
    migration.
11. **The `department_kind` value list.** `SECURITY` is the only one that changes behaviour today.
    *Recommend `SECURITY, MAINTENANCE, HOUSEKEEPING, FACILITIES, OTHER`* — small, and only `SECURITY`
    is load-bearing in RLS, so adding kinds later is cheap.
12. ~~**Can a staff member also be a resident?**~~ **Resolved: yes**, and it costs nothing — one
    membership holding both a `staff_assignment` and a `unit_residency` (§6.6). They land on the
    staff shell with `is_resident = true`, and switch via the same mechanism the admin↔resident
    switcher already uses.
13. ~~**Can one person hold two staff assignments?**~~ **Resolved** by the product owner, and not the
    way this item recommended: cardinality is **rank-dependent** (§3.10). One manager per department;
    managers and supervisors serve one department; workers may serve several. The token therefore
    carries `department_ids` as an **array** — the single-`department_id` assumption behind the old
    recommendation is what made it wrong.
