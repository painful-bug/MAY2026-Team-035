# Eraser.io AI prompt — HomeBandhu UML Class Diagram

**How to use**

1. Open Eraser → new diagram → AI (Diagram-as-code / "Generate diagram").
2. Copy **everything below the horizontal rule** and paste it as a single prompt.
3. If Eraser truncates the input, run it in three passes instead:
   - Pass 1 = Sections 0–6 + 8 (notation, enums, domain classes, generalizations)
   - Pass 2 = "Keep the existing diagram and add:" + Sections 9–13 (associations, service/repository/infrastructure layers)
   - Pass 3 = "Keep the existing diagram and add:" + Sections 14–16 (constraint notes, legend, layout)
4. Model source of truth is `docs/plan.md` / `PLAN.md` (target schema), **not** the transitional
   `backend/supabase/migrations/0001_init.sql` (which still has `profiles.role` and a `TECHNICIAN` role).
   The class diagram must match the ERD that was already generated.

---

# TASK

Generate a **complete, submission-ready UML class diagram** for a multi-tenant residential-community
management platform called **HomeBandhu** (React + FastAPI + Supabase Postgres with Row-Level Security).

This is **not** an ER diagram. It is a **UML class diagram** covering four architectural layers:
domain model, application/service layer, persistence layer, and infrastructure/external systems.
It is the companion diagram to an already-approved ERD, so the domain classes must correspond 1:1 with
the ERD tables, but expressed as classes with **attributes, operations, visibility, stereotypes,
generalization, composition/aggregation, association classes, interfaces, and multiplicities**.

---

## 0. OUTPUT FORMAT AND ERASER CONVENTIONS

- Emit Eraser **diagram-as-code**. Use the entity/ERD block syntax as the carrier for UML class boxes.
- Set the header properties:
  `colorMode bold`, `styleMode shadow`, `typeface clean`, `direction right`.
- Canvas: assume **A1 landscape**, high density. Prefer wide horizontal layering over tall stacks.
- Each class is one block: `ClassName [icon: ..., color: ...] { ... }`.
- Members are one per line: `memberName Type`. Put attributes first, then a `// operations` comment
  line, then operations written as `operationName(params) ReturnType`.
- Use `//` comment lines inside blocks for stereotypes and constraints when a note is not possible.
- If `group { }` blocks are valid in this diagram type, wrap each layer/subdomain in a group with the
  colors in Section 3. If groups are not valid, **fall back to color-coding plus spatial clustering** —
  never drop the grouping information.
- If the parser rejects visibility prefixes (`+ - #`) or parentheses in member names, drop only those
  characters and keep every class, member, relationship and note. Never silently omit content.
- Add free-floating text notes for every constraint listed in Section 14.

**Syntax anchor (follow this shape exactly):**

```
colorMode bold
styleMode shadow
typeface clean
direction right

Community [icon: home, color: navy] {
  // «aggregate root» «tenant root»
  id UUID
  name String
  status CommunityStatus
  // operations
  activate(admin) void
  transferAdmin(successor) AdminMembership
}

Community.id < Building.communityId
```

---

## 1. UML NOTATION RULES

- **Visibility:** `+` public, `-` private, `#` protected. Identity/audit fields are `-`; business
  attributes are `-` with public accessors implied; operations are `+` unless internal (`-`).
- **Stereotypes** in guillemets on the first comment line of each class. Use exactly these:
  `«aggregate root»`, `«entity»`, `«value object»`, `«enumeration»`, `«association class»`,
  `«event»` (append-only/immutable), `«abstract»`, `«interface»`, `«service»`, `«repository»`,
  `«controller»`, `«gateway»`, `«DTO»`, `«external system»`, `«singleton»`, `«policy»`.
- **Do not repeat foreign-key columns as attributes.** Every FK in the ERD becomes a typed,
  navigable association end with a role name (Section 9). Nothing is lost — the association list
  covers every declared FK.
- Keep the surrogate `- id: UUID {PK}` on every persistent class, and `- createdAt: DateTime`,
  `- updatedAt: DateTime` where the ERD declares them.
- Mark uniqueness and nullability with UML property strings: `{unique}`, `{required}`, `{0..1}`,
  `{readOnly}`, `{derived}` (prefix derived attributes with `/`).
- **Multiplicities on both ends of every association.** Optional ends are `0..1`; optional
  collections are `0..*`; mandatory collections are `1..*`.
- Relationship glyphs:
  - Generalization: solid line, hollow triangle at parent.
  - Realization (class → interface): dashed line, hollow triangle.
  - Composition (lifecycle-owned children): solid line, filled diamond at owner.
  - Aggregation (shared reference): solid line, hollow diamond.
  - Association: plain solid line with role name + multiplicity.
  - Dependency (uses / calls / creates): dashed open arrow, labelled `«uses»`, `«creates»`, `«calls»`.
  - Association class: dashed line from the class to the middle of the association it qualifies.
- Every self-referencing association gets an explicit role name on both ends.

---

## 2. TYPE MAPPING (use these UML types, not SQL types)

`UUID`, `String`, `Text`, `Boolean`, `Integer`, `SmallInt`, `Long`, `Decimal`, `Money` (= Decimal(12,2)),
`DateTime` (= timestamptz), `Date`, `Time`, `JSON` (= jsonb), `CurrencyCode` (= char(3)),
`CountryCode` (= char(2)), `GeoCoordinate` (= numeric(9,6) pair), `List<T>`, `Set<T>`, `Optional<T>`.
Add a legend note: "DateTime ≡ timestamptz, Money ≡ numeric(12,2), JSON ≡ jsonb, all ids are UUID".

---

## 3. LAYERS AND COLOR GROUPS

Lay the diagram out in four horizontal bands, left to right within each band:

**Band A — Presentation & API layer** (grey `#607D8B`): controllers/routers, guards, DTOs.
**Band B — Application/service layer** (orange `#F57C00`): services, policies, schedulers.
**Band C — Domain model** (the seven ERD colors below): entities, enums, value objects.
**Band D — Persistence & infrastructure** (slate `#455A64` / external in dashed borders).

Domain subdomain colors (must match the existing ERD):

1. **Navy** — Supabase identity and community foundation
2. **Teal** — Buildings, units, resident occupancy
3. **Gold** — Roles, staff, departments, vendors, skills
4. **Red** — Complaints, work orders, scheduling
5. **Purple** — Visitor management
6. **Green** — Amenities and finance
7. **Blue** — Notices, policies, notifications, audit, media

External systems (`auth.users`, Supabase Storage, Supabase Realtime, SMS/Email provider) get
**dashed borders** and the `«external system»` stereotype, and sit at the far edge of the canvas.

---

## 4. ENUMERATIONS

Render each as a `«enumeration»` class listing its literals. Group them in a compact "Enumerations"
cluster near the domain band so they do not create long connectors; connect an enum only to the class
that owns it, or, if that would clutter, omit the connector and rely on the typed attribute.

