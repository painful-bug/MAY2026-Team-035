# Conflict resolutions — milestone-1 artifacts

**Date:** 2026-07-29
**Resolves:** every issue catalogued in [`MILESTONE1_ARTIFACT_ISSUES.md`](MILESTONE1_ARTIFACT_ISSUES.md)
**Status:** proposals. Nothing here has been applied to any artifact — the ERD, class diagrams and
component design are maintained by other people. Each resolution names its owner.

---

## 0. The three constraints every resolution had to satisfy

1. **Zero frontend conflicts.** No resolution may require a change to `frontend/src/` to work. Where
   the frontend is wrong, the backend adapts at the boundary and the frontend change becomes
   optional cleanup.
2. **Minimal change to the ERD, class diagrams and component design.** Prefer a column to a table,
   a table to a redesign, a note to a column, and derivation to storage.
3. **Resolve in the layer that owns the truth.** If the frontend's behaviour is the product, the
   schema moves. If the schema is right, the API adapts and the document gets a note.

Four techniques do most of the work below, so they are named once here:

- **Additive boundary.** The API response is a superset of what the frontend already reads. New ids
  and ISO instants ride alongside the display strings the frontend uses today. Nothing breaks; the
  frontend adopts the better fields whenever it wants.
- **Derivation over storage.** If a requirement can be computed from data that already exists, it
  gets a view or a rule, not a table.
- **Structural enforcement over convention.** Where a resolution risks silent corruption, prefer a
  constraint the database enforces over a rule a developer must remember.
- **Phase tagging.** A table with no v1 consumer stays in the ERD with a note, rather than being
  deleted or quietly built.

**How to read the tables:** *Cost* is measured against the v1 ERD as submitted. Owner is who has to
make the edit, not who decided it.

---

## 1. ERD internal defects

### R1 — `units` uniqueness scoped by building *(audit 1.1 #1 — ranked first)*

**Decision:** replace `units_community_label_uq` with **two partial unique indexes.**

```sql
-- units inside a building: label unique within that building
create unique index units_building_label_uq
  on units (building_id, unit_label) where building_id is not null;

-- standalone units (villas, plots): label unique within the community
create unique index units_community_standalone_label_uq
  on units (community_id, unit_label) where building_id is null;
```

**Why two.** `units.building_id` is nullable, and Postgres treats NULLs as distinct in a unique
index — a single `(community_id, building_id, unit_label)` index would silently permit duplicate
villa labels. The alternative, making `building_id` NOT NULL and inventing a synthetic building for
villa communities, pollutes every villa query with a fake row. Two partial indexes cost nothing at
runtime and each says exactly what it means.

DBML cannot express a partial index, so in the `.dbml` this becomes the two index entries plus a
`Note` recording the `where` clauses. **Owner:** ERD. **Cost:** one index replaced by two.

This index is load-bearing for R21 (find-or-create units), so it should land first.

---

### R2 — invitation secrets *(audit 1.1 #2)*

**Decision:** keep the "never store plaintext" note, which is correct, and add the two digest
columns that make it satisfiable.

| Column | Purpose |
|---|---|
| `invite_token_digest text` | the high-entropy secret embedded in the `/join/<token>` magic link |
| `invite_code_digest text` | the short human-typable code from the login screen's invite-code path |

**Why two and not one.** The link and the code have different entropy budgets and must not be the
same secret — a code short enough to read over the phone is short enough to guess, and reusing it as
the link token would drag the link down to the code's strength. This mirrors the pattern the
frontend already uses for visitor passes, which carry a `qrToken` *and* a separate `securityCode`.

Store `hmac-sha256(secret, server_pepper)`, not bcrypt: the token is high-entropy, so a slow KDF buys
nothing and costs latency on every gate scan.

**On the short code's low entropy:** under the OAuth flow, redemption happens *after* the resident is
authenticated, so attempts are attributable to an account and can be rate-limited per account rather
than per IP. That is what makes a short code defensible here; without authentication-first it would
not be.

**Owner:** ERD. **Cost:** +2 columns on `resident_invites`.

---

### R3 — optimistic concurrency *(audit 1.1 #3)*

**Decision:** **do not add `version` columns.** Use the existing `updated_at` as the concurrency
token.

```sql
update departments set ..., updated_at = now()
 where id = $1 and updated_at = $2;   -- 0 rows affected -> 409 Conflict
```

Every table already carries `updated_at timestamptz not null`. `timestamptz` has microsecond
resolution, so two updates to the *same row* colliding inside one microsecond is not a practical
concern at human editing speed. This costs zero schema change and solves the stated problem.

**Two conditions attach to it**, and it is unsafe without them:
- `updated_at` must be maintained by a `BEFORE UPDATE` trigger on every table, not by application
  code, or a forgotten assignment makes the check pass when it should fail. One migration covers all
  tables.
- The timestamp must survive the round trip without truncation. Send it as the raw
  `2026-07-29T10:15:30.123456+00:00` string and echo it back verbatim; a client that reformats to
  millisecond precision breaks the comparison.

**Owner:** backend (trigger migration). **Cost:** zero ERD change.

---

### R4 — tenant isolation on child tables *(audit 1.1 #4)*

**Decision:** split the problem. Not all 17 child tables have the same risk.

