# Graph Report - .  (2026-07-23)

## Corpus Check
- 257 files · ~160,778 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 987 nodes · 2347 edges · 78 communities (54 shown, 24 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 295 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Amenity Management|Amenity Management]]
- [[_COMMUNITY_Booking Approvals|Booking Approvals]]
- [[_COMMUNITY_Admin Dashboard Management|Admin Dashboard Management]]
- [[_COMMUNITY_Booking Persistence|Booking Persistence]]
- [[_COMMUNITY_Invitation API|Invitation API]]
- [[_COMMUNITY_Amenities Persistence|Amenities Persistence]]
- [[_COMMUNITY_Backend Configuration|Backend Configuration]]
- [[_COMMUNITY_Authentication API|Authentication API]]
- [[_COMMUNITY_Amenity Ledger Persistence|Amenity Ledger Persistence]]
- [[_COMMUNITY_API Authentication Dependencies|API Authentication Dependencies]]
- [[_COMMUNITY_Backend Errors and Auth|Backend Errors and Auth]]
- [[_COMMUNITY_Frontend Dependencies|Frontend Dependencies]]
- [[_COMMUNITY_Onboarding Admin Profile|Onboarding Admin Profile]]
- [[_COMMUNITY_Community Onboarding|Community Onboarding]]
- [[_COMMUNITY_Amenity Booking Forms|Amenity Booking Forms]]
- [[_COMMUNITY_Amenity Time Blocking|Amenity Time Blocking]]
- [[_COMMUNITY_Ledger Financial Actions|Ledger Financial Actions]]
- [[_COMMUNITY_RBAC Role Model|RBAC Role Model]]
- [[_COMMUNITY_User Login Flow|User Login Flow]]
- [[_COMMUNITY_Amenity Booking Data|Amenity Booking Data]]
- [[_COMMUNITY_Invitation Repository|Invitation Repository]]
- [[_COMMUNITY_Admin Authentication|Admin Authentication]]
- [[_COMMUNITY_Association Registration|Association Registration]]
- [[_COMMUNITY_Profile Repository|Profile Repository]]
- [[_COMMUNITY_Ledger Actions|Ledger Actions]]
- [[_COMMUNITY_Legacy Invite Redemption|Legacy Invite Redemption]]
- [[_COMMUNITY_Payments and Pending Requests|Payments and Pending Requests]]
- [[_COMMUNITY_Onboarding Completion|Onboarding Completion]]
- [[_COMMUNITY_Admin Profile|Admin Profile]]
- [[_COMMUNITY_User and Association Seeds|User and Association Seeds]]
- [[_COMMUNITY_Backend Auth Architecture|Backend Auth Architecture]]
- [[_COMMUNITY_Booking Status and Ledger Table|Booking Status and Ledger Table]]
- [[_COMMUNITY_Ledger Audit Detail|Ledger Audit Detail]]
- [[_COMMUNITY_Invitation Tests|Invitation Tests]]
- [[_COMMUNITY_Amenity Timeline Workflows|Amenity Timeline Workflows]]
- [[_COMMUNITY_Workspace Scripts|Workspace Scripts]]
- [[_COMMUNITY_Deployment Architecture|Deployment Architecture]]
- [[_COMMUNITY_Legacy Frontend Architecture|Legacy Frontend Architecture]]
- [[_COMMUNITY_Resident Invitation Flows|Resident Invitation Flows]]
- [[_COMMUNITY_Invitation Redemption Service|Invitation Redemption Service]]
- [[_COMMUNITY_Access Request Flow|Access Request Flow]]
- [[_COMMUNITY_UI Design System|UI Design System]]
- [[_COMMUNITY_Lint Configuration|Lint Configuration]]
- [[_COMMUNITY_Resident Service Flows|Resident Service Flows]]
- [[_COMMUNITY_Amenity Reports|Amenity Reports]]
- [[_COMMUNITY_Cross-Tab Zustand|Cross-Tab Zustand]]
- [[_COMMUNITY_Community Map Assets|Community Map Assets]]
- [[_COMMUNITY_Amenity App State|Amenity App State]]
- [[_COMMUNITY_Onboarding UI|Onboarding UI]]
- [[_COMMUNITY_Hero Artwork|Hero Artwork]]
- [[_COMMUNITY_Complaint State|Complaint State]]
- [[_COMMUNITY_Department State|Department State]]
- [[_COMMUNITY_Notice State|Notice State]]
- [[_COMMUNITY_Backend App Init|Backend App Init]]
- [[_COMMUNITY_Core Init|Core Init]]
- [[_COMMUNITY_Domain Init|Domain Init]]
- [[_COMMUNITY_Repository Init|Repository Init]]
- [[_COMMUNITY_Router Init|Router Init]]
- [[_COMMUNITY_Service Init|Service Init]]
- [[_COMMUNITY_API v1 Init|API v1 Init]]
- [[_COMMUNITY_React Asset|React Asset]]
- [[_COMMUNITY_Vite Asset|Vite Asset]]
- [[_COMMUNITY_Booking Validation|Booking Validation]]
- [[_COMMUNITY_Vite Template Docs|Vite Template Docs]]
- [[_COMMUNITY_Backend Package|Backend Package]]
- [[_COMMUNITY_Favicon Asset|Favicon Asset]]
- [[_COMMUNITY_Bluesky Icon|Bluesky Icon]]
- [[_COMMUNITY_Discord Icon|Discord Icon]]
- [[_COMMUNITY_Documentation Icon|Documentation Icon]]
- [[_COMMUNITY_GitHub Icon|GitHub Icon]]
- [[_COMMUNITY_SVG Icon Sprite|SVG Icon Sprite]]
- [[_COMMUNITY_Social Icon|Social Icon]]
- [[_COMMUNITY_X Icon|X Icon]]
- [[_COMMUNITY_Staff Security Hierarchy|Staff Security Hierarchy]]