- `MembershipRole`: RESIDENT, WORKER, SECURITY, MANAGER, ADMIN  ← **the only role enum; fixed for v1**
- `MembershipStatus`: PENDING, ACTIVE, SUSPENDED, ENDED
- `CommunityType`: APARTMENT, VILLA
- `CommunityStatus`: PENDING, ACTIVE, SUSPENDED, ARCHIVED
- `RegistrationStatus`: SUBMITTED, OTP_VERIFIED, UNDER_REVIEW, APPROVED, REJECTED
- `UnitStatus`: ACTIVE, VACANT, ARCHIVED
- `UnitType`: FLAT, VILLA, SHOP, OFFICE
- `OccupancyType`: OWNER, TENANT, FAMILY_MEMBER, OCCUPANT
- `ProfileStatus`: ACTIVE, DISABLED
- `EmploymentType`: IN_HOUSE, VENDOR_CONTRACT, TEMPORARY
- `StaffAssignmentStatus`: ACTIVE, SUSPENDED, ENDED
- `ProficiencyLevel`: TRAINEE, INTERMEDIATE, EXPERT
- `Weekday`: SUN, MON, TUE, WED, THU, FRI, SAT (0–6)
- `InviteStatus`: ISSUED, SENT, ACCEPTED, EXPIRED, REVOKED
- `AccessRequestStatus`: PENDING, APPROVED, REJECTED, WITHDRAWN
- `ComplaintStatus`: OPEN, ACKNOWLEDGED, IN_PROGRESS, RESOLVED, CLOSED, REOPENED
- `Urgency`: LOW, MEDIUM, HIGH, CRITICAL
- `WorkOrderStatus`: DRAFT, OPEN, ASSIGNED, SCHEDULED, IN_PROGRESS, AWAITING_VERIFICATION, RESOLVED, CLOSED, CANCELLED
- `Priority`: LOW, NORMAL, HIGH, EMERGENCY
- `AssignmentStatus`: OFFERED, ACCEPTED, DECLINED, IN_PROGRESS, COMPLETED, CANCELLED
- `ProposalStatus`: PROPOSED, COUNTERED, ACCEPTED, REJECTED, EXPIRED
- `VerificationMethod`: RESIDENT_OTP, RESIDENT_CONFIRMATION, MANAGER_OVERRIDE
- `VisitorType`: GUEST, DELIVERY, CAB, SERVICE, VENDOR, STAFF
- `VisitorRequestStatus`: PENDING, APPROVED, REJECTED, CHECKED_IN, CHECKED_OUT, EXPIRED
- `BookingMode`: SLOT, FULL_DAY, MULTI_DAY
- `BookingSeriesStatus`: REQUESTED, APPROVED, REJECTED, CANCELLED, COMPLETED
- `OccurrenceStatus`: SCHEDULED, CANCELLED, COMPLETED, NO_SHOW
- `ChargeType`: BOOKING_FEE, DEPOSIT, DAMAGE, REFUND, ADJUSTMENT
- `ChargeStatus`: PENDING, INVOICED, PAID, REFUNDED, WAIVED
- `FinancialEventType`: CHARGE_RAISED, PAYMENT_RECEIVED, REFUND_ISSUED, DAMAGE_DEDUCTED, WAIVED
- `InvoiceType`: MAINTENANCE, AMENITY, PENALTY, MISC
- `InvoiceStatus`: DRAFT, ISSUED, PARTIALLY_PAID, PAID, OVERDUE, VOID
- `PaymentStatus`: INITIATED, SUCCEEDED, FAILED, REFUNDED
- `PaymentMethod`: UPI, CARD, NETBANKING, CASH, CHEQUE, BANK_TRANSFER
- `NoticeStatus`: DRAFT, PUBLISHED, EXPIRED, ARCHIVED
- `PolicyStatus`: DRAFT, ACTIVE, SUPERSEDED, ARCHIVED
- `NotificationChannel`: IN_APP, PUSH, EMAIL, SMS
- `DeliveryStatus`: QUEUED, SENT, DELIVERED, READ, FAILED
- `MediaStatus`: PENDING, READY, QUARANTINED, DELETED
- `StorageBucket`: PROFILE_AVATARS, WORK_EVIDENCE, VISITOR_MEDIA
- `AttachmentType`: EVIDENCE, COMPLETION_PHOTO, ID_PROOF, VISITOR_PHOTO, OTHER

---

## 5. ABSTRACT BASE TYPES AND INTERFACES

```
«abstract» BaseEntity
  - id: UUID {PK}
  - createdAt: DateTime {required, readOnly}
  - updatedAt: DateTime {required}
  + touch(): void
  + isPersisted(): Boolean

«abstract» TenantScopedEntity  (extends BaseEntity)
  # communityId: UUID {required}   // RLS tenant discriminator
  + belongsTo(community: Community): Boolean
  + assertTenant(ctx: SecurityContext): void

«abstract» AuditableEvent  (extends BaseEntity)  «event»
  - eventType: String {required}
  - metadata: JSON {0..1}
  - occurredAt: DateTime {required, readOnly}
  + isImmutable(): Boolean = true

«abstract» AttachmentLink  «association class»
  - attachmentType: AttachmentType {required}
  - createdAt: DateTime {required}

«interface» Schedulable
  + scheduledRange(): TimeRange
  + overlaps(other: Schedulable): Boolean
  + assertNoOverlap(): void

«interface» Approvable
  + approve(by: CommunityMembership): void
  + reject(by: CommunityMembership, reason: String): void
  + isApproved(): Boolean

«interface» Cancellable
  + cancel(by: CommunityMembership, reason: String): void
  + isCancelled(): Boolean

«interface» Auditable
  + auditTrail(): List<AuditEvent>

«value object» TimeRange
  - startsAt: DateTime
  - endsAt: DateTime
  + durationMinutes(): Integer
  + overlaps(other: TimeRange): Boolean
  + contains(at: DateTime): Boolean

«value object» Money
  - amount: Decimal
  - currencyCode: CurrencyCode
  + plus(other: Money): Money
  + minus(other: Money): Money
  + isZero(): Boolean

«value object» PostalAddress
  - line1: String {required}
  - line2: String {0..1}
  - city: String {required}
  - state: String {required}
  - postalCode: String {required}
  - countryCode: CountryCode {required}
  + formatted(): String

«value object» GeoPoint
  - latitude: Decimal
  - longitude: Decimal
```

**Generalization instruction:** every persistent domain class specializes `BaseEntity`, and every
community-scoped class specializes `TenantScopedEntity`. To avoid 45 crossing arrows, draw the
generalization arrows **only** from these nine classes: `Community`, `Unit`, `CommunityMembership`,
`Complaint`, `WorkOrder`, `VisitorAccessRequest`, `AmenityBookingSeries`, `Invoice`, `MediaAsset`.
Add a note: *"All remaining domain classes also specialize BaseEntity / TenantScopedEntity; arrows
elided for readability."*

---

## 6. DOMAIN CLASSES

Create every class below. Attributes are given as `name: Type {constraints}`; operations follow.
`PostalAddress` and `GeoPoint` are embedded value objects (composition, `1`).

### 6.1 NAVY — Identity and community foundation

**`AuthUser` «external system» «entity»** (Supabase Auth, schema `auth.users`, dashed border)
`- id: UUID {PK}`, `- email: String {unique, required}`, `- emailConfirmedAt: DateTime {0..1}`, `- createdAt: DateTime`
ops: `+ isConfirmed(): Boolean`

**`Profile` «aggregate root»** — extends `AuthUser` identity 1:1 (`profiles.id = auth.users.id`)
`- id: UUID {PK}`, `- displayName: String {required}`, `- phoneE164: String {unique}`,
`- phoneVerifiedAt: DateTime {0..1}`, `- avatarObjectPath: String {0..1}`, `- status: ProfileStatus {required}`,
`- createdAt`, `- updatedAt`
ops: `+ verifyPhone(otp: String): Boolean`, `+ updateAvatar(asset: MediaAsset): void`,
`+ activeMemberships(): List<CommunityMembership>`, `+ membershipIn(c: Community): Optional<CommunityMembership>`,
`+ /isActive(): Boolean`

**`CommunityRegistrationRequest` «aggregate root»**
`- id: UUID {PK}`, `- associationName: String {required}`, `- communityType: CommunityType {required}`,
`- address: PostalAddress {required}`, `- applicantEmail: String {required}`,
`- applicantPhoneE164: String {required}`, `- otpVerifiedAt: DateTime {0..1}`,
`- status: RegistrationStatus {required}`, `- reviewNotes: Text {0..1}`,
`- reviewedByOperatorRef: String {0..1}`, `- reviewedAt: DateTime {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ verifyOtp(code: String): Boolean`, `+ approve(operatorRef: String): Community`,
`+ reject(reason: String): void`, `+ /isVerified(): Boolean`

**`Community` «aggregate root» «tenant root»**
`- id: UUID {PK}`, `- name: String {required}`, `- communityType: CommunityType {required}`,
`- status: CommunityStatus {required}`, `- address: PostalAddress {required}`,
`- location: GeoPoint {0..1}`, `- activatedAt: DateTime {0..1}`, `- archivedAt: DateTime {0..1}`,
`- createdAt`, `- updatedAt`
ops: `+ activate(admin: AdminMembership): void`, `+ archive(reason: String): void`,
`+ transferAdmin(successor: CommunityMembership): AdminMembership`,
`+ activeAdmin(): AdminMembership`, `+ addBuilding(label: String): Building`,
`+ addUnit(label: String, type: UnitType): Unit`, `- assertSingleActiveAdmin(): void`

### 6.2 TEAL — Buildings, units, occupancy

**`Building` «entity»**
`- id: UUID {PK}`, `- label: String {required}`, `- buildingType: String {0..1}`,
`- sortOrder: Integer {required}`, `- location: GeoPoint {0..1}`, `- status: String {required}`, `- createdAt`, `- updatedAt`
ops: `+ rename(label: String): void`, `+ units(): List<Unit>`, `+ archive(): void`