**Tables read directly as their own list** get a denormalized `community_id` **with a composite
foreign key**, so divergence is impossible rather than merely unlikely:

```sql
alter table complaints add constraint complaints_id_community_uq unique (id, community_id);

alter table complaint_events add column community_id uuid not null;
alter table complaint_events add constraint complaint_events_parent_fk
  foreign key (complaint_id, community_id) references complaints (id, community_id);
```

This is the point of the resolution: a plain denormalized column plus a trigger is a rule someone can
forget. A composite FK is checked by the database on every write, so a row whose `community_id`
disagrees with its parent *cannot be inserted*. The extra unique index on the parent is nearly free —
`id` is already the primary key.

Applies to the six tables that back a top-level screen: `complaint_events`,
`amenity_booking_occurrences`, `amenity_booking_charges`, `amenity_financial_events`,
`invoice_line_items`, `notification_deliveries`.

**Everything else keeps a parent-join policy**, because it is only ever read under a known parent:

```sql
create policy ... on booking_guests using (
  exists (select 1 from amenity_booking_series s
           where s.id = booking_guests.booking_series_id
             and s.community_id = any (current_communities()))
);
```

with `current_communities()` declared `STABLE SECURITY DEFINER` so Postgres evaluates it once per
statement rather than once per row.

**Owner:** ERD (6 columns + 6 unique constraints), backend (policies). **Cost:** moderate, and much
cheaper now than after the endpoints exist.

---

### R5 — complaint categories become a relationship *(audit 1.1 #5, #8, and the departments gap)*

**Decision:** add one table and change one column.

```sql
create table complaint_categories (
  id uuid primary key,
  community_id uuid not null references communities(id),
  name text not null,
  department_id uuid references departments(id),
  sla_hours integer,
  status text not null,
  unique (community_id, name)
);
-- complaints.category text  ->  complaints.category_id uuid references complaint_categories(id)
```

**This single change resolves three separate audit items**, which is why it is worth its cost:
- 1.1 #5 — a free-text category cannot carry a relationship; a row can.
- 1.1 #8 — there is now a real `departments → complaint_categories → complaints` path, so *"prevent a
  department from being deleted while it is responsible for unresolved complaints"* becomes an
  enforceable query. Previously the only path ran through `work_orders`, which has no UI, so the rule
  was unenforceable in practice.
- The departments requirement for *"complaint categories"* and *"service-level targets"* (§3 of the
  component design) lands here rather than needing columns on `departments`.

**Zero frontend conflict:** the frontend posts `category: "Plumbing"`. The API resolves the string to
an id on write and emits the string on read. The rows are seeded per community at founding from the
frontend's fixed category list, so the lookup never misses.

**Owner:** ERD. **Cost:** +1 table, 1 column retyped.

---

### R6 — visitor group size *(audit 1.1 #6)*

**Decision:** add `guest_count integer not null default 1` to `visitor_access_requests`.

The frontend records a count and no per-guest detail, so a `visitor_guests` table would be storage
for data nobody collects. `amenity_booking_series` already carries `guest_count` as a plain integer,
so this is the consistent shape.

**Owner:** ERD. **Cost:** +1 column.

---

### R7 — the QR pass *(audit 1.1 #7 — correcting the audit)*

**Decision:** add `qr_token_digest text` to `visitor_access_requests`.

**The audit was directionally right but for a slightly wrong reason,** and the correction matters.
I wrote that the QR "has nowhere to live", which would be false if the QR merely encoded the access
code — a QR is a rendering, not a credential, and renderings are never stored. The frontend settles
it: `createVisitorsSlice.js` mints a `qrToken` that is **independent of** the `securityCode`, embeds
both in the payload, and gate verification matches on `item.qrToken === payload.token`. Two distinct
secrets, so two digests. Same reasoning as R2.

The QR *image* still needs no storage — it is regenerated from the payload on demand, which is
exactly what `DashboardHome.jsx` does with `QRCode.toDataURL`.

**Owner:** ERD. **Cost:** +1 column.

---

### R8 — department attributes *(audit 1.2, departments — 6 of 6 missing)*

**Decision:** four columns on `departments`, and two of the six requirements turn out to need
nothing at all.

| Requirement | Resolution |
|---|---|
| contact details | `contact_email text`, `contact_phone_e164 text` — 2 columns |
| operating hours | `opens_at time`, `closes_at time` — 2 columns |
| department head | **no column** — see below |
| staff members | **already exists** via `staff_assignments.department_id` |
| complaint categories | resolved by R5 |
| service-level targets | resolved by R5 (`complaint_categories.sla_hours`) |

**On operating hours:** the frontend stores `operatingHours: { start: '08:00', end: '20:00' }` — one
window, not a weekly schedule. A `department_hours` table modelled on `amenity_rules` would be the
"proper" shape and would store nothing the product collects. Two columns now; the table is the
migration path if per-weekday hours are ever specified.

**On the department head:** rather than `departments.head_membership_id`, add
`staff_assignments.rank text` (`member` | `supervisor` | `head`), with

```sql
create unique index staff_assignment_dept_head_uq
  on staff_assignments (department_id) where rank = 'head' and status = 'active';
```

One column instead of one column — but this one **also resolves audit 1.4 #2 and 4.2**, the
supervisor problem. The frontend's `departments[].staff[].role` mixes `"Supervisor"` (a rank) with
`"Technician"` (a job title); `staff_assignments` already has `job_title`, so adding `rank` gives the
second axis its own home and stops two different things sharing one field.