## God Nodes (most connected - your core abstractions)
1. `useApp()` - 49 edges
2. `Role` - 46 edges
3. `Principal` - 39 edges
4. `Session` - 32 edges
5. `genId()` - 24 edges
6. `useAuthStore` - 24 edges
7. `Profile` - 20 edges
8. `AuthenticationError` - 19 edges
9. `CreateInvitationRequest` - 19 edges
10. `InvitationCreated` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Mock Data and Zustand Boundary` --semantically_similar_to--> `Zustand Browser-Persisted Domain State`  [INFERRED] [semantically similar]
  docs/AGENTS.md → AGENTS.md
- `Separate Resident and Admin Portals` --semantically_similar_to--> `Role-Gated Resident and Admin Dashboards`  [INFERRED] [semantically similar]
  docs/AGENTS.md → AGENTS.md
- `Separate Role-Based Portals` --semantically_similar_to--> `Role-Gated Resident and Admin Dashboards`  [INFERRED] [semantically similar]
  README.md → AGENTS.md
- `Frontend-Only Browser-Persisted Demo` --semantically_similar_to--> `Zustand Browser-Persisted Domain State`  [INFERRED] [semantically similar]
  README.md → AGENTS.md
- `Resident and Admin Dashboard Review Flows` --semantically_similar_to--> `Role-Gated Resident and Admin Dashboards`  [INFERRED] [semantically similar]
  implemented_flows.md → AGENTS.md

## Import Cycles
- 1-file cycle: `backend/app/main.py -> backend/app/main.py`
- 1-file cycle: `backend/app/services/invitation_service.py -> backend/app/services/invitation_service.py`
- 1-file cycle: `backend/app/core/exceptions.py -> backend/app/core/exceptions.py`
- 1-file cycle: `backend/app/repositories/invitations_repository.py -> backend/app/repositories/invitations_repository.py`
- 3-file cycle: `frontend/src/store/appStore.js -> frontend/src/store/slices/createAmenitiesSlice.js -> frontend/src/store/authStore.js -> frontend/src/store/appStore.js`
- 3-file cycle: `frontend/src/store/appStore.js -> frontend/src/store/slices/createComplaintsSlice.js -> frontend/src/store/authStore.js -> frontend/src/store/appStore.js`
- 3-file cycle: `frontend/src/store/appStore.js -> frontend/src/store/slices/createVisitorsSlice.js -> frontend/src/store/authStore.js -> frontend/src/store/appStore.js`

## Hyperedges (group relationships)
- **Persisted Cross-Tab Frontend State Pattern** — agents_zustand_browser_state, agents_cross_tab_rehydration, docs_claude_zustand_browser_persistence, readme_frontend_only_demo [INFERRED 0.95]
- **Supabase RBAC Enforcement Pattern** — docs_plan_defense_in_depth_rbac, docs_plan_access_token_hook, backend_readme_defense_in_depth_rbac, backend_readme_trust_scoped_supabase_clients [INFERRED 0.95]
- **Resident Onboarding Flow Variants** — implemented_flows_access_request_registration, implemented_flows_admin_registration_review, implemented_flows_admin_resident_invitation, implemented_flows_invite_link_join, implemented_flows_invite_code_join [INFERRED 0.85]
- **Layered Structure** — assets_hero_upper_layer, assets_hero_lower_layer, assets_hero_vertical_connection [EXTRACTED 1.00]
- **Residential Community Layout** — assets_onboarding_map_apartment_buildings, assets_onboarding_map_internal_road_network, assets_onboarding_map_landscaped_park, assets_onboarding_map_water_feature [EXTRACTED 1.00]

## Communities (78 total, 24 thin omitted)

### Community 0 - "Amenity Management"
Cohesion: 0.06
Nodes (41): AmenityCard(), currencyFormatter, AmenityFormField(), AmenityFormModal(), AmenityHeader(), AmenityImagePicker(), AmenityStatusToggle(), AmenityTabs() (+33 more)

### Community 1 - "Booking Approvals"
Cohesion: 0.07
Nodes (44): ApprovalFilters(), ApprovalRow(), formatBookingDate(), formatCurrency(), formatRequestedOn(), ApprovalStatusBadge(), STATUS_CLASSES, ApprovalTable() (+36 more)

### Community 2 - "Admin Dashboard Management"
Cohesion: 0.08
Nodes (31): AdminHome(), Admins(), Complaints(), CreateDepartment(), emptyStaff(), ROLES, Maintenance(), Notices() (+23 more)

### Community 3 - "Booking Persistence"
Cohesion: 0.09
Nodes (40): DEFAULT_REPORT_FILTERS, isCancelledBooking(), BOOKING_TIMELINE_STATE, cloneBookings(), getLocalStorage(), isCurrentBookingCollection(), loadAmenityBookings(), persistBookings() (+32 more)

### Community 4 - "Invitation API"
Cohesion: 0.15
Nodes (40): Client, CreateInvitationRequest, InvitationCreated, Principal, RedeemRequest, Session, Principal, Any (+32 more)

### Community 5 - "Amenities Persistence"
Cohesion: 0.15
Nodes (29): amenitiesManagementMock, cloneAmenities(), getLocalStorage(), loadAmenities(), persistAmenities(), saveAmenities(), cloneAmenity(), createAmenity() (+21 more)

### Community 6 - "Backend Configuration"
Cohesion: 0.09
Nodes (28): get_settings(), Application configuration.  Settings are read once from the environment (or a lo, Typed, environment-driven application settings., CORS origins parsed from the comma-separated env value., True when running with production configuration., Return the cached settings instance., Settings, create_app() (+20 more)

### Community 7 - "Authentication API"
Cohesion: 0.16
Nodes (31): Client, Principal, Profile, Session, BaseModel, MessageResponse, OtpRequest, OtpVerifyRequest (+23 more)

### Community 8 - "Amenity Ledger Persistence"
Cohesion: 0.17
Nodes (23): EMPTY_LEDGER_SUMMARY, cloneTransactions(), getLocalStorage(), isValidLedger(), loadAmenityLedger(), persistTransactions(), saveAmenityLedger(), deductDamageCharges() (+15 more)

### Community 9 - "API Authentication Dependencies"
Cohesion: 0.12
Nodes (26): _extract_token(), get_current_user(), get_request_client(), Shared FastAPI dependencies for authentication and authorization.  These wrap th, Resolve and verify the caller from the ``Authorization`` header., Return a Supabase client scoped to the caller's token (RLS enforced).      Use t, Build a dependency that admits only callers satisfying one of ``roles``.      Ro, require_role() (+18 more)

### Community 10 - "Backend Errors and Auth"
Cohesion: 0.11
Nodes (23): FastAPI, Any, Client, Principal, Profile, Session, AppError, Application error hierarchy and FastAPI exception handlers.  Services raise thes (+15 more)

### Community 11 - "Frontend Dependencies"
Cohesion: 0.08
Nodes (23): dependencies, lucide-react, react, react-dom, react-router-dom, tailwindcss, @tailwindcss/vite, zustand (+15 more)

### Community 12 - "Onboarding Admin Profile"
Cohesion: 0.17
Nodes (16): defaultEnabledModules, onboardingModules, createEmptyAdminProfile(), createInitialAdminProfileState(), createOnboardingAdminProfileSlice(), editableProfileFields, normalizeAdminProfile(), createInitialCompletionState() (+8 more)

### Community 13 - "Community Onboarding"
Cohesion: 0.16
Nodes (10): COMMUNITY_TYPES, ONBOARDING_CONFIG, ONBOARDING_STEPS, InstructionPanel(), LOCATION_STATUS, LocationList(), MapCard(), MapMarker() (+2 more)

### Community 14 - "Amenity Booking Forms"
Cohesion: 0.17
Nodes (11): BookingFormModal(), createInitialValues(), FormSection(), ChargeOverride(), GuestList(), CreateBookingModal(), InternalNotes(), ResidentSearch() (+3 more)

### Community 15 - "Amenity Time Blocking"
Cohesion: 0.20
Nodes (10): BlockTimeDetails(), BlockTimeModal(), getInitialBlockTime(), minutesToTime(), timeToMinutes(), validateBlockedSlot(), ConfirmationFooter(), ModalFooter() (+2 more)

### Community 16 - "Ledger Financial Actions"
Cohesion: 0.24
Nodes (10): ConfirmationDialog(), DamageDeductionModal(), FinancialSummary(), ForceCancelDialog(), LedgerSummaryCard(), RefundModal(), AmenityLedgerPage(), useAmenityLedgerStore (+2 more)

### Community 17 - "RBAC Role Model"
Cohesion: 0.17
Nodes (14): effective_roles(), Role definitions and the RBAC hierarchy.  The five roles mirror the ``user_role`, Return every role ``role`` satisfies, including itself., Return True if ``user_role`` meets the ``required`` role.      An admin satisfie, Return True if ``user_role`` satisfies at least one of ``required``., role_satisfies(), satisfies_any(), Enum (+6 more)