**`Unit` «aggregate root»**
`- id: UUID {PK}`, `- unitLabel: String {required, unique per community}`, `- unitType: UnitType {required}`,
`- floorNumber: Integer {0..1}`, `- areaSqft: Decimal {0..1}`, `- location: GeoPoint {0..1}`,
`- status: UnitStatus {required}`, `- archivedAt: DateTime {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ primaryContact(): UnitResidency`, `+ transferPrimaryContact(to: UnitResidency, by: CommunityMembership): void`,
`+ activeResidents(): List<UnitResidency>`, `+ /outstandingBalance(): Money`, `+ archive(): void`

**`UnitResidency` «entity»**
`- id: UUID {PK}`, `- occupancyType: OccupancyType {required}`, `- status: MembershipStatus {required}`,
`- isPrimaryContact: Boolean {required}`, `- moveInDate: Date {0..1}`, `- moveOutDate: Date {0..1}`,
`- createdAt`, `- updatedAt`
ops: `+ makePrimary(): void`, `+ nominateSuccessor(next: UnitResidency): void`,
`+ endOccupancy(on: Date, reason: String): void`, `+ /isActive(): Boolean`

### 6.3 GOLD — Roles, staff, departments, vendors, skills

**`CommunityMembership` «aggregate root» «abstract»** — *role lives here, never on `Profile`*
`- id: UUID {PK}`, `- role: MembershipRole {required, readOnly}`, `- status: MembershipStatus {required}`,
`- activatedAt: DateTime {0..1}`, `- endedAt: DateTime {0..1}`, `- endReason: String {0..1}`,
`- createdAt`, `- updatedAt`
ops: `+ activate(): void`, `+ end(reason: String): void`, `+ /isActive(): Boolean`,
`+ can(action: String): Boolean`, `+ scopeCommunityIds(): Set<UUID>`,
`- assertSingleCommunityScope(): void`

Subclasses (single-table inheritance discriminated by `role`; add that as a note):
- **`ResidentMembership`** `{role = RESIDENT}` — ops: `+ raiseComplaint(...): Complaint`,
  `+ requestBooking(...): AmenityBookingSeries`, `+ preApproveVisitor(...): VisitorAccessRequest`,
  `+ payInvoice(i: Invoice, m: PaymentMethod): Payment` — *single community only*
- **`WorkerMembership`** `{role = WORKER}` — ops: `+ acceptAssignment(a: WorkOrderAssignment): void`,
  `+ declineAssignment(a, reason): void`, `+ propose(range: TimeRange, quote: Money): WorkOrderProposal`,
  `+ submitCompletionEvidence(wo, media): void` — *multi-community*
- **`SecurityMembership`** `{role = SECURITY}` — ops: `+ validateAccessCode(code: String): VisitorAccessRequest`,
  `+ checkIn(r: VisitorAccessRequest): void`, `+ checkOut(r: VisitorAccessRequest): void`
  — *visitor operations only; no resident-directory access* — *multi-community*
- **`ManagerMembership`** `{role = MANAGER}` — ops: `+ assignWorkOrder(wo, staff): WorkOrderAssignment`,
  `+ manageStaff(a: StaffAssignment): void`, `+ overrideBooking(o: AmenityBookingOccurrence): void`
  — *cannot grant roles, transfer admin, publish policy, or change financial settings* — *multi-community*
- **`AdminMembership`** `{role = ADMIN}` — ops: `+ inviteResident(unit, email): ResidentInvite`,
  `+ grantRole(p: Profile, r: MembershipRole): CommunityMembership`, `+ issueInvoice(...): Invoice`,
  `+ publishPolicy(p: Policy): PolicyRevision`, `+ transferAdminRights(to: CommunityMembership): void`
  — *exactly one active per community; single community only*

**`Department` «entity»**
`- id: UUID {PK}`, `- name: String {required, unique per community}`, `- description: Text {0..1}`,
`- status: String {required}`, `- createdAt`, `- updatedAt`
ops: `+ activate(): void`, `+ deactivate(): void`, `+ /headcount(): Integer`

**`Vendor` «entity»** — *not tenant-scoped; shared across communities*
`- id: UUID {PK}`, `- legalName: String {required}`, `- contactName: String {0..1}`,
`- contactEmail: String {0..1}`, `- contactPhoneE164: String {0..1}`, `- address: Text {0..1}`,
`- status: String {required}`, `- createdAt`, `- updatedAt`
ops: `+ deactivate(): void`, `+ assignments(): List<StaffAssignment>`

**`StaffAssignment` «entity»** — extends a staff membership with employment data
`- id: UUID {PK}`, `- employmentType: EmploymentType {required}`, `- employeeCode: String {0..1}`,
`- jobTitle: String {0..1}`, `- status: StaffAssignmentStatus {required}`,
`- assignedAt: DateTime {required}`, `- endedAt: DateTime {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ addSkill(s: Skill, level: ProficiencyLevel): StaffSkill`, `+ hasSkill(name: String): Boolean`,
`+ isAvailable(range: TimeRange): Boolean`, `+ acceptedAssignments(): List<WorkOrderAssignment>`, `+ end(reason: String): void`
constraint note: *one active staff assignment per membership*

**`Skill` «entity»** — *technician / serviceman / plumber / electrician are skills, NOT roles*
`- id: UUID {PK}`, `- name: String {unique, required}`, `- category: String {0..1}`,
`- description: Text {0..1}`, `- status: String {required}`, `- createdAt`, `- updatedAt`

**`StaffSkill` «association class»** (StaffAssignment ↔ Skill, composite PK)
`- proficiencyLevel: ProficiencyLevel {0..1}`, `- verifiedAt: DateTime {0..1}`, `- createdAt`
ops: `+ verify(by: CommunityMembership): void`, `+ /isVerified(): Boolean`

**`WorkerAvailabilityRule` «entity»** *realizes* `Schedulable`
`- id: UUID {PK}`, `- weekday: Weekday {required}`, `- startTime: Time {required}`, `- endTime: Time {required}`,
`- effectiveFrom: Date {required}`, `- effectiveTo: Date {0..1}`, `- status: String {required}`, `- createdAt`, `- updatedAt`
ops: `+ covers(at: DateTime): Boolean`, `+ toRangeOn(day: Date): TimeRange`

**`WorkerUnavailability` «entity»** *realizes* `Schedulable`
`- id: UUID {PK}`, `- range: TimeRange {required}`, `- reason: String {0..1}`, `- status: String {required}`,
`- createdAt`, `- updatedAt`
ops: `+ blocks(range: TimeRange): Boolean`

### 6.4 NAVY/TEAL — Resident onboarding

**`ResidentInvite` «aggregate root»**
`- id: UUID {PK}`, `- recipientEmail: String {required}`, `- status: InviteStatus {required}`,
`- authInviteSentAt: DateTime {0..1}`, `- expiresAt: DateTime {required}`,
`- acceptedAt: DateTime {0..1}`, `- revokedAt: DateTime {0..1}`, `- revocationReason: String {0..1}`,
`- createdAt`, `- updatedAt`
ops: `+ send(): void`, `+ revoke(by: CommunityMembership, reason: String): void`,
`+ reissue(): ResidentInvite`, `+ accept(p: Profile): UnitResidency`, `+ /isRedeemable(): Boolean`
note: *single-use; only hashes are ever stored — never a plaintext token*

**`AccessRequest` «aggregate root»** *realizes* `Approvable`
`- id: UUID {PK}`, `- applicantName: String {required}`, `- applicantEmail: String {required}`,
`- applicantPhoneE164: String {required}`, `- requestedOccupancyType: OccupancyType {required}`,
`- status: AccessRequestStatus {required}`, `- reviewedAt: DateTime {0..1}`,
`- decisionReason: String {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ approve(by: CommunityMembership): ResidentInvite`, `+ reject(by, reason): void`, `+ withdraw(): void`

### 6.5 RED — Complaints, work orders, scheduling

**`Complaint` «aggregate root» «Auditable»**
`- id: UUID {PK}`, `- title: String {required}`, `- description: Text {required}`,
`- category: String {required}`, `- urgency: Urgency {required}`, `- status: ComplaintStatus {required}`,
`- submittedAt: DateTime {required}`, `- resolvedAt: DateTime {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ changeStatus(next: ComplaintStatus, actor: CommunityMembership, note: String): ComplaintEvent`,
`+ escalate(): void`, `+ raiseWorkOrder(dept: Department): WorkOrder`, `+ resolve(): void`, `+ reopen(reason: String): void`