**Owner:** ERD. **Cost:** +5 columns, +1 partial index, 0 tables.

---

## 2. Requirements with no schema behind them

### R9 — complaints *(audit 1.2, complaints — 9 requirements, 0 columns)*

The largest single gap. Decision per requirement:

| Requirement | Resolution |
|---|---|
| assignee | `assigned_to_membership_id`, `assigned_by_membership_id`, `assigned_at` on `complaints` |
| progress | `progress_percent smallint` — the frontend stores `progress: 65`, an integer percent |
| SLA / expected resolution | `due_at timestamptz`, computed at insert from the category SLA and urgency |
| reopen | `reopen_count integer not null default 0`, `last_reopened_at timestamptz` |
| rating and feedback | `resolution_rating smallint`, `resolution_feedback text`, `resolution_confirmed_at timestamptz` |
| management notes | **no column** — `complaint_events` already has `note`; a note is an event |
| comments | **new table** `complaint_comments` |
| unread updates | **new table** `complaint_read_receipts (complaint_id, membership_id, last_read_at)` |
| attachments | **new table** `complaint_attachments (complaint_id, media_asset_id, attachment_type, created_at)` |

**Direct assignment, not work orders.** The ERD routes assignment through `work_orders`; the frontend
assigns a complaint straight to a person. Under the resolution principle the frontend owns this truth
— it is the shipped product — so assignment columns go on `complaints`, and `work_orders` stays as
the phase-2 dispatch path (R16). This is the one place where I am consciously duplicating a concept
rather than reusing one, and it is worth naming as a cost.

**Why comments are a separate table and notes are not.** `complaint_events` is an audit stream: append
only, never edited, machine-generated. A management note fits that exactly. A resident↔management
conversation does not — it needs authorship, visibility (`resident` vs `internal`) and eventually
edit and delete. Overloading `complaint_events` with it would repeat the same mistake the audit
flagged for the activity feed in R12: collapsing an audit log and a user-facing surface yields either
a leaky log or a useless one.

`complaint_attachments` is the exact shape of the existing `work_order_attachments` and
`visitor_attachments`, so it adds a table but no new concept.

**Owner:** ERD. **Cost:** +9 columns, +3 tables.

---

### R10 — onboarding module selection *(audit 1.2, no table)*

**Decision:** add `community_modules (community_id, module_key, enabled boolean, updated_at)`, primary
key `(community_id, module_key)`. Ten rows per community.

The cheaper option is `communities.enabled_modules jsonb` — one column, zero tables. I am
recommending the table anyway, and the reason is the Settings screen: the frontend's onboarding step 3
promises features *"can be changed later from the Admin Settings page"*, which means each module is
independently toggled by an admin and each toggle is an auditable act. A jsonb blob cannot be audited
per key, cannot be RLS'd per key, and cannot answer "which communities have amenities enabled"
without a scan.

This is also the only real persisted state the Settings screen has (see R25).

**Owner:** ERD. **Cost:** +1 table.

---

### R11 — management contact information *(audit 1.2)*

**Decision:** **no table.** Once departments carry `contact_email` and `contact_phone_e164` (R8), the
management contact directory is a query over departments. Truly external emergency numbers — police,
ambulance, fire — are national constants, not community data, and belong in the app bundle rather
than in a per-tenant table.

**Cost:** zero.

---

### R12 — the activity feed *(audit 1.2)*

**Decision:** keep `audit_events` as the append-only compliance log. Expose the activity feed as a
**view** over it, not a second table.

```sql
create view community_activity with (security_invoker = true) as
select id, community_id, actor_membership_id, event_type, occurred_at,
       metadata -> 'public' as detail          -- redacted projection, not the raw blob
  from audit_events
 where event_type in (/* explicit allow-list */);
```

The audit's objection was that collapsing the two yields either a leaky feed or a useless audit
trail. A view resolves that precisely: the allow-list decides what is *visible* and the projection
decides what is *shown*, while the underlying log keeps everything. `security_invoker = true` makes
the view respect the caller's RLS rather than the view owner's, which is the difference between this
being safe and being a tenant leak.

**Owner:** backend. **Cost:** zero ERD change.

---

### R13 — amenity settings *(audit 1.2)*

| Requirement | Resolution |
|---|---|
| cleaning buffer | `amenity_rules.buffer_minutes integer` |
| resident booking limits | `amenity_rules.max_active_bookings_per_unit integer` |
| private bookings | `amenities.allow_private_booking boolean` — the *setting*; the per-booking flag `amenity_booking_series.is_private` already exists |
| maintenance mode | covered by R14 |

**Owner:** ERD. **Cost:** +3 columns, 0 tables.

---

### R14 — blocked maintenance periods *(audit 1.2)*

**Decision:** **do not add an `amenity_blocked_slots` table.** Represent a maintenance block as an
`amenity_booking_occurrences` row with `status = 'blocked'`, which requires making
`amenity_booking_series.unit_id` nullable:

```sql
alter table amenity_booking_series alter column unit_id drop not null;
alter table amenity_booking_series add constraint booking_series_unit_required
  check (unit_id is not null or booking_type = 'maintenance_block');
```