### Community 18 - "User Login Flow"
Cohesion: 0.31
Nodes (8): AuthCard(), PhoneNumberField(), LoginPage(), OtpVerificationPage(), AuthFlowRoute(), AUTH_ROUTES, AUTH_FLOW_STATE, useAuthStore

### Community 19 - "Amenity Booking Data"
Cohesion: 0.18
Nodes (7): amenityBookingsMock, today, amenityLedgerMock, today, initialVisitors, shortTime(), todayISO()

### Community 20 - "Invitation Repository"
Cohesion: 0.22
Nodes (13): Client, datetime, Role, find_by_code_hash(), find_by_token_hash(), _find_one(), insert_invitation(), mark_redeemed() (+5 more)

### Community 21 - "Admin Authentication"
Cohesion: 0.29
Nodes (9): registeredAdmins, demoAuthAccounts, findRegisteredAdmin(), verifyAdminOtp(), ADMIN_REGISTRATION_STATUS, initialAdminAuthState, isValidMobileNumber(), normalizePhoneNumber() (+1 more)

### Community 22 - "Association Registration"
Cohesion: 0.24
Nodes (9): AssociationRegistrationPage(), communityTypeOptions, CommunityUnitInput(), SegmentedToggle(), canAddBlock(), canAddVilla(), createNextBlock(), createNextVilla() (+1 more)