**`ComplaintEvent` «event»** (extends `AuditableEvent`, append-only)
`- id: UUID {PK}`, `- eventType: String {required}`, `- previousStatus: ComplaintStatus {0..1}`,
`- newStatus: ComplaintStatus {0..1}`, `- note: Text {0..1}`, `- metadata: JSON {0..1}`, `- createdAt`

**`WorkOrder` «aggregate root»** *realizes* `Schedulable`
`- id: UUID {PK}`, `- title: String {required}`, `- description: Text {required}`,
`- serviceCategory: String {required}`, `- priority: Priority {required}`, `- status: WorkOrderStatus {required}`,
`- preferredRange: TimeRange {0..1}`, `- scheduledRange: TimeRange {0..1}`,
`- escalationRequired: Boolean {required}`, `- resolvedAt: DateTime {0..1}`, `- closedAt: DateTime {0..1}`,
`- createdAt`, `- updatedAt`
ops: `+ assign(staff: StaffAssignment, by: CommunityMembership): WorkOrderAssignment`,
`+ schedule(range: TimeRange): void`, `+ recordView(staff: StaffAssignment): WorkOrderView`,
`+ attachEvidence(m: MediaAsset, t: AttachmentType): WorkOrderAttachment`,
`+ verifyCompletion(method: VerificationMethod): WorkOrderCompletionVerification`, `+ close(): void`

**`WorkOrderAssignment` «entity»** *realizes* `Schedulable`
`- id: UUID {PK}`, `- status: AssignmentStatus {required}`, `- assignedAt: DateTime {required}`,
`- acceptedAt: DateTime {0..1}`, `- declinedAt: DateTime {0..1}`, `- declineReason: String {0..1}`,
`- scheduledRange: TimeRange {0..1}`, `- completedAt: DateTime {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ accept(): void`, `+ decline(reason: String): void`, `+ complete(at: DateTime): void`,
`+ overlaps(other: WorkOrderAssignment): Boolean`
constraint note: *accepted assignments for one worker may never overlap (Postgres `EXCLUDE USING gist`)*

**`WorkOrderProposal` «entity»** — versioned counter-offers, never overwritten
`- id: UUID {PK}`, `- proposalVersion: Integer {required}`, `- proposedRange: TimeRange {required}`,
`- quotedAmount: Money {0..1}`, `- status: ProposalStatus {required}`, `- note: Text {0..1}`,
`- expiresAt: DateTime {0..1}`, `- acceptedAt: DateTime {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ counter(range: TimeRange, quote: Money): WorkOrderProposal`, `+ accept(): WorkOrderAssignment`,
`+ reject(reason: String): void`, `+ expire(): void`

**`WorkOrderView` «association class»** (WorkOrder ↔ StaffAssignment, composite PK)
`- firstViewedAt: DateTime {required}`, `- lastViewedAt: DateTime {required}`, `- viewCount: Integer {required}`
ops: `+ touch(): void`

**`WorkOrderCompletionVerification` «entity»**
`- id: UUID {PK}`, `- verificationMethod: VerificationMethod {required}`, `- otpDigest: String {0..1}`,
`- verifiedAt: DateTime {0..1}`, `- notes: Text {0..1}`, `- createdAt`
ops: `+ issueOtp(): String`, `+ verify(submitted: String): Boolean`

### 6.6 PURPLE — Visitor management

**`SavedVisitor` «entity»**
`- id: UUID {PK}`, `- visitorName: String {required}`, `- phoneE164: String {0..1}`,
`- visitorType: VisitorType {required}`, `- notes: Text {0..1}`, `- isActive: Boolean {required}`,
`- createdAt`, `- updatedAt`
ops: `+ deactivate(): void`, `+ toRequest(unit: Unit): VisitorAccessRequest`

**`VisitorAccessRequest` «aggregate root»** *realizes* `Approvable`, `Auditable`
`- id: UUID {PK}`, `- visitorName: String {required}`, `- visitorPhoneE164: String {0..1}`,
`- visitorType: VisitorType {required}`, `- purpose: String {0..1}`, `- status: VisitorRequestStatus {required}`,
`- requestedArrivalAt: DateTime {0..1}`, `- validFrom: DateTime {0..1}`, `- validUntil: DateTime {0..1}`,
`- accessCodeDigest: String {0..1}`, `- approvedAt: DateTime {0..1}`, `- rejectedAt: DateTime {0..1}`,
`- rejectionReason: String {0..1}`, `- checkedInAt: DateTime {0..1}`, `- checkedOutAt: DateTime {0..1}`,
`- createdAt`, `- updatedAt`
ops: `+ approve(by: CommunityMembership): void`, `+ reject(by, reason: String): void`,
`+ issueAccessCode(): String`, `+ validateCode(code: String): Boolean`,
`+ checkIn(by: SecurityMembership): VisitorEvent`, `+ checkOut(by: SecurityMembership): VisitorEvent`,
`+ /isValidNow(): Boolean`
note: *only the digest of the one-time code is stored*

**`VisitorEvent` «event»** (extends `AuditableEvent`)
`- id: UUID {PK}`, `- eventType: String {required}`, `- metadata: JSON {0..1}`, `- createdAt`

### 6.7 GREEN — Amenities, bookings, finance

**`Amenity` «aggregate root»**
`- id: UUID {PK}`, `- name: String {required, unique per community}`, `- description: Text {0..1}`,
`- category: String {0..1}`, `- capacity: Integer {0..1}`, `- bookingMode: BookingMode {required}`,
`- approvalRequired: Boolean {required}`, `- status: String {required}`, `- createdAt`, `- updatedAt`
ops: `+ ruleAt(when: DateTime): AmenityRule`, `+ isAvailable(range: TimeRange): Boolean`,
`+ requestBooking(by: ResidentMembership, ranges: List<TimeRange>): AmenityBookingSeries`, `+ deactivate(): void`

**`AmenityRule` «entity»**
`- id: UUID {PK}`, `- weekday: Weekday {0..1}`, `- opensAt: Time {0..1}`, `- closesAt: Time {0..1}`,
`- maxDurationMinutes: Integer {0..1}`, `- maxGuests: Integer {0..1}`, `- advanceBookingDays: Integer {0..1}`,
`- cancellationDeadlineMinutes: Integer {0..1}`, `- bookingCharge: Money {0..1}`, `- depositAmount: Money {0..1}`,
`- effectiveFrom: Date {required}`, `- effectiveTo: Date {0..1}`, `- status: String {required}`, `- createdAt`, `- updatedAt`
ops: `+ allows(range: TimeRange, guests: Integer): Boolean`, `+ chargeFor(range: TimeRange): Money`,
`+ isCancellableAt(now: DateTime, start: DateTime): Boolean`

**`AmenityBookingSeries` «aggregate root»** *realizes* `Approvable`, `Cancellable`
`- id: UUID {PK}`, `- title: String {required}`, `- bookingType: String {required}`,
`- isPrivate: Boolean {required}`, `- guestCount: Integer {required}`, `- notes: Text {0..1}`,
`- status: BookingSeriesStatus {required}`, `- requestedAt: DateTime {required}`,
`- approvedAt: DateTime {0..1}`, `- rejectedAt: DateTime {0..1}`, `- rejectionReason: String {0..1}`,
`- createdAt`, `- updatedAt`
ops: `+ addOccurrence(range: TimeRange): AmenityBookingOccurrence`, `+ approve(by): void`,
`+ reject(by, reason): void`, `+ cancelOccurrence(o, reason): void`, `+ addGuest(name, phone): BookingGuest`,
`+ /totalCharges(): Money`

**`AmenityBookingOccurrence` «entity»** *realizes* `Schedulable`, `Cancellable`
`- id: UUID {PK}`, `- range: TimeRange {required}`, `- status: OccurrenceStatus {required}`,
`- cancelledAt: DateTime {0..1}`, `- cancellationReason: String {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ cancel(by: CommunityMembership, reason: String): void`, `+ overlaps(other): Boolean`,
`+ raiseCharge(t: ChargeType, amount: Money): AmenityBookingCharge`, `+ complete(): void`
constraint note: *active occurrences of one amenity may never overlap (`EXCLUDE USING gist`)*

**`BookingGuest` «entity»**
`- id: UUID {PK}`, `- guestName: String {required}`, `- phoneE164: String {0..1}`, `- createdAt`