**This is not a preference, it is forced.** A PostgreSQL exclusion constraint cannot span two tables.
`amenity_booking_occurrences` already carries the no-overlap exclusion constraint that stops
double-booking. If a block lived in a separate table it could not participate in that constraint, so a
resident booking could be created *inside* a maintenance window and the database would not stop it —
which is exactly the failure the audit predicted. Putting the block in the same table makes the
existing constraint do the work with no new enforcement code.

The cost is honest: a nullable `unit_id` means every read path must handle a series with no unit. The
CHECK constraint keeps that to precisely the maintenance-block case.

**Owner:** ERD. **Cost:** 1 nullability change, 1 check, 0 tables.

---

### R15 — forced cancellation *(audit 1.2)*

**Decision:** **derivable, no change.** `amenity_booking_occurrences` already has
`cancelled_by_membership_id` and `cancellation_reason`. A forced cancellation is one where the
canceller is an admin membership rather than the requesting resident. If the distinction ever needs
to be queried directly rather than computed, add `cancellation_kind text` then — not now.

**Cost:** zero.

---

### R16 — the 12 orphan tables *(audit 1.3)*

**Decision:** keep all 12, tag each with `Phase 2 — no v1 endpoint, no v1 RLS policy`, and build
nothing against them.

- **Work orders (5)** — the dispatch subsystem. R9 gives v1 direct complaint assignment; work orders
  become the escalation path when scheduling, quoting and vendor dispatch are actually built.
- **Workforce (5)** — `vendors`, `skills`, `staff_skills`, `worker_availability_rules`,
  `worker_unavailability`. Meaningful only once work orders are dispatched to them.
- **Policies (2)** — no requirement references them at all. Genuinely speculative.

Deleting them would discard design work that is probably right; building them would spend v1 effort
on screens nobody has designed. A note converts an unexamined surface into a dated decision, which is
all the audit asked for.

**A thirteenth table joins them:** `community_registration_requests` is orphaned by the OAuth
decision. It models operator review of a founding application (`reviewed_by_operator_ref`,
`review_notes`, `otp_verified_at`), and the agreed flow is self-serve — the founder authenticates
with OAuth and the community is created immediately, with no review queue and no OTP. Tag it
`Superseded by self-serve founding` rather than deleting it, in case moderated onboarding returns.

**Amended 2026-08-10 — seven of the twelve are no longer parked.** The service-operations feature
(`0034`–`0043`) built the dispatch subsystem R16 said to build nothing against. That ruling is
overturned rather than quietly worked around, and this is the list, because without it the next
reader cannot tell an un-parked table from an overlooked one.

| Table | Now | Where |
|---|---|---|
| `work_orders` | **live** — extended additively with a department, a supervisor, a schedule, a status vocabulary and a failed-attempt count | `0036` §1 |
| `work_order_assignments` | **live** — extended with an offer/response lifecycle and the GiST exclusion constraint the design ERD had already drawn | `0036` §2 |
| `worker_availability_rules` | **live** — activated by a nullable `service_provider_id` beside the existing `staff_assignment_id` | `0036` §3 |
| `worker_unavailability` | **live** — same | `0036` §3 |
| `skills` | **live** — plus `service_provider_skills` and `skill_categories`, which is what makes "communities that need my trades" a query | `0034` |
| `staff_skills` | **superseded** by `service_provider_skills` (D2). Skills belong to the *person*, because the search that matters runs before anybody has hired them — keyed to a roster row, it returns nothing for exactly the people who need it | `0034` |
| `vendors` | **superseded** by `service_providers` (D1). A service person is a `profiles` row with a global provider record and a `worker` membership per community, not a company outside the tenancy model | `0034` |

**Still parked, and the reasoning is unchanged:** the two policy tables — nothing references them yet
— and `community_registration_requests`, still superseded by self-serve founding. The three
work-order tables that were never in R16's five (`work_order_proposals`, and the two verification
tables in the design ERD) are design-ERD-only and have no migration behind them either way.

**The two superseded tables are deleted in Step 12** of `plans/SERVICE_OPERATIONS_PLAN.md`, not here;
a `CHANGE_LOG.md` line will say what replaced each. **Done 2026-08-10:**
`0044_retire_dead_tables.sql` drops both, plus `staff_assignments.vendor_id`,
the one live reference `vendors` ever had.

**What R16 got right, and is worth keeping in view.** *"Deleting them would discard design work that
is probably right"* — it was right. `work_order_assignments` needed an offer lifecycle and an
exclusion constraint bolted on, and nothing else; the shape held for two years of nobody using it.
The part that did not hold is `staff_skills`, and it did not hold for a reason no audit could have
seen from the schema: the question the product actually asks is *which communities need my trades*,
which is asked by somebody who is on no roster at all.


**Owner:** ERD (notes only). **Cost:** zero structural change.

---

## 3. Contradictions with the frontend

### R17 — role vocabulary and the resident-who-is-also-staff *(audit 1.4 rows 1–2)*

**Decision:** three parts, none of which touches the enum.

**(a) Keep the 5-value enum; project the display string.** The API computes the frontend's 4-string
vocabulary (`Admin` | `Resident` | `Security` | `SecurityManager`) server-side and emits it as
`displayRole`. This is the C2 decision already recorded in `BACKEND_PLAN.md`, unchanged.