### Community 23 - "Profile Repository"
Cohesion: 0.27
Nodes (12): Client, Profile, Role, NotFoundError, A requested resource does not exist., get_profile(), Data access for the ``profiles`` table.  Reads use a caller-scoped client so Row, Fetch a single profile by user id.      Args:         client: A Supabase client (+4 more)

### Community 24 - "Ledger Actions"
Cohesion: 0.21
Nodes (9): FORCE_CANCEL_REASONS, LEDGER_ACTION, LEDGER_FILTERS, PAYMENT_STATUS, PAYMENT_STATUS_LABELS, ACTION_META, LedgerActionsMenu(), LedgerFilters() (+1 more)

### Community 25 - "Legacy Invite Redemption"
Cohesion: 0.21
Nodes (8): initialInvitations, applyRedeem(), inviteError, again, r, t1, t2, createInvitationsSlice()

### Community 26 - "Payments and Pending Requests"
Cohesion: 0.22
Nodes (7): initialPayments, initialPendingRequests, createPaymentsSlice(), createPendingRequestsSlice(), createToastsSlice(), createUiSlice(), createVisitorsSlice()

### Community 27 - "Onboarding Completion"
Cohesion: 0.27
Nodes (10): FeatureConfigurationPage(), MapConfigurationPage(), OtpInput(), OnboardingOtpPage(), OnboardingSuccessPage(), OnboardingFlowRoute(), ASSOCIATION_CREATION_STATUS, useAppStore (+2 more)