**`AmenityBookingCharge` «entity»**
`- id: UUID {PK}`, `- chargeType: ChargeType {required}`, `- amount: Money {required}`,
`- status: ChargeStatus {required}`, `- description: Text {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ settle(): void`, `+ refund(amount: Money, reason: String): AmenityFinancialEvent`,
`+ deductDamage(amount: Money, reason: String): AmenityFinancialEvent`, `+ waive(reason: String): void`

**`AmenityFinancialEvent` «event»** (extends `AuditableEvent`, append-only ledger)
`- id: UUID {PK}`, `- eventType: FinancialEventType {required}`, `- amount: Money {required}`,
`- paymentReference: String {0..1}`, `- reason: String {0..1}`, `- metadata: JSON {0..1}`, `- createdAt`

**`Invoice` «aggregate root»** — *liability belongs to the UNIT, not to a person*
`- id: UUID {PK}`, `- invoiceNumber: String {unique, required}`, `- invoiceType: InvoiceType {required}`,
`- status: InvoiceStatus {required}`, `- billingPeriodStart: Date {0..1}`, `- billingPeriodEnd: Date {0..1}`,
`- issuedOn: Date {required}`, `- dueOn: Date {required}`, `- subtotalAmount: Money {required}`,
`- taxAmount: Money {required}`, `- totalAmount: Money {required}`, `- outstandingAmount: Money {required}`,
`- createdAt`, `- updatedAt`
ops: `+ addLineItem(desc: String, qty: Decimal, unit: Money): InvoiceLineItem`, `+ issue(): void`,
`+ applyPayment(p: Payment): void`, `+ recalculateTotals(): void`, `+ markOverdue(): void`, `+ /isSettled(): Boolean`

**`InvoiceLineItem` «entity»**
`- id: UUID {PK}`, `- description: Text {required}`, `- quantity: Decimal {required}`,
`- unitAmount: Money {required}`, `- totalAmount: Money {required}`, `- createdAt`
ops: `+ recalculate(): Money`

**`Payment` «aggregate root»** — *identifies the resident who paid*
`- id: UUID {PK}`, `- amount: Money {required}`, `- paymentMethod: PaymentMethod {required}`,
`- providerReference: String {unique, 0..1}`, `- status: PaymentStatus {required}`,
`- paidAt: DateTime {0..1}`, `- createdAt`, `- updatedAt`
ops: `+ capture(): void`, `+ fail(reason: String): PaymentEvent`, `+ refund(amount: Money): PaymentEvent`

**`PaymentEvent` «event»** (extends `AuditableEvent`)
`- id: UUID {PK}`, `- eventType: String {required}`, `- previousStatus: PaymentStatus {0..1}`,
`- newStatus: PaymentStatus {0..1}`, `- metadata: JSON {0..1}`, `- createdAt`

### 6.8 BLUE — Notices, policies, notifications, audit, media

**`Notice` «entity»**
`- id: UUID {PK}`, `- title: String {required}`, `- body: Text {required}`, `- category: String {0..1}`,
`- urgency: Urgency {required}`, `- publishedAt: DateTime {0..1}`, `- expiresAt: DateTime {0..1}`,
`- status: NoticeStatus {required}`, `- createdAt`, `- updatedAt`
ops: `+ publish(): Notification`, `+ expire(): void`, `+ archive(): void`

**`Policy` «aggregate root»**
`- id: UUID {PK}`, `- policyCode: String {required, unique per community}`, `- title: String {required}`,
`- status: PolicyStatus {required}`, `- currentRevisionNumber: Integer {required}`, `- createdAt`, `- updatedAt`
ops: `+ addRevision(body: Text, effectiveAt: DateTime): PolicyRevision`,
`+ currentRevision(): PolicyRevision`, `+ supersede(): void`, `+ archive(): void`

**`PolicyRevision` «entity» «immutable»**
`- id: UUID {PK}`, `- revisionNumber: Integer {required}`, `- sectionReference: String {0..1}`,
`- body: Text {required}`, `- effectiveAt: DateTime {required}`, `- publishImmediately: Boolean {required}`,
`- publishedAt: DateTime {0..1}`, `- createdAt`
ops: `+ publish(): void`, `+ /isEffective(at: DateTime): Boolean`

**`Notification` «entity»** — polymorphic source via `sourceType` + `sourceId`
`- id: UUID {PK}`, `- sourceType: String {required}`, `- sourceId: UUID {0..1}`,
`- notificationType: String {required}`, `- title: String {required}`, `- body: Text {required}`,
`- payload: JSON {0..1}`, `- scheduledFor: DateTime {0..1}`, `- sentAt: DateTime {0..1}`, `- createdAt`
ops: `+ fanOut(recipients: List<Profile>, channels: Set<NotificationChannel>): List<NotificationDelivery>`,
`+ send(): void`

**`NotificationDelivery` «entity»**
`- id: UUID {PK}`, `- channel: NotificationChannel {required}`, `- status: DeliveryStatus {required}`,
`- deliveredAt: DateTime {0..1}`, `- readAt: DateTime {0..1}`, `- failedAt: DateTime {0..1}`,
`- failureReason: String {0..1}`, `- createdAt`
ops: `+ markRead(): void`, `+ markFailed(reason: String): void`
constraint: `{unique (notification, profile, channel)}`

**`AuditEvent` «event» «immutable»** (extends `AuditableEvent`)
`- id: UUID {PK}`, `- eventType: String {required}`, `- targetType: String {required}`,
`- targetId: UUID {0..1}`, `- metadata: JSON {0..1}`, `- occurredAt: DateTime {required}`
ops: `+ «static» record(actor, type, target, meta): AuditEvent`

**`MediaAsset` «aggregate root»**
`- id: UUID {PK}`, `- bucketId: StorageBucket {required}`, `- objectPath: String {unique, required}`,
`- originalFilename: String {required}`, `- mimeType: String {required}`, `- byteSize: Long {required}`,
`- sha256: String {0..1}`, `- status: MediaStatus {required}`, `- createdAt`, `- deletedAt: DateTime {0..1}`
ops: `+ signedUrl(ttlSeconds: Integer): String`, `+ softDelete(): void`, `+ /isReady(): Boolean`

**`WorkOrderAttachment` «association class»** (extends `AttachmentLink`) — WorkOrder ↔ MediaAsset
**`VisitorAttachment` «association class»** (extends `AttachmentLink`) — VisitorAccessRequest ↔ MediaAsset

---

## 7. ASSOCIATION CLASSES

Draw `StaffSkill`, `WorkOrderView`, `WorkOrderAttachment`, `VisitorAttachment` as proper UML
association classes: a small class box attached by a dashed line to the midpoint of the
many-to-many association it qualifies. Do **not** render them as ordinary entities with two arrows.

---

## 8. GENERALIZATION / REALIZATION EDGES

- `Profile` ─▷ (1:1 identity extension of) `AuthUser` — dashed `«extends identity»` (external boundary)
- `ResidentMembership`, `WorkerMembership`, `SecurityMembership`, `ManagerMembership`, `AdminMembership` ─▷ `CommunityMembership`
- `ComplaintEvent`, `VisitorEvent`, `PaymentEvent`, `AmenityFinancialEvent`, `AuditEvent` ─▷ `AuditableEvent`
- `WorkOrderAttachment`, `VisitorAttachment` ─▷ `AttachmentLink`
- `TenantScopedEntity` ─▷ `BaseEntity`
- Realizations (dashed ▷): `WorkOrder`, `WorkOrderAssignment`, `AmenityBookingOccurrence`,
  `WorkerAvailabilityRule`, `WorkerUnavailability` ⟶ `Schedulable`;
  `AccessRequest`, `VisitorAccessRequest`, `AmenityBookingSeries` ⟶ `Approvable`;
  `AmenityBookingSeries`, `AmenityBookingOccurrence` ⟶ `Cancellable`;
  `Complaint`, `VisitorAccessRequest`, `Payment`, `Policy` ⟶ `Auditable`

---

## 9. ASSOCIATIONS — draw EVERY line below with both multiplicities and the role name

Notation used here: `Source [mult] —(kind)— [mult] Target : roleName`.
`◆` = composition, `◇` = aggregation, plain = association, `⇢` = dependency.