**(b) Add `departments.kind text`** (`security` | `maintenance` | `housekeeping` | …) — one column.
The ERD's `manager` is generic; the frontend's is specifically a *security* manager. With
`departments.kind`, `role = 'manager'` + `kind = 'security'` projects to `SecurityManager` and the
enum stays honest for the maintenance manager who will exist later.

**(c) Residency, not role, grants resident capabilities.** This is the important one and it costs
nothing.

The audit worried that a security supervisor who lives in the community is unrepresentable, because
`active_membership_per_profile_community_uq` permits only one membership per person per community.
The resolution is to stop treating "resident" as the thing that grants resident access. **An active
`unit_residencies` row grants the resident portal; `community_memberships.role` grants staff and
admin powers.** A security guard who lives on site holds one `security` membership and one residency,
and gets both surfaces. The uniqueness constraint stays exactly as written.

This also explains something already true in the product: the component design's *"administrators, who
may also be residents"* works today for precisely this reason — an admin membership can own a
residency. The rule was already in use; it just was not written down. `role = 'resident'` becomes the
name for "holds no staff duties", which is what it always meant.

**Owner:** ERD (1 column), backend (RLS keyed on residency). **Cost:** +1 column.

---

### R18 — committee designation *(audit 1.4 row 3)*

**Decision:** add `community_memberships.title text`.

Onboarding collects a `designation` — President, Secretary, Treasurer. It is not a job title
(`staff_assignments.job_title` belongs to staff, and a committee member is not staff) and it is not a
role (it grants no permissions). It is a label on the membership, so it goes on the membership.

**Owner:** ERD. **Cost:** +1 column.

---

### R19 — community address *(audit 1.4 row 4)*

**Decision:** relax `address_line_1`, `city`, `state`, `postal_code` to nullable on `communities`;
keep `country_code` NOT NULL with default `'IN'`.

The onboarding flow collects no address, and all five columns are NOT NULL, so **registration cannot
succeed as specified** — this is a hard blocker, not a data-quality wish. Adding an address step is
the better product answer but it is a frontend change, and the frontend team owns that.

**Flagged for the PO:** an invoice document with no issuer address is a problem in most Indian states.
The recommendation is an address step in a later onboarding iteration, gated before the first invoice
is issued rather than before the community is created.

**Owner:** ERD. **Cost:** 4 nullability changes.

---

### R20 — map coordinates *(audit 1.4 row 5)*

**Decision:** add `map_x numeric(6,3)` and `map_y numeric(6,3)` to `buildings` and `units`. Keep
`latitude`/`longitude` for real geography, nullable and unused in v1.

The frontend's map coordinates are 0–100 percentages of a bundled PNG. `numeric(9,6)` accepts `41.889`
as a latitude without complaint, which is the danger — it is not a validation failure, it is silently
wrong data that looks right. Renaming the existing columns would destroy the geo intent; adding two
is unambiguous and costs four columns total.

**Owner:** ERD. **Cost:** +2 columns × 2 tables.

---

### R21 — flat inventory *(audit 1.4 row 6 — ranked third)*

**Decision:** **find-or-create units on first reference**, for v1.

Onboarding creates blocks and villas, never flats, but `unit_residencies.unit_id` is NOT NULL — so
the founding admin's own residency has nothing to point at, and registration cannot complete. Three
ways out:

| Option | Verdict |
|---|---|
| Frontend adds a units-per-block step | Best product answer. Frontend change — not ours to make. |
| Backend generates units from a floors × units-per-floor spec | Needs input nobody collects. |
| **Find-or-create on first reference** | **Chosen.** Zero frontend change, works immediately. |

When the founding admin submits `unitNumber: "A-101"`, the backend resolves `"A"` to a building in
that community and creates the `units` row if it is absent. Same on invite and on access-request
approval.

**Two consequences, both accepted:**
- The unit list is only as complete as what has been referenced. You cannot show occupancy for a flat
  nobody has mentioned. Acceptable while there is no screen that lists all units.
- It makes R1 load-bearing: find-or-create keys on `(building, label)`, so with the current
  community-scoped unique index the second block's "101" would collide with the first block's. **R1
  must land before this.**

**On unparseable labels:** `unitNumber` is free text. If the prefix does not resolve to a building,
create the unit with `building_id = null` — the standalone branch of R1's index still protects it,
and the row can be reparented later without data loss.

**Owner:** backend. **Cost:** zero ERD change, given R1.

---

### R22 — money representation *(audit 1.4 row 7)*

**Decision:** **no change.** The frontend's `amount: 4250` means ₹4,250 — major units, not paise. The
API contract states that amounts are decimal in major units; `4250` casts to `4250.00` losslessly.

Recorded rather than silently assumed, because the failure mode if the frontend ever switches to minor
units is a hundredfold error that no type system would catch.

**Cost:** zero.

---

### R23 — labels used as foreign keys *(audit 4.1)*

**Decision:** apply the **additive boundary** rule. Every entity in every response carries both:

```jsonc
{
  "id": "…uuid…",
  "assignee":   "Ramesh - Plumber",     // what the frontend renders today
  "assigneeId": "…uuid…",               // what it should use
  "flat":       "B-1204",
  "unitId":     "…uuid…"
}
```

On write the API accepts either form during the transition. The frontend needs no change to keep
working and no migration to start improving. Same treatment for `apartmentId`, `departments[].head`
and `complaints[].category`.