### Community 28 - "Admin Profile"
Cohesion: 0.29
Nodes (7): AdminProfilePage(), getInputClassName(), adminDesignations, ProfileImageUploader(), SectionCard(), getProfileInitials(), validateAdminProfile()

### Community 29 - "User and Association Seeds"
Cohesion: 0.26
Nodes (6): initialUsers, genId(), createAssociationRegistration(), createActivitiesSlice(), seedActivities, createUsersSlice()

### Community 30 - "Backend Auth Architecture"
Cohesion: 0.22
Nodes (11): Admin-Initiated Invitation Registration, Defense-in-Depth RBAC Enforcement, SMS OTP Existing-Member Login, Supabase Access-Token Role Hook, Custom Phone Invitation Token and Code Carrier, JWT Claims, Postgres RLS, and FastAPI RBAC, FastAPI and Supabase Backend Target, Phased Backend Delivery Plan (+3 more)

### Community 31 - "Booking Status and Ledger Table"
Cohesion: 0.25
Nodes (7): BookingStatusBadge(), STATUS_CLASSES, LedgerRow(), LedgerTable(), TABLE_COLUMNS, PaymentStatusBadge(), TABLE_COLUMNS

### Community 32 - "Ledger Audit Detail"
Cohesion: 0.24
Nodes (4): getBookingTypeLabel(), AuditTimeline(), TransactionDetailsPanel(), TransactionHistory()

### Community 33 - "Invitation Tests"
Cohesion: 0.25
Nodes (7): _invite(), Unit tests for the pure invite-redemption decision and token hashing., test_expired_invite_is_expired(), test_missing_invite_is_invalid(), test_naive_expiry_is_treated_as_utc(), test_redeemed_invite_is_used(), test_valid_invite_returns_none()

### Community 34 - "Amenity Timeline Workflows"
Cohesion: 0.44
Nodes (6): TimelineActions(), useAmenityBookingWorkflow(), useBookingTimelineSelection(), longDate(), AmenityDashboardPage(), useAmenityBookingsStore

### Community 35 - "Workspace Scripts"
Cohesion: 0.20
Nodes (9): name, private, scripts, build, dev, lint, preview, version (+1 more)

### Community 36 - "Deployment Architecture"
Cohesion: 0.25
Nodes (9): FastAPI Service over Supabase, Single Supabase Client Construction Boundary, Trust-Scoped Supabase Clients, Single Supabase Access Boundary, Trust-Scoped Server-Side Supabase Clients, HomeBandhu HTML Application Bootstrap, Frontend-Only Browser-Persisted Demo, HomeBandhu Application (+1 more)

### Community 37 - "Legacy Frontend Architecture"
Cohesion: 0.29
Nodes (8): HomeBandhu Frontend Architecture, Role-Gated Resident and Admin Dashboards, Simulated Phone OTP Authentication, Current HomeBandhu Frontend Architecture, Role-Gated Parallel Layout Shells, Duplicated Role Layout Shells, Architecture Documentation Update Request, Resident and Admin Dashboard Review Flows

### Community 38 - "Resident Invitation Flows"
Cohesion: 0.32
Nodes (8): Single-Use Resident Invite Onboarding, Invite Token and Code Redemption, Simulated OTP Login, Admin Resident Invitation Flow, HomeBandhu Implemented User Flows, Invite Code Join Flow, Invite Link Join Flow, Public OTP Login Flow