**Foundation**
- `AuthUser [1] — [1] Profile : identity`
- `Profile [0..1] — [0..*] CommunityRegistrationRequest : applicant`
- `CommunityRegistrationRequest [0..1] — [0..1] Community : createdCommunity`
- `Community [1] ◆ [0..*] Building : buildings`
- `Community [1] ◆ [0..*] Unit : units`
- `Building [0..1] ◇ [0..*] Unit : unitsInBuilding`
- `Community [1] ◆ [0..*] CommunityMembership : memberships`
- `Profile [1] — [0..*] CommunityMembership : memberOf`
- `Community [1] — [0..1] AdminMembership : activeAdmin {subsets memberships}`
- `CommunityMembership [0..1] — [0..*] CommunityMembership : invitedBy / invitees`

**Occupancy**
- `Community [1] — [0..*] UnitResidency : residencies`
- `Unit [1] ◆ [0..*] UnitResidency : occupancyHistory`
- `Profile [1] — [0..*] UnitResidency : occupies`
- `CommunityMembership [0..1] — [0..*] UnitResidency : viaMembership`

**Staffing**
- `Community [1] ◆ [0..*] Department : departments`
- `CommunityMembership [0..1] — [0..*] Department : createdBy`
- `Community [1] — [0..*] StaffAssignment : staffing`
- `CommunityMembership [1] — [0..1] StaffAssignment : staffProfile`
- `Department [0..1] — [0..*] StaffAssignment : members`
- `Vendor [0..1] — [0..*] StaffAssignment : contractedStaff`
- `StaffAssignment [1] — [0..*] StaffSkill [0..*] — [1] Skill : skills` (association class `StaffSkill`)
- `CommunityMembership [0..1] — [0..*] StaffSkill : verifiedBy`
- `StaffAssignment [1] ◆ [0..*] WorkerAvailabilityRule : availability`
- `StaffAssignment [1] ◆ [0..*] WorkerUnavailability : timeOff`

**Onboarding**
- `Community [1] — [0..*] ResidentInvite : invites`
- `Unit [1] — [0..*] ResidentInvite : forUnit`
- `UnitResidency [0..1] — [0..1] ResidentInvite : preparedResidency`
- `AuthUser [0..1] ⇢ [0..*] ResidentInvite : invitedAuthUser` (dashed, crosses external boundary)
- `CommunityMembership [0..1] — [0..*] ResidentInvite : issuedBy`
- `CommunityMembership [0..1] — [0..*] ResidentInvite : revokedBy`
- `Profile [0..1] — [0..*] ResidentInvite : acceptedBy`
- `Community [1] — [0..*] AccessRequest : accessRequests`
- `Unit [0..1] — [0..*] AccessRequest : requestedUnit`
- `Profile [0..1] — [0..*] AccessRequest : applicant`
- `CommunityMembership [0..1] — [0..*] AccessRequest : reviewedBy`
- `ResidentInvite [0..1] — [0..1] AccessRequest : resultingInvite`

**Complaints and work orders**
- `Community [1] — [0..*] Complaint : complaints`
- `Unit [0..1] — [0..*] Complaint : raisedForUnit`
- `ResidentMembership [1] — [0..*] Complaint : raisedBy`
- `Complaint [1] ◆ [0..*] ComplaintEvent : timeline`
- `CommunityMembership [0..1] — [0..*] ComplaintEvent : actor`
- `Community [1] — [0..*] WorkOrder : workOrders`
- `Complaint [0..1] — [0..*] WorkOrder : derivedWorkOrders`
- `Department [0..1] — [0..*] WorkOrder : handledBy`
- `CommunityMembership [0..1] — [0..*] WorkOrder : createdBy`
- `WorkOrder [1] ◆ [0..*] WorkOrderAssignment : assignments`
- `StaffAssignment [1] — [0..*] WorkOrderAssignment : assignedWork`
- `CommunityMembership [0..1] — [0..*] WorkOrderAssignment : assignedBy`
- `WorkOrder [1] ◆ [0..*] WorkOrderProposal : proposals`
- `WorkOrderAssignment [0..1] — [0..*] WorkOrderProposal : forAssignment`
- `CommunityMembership [1] — [0..*] WorkOrderProposal : proposedBy`
- `WorkOrderProposal [0..1] — [0..*] WorkOrderProposal : parent / counterOffers`
- `WorkOrder [1] — [0..*] WorkOrderView [0..*] — [1] StaffAssignment : viewedBy` (association class)
- `WorkOrder [1] — [0..*] WorkOrderCompletionVerification : verifications`
- `WorkOrderAssignment [0..1] — [0..*] WorkOrderCompletionVerification : forAssignment`
- `ResidentMembership [0..1] — [0..*] WorkOrderCompletionVerification : residentConfirmedBy`

**Media**
- `Community [0..1] — [0..*] MediaAsset : media`
- `Profile [0..1] — [0..*] MediaAsset : uploadedBy`
- `WorkOrder [1] — [0..*] WorkOrderAttachment [0..*] — [1] MediaAsset : evidence` (association class)
- `VisitorAccessRequest [1] — [0..*] VisitorAttachment [0..*] — [1] MediaAsset : visitorMedia` (association class)
- `SupabaseStorage [1] ⇢ [0..*] MediaAsset : «resolves via bucketId + objectPath»` (dotted)

**Visitors**
- `Community [1] — [0..*] SavedVisitor : savedVisitors`
- `CommunityMembership [0..1] — [0..*] SavedVisitor : createdBy`
- `Community [1] — [0..*] VisitorAccessRequest : visitorRequests`
- `Unit [1] — [0..*] VisitorAccessRequest : visitingUnit`
- `ResidentMembership [1] — [0..*] VisitorAccessRequest : requestedBy`
- `SecurityMembership [0..1] — [0..*] VisitorAccessRequest : handledBySecurity`
- `SavedVisitor [0..1] — [0..*] VisitorAccessRequest : fromSavedVisitor`
- `CommunityMembership [0..1] — [0..*] VisitorAccessRequest : approvedBy`
- `SecurityMembership [0..1] — [0..*] VisitorAccessRequest : checkedInBy`
- `SecurityMembership [0..1] — [0..*] VisitorAccessRequest : checkedOutBy`
- `VisitorAccessRequest [1] ◆ [0..*] VisitorEvent : timeline`
- `CommunityMembership [0..1] — [0..*] VisitorEvent : actor`

**Amenities and bookings**
- `Community [1] ◆ [0..*] Amenity : amenities`
- `CommunityMembership [0..1] — [0..*] Amenity : createdBy`
- `Amenity [1] ◆ [0..*] AmenityRule : rules`
- `Community [1] — [0..*] AmenityBookingSeries : bookings`
- `Amenity [1] — [0..*] AmenityBookingSeries : bookedAmenity`
- `Unit [0..1] — [0..*] AmenityBookingSeries : bookedForUnit`
- `ResidentMembership [1] — [0..*] AmenityBookingSeries : requestedBy`
- `CommunityMembership [0..1] — [0..*] AmenityBookingSeries : approvedBy`
- `AmenityBookingSeries [1] ◆ [1..*] AmenityBookingOccurrence : occurrences`
- `Amenity [1] — [0..*] AmenityBookingOccurrence : scheduledOn`
- `CommunityMembership [0..1] — [0..*] AmenityBookingOccurrence : cancelledBy`
- `AmenityBookingSeries [1] ◆ [0..*] BookingGuest : guests`
- `AmenityBookingOccurrence [1] ◆ [0..*] AmenityBookingCharge : charges`
- `AmenityBookingCharge [1] ◆ [0..*] AmenityFinancialEvent : ledger`
- `CommunityMembership [0..1] — [0..*] AmenityFinancialEvent : actor`

**Finance**
- `Community [1] — [0..*] Invoice : invoices`
- `Unit [1] — [0..*] Invoice : billedUnit`
- `CommunityMembership [0..1] — [0..*] Invoice : createdBy`
- `Invoice [1] ◆ [1..*] InvoiceLineItem : lineItems`
- `AmenityBookingCharge [0..1] — [0..1] InvoiceLineItem : billedCharge`
- `Invoice [1] — [0..*] Payment : payments`
- `Profile [1] — [0..*] Payment : payer`
- `CommunityMembership [0..1] — [0..*] Payment : receivedBy`
- `Payment [1] ◆ [0..*] PaymentEvent : timeline`
- `CommunityMembership [0..1] — [0..*] PaymentEvent : actor`

**Communication, policy, audit**
- `Community [1] — [0..*] Notice : notices` ; `CommunityMembership [0..1] — [0..*] Notice : createdBy`
- `Community [1] — [0..*] Policy : policies` ; `CommunityMembership [0..1] — [0..*] Policy : createdBy`
- `Policy [1] ◆ [1..*] PolicyRevision : revisions` ; `CommunityMembership [0..1] — [0..*] PolicyRevision : authoredBy`
- `Community [1] — [0..*] Notification : notifications`
- `Notification [1] ◆ [0..*] NotificationDelivery : deliveries`
- `Profile [1] — [0..*] NotificationDelivery : recipient`
- `Community [0..1] — [0..*] AuditEvent : auditTrail`
- `Profile [0..1] — [0..*] AuditEvent : actorProfile`
- `CommunityMembership [0..1] — [0..*] AuditEvent : actorMembership`

---

## 10. PRESENTATION / API LAYER (Band A, grey)

All are `«controller»` FastAPI routers under `/api/v1`. Show each with its route operations and a
`«uses»` dependency arrow to its service. Do not connect controllers directly to domain classes.

- `AuthController` — `+ requestOtp(body: OtpRequest): MessageResponse`, `+ verifyOtp(body: OtpVerifyRequest): SessionDTO`, `+ refresh(body: RefreshRequest): SessionDTO`, `+ me(): ProfileDTO`
- `RegistrationController` — `+ submit(...)`, `+ verifyOtp(...)`, `+ reviewDecision(...)`
- `MembershipController` — `+ listMembers(...)`, `+ grantRole(...)`, `+ endMembership(...)`, `+ transferAdmin(...)`
- `UnitController` — `+ listUnits(...)`, `+ createUnit(...)`, `+ transferPrimaryContact(...)`
- `InvitationController` — `+ createInvitation(body: CreateInvitationRequest): InvitationCreated`, `+ revoke(...)`, `+ reissue(...)`, `+ redeem(body: RedeemRequest): SessionDTO`
- `AccessRequestController`, `ComplaintController`, `WorkOrderController`, `SchedulingController`,
  `VisitorController`, `AmenityController`, `BookingController`, `InvoiceController`,
  `PaymentController`, `NoticeController`, `PolicyController`, `NotificationController`,
  `MediaController`, `AuditController` — each with 3–5 representative route operations.

Security plumbing (grey, `«policy»`):
- `RoleGuard` — `+ requireRole(roles: Set<MembershipRole>): Dependency`, `+ requireMembership(communityId): Dependency`
- `SecurityContext` «DTO» — `- userId: UUID`, `- role: MembershipRole`, `- communityId: UUID`, `- membershipId: UUID`, `+ isAdmin(): Boolean`, `+ can(action: String): Boolean`
- `RolePolicy` «policy» — `+ effectiveRoles(r: MembershipRole): Set<MembershipRole>`, `+ satisfies(user, required): Boolean`, `+ satisfiesAny(user, required): Boolean`
- `RlsPolicySet` «policy» — `+ tenantPredicate(table: String): String`, `+ appliesTo(table): Boolean`
  — note: *RLS is the real authorization boundary; guards are defence in depth*

DTO cluster «DTO» (compact box list, no attributes needed beyond 3–4 each):
`OtpRequest`, `OtpVerifyRequest`, `RefreshRequest`, `SessionDTO`, `ProfileDTO`, `MessageResponse`,
`CreateInvitationRequest`, `InvitationCreated`, `RedeemRequest`, `PaginatedResponse<T>`, `ErrorResponse`.
Draw one `«maps to»` dashed arrow from the DTO cluster to the domain band, not one per DTO.

---

## 11. APPLICATION / SERVICE LAYER (Band B, orange, `«service»`)

Each service depends (`«uses»`, dashed) on its repositories and on `AuditService`.

- `AuthService` — `+ requestLoginOtp(phone): void`, `+ verifyLoginOtp(phone, token): SessionDTO`, `+ refreshSession(token): SessionDTO`, `+ currentProfile(ctx): Profile`
- `RegistrationService` — `+ submitRequest(dto): CommunityRegistrationRequest`, `+ verifyOtp(id, code): void`, `+ approve(id, operatorRef): Community`, `+ reject(id, reason): void`
- `MembershipService` — `+ grantRole(profile, community, role): CommunityMembership`, `+ endMembership(id, reason): void`, `+ transferAdmin(community, successor): AdminMembership`, `- assertSingleActiveAdmin(community): void`
- `ResidencyService` — `+ addResidency(...)`, `+ transferPrimaryContact(unit, to, by): void`, `+ endOccupancy(id, date): void`
- `StaffService` — `+ createAssignment(...)`, `+ assignSkill(...)`, `+ setAvailability(...)`, `+ markUnavailable(...)`
- `InvitationService` — `+ createInvitation(ctx, dto): InvitationCreated`, `+ evaluate(invite): Optional<String>`, `+ redeem(dto): SessionDTO`, `+ revoke(id, reason): void`, `- provisionAndLogin(...): SessionDTO`
- `AccessRequestService` — `+ submit(dto)`, `+ approve(id, by): ResidentInvite`, `+ reject(id, reason)`
- `ComplaintService` — `+ raise(...)`, `+ changeStatus(...)`, `+ escalate(...)`, `+ attachMedia(...)`
- `WorkOrderService` — `+ createFromComplaint(...)`, `+ assign(...)`, `+ recordView(...)`, `+ verifyCompletion(...)`, `+ close(...)`
- `SchedulingService` — `+ findAvailableWorkers(range, skill): List<StaffAssignment>`, `+ assertNoWorkerOverlap(a): void`, `+ assertNoAmenityOverlap(o): void`, `+ reschedule(...)`
- `ProposalService` — `+ propose(...)`, `+ counter(...)`, `+ accept(...)`, `+ expireStale(): Integer`
- `VisitorService` — `+ preApprove(...)`, `+ approve(...)`, `+ issueCode(...)`, `+ validateCode(code): VisitorAccessRequest`, `+ checkIn(...)`, `+ checkOut(...)`
- `AmenityService` — `+ create(...)`, `+ setRules(...)`, `+ availability(amenity, day): List<TimeRange>`
- `BookingService` — `+ request(...)`, `+ approve(...)`, `+ cancelOccurrence(...)`, `+ priceSeries(series): Money`
- `BillingService` — `+ generateInvoice(unit, period): Invoice`, `+ addAmenityCharges(invoice): void`, `+ markOverdue(): Integer`
- `PaymentService` — `+ initiate(invoice, method, payer): Payment`, `+ confirm(reference): Payment`, `+ refund(payment, amount, reason): Payment`
- `NoticeService`, `PolicyService`, `NotificationService`, `MediaService`, `AuditService`
  - `NotificationService` — `+ publish(source, recipients, channels): Notification`, `+ markRead(deliveryId): void`
  - `MediaService` — `+ createUploadUrl(bucket, path): String`, `+ register(asset): MediaAsset`, `+ signedUrl(asset, ttl): String`
  - `AuditService` — `+ record(ctx, eventType, target, metadata): AuditEvent`, `+ trailFor(targetType, targetId): List<AuditEvent>`

---

## 12. PERSISTENCE LAYER (Band D, slate, `«repository»`)

- `«interface» Repository<T>` — `+ getById(id: UUID): Optional<T>`, `+ list(filter: Query): List<T>`, `+ insert(entity: T): T`, `+ update(entity: T): T`, `+ softDelete(id: UUID): void`
- Concrete repositories realizing `Repository<T>` (dashed ▷), each with 2–4 domain-specific finders:
  `ProfileRepository` (`+ getProfile(userId)`, `+ upsertProfileRole(...)`),
  `CommunityRepository`, `MembershipRepository` (`+ activeAdminFor(communityId)`, `+ activeFor(profileId)`),
  `UnitRepository`, `ResidencyRepository` (`+ primaryContactFor(unitId)`),
  `DepartmentRepository`, `VendorRepository`, `StaffAssignmentRepository` (`+ availableWorkers(range, skill)`),
  `SkillRepository`, `InvitationRepository` (`+ findByTokenHash(hash)`, `+ findByCodeHash(hash)`, `+ markRedeemed(id)` — *compare-and-set, single use*),
  `AccessRequestRepository`, `ComplaintRepository`, `WorkOrderRepository`, `AssignmentRepository`,
  `ProposalRepository`, `VisitorRepository`, `AmenityRepository`, `BookingRepository`,
  `InvoiceRepository`, `PaymentRepository`, `NoticeRepository`, `PolicyRepository`,
  `NotificationRepository`, `MediaRepository`, `AuditRepository`.
- Every repository has a `«uses»` dependency on `SupabaseClientFactory`.
- Add a note: *"Services depend on the `Repository<T>` abstraction, never on the Supabase SDK
  (Dependency Inversion). Only repositories and gateways touch Postgres."*

---

## 13. INFRASTRUCTURE AND EXTERNAL SYSTEMS (Band D + far edge, dashed)

- `Settings` «singleton» — `- supabaseUrl: String`, `- supabaseAnonKey: String`, `- supabaseServiceRoleKey: String`, `- supabaseJwtSecret: String`, `- frontendBaseUrl: String`, `- inviteTtlHours: Integer`, `- corsOrigins: String`, `- env: String`, `+ isProduction(): Boolean`, `+ corsOriginList(): List<String>`
- `SupabaseClientFactory` «gateway» «singleton» — `+ anonClient(): Client`, `+ userClient(jwt: String): Client`, `+ serviceClient(): Client`
  note: *user client ⇒ RLS enforced; service client ⇒ RLS bypassed, trusted server code only*
- `TokenService` «gateway» — `+ generateToken(): String`, `+ generateCode(): String`, `+ hashSecret(v: String): String`, `+ normalizeCode(v: String): String`
  note: *only digests persist; plaintext is returned to the caller exactly once*
- `JwtVerifier` «gateway» — `+ decode(token: String): SecurityContext`, `+ claims(token): JSON`
- `AppLogger` «gateway» — `+ info(...)`, `+ warning(...)`, `+ error(...)`
- Exception hierarchy (generalization arrows): `AppError` ◁— `AuthenticationError`, `AuthorizationError`, `ValidationError`, `NotFoundError`, `ConflictError`; each with `- message: String`, `- code: String`, `- httpStatus: Integer`
- `«external system» SupabaseAuth (GoTrue)` — `+ signInWithOtp(...)`, `+ verifyOtp(...)`, `+ refreshSession(...)`, `+ admin.createUser(...)`, `+ admin.inviteUserByEmail(...)`
- `«external system» SupabasePostgres` — `+ rpc(name, args)`, `+ from(table)`, hosts RLS policies and `EXCLUDE USING gist` constraints
- `«external system» SupabaseStorage (private buckets)` — `- buckets: {profile-avatars, work-evidence, visitor-media}`, `+ createSignedUploadUrl(...)`, `+ createSignedUrl(...)`, `+ remove(...)`
- `«external system» SupabaseRealtime` — `+ subscribe(table, filter)`; dashed arrow to the frontend store
- `«external system» SmsOtpProvider`, `«external system» EmailProvider`

Dependency arrows: `AuthService ⇢ SupabaseAuth`, `InvitationService ⇢ SupabaseAuth`,
`InvitationService ⇢ TokenService`, `MediaService ⇢ SupabaseStorage`,
`SupabaseClientFactory ⇢ SupabasePostgres`, `RoleGuard ⇢ JwtVerifier`, all services `⇢ AppError`.

**Optional compact frontend cluster** (only if space allows; 6 boxes max, light grey):
`ApiClient` (`+ get/post/patch`, `+ withAuth(token)`), `AuthStore`, `AppStore`,
`ServiceAdapter<T>` «interface», `RealtimeSubscription`, `ToastStore`.
Arrow: `ApiClient ⇢ AuthController` labelled `«HTTPS/JSON»`.

---

## 14. CONSTRAINT NOTES (render each as a visible note anchored to the named class)

1. **`{invariant}` on `Community`** — `activeAdminMembership` must reference an **active `ADMIN`**
   membership of the *same* community; every ACTIVE community has exactly one.
2. **`{enum}` on `CommunityMembership`** — role ∈ {RESIDENT, WORKER, SECURITY, MANAGER, ADMIN}.
   Role lives here, never on `Profile`. There is **no** public `users(id, role)` class.
3. **`{scope}` on `CommunityMembership`** — RESIDENT and ADMIN: at most one active membership across
   all communities. WORKER, SECURITY, MANAGER: many communities allowed. Staff and non-staff
   memberships may not be mixed for one profile.
4. **`{skill ≠ role}` on `Skill`** — *technician* and *serviceman* are skills of a WORKER, not roles.
5. **`{invariant}` on `Unit`** — exactly one `UnitResidency` with `isPrimaryContact = true` and
   `status = ACTIVE` (partial unique index). Transfer: the current primary nominates an active
   resident of the same unit; the community admin may appoint only when no active primary exists.
6. **`{exclusion}` on `WorkOrderAssignment`** — accepted/confirmed assignments of the same worker
   must not overlap in time (`EXCLUDE USING gist (staff_assignment_id WITH =, range WITH &&)`).
   Proposals may overlap until one is accepted.
7. **`{exclusion}` on `AmenityBookingOccurrence`** — active occurrences of the same amenity must not
   overlap in time (same gist exclusion pattern).
8. **`{security}` on `ResidentInvite`** — single-use; only token/code **digests** are stored;
   redemption is a compare-and-set so a race cannot redeem twice.
9. **`{security}` on `VisitorAccessRequest`** — only `accessCodeDigest` is stored;
   SECURITY may read visitor rows in its own community only, and resident contact lookup is a
   narrow audited RPC — there is **no** broad resident-directory association from `SecurityMembership`.
10. **`{billing}` on `Invoice`** — liability belongs to the `Unit`; `Payment.payer` records which
    resident actually paid. The two must not be conflated.
11. **`{immutability}`** — `ComplaintEvent`, `VisitorEvent`, `PaymentEvent`, `AmenityFinancialEvent`,
    `AuditEvent` and `PolicyRevision` are append-only; no update or delete operations exist.
12. **`{auditable}`** — every role change, approval, financial transition, security action, invitation
    action and policy change must emit an `AuditEvent`.
13. **`{storage}` on `MediaAsset`** — the only bridge to Supabase Storage is
    `bucketId` + `objectPath`; buckets are private and access is granted through `storage.objects` RLS.
14. **`{multi-tenancy}`** — draw a large dashed rounded rectangle labelled
    **"RLS tenant boundary — every enclosed class carries `communityId`; Postgres Row-Level Security
    isolates tenant data, and `auth.uid()` + membership predicates authorize every row"** around all
    community-scoped domain classes. `Profile`, `AuthUser`, `Vendor`, `Skill` and
    `CommunityRegistrationRequest` sit **outside** this boundary — label them "global scope".

---

## 15. LEGEND

Place a legend box in the bottom-left corner containing:
- Visibility: `+` public, `-` private, `#` protected
- Relationship glyphs: generalization ▷, realization ⇢▷, composition ◆, aggregation ◇,
  association —, dependency ⇠ ⇢, association class ┈
- Multiplicities: `1`, `0..1`, `0..*`, `1..*`
- Property strings: `{unique}`, `{required}`, `{readOnly}`, `{PK}`, `/derived`
- Stereotype key: «aggregate root», «entity», «value object», «enumeration», «association class»,
  «event», «service», «repository», «controller», «gateway», «DTO», «interface», «external system»
- Type key: `DateTime ≡ timestamptz`, `Money ≡ numeric(12,2)`, `JSON ≡ jsonb`, all ids are `UUID`
- The seven subdomain colors with their labels
- A "dashed border = external system (outside our deployment)" line

---

## 16. LAYOUT AND QUALITY REQUIREMENTS

- Orthogonal connectors only; minimize crossings; never route a line through a class box.
- Cluster by subdomain first, then by dependency direction (left → right: API → service → domain → persistence).
- Place `CommunityMembership` and `Community` centrally — they are the highest-degree classes.
  Consider drawing the many `CommunityMembership` actor/creator associations with short labelled
  connectors or a shared bus line to prevent a hairball.
- Keep every class box readable at 100% zoom on A1; no truncated member names.
- Title block, top-left: **"HomeBandhu — UML Class Diagram (Domain, Application, Persistence and
  Infrastructure Layers)"**, with a version/date line.

**Completeness checklist — verify before returning:**
- 47 domain classes + 5 membership subclasses + 6 abstract/interface types + 5 value objects
- ~38 enumerations
- 4 association classes drawn with UML association-class notation
- Every FK from Section 9 present exactly once, with role name and both multiplicities
- All 14 constraint notes rendered
- Legend, RLS tenant boundary, and title block present
- No `users(id, role)` class anywhere; no role attribute on `Profile`;
  `auth.users` and Supabase Storage clearly external

**Do not:** invent tables or attributes not listed here; merge classes to "simplify"; drop the
association classes; omit multiplicities; use ER crow's-foot notation instead of UML; or replace
operations with attribute-only boxes.