**Owner:** backend. **Cost:** response size.

---

### R24 — display strings where instants belong *(audit 4.4)*

**Decision:** emit ISO-8601 instants as the canonical field, and keep the pre-formatted string
alongside it, marked deprecated.

```jsonc
{ "submittedAt": "2026-07-29T08:15:30Z", "timeAgo": "2h ago" }
```

This is the one resolution I am not happy with. Server-side relative-time formatting is wrong on
principle — it bakes the server's clock and the server's locale into a value the client should
compute — but removing `timeAgo` is a frontend change and the zero-conflict constraint forbids it.

**The cost must be stated because it is easy to miss:** any response containing `timeAgo` is
**not cacheable**. It must carry `Cache-Control: no-store`, and it must never sit behind a CDN. A
cached `"2h ago"` is wrong the moment it is served. This is a real constraint on the caching design,
not a note. `timeAgo` should be deleted the day the frontend adopts `submittedAt`.

**Owner:** backend now, frontend eventually. **Cost:** an un-cacheable response class.

---

### R25 — Settings screen promises *(audit 4.5)*

**Decision:** out of scope for v1; build nothing. The screen's four `useState` toggles promise
automated monthly billing and late-payment fines, which exist in no table, no requirement and no
component-design section. Its one legitimate persisted control is module toggling, which R10 provides.

**Flagged for the PO:** the toggles currently look functional and do nothing. Either they get a
backend and a requirement, or they should be visibly marked as coming soon — a control that silently
discards the user's intent is worse than an absent one.

**Cost:** zero.

---

### R26 — module editing after onboarding *(audit 4.6)*

**Decision:** resolved by R10. Onboarding's *"can be changed later from the Admin Settings page"*
becomes true once `community_modules` exists and Settings gets `GET`/`PATCH /communities/{id}/modules`.

---

### R27 — empty states *(audit 4.7)*

**Decision:** backend action is to make empty states *reachable* — every list endpoint returns
`{ items: [], total: 0 }` rather than 404, and pagination envelopes are identical whether or not there
is data. Rendering them is a frontend concern, flagged rather than fixed: the dashboard has never once
rendered with zero complaints, and a newly founded community has zero of everything. **This is the
first thing a real founding admin will see.**

**Owner:** backend (contract), frontend (rendering).

---

### R28 — staff have no accounts *(audit 4.3)*

**Decision:** make `resident_invites` serve staff too — two changes, no new table.

```sql
alter table resident_invites alter column unit_id drop not null;
alter table resident_invites add column intended_role membership_role not null default 'resident';
alter table resident_invites add constraint invite_unit_required
  check (unit_id is not null or intended_role <> 'resident');
```

A staff invitation is the same object as a resident invitation — a pending grant of a membership,
addressed to someone, expiring, single-use, revocable. The only real difference is that it targets a
role rather than a unit. Creating a parallel `staff_invites` table would duplicate eleven columns and
two state machines to express that one difference.

Under OAuth the flow is simple: pre-create the membership as `status = 'invited'`, and match on the
provider's verified email at first sign-in. `recipient_email` and `invited_auth_user_id` are already
there for exactly this.

**Renaming the table** to `membership_invites` would be more honest, and it is deliberately *not*
proposed — the rename touches the class diagram, the ERD image, and every document that names it, to
buy nothing functional.

**Owner:** ERD. **Cost:** 1 nullability change, +1 column, +1 check.

---

## 4. Class diagram

**Owner for all three:** the class-diagram maintainer. None affects the backend directly.

### R29 — role as state, not type *(audit 2.1)*

**Decision:** delete the five `CommunityMembership` subclasses (`ResidentMembership`,
`WorkerMembership`, `SecurityMembership`, `ManagerMembership`, `AdminMembership`); keep one concrete
`CommunityMembership` with `role: MembershipRole`.

Promotion is an `UPDATE`, and no ORM can change an object's class. With R17(c), the resident-plus-staff
case that motivated multiple inheritance disappears entirely — it is one membership plus one
`UnitResidency`. **Net effect: five classes deleted, nothing added.** This is the largest single
simplification available in any artifact.

### R30 — behaviour without state *(audit 2.2)*

**Decision:** follows R9. `Complaint.reopen(reason)` gains `reopenCount`, `escalate()` gains an
assignee to escalate to, `resolve()` gains `resolutionRating` and `resolutionFeedback`. The methods
were right; the attributes were missing.

### R31 — the split invariant *(audit 2.3)*

**Decision:** with R17(c) the per-subclass invariant collapses into two rules, both expressible as
partial unique indexes:

- at most one **active membership** per `(profile, community, role)`;
- at most one **active admin** per community.

The residency question — *may one person hold active residencies in two communities?* — is a genuine
product decision that the current wording ("RESIDENT: one active membership across all communities")
answers implicitly and probably by accident. Someone who owns flats in two societies is not exotic.
**PO decision required.**

---

## 5. Design of components

**Owner for all four:** the component-design author. No backend impact.

| # | Issue | Resolution |
|---|---|---|
| R32 | §10 lists a `notifications` slice that does not exist | The ERD *does* have `notifications` and `notification_deliveries`, so the document describes intent that the frontend has not built. Cheapest fix: strike the word from §10. Backend is unaffected. |
| R33 | §1 per-tab sessions cannot survive a real backend | **Reframe, do not delete.** Cookies are scoped to an origin, never to a tab, so the literal behaviour is impossible with server-issued sessions — but the *need* behind it is stated two bullets later: *"switch between the administrator and resident interfaces."* That is supported. Mark the tab behaviour as prototype-only and let the role switcher carry the requirement. |
| R34 | §1 *"separate entry and login flows"* superseded by OAuth | Mark superseded, dated 2026-07-29, referencing `ADMIN_REGISTRATION_FLOW.md`. Not a defect at the time of writing. |
| R35 | §2 collects a unit number while creating only blocks and villas | Resolved in the backend by R21. The document should say the association configures *buildings*, and that unit inventory is populated on first reference. |

Also: §2 *"Create a simulated association and administrator record after OTP confirmation"* — strike
"after OTP confirmation".

---

## 6. Net change to the v1 ERD

| Kind | Count | Where |
|---|---|---|
| New tables | **5** | `complaint_categories`, `complaint_comments`, `complaint_read_receipts`, `complaint_attachments`, `community_modules` |
| New columns | **~33** | across `complaints`, `departments`, `staff_assignments`, `amenities`, `amenity_rules`, `resident_invites`, `visitor_access_requests`, `community_memberships`, `buildings`, `units`, and the 6 tables in R4 |
| Retyped columns | **1** | `complaints.category` → `category_id` |
| Nullability relaxed | **7** | 4 on `communities`, `amenity_booking_series.unit_id`, `resident_invites.unit_id`, plus the R4 group |
| Index changes | **3** | R1 (1 → 2 partial), R8 head index, R4 composite-FK uniques |
| Notes only | **13 tables** | the 12 orphans + `community_registration_requests` |
| **Tables deleted** | **0** | |
| **Frontend files changed** | **0** | |

Five new tables against 48 is roughly a 10% expansion, and every one of them backs a requirement that
already exists in the component design.

**Things deliberately *not* added,** each of which a less careful pass would have added: `version`
columns (R3), `emergency_contacts` (R11), an activity-feed table (R12), `amenity_blocked_slots`
(R14), `department_hours` (R8), `staff_invites` (R28), `visitor_guests` (R6), a QR column (R7).
**Eight tables avoided** — more than the five added.

---

## 7. Build order

R1 and R21 are coupled, and R5 unblocks the two largest gaps. Suggested sequence:

1. **R1** — units index. Nothing else is safe until this is right.
2. **R21** — find-or-create units. Unblocks registration, which unblocks everything.
3. **R2**, **R28** — invitations, so residents and staff can exist.
4. **R5**, **R8**, **R9** — the complaints and departments subsystem. Largest gap by volume.
5. **R17**, **R18** — role projection and designation.
6. **R4**, **R3** — tenant isolation and concurrency. Cheap now, invasive after endpoints exist.
7. **R10**, **R13**, **R14**, **R20** — modules, amenity settings, coordinates.
8. **R16** and the §5 documentation edits — no code.

---

## 8. Conflicts these resolutions *create*

Added after the resolutions were written, by auditing the §0 "zero frontend conflicts" claim against
the frontend rather than trusting it. **Two of the resolutions break that claim.** Ranked by how much
they change.

### C1 — `complaints.assigned_to_membership_id` cannot be satisfied *(breaks R9)*

The FK chain is `staff_assignments.membership_id` NOT NULL → `community_memberships.profile_id` NOT
NULL → `profiles.id` → `auth.users.id`. **Every assignable person needs an auth account.** The
frontend has two assignment paths and neither produces one:

- `DepartmentDetail.jsx:193` assigns from a department staff member —
  `assignee: \`${staffMember.name} - ${staffMember.role}\``. Department staff are plain records with
  no account (audit 4.3), so there is no membership to reference.
- `Complaints.jsx:175-176` is a **free-text input**. The admin can type anything. There is no
  referent at all, not even a bad one.

R28 gives staff an invite path, but that requires the person to actually sign in — so complaint
assignment would be blocked on every staff member completing OAuth. That is not a v1 story.

**Options, none free:**

| Option | Cost |
|---|---|
| **Shadow accounts** — `supabase.auth.admin.createUser()` with the staff member's phone when an admin adds them, never signed in | Closest to the ERD's intent. Creates `auth.users` rows for people who may never log in, which inflates the auth table and any per-MAU billing. |
| **Keep `assigned_to_membership_id` nullable, add `assignee_label text`** | Zero frontend conflict, works today, and the label is what the frontend already renders. Accepts unreferenced assignees — exactly the defect audit 4.1 complains about. |
| **Model department staff as their own table** without an account | A third people-shaped table beside `profiles` and `community_memberships`. Rejected — it is the biggest structural change on this page. |

**Recommendation: nullable FK plus label, now; shadow accounts when staff dashboards are built.**
This is a deliberate, temporary retreat from referential integrity, and it should be recorded as one
rather than discovered later.

**A second-order break:** `DepartmentDetail.jsx:217` does `complaint.assignee?.split(' - ')[0]` to
recover the staff name, then matches it against `staff[].name`. The `" - "` string format is
load-bearing. R8 splits the frontend's `staff[].role` into `rank` and `job_title` — so the API must
re-join them into exactly `${name} - ${role}` or that reverse lookup silently stops matching. A
splitting resolution and a string-parsing frontend do not coexist by accident.

### C2 — complaint categories are many-to-many in the UI *(breaks R5)*

`Departments.jsx:211-213` toggles categories into a per-department multi-select from a fixed list.
**Nothing prevents two departments from both selecting "Plumbing"**, and
`createDepartmentsSlice.js:151` filters complaints with `department.categories.some(...)`, so a
shared category legitimately appears under both departments.

R5 makes `complaint_categories.department_id` single-valued with `unique(community_id, name)`, which
forbids that outright. The second department to claim "Plumbing" either fails or steals it.

**Fix:** a join table — `department_categories (department_id, category_id)` — and move
`sla_hours` onto `complaint_categories` where it already is. Cost is +1 table (six new, not five).
R5's other two benefits survive intact: the department-deletion rule still has a real path, and
categories are still rows rather than free text.

The alternative is asking the frontend to enforce exclusivity, which is a frontend change and a
product restriction nobody asked for.

### C3 — the additive-boundary resolutions require a server seam

R5 (string↔id), R17a (`displayRole`), R21 (find-or-create units), R23 (label + id in one response)
and R24 (`timeAgo` beside an instant) all assume something sits between the browser and the database
and shapes the response. **If the frontend calls `supabase-js` directly against PostgREST, none of
them exist.** That conflicts with the standing "use Supabase functionality as much as possible"
direction, which points at exactly that direct-access architecture.

It is resolvable inside Supabase, and the shape is worth deciding on purpose:

- **Reads through views.** A `security_invoker` view computes `displayRole`, joins the labels beside
  the ids, and can carry a computed `time_ago`. RLS still applies as the caller.
- **Writes through RPC.** `create_complaint(...)`, `register_community(...)` as `SECURITY DEFINER`
  functions — this is where find-or-create and string→id resolution live.
- **Edge Functions** only where an external call is involved.

**One thing that turns out not to need it:** R3's conditional update works natively —
`PATCH /departments?id=eq.X&updated_at=eq.Y` returns zero rows on a stale token, which is the 409.
No RPC required.

**Decision needed: direct table access, or views-and-RPC as the only seam?** Choosing direct access
means dropping R23 and R24 and pushing that work to the frontend.

### C4 — three schema descriptions would now exist

If the ERD owner applies these to v1, the repo holds v1-as-submitted, v1-plus-35-resolutions, and our
unagreed 63-table `homebandhu.dbml` draft — which already resolves many of the same issues
*differently*. Three descriptions of one database is worse than the problem being solved.

**Recommendation: pick one destination before any of this is applied.** Either fold the resolutions
into the v2 draft and propose that as a single artifact, or apply them to v1 and delete the draft.
Not both.

### C5 — merge timing

These 35 proposals target three artifacts that other people are editing right now. The zero-conflict
claim is also measured against `frontend/src` **as read on 2026-07-29** — the recent Security Manager
dashboard work means the frontend is moving, and a new screen can invalidate a resolution without
anyone noticing. Worth re-running the frontend checks in C1 and C2 immediately before applying
anything.

### Smaller ones, found in the same pass

| # | Issue | Fix |
|---|---|---|
| C6 | **R28 breaks an existing constraint.** `resident_invites` has *"Partial UQ: active invitation per recipient/unit"*. Making `unit_id` nullable means staff invites fall into the NULL-distinctness hole — the same trap R1 exists to avoid — so a staff member could be invited unlimited times. | Add a second partial index on `(community_id, recipient_email) where unit_id is null and status = 'active'`. |
| C7 | **R14 needs the exclusion constraint's predicate edited**, which I did not state. The existing constraint covers *active* occurrences; unless `'blocked'` is added to that predicate, maintenance blocks sit in the table and block nothing. | One-line change to the constraint, and it must ship in the same migration as R14 or the feature is silently inert. |
| C8 | **R28 gives staff a weaker invite than residents.** Matching the provider's verified email at first sign-in has no second factor, while the PO ruled the resident invite token is mandatory 2FA. Defensible — staff are added by a named admin — but it is currently a side effect, not a decision. | PO call. |
| C9 | **R21's parsing is ambiguous where the frontend is inconsistent.** `flat: 'B-1204'` carries the tower; onboarding's `unitNumber` is free text and may be `"1204"` with no prefix. | Already handled by the `building_id = null` fallback, but it means an onboarding admin can land in the standalone branch inside an apartment community. Reparentable later; worth expecting in the data. |

**Net effect on §6:** six new tables rather than five (C2), and `complaints` gains
`assignee_label text` with a nullable FK rather than a NOT NULL one (C1).

---

## 9. Still requires a product decision

Not resolvable from the artifacts. Each blocks nothing today but will be decided by default if left
alone.

1. **Community address** (R19) — add an onboarding step, or accept invoices without an issuer address?
2. **One residency or many** (R31) — may a person hold active residencies in two communities?
3. **Settings toggles** (R25) — build monthly billing and late fines, or mark them coming soon?
4. **Work orders and workforce** (R16) — confirm phase 2, or cut the 10 tables entirely?
5. **Policies** (R16) — no requirement references them at all. Keep or cut?
6. **`community_registration_requests`** (R16) — confirm that founding is self-serve with no review
   queue, which is what the OAuth flow assumes.