### Community 39 - "Invitation Redemption Service"
Cohesion: 0.39
Nodes (7): datetime, evaluate_invitation(), _parse_dt(), Invitation service: admin-initiated resident registration.  Two entry points:  `, Redeem an invite via link token or typed code and return a session., Return a rejection reason for ``invite``, or None if it is redeemable.      Reas, redeem()

### Community 40 - "Access Request Flow"
Cohesion: 0.29
Nodes (7): Backend-Ready Frontend Design, Legacy Frontend Prototype Guidance, Mock Data and Zustand Boundary, Admin Approval for Resident Registration, Separate Resident and Admin Portals, Public Access Request Registration Flow, Admin Pending Registration Review Flow

### Community 41 - "UI Design System"
Cohesion: 0.29
Nodes (7): Graduated Corner-Radius Scale, Indigo Brand and Semantic Color System, Reusable Component Patterns, Soft Quiet SaaS Visual Language, Standard Toast and Activity Action Feedback, Micro-Label and Value Typography Hierarchy, HomeBandhu Visual Design System

### Community 42 - "Lint Configuration"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 43 - "Resident Service Flows"
Cohesion: 0.33
Nodes (6): Admin Complaint Update Flow, Admin Management Action Flows, Resident Amenity Booking Flow, Resident Complaint Submission Flow, Resident Maintenance Payment Flow, Resident Service Action Flows

### Community 44 - "Amenity Reports"
Cohesion: 0.47
Nodes (4): AmenityReportsPage(), KpiCard(), ReportTable(), useAmenityReportsStore

### Community 45 - "Cross-Tab Zustand"
Cohesion: 0.50
Nodes (5): Cross-Tab Storage Rehydration, Global Toast and Activity Feedback, Zustand Browser-Persisted Domain State, Toast and Activity Feed Side Effects, Zustand Persistence and Cross-Tab Synchronization

### Community 46 - "Community Map Assets"
Cohesion: 0.40
Nodes (5): Apartment Buildings, Internal Road Network, Landscaped Park, Residential Community Aerial Map, Water Feature

### Community 47 - "Amenity App State"
Cohesion: 0.60
Nodes (3): initialAmenities, initialBookings, createAmenitiesSlice()

### Community 48 - "Onboarding UI"
Cohesion: 0.50
Nodes (3): FeatureModuleCard(), MODULE_ICONS, ToggleSwitch()

### Community 49 - "Hero Artwork"
Cohesion: 0.83
Nodes (4): Layered Platform Illustration, Lower Purple Layer, Upper Outlined Layer, Vertical Dashed Connection

## Ambiguous Edges - Review These
- `Frontend-Only Browser-Persisted Demo` → `FastAPI Service over Supabase`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to
- `Current HomeBandhu Frontend Architecture` → `FastAPI and Supabase Backend Target`  [AMBIGUOUS]
  docs/CLAUDE.md · relation: conceptually_related_to
- `JWT Claims, Postgres RLS, and FastAPI RBAC` → `Resident to Committee to Admin Hierarchy`  [AMBIGUOUS]
  roles.md · relation: conceptually_related_to

## Knowledge Gaps
- **87 isolated node(s):** `Logger`, `homebandhu-backend`, `$schema`, `plugins`, `react/rules-of-hooks` (+82 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Frontend-Only Browser-Persisted Demo` and `FastAPI Service over Supabase`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Current HomeBandhu Frontend Architecture` and `FastAPI and Supabase Backend Target`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `JWT Claims, Postgres RLS, and FastAPI RBAC` and `Resident to Committee to Admin Hierarchy`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `genId()` connect `User and Association Seeds` to `Booking Persistence`, `Amenities Persistence`, `Amenity Ledger Persistence`, `Amenity Booking Forms`, `Amenity App State`, `Complaint State`, `Department State`, `Notice State`, `Amenity Booking Data`, `Legacy Invite Redemption`, `Payments and Pending Requests`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `Role` connect `Invitation API` to `Invitation Redemption Service`, `Authentication API`, `API Authentication Dependencies`, `RBAC Role Model`, `Invitation Repository`, `Profile Repository`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `AmenityFormField()` connect `Amenity Management` to `Ledger Financial Actions`, `Booking Approvals`, `Amenity Booking Forms`, `Amenity Time Blocking`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Are the 38 inferred relationships involving `Role` (e.g. with `Client` and `Principal`) actually correct?**
  _`Role` has 38 INFERRED edges - model-reasoned connections that need verification._