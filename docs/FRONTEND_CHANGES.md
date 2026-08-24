# Frontend changes

## Scope

The frontend is now a same-origin React client for the FastAPI API. It does not
import a Supabase SDK, retain provider credentials, or treat browser storage as
tenant data. The selected authentication mechanism and all authorization
decisions are resolved by the backend.

## Authentication and registration

`src/lib/api/client.js` is the one HTTP boundary. It sends cookies with every
request, attaches the readable CSRF cookie to unsafe methods, and performs one
refresh attempt after an unauthorized response. `src/lib/auth/authService.js`
and `src/store/authStore.js` use that boundary to:

- fetch the server session;
- start configured OAuth at `/api/v1/auth/oauth/{provider}/start` (with a
  Google compatibility alias), submit email/password credentials to the BFF,
  and complete explicit email-confirmation/password-recovery actions;
- carry the sign-in card's **Remember me** answer — off by default — on
  whichever method the user picked: `?remember=true` on the OAuth start, and
  `remember_me` in the sign-in body. Left off, the backend gives the session a
  browser-session refresh cookie, so the login page is there again next time
  rather than the user being signed straight back in (API.md § 1.2);
- complete the callback by re-reading the server session;
- redeem a previously prepared invitation; and
- clear the client session after backend logout.

Phone OTP, resident-local login, and direct Supabase authentication remain
removed. `AuthEntryPage`, `RegistrationPage`, and
the registration feature provide the supported entry points: Google sign-in,
email/password backup, create-community onboarding, community search, join
requests, and invitation redemption. When a `VITE_TURNSTILE_SITE_KEY` is
configured, the small Turnstile component passes its token through the BFF to
Supabase; it does not retain or validate the token locally.

The Join Community tab debounces its database search, cancels stale requests,
shows explicit empty/pending/rejected states, and lets applicants provide an
optional E.164 phone number through separate country-code and local-number
controls. The country code defaults to `+91` and can be changed before submit.

## Dashboard data flow

`src/components/dashboard/DashboardDataBootstrap.jsx` is mounted inside
`AdminLayout.jsx`. After the admin route guard resolves it performs this sequence:

1. It calls `GET /api/v1/dashboard/snapshot`.
2. It writes the returned projection into `useAppStore` with
   `hydrateDashboard`.
3. It opens an `EventSource` to `GET /api/v1/events`.
4. On `dashboard.refresh`, it debounces another snapshot request and dispatches
   `homebandhu:dashboard-refresh` so feature views can reload derived data.
5. On leaving the admin layout, including logout, it closes the stream and calls
   `clearDashboard`; no tenant data survives in local storage.

`src/lib/dashboard/dashboardApi.js` isolates the snapshot and SSE protocol,
which keeps future transport changes out of dashboard views. `src/store/appStore.js`
is deliberately a render cache: its domain collections begin empty and only
the snapshot hydrator supplies records.

The snapshot contains normalized UI records for users, complaints, visitors,
amenities, bookings, invoices/payments, notices, departments, and activity.
Other portals use their own route-specific queries and snapshots; they never
hydrate this admin projection.

## Amenity management

`src/features/amenities/services/amenitiesService.js` reads current amenities
from the snapshot and sends administrator/manager mutations to the dashboard
API. The service maps the existing form model to the API DTO, so pages and form
components did not need duplicate request logic. Each successful mutation is
subsequently reflected by the SSE-triggered snapshot refresh.

Booking reads use the same snapshot protocol. Their local cache is only a
short-lived derived view while a page is open; it is not persisted. Financial
ledger UI keeps no seeded transactions or browser persistence. Booking and
ledger mutation endpoints remain a follow-up integration boundary and must not
be represented as durable client-only records.

## Worker portal

- `src/layouts/WorkerLayout.jsx` shows the marketplace registration screen only
  when the provider profile is incomplete **and** the caller holds no active
  engagement ranked `manager` or `supervisor` (`holdsLeadershipEngagement` in
  `src/lib/staffVocabulary.js`, reading `communities[].rank` from
  `GET /worker/snapshot`). Department leadership never registers — an
  administrator creates them by email — so the form asked them for coordinates
  and trades that nothing would ever match them on, and blocked their own
  Complaints screen behind it. Technicians (`member`) and unregistered
  marketplace professionals keep the gate unchanged. Four screens that edit or
  read the `service_providers` row — Profile, Settings, Availability, and the
  marketplace half of Communities — now say plainly that there is no marketplace
  profile instead of erroring, 404-ing on save, or, in Settings' case, holding a
  "Loading settings…" spinner that never resolved.

- `src/features/departments/components/PendingInvitations.jsx` renders
  `blockedReason` when the API supplies one. The two leadership rulings of
  2026-08-21 — leadership is never a marketplace provider, and is held in one
  community at a time — are refused at *claim* time, inside a session read with
  nobody watching a screen, so this list is the only place the answer surfaces.
  Without it the row said "waiting for first sign-in", which after a blocked
  claim is false: they signed in and were turned away. The sentence comes from
  the database rather than being reconstructed here, so it names which rule
  refused them. The row stays `pending` and both existing verbs — correct the
  address, withdraw the invitation — are still offered, because the situation is
  not terminal.

- **The supervisor's work-order queue is mounted in the worker portal**
  (`src/App.jsx`, `src/pages/WorkerDashboard/WorkOrders.jsx`,
  `src/layouts/WorkerLayout.jsx`; product ruling, 2026-08-21 — *"the supervisor
  is the channel through whom the worker gets the job"*). `WORK_ORDER_ROUTES`
  was mounted under `/admin`, `/manager` and `/security-manager` and never under
  `/worker`, which is where `_portal_for` sends every supervisor of a
  non-security department: their whole workspace was one complaint list. Two
  routes now serve them — `/worker/work-orders`, which is what the nav item can
  link to before a snapshot has loaded, and
  `/worker/departments/:departmentId/work-orders`, the shape every other portal
  uses — and both render **the same `AdminDashboard/WorkOrderTriage`**, not a
  copy. No permission changed: every one of the nine work-order endpoints
  already admitted a `worker` membership at the router and narrows to
  `can_supervise_department` in Postgres
  (`backend/tests/api/test_work_orders.py::test_api_337`).
- The rank and the department both come from `GET /worker/snapshot`'s
  `communities[]`, which already carries `rank`, `status` and `departmentId` —
  nothing on the session carries a rank, and a supervisor's department is their
  roster row's rather than their membership's. `supervisedEngagement` moved out
  of `WorkerDashboard/Complaints.jsx` into `src/lib/staffVocabulary.js` so the
  two screens that ask "which department do you supervise" ask it once.
- The nav entry **"Work orders"** is hidden for rank `member` and for
  marketplace professionals — the first hidden entry in this sidebar, and only
  because the layout now holds the rank the registration gate already reads.
  Anybody who deep-links either URL without an active supervisor engagement gets
  the Complaints screen's own sentence, in the same words.
- One thing the mount exposed: `GET /departments/{id}` is
  `require_admin_or_manager`, so a supervisor cannot make the read that supplies
  the triage screen's trade list. It is context rather than the screen's
  subject — the assign box's roster comes from `GET /work-orders/{id}/candidates`,
  which does admit them — so its refusal now renders as one sentence about the
  trade box instead of a bare *"You do not have permission for this community
  action."* under the queue. No portal branch: the sentence is true wherever
  that read fails.

- **Their notification links now arrive somewhere they may go.**
  `src/features/notifications/portalUrl.js` rewrites an admin-shaped
  notification url for the reader's own portal, and its table knew only
  `manager` and `security-manager` — so a supervisor, whose portal is `worker`,
  had every link handed back unrewritten and was redirected home by
  `ProtectedRoute`. The table is now per-portal: `worker` gets department
  **work-orders**, **complaints** and **messages**, and deliberately not hiring,
  staff or candidates, because `/worker` mounts no such screen and a rewrite to
  a route that does not exist fails more confusingly than one that visibly
  bounces. Manager and security-manager behaviour is unchanged.
  `portalUrl.test.js` is new — the module's only coverage was the Python mirror
  in `backend/tests/test_notification_links.py`, which compares this file's
  source text rather than running it.
- **The department root joined that list later the same day**, on the product
  owner's ruling, and it is the one rule in the table that does not point at a
  screen the portal mounts. It was left out first because a worker's base is a
  jobs dashboard rather than a department overview — true of the screens, and
  the wrong question: `/admin/departments/{id}` is Admin-guarded, so a
  worker-portal reader who follows it is sent to `/worker` by the guard
  regardless. The only choice on offer was between arriving there deliberately
  and arriving there via a click that appeared to do nothing. They are a live
  audience for it rather than a hypothetical one —
  `notify_department_leadership` includes supervisor-rank roster holders, and
  `staff_invitation.blocked` carries that url. The doctrine is intact: it
  forbids rewriting to a route that does not exist, and every portal's base
  exists. No migration; nothing in the database changed.

## Choosing a location

- `src/components/common/LocationPicker.jsx` replaces `LocationCoordinatesInput`
  everywhere a person is asked where something is — provider registration and
  worker settings, founder onboarding, and admin society settings. Four ways in,
  in that order of prominence: type an address and press **Search** (explicit
  submit only — the upstream, OpenStreetMap's Nominatim behind
  `GET /api/v1/geo/search`, forbids autocomplete), click or drag a pin on a
  Leaflet map with OSM tiles, use the device's location, or open the collapsed
  *Enter coordinates manually* disclosure and type the two numbers. All four
  write the same one pair of coordinates, and the first three also fill in an
  editable, optional `locationLabel` ("Andheri West, Mumbai"), which is now shown
  on hiring candidate cards and on the worker's own profile. The map lives in
  `src/components/common/LocationMap.jsx` and is loaded with `React.lazy`,
  importing Leaflet's stylesheet with it, so it ships as its own chunk
  (~151 kB JS + 15 kB CSS) that no other route pays for; a chunk that fails to
  load costs the map and nothing else.

## Taking somebody off a roster

Three changes from the 2026-08-21 product-owner rulings on removal continuity
(`COMPLAINT_ENGINE_HANDOFF.md` §15).

- **A confirmation sheet replaces two `window.prompt` calls**
  (`src/pages/AdminDashboard/DepartmentHiring.jsx`, ruling 4). The prompt asked
  for a reason and, by being the only thing in the way, doubled as the
  confirmation — so *Remove* followed by Enter took somebody off a roster having
  said nothing about what they were holding. The sheet names the person and their
  rank, states both counts the API actually returns (`openCommitmentCount` and
  the new `supervisedWorkOrderCount`, with zero said out loud rather than
  hidden), warns *"they are this department's last supervisor — the manager will
  cover the queue"* when that is true, keeps the reason field as the optional
  thing it always was, and has an explicit Cancel that writes nothing. Styled
  after `EmployeeDetail.jsx`'s `ApproveModal`, the only modal precedent on this
  surface. The three-state button logic is untouched — pending departure opens
  the handover, booked items start one, otherwise Remove — because the sheet is a
  confirm layer and not a redesign of when each verb is offered.

- **The manager's Complaints screen says when the queue is theirs**
  (`src/pages/ManagerDashboard/Complaints.jsx`, ruling 3). While the department
  has no active supervisor: *"You're covering this department's complaint queue
  until a new supervisor is invited."* The database sends a
  `department.supervision_uncovered` notification at the moment the last
  supervisor is removed; a notification is a moment and this is the standing
  fact, so it stays up for exactly as long as it is true. The zero-supervisor
  answer comes from `department.staff`, which `useManagerDepartment` already
  loads for every screen in this portal — no second read, and no way for the
  banner and the roster to disagree. **No new workspace sits behind it**:
  `can_manage_department` implies `can_supervise_department`, so this screen is
  already a strict superset of the supervisor's.

- **The admin "Assign to staff" dropdown is gone**
  (`src/pages/AdminDashboard/DepartmentDetail.jsx`, ruling 6 — this executes
  R13). It wrote `assigneeStaffId` into zustand and nowhere else: no server saw
  it, no worker was told, and the roster panel beside it counted those local
  writes back as *"N active"*, a number the browser invented that did not survive
  a reload. A control that assigns nobody, next to a count that measures nothing,
  reads as the feature being present. Replaced by the link R13 named — **Raise
  work order**, deep-linked to the triage screen with `?complaint=…` — which is
  the assignment that exists. The invented count went with it; the real numbers a
  roster row carries are on the hiring screen and come from the database.

- **`activeAssignmentCount` is gone from every roster surface** (ruling 5). It
  counted open complaints by two columns nothing writes, so it rendered as "0
  open complaints" on every row of every roster, forever. `DepartmentHiring.jsx`
  and `EmployeeDetail.jsx` now show `supervisedWorkOrderCount` instead, and only
  for the leadership rows it means anything for.

## Following a complaint notification to the row

Product ruling, 2026-08-21: a `?complaint=` deep link must highlight the
complaint it names on **both** the worker (supervisor) and the admin complaints
screens. The resident screen is deliberately left alone while that portal is
still a dummy-data demo (`docs/potential issues/09-…`).

- **`src/pages/WorkerDashboard/Complaints.jsx` reads `?complaint=` and passes
  `highlightId`.** Every machine part already existed: the shared
  `features/complaints/components/DepartmentComplaintList` has taken
  `highlightId` and ringed that card since the manager's screen was built, and
  the worker screen renders that same component. It simply never passed the
  prop — so a supervisor whose link `portalUrl.js` had just started rewriting
  arrived at their own department queue and then had to find the row. Nothing
  else about the screen moved: `canMove={false}` and the roster gate are
  unchanged, and a technician still gets the same refusal sentence whether or
  not the url carries a complaint.

- **`src/pages/AdminDashboard/Complaints.jsx` reads `?complaint=` and rings the
  card.** A different surface with a different idiom — it renders the dashboard
  snapshot's `complaints` projection from the zustand store rather than the
  shared department list — so the highlight is implemented in its own terms: the
  named card takes `border-2 border-indigo-400 bg-indigo-50/40` in place of its
  usual hairline border, carries `aria-current="true"` so the mark is not
  colour-only, and is scrolled into view once the snapshot has arrived. **Marked,
  never filtered**, matching the shared list and `WorkOrderTriage`'s `?job=`: a
  queue narrowed to one card hides the rest of an inbox the reader still has to
  work. The status filter is untouched and mounts at *All*, so a linked
  complaint is on screen whatever its status. No lifecycle behaviour, mutation
  or route changed — this screen belongs to the complaint-engine owner and the
  ruling is recorded in `docs/COMPLAINT_ENGINE_HANDOFF.md` §16.

- The admin half is what `backend/tests/test_notification_links.py` measures:
  `("/admin/complaints", "complaint")` has left `IGNORED_QUERY_PARAMETERS`,
  which is an equality assertion precisely so that a screen starting to honour
  its parameter is a visible change rather than a silent improvement.
  `("/resident/complaints", "complaint")` stays on record.

## A refused complaint write no longer stays on screen

An audit rumour (2026-08-21) claimed the admin complaints screen's *Save
Changes* button wrote to the zustand store only. Verified false on 2026-08-22:
`store/slices/createComplaintsSlice.js` has sent `PATCH /complaints/{id}` and
`POST /complaints/{id}/comments` after its optimistic store write since the
portal was wired to the API, and the SSE re-snapshot
(`DashboardDataBootstrap`) replaces the optimistic copy with server truth
within a beat of every successful write.

What the audit *did* expose was the failure path: a **failed** write fires no
SSE event, so the refused state sat on the card indefinitely with only a
transient toast to contradict it.

- **`src/store/slices/createComplaintsSlice.js` now corrects the record when
  the server refuses a write.** The catch re-reads the dashboard snapshot
  (server truth); if even that read fails — the network being down is usually
  why the write failed — it restores the one affected row to the last state the
  server agreed to. Both writers (`updateComplaint`, `addComplaintComment`)
  get the same treatment and return `null` on failure. Covered by the slice's
  first test file, `createComplaintsSlice.test.js`.

## The triage screen's error line names the field

`WorkOrderTriage.jsx`'s `Failure` component rendered only `error.message`,
which for a 422 is the envelope's generic sentence ("The request could not be
validated.") — the person is left staring at six inputs with no idea which one
the server meant, which is how the hosted-drift raise failure of 2026-08-22
surfaced as an undiagnosable red line. The component now also renders the
envelope's `details` array (`field: message`, one line each) whenever the
`ApiError` carries it. `client.js` already preserved `details`; no API change.

## The supervisor lands on their department, not on an empty calendar

Added 2026-08-22, phase one of the supervisor triage dashboard. Built against
the frozen contract in `docs/plans/SUPERVISOR_TRIAGE_SPEC.md`; the product
rulings behind it are `docs/COMPLAINT_ENGINE_HANDOFF.md` §18.

**The defect this closes.** `_portal_for` sends every service person to
`/worker`, because rank is not role (`0035`) — the supervisor and the
technician they dispatch hold the same `worker` membership. So the portal's
index was `WorkerHome` for both, and `WorkerHome` is a technician's day: offers
waiting on you, what is booked today, a link to your calendar. A supervisor
holds no jobs. Their front door was three empty states and a calendar with
nothing in it.

- **`src/pages/WorkerDashboard/WorkerLanding.jsx`** is the fork and is all it
  is. It asks `supervisedEngagement` of the `communities[]` on
  `GET /worker/snapshot` — the only place the browser can learn a rank, and a
  read `WorkerLayout` has already made under the same react-query key, so the
  fork costs no request — and renders `WorkerHome` unchanged for a technician
  or a marketplace professional, `SupervisorDashboard` for a manager or a
  supervisor. `WorkerHome` itself is untouched: a branch inside it would have
  made one component answer two jobs.
- **`src/pages/WorkerDashboard/SupervisorDashboard.jsx`** is the new surface:
  four stacked sections in the order the work travels — new complaints, taken
  up by you, assigned with work pending, being worked right now — fed by one
  read, `GET /departments/{id}/triage-snapshot`, in place of the N+1 the
  work-order triage screen does today.
- **The browser never re-buckets.** The contract puts the bucketing rules in
  Postgres and they are genuinely intricate (a taken-up complaint whose job
  became engaged appears in `assignedPending` *as its work order*, not in
  `takenUp`). The page renders the four arrays as they arrive. The one
  rearrangement it makes is section 1's urgent stack, which the spec pins on
  the client deliberately: a **stable partition**, High on top, server order
  preserved inside each half, nothing moved between sections.
- **`src/lib/triageDisplay.js`** holds every display decision, none of them in
  React. Category chips take a colour from a deterministic hash of the
  lowercased, trimmed trade name over a fixed eight-colour palette — the
  `communityColor.js` idiom, so "Plumbing" is one colour on every device with
  no column, no migration and no field in any response to drift. The palette
  deliberately excludes rose and amber, which are the High and Medium priority
  tones: a category chip that came out rose would read as a priority at a
  glance. Priority is rose/amber/slate **and always carries its word**, so the
  one field a supervisor triages on is never colour-only.
- **Section 1 is complete**, including *Take up* → `POST
  /complaints/{id}/take-up`. Its refusals render on the card they belong to
  rather than in a page banner, because a 409 names whoever got there first and
  that sentence is only useful beside the complaint it is about. Reassignment
  badges — "Returned to pool", "Reopened ×N", "Moved to this department" — ride
  on fields the complaint engine already exposes.
- **Sections 2–4 render minimally this phase** — a title and a status chip
  behind honest headers and honest empty states. Elapsed time, the assignee and
  the "Inherited" badge for work re-stamped by a removal wait on product
  review; the shell ships now so the shape of the page is reviewable rather
  than described.
- **Refresh** follows the frozen rule: react-query with a 60s `staleTime`, plus
  an invalidation hung off the `homebandhu:dashboard-refresh` window event
  `DashboardDataBootstrap` dispatches after every SSE beat — the pattern
  `PendingRegistrations.jsx` set. No new SSE channel.
- **`src/features/triage/triageApi.js`** is the HTTP boundary for both calls,
  in the house shape: no state, no caching, no error translation.

**Neither endpoint is live yet.** The migration adding `taken_up_at`,
`started_at` and `supervision_inherited_at` is hand-applied by the owner; until
it lands, both calls 404 and the page renders its failure line with a retry
rather than four empty sections that would look like a quiet department. That
is why `SupervisorDashboard.test.jsx` mocks `lib/api/client` — it is the only
thing holding the page to the contract until the backend catches up. 33 new
tests across `src/lib/triageDisplay.test.js` (chip determinism, the palette's
distance from the priority tones, the urgent partition losing nothing) and
`SupervisorDashboard.test.jsx` (the fork in both directions, bucketing-free
rendering, badges, the take-up POST and its 409, the refresh event).

**One gap, recorded rather than half-solved.** Somebody who is a supervisor in
one society and a technician in another sees the supervisor surface at
`/worker`, and their own jobs are then reachable only from the calendar. That
is the same person `supervisedEngagement`'s doc comment already describes —
one roster row picked out of several — and the fix is the portal-wide
engagement switcher recorded there, not a second branch in the fork.

## The supervisor dashboard becomes a place to act, not only to look

Added 2026-08-22, phase two of the supervisor triage dashboard, built against
**Amendment 2** of `docs/plans/SUPERVISOR_TRIAGE_SPEC.md` (product rulings
A1–A4 of the same day). Phase one's page shell and section 1 are unchanged
where the amendment did not touch them.

**Five sections now, and each complaint appears exactly once.** `openRequests`
slots in third — jobs raised that nobody has committed to. The bucketing is
still entirely the server's and the browser still re-buckets nothing; what
changed is the contract underneath it. *Committed* replaced *engaged*: an
offered-but-unaccepted job is an **open request**, not an assignment (ruling
A3), because the department is still looking for somebody. *Furthest stage
wins*: a complaint with any live work order is that work order in sections 3–5
and is not also a card in 1–2. `MinimalRow` is retired — every section draws a
full card.

- **Three universal actions on every card in every section**, as icon buttons
  with `aria-label`s and visible focus rings (`triageParts.jsx::CardActions`):
  - **Eye** → `ComplaintDetailModal.jsx`. Full complaint, category/priority/
    status chips, the stage in words, the complete staff timeline, and the
    stage's own buttons repeated inside — the same nodes the card renders, not a
    second implementation of them.
  - **Chat** → `POST /complaints/{id}/chat`, then the existing `hb:chat-open`
    window event with `{ threadId }`. Work-order cards carry `complaintId`, so
    the thread is the complaint's rather than the job's.
  - **Note** → a composer posting `POST /complaints/{id}/notes`, 1–2000
    characters, pending and error states, invalidating the detail query so the
    note appears on the timeline it was written onto.
  A work order whose `complaintId` is null (the frozen DTO allows it) keeps all
  three buttons, disabled, with the reason in their `aria-label` — a card in a
  row of identical ones that silently lost its controls is harder to read than
  one that says why.
- **Stage actions.** §1 *Take up* is unchanged. §2 gains **Raise job request**,
  which deep-links to the work-order queue's existing raise form
  (`{portal}/departments/{id}/work-orders?tab=raise&complaint={id}`, ruling A6 —
  no second inline form) and **Resolved**, behind a confirm step because
  resolving cancels every unstarted job on the complaint and notifies the
  workers holding them. §3 gains **Mark as resolved**, **Raise priority** and
  **Assign**. §4 and §5 are monitor-only, and a test pins that they stay so.
- **The manual assign is labelled as what it is.** Ruling A4 made it a true
  force-assign, so the button says *Assign without asking*, the modal says the
  worker **cannot decline it** and names the ordinary offer flow as the other
  route, and the confirm reads *Assign {name} — they cannot decline*. It posts
  `{ staffAssignmentId, force: true }` to the existing assign endpoint; the
  candidate list is the same ranked `GET /work-orders/{id}/candidates` the queue
  uses, with earlier decliners shown rather than hidden, because on a forced
  assignment that is context for the decision.
- **Raise priority is one-way and says so.** At High the button stays, disabled,
  with a `title` explaining that this is the top of the scale and the level that
  arms the dispatch engine's automatic force-assign. Hiding it would have left a
  supervisor wondering whether the feature exists.
- **`ChatDock` learns a third opening shape.** `hb:chat-open` already carried
  `{ communityId }` (compose) and `{}` (mailbox); `{ threadId }` now opens that
  conversation directly and re-reads the mailbox behind it, because a thread
  created seconds ago is not in the list the dock last fetched and *Back* has to
  land somewhere that contains it.
- **The eye popup reads a different DTO from every other complaint screen**, and
  `src/lib/triageDisplay.js` is where that seam lives.
  `GET /complaints/staff/complaints/{id}` answers `to_jsonb(complaints_row)` and
  raw `complaint_events` rows: snake_case keys and **storage** vocabulary
  (`open`, `high`). `staffComplaintFields`, `timelineEntries` and
  `complaintStatusLabel` translate it — the last one carrying the backend's own
  asymmetry, where `closed` reads as `Resolved` — so no component reads a raw
  column and no database word reaches the screen. Internal notes
  (`note_added` with `internal: true`) are shown here under a lock chip; the
  resident's projection drops them, which is the whole point of them.
- **Elapsed time in §5 is a live clock**, one 60-second interval for the page
  and none at all when nothing is under way. Mount-computed would have been less
  code and wrong on the screen this is: a card that says "under way 5m" three
  hours later reads as fresh.
- **The "Inherited" badge ships** (`inheritedAt`, v1 decision 3) on §4/§5 cards —
  work re-stamped onto this supervisor when somebody left.
- **React-query hygiene is unchanged**: 60s `staleTime`, the
  `homebandhu:dashboard-refresh` listener, every mutation invalidating
  `['supervisor-triage']` (and `['staff-complaint', id]` where the timeline
  moved), and per-card pending and error state keyed off `mutation.variables` —
  which is what keeps the resolve 409 about a running job on the one card it is
  about, verbatim, exactly as the take-up 409 already was.

**New files**: `src/pages/WorkerDashboard/triageParts.jsx` (chip, section, empty,
failure, icon button, card actions, modal shell — the `JobDetailModal` shell
idiom, since this codebase has no shared `Modal`),
`ComplaintDetailModal.jsx`, `NoteComposer.jsx`, `AssignPickerModal.jsx`.
`src/features/triage/triageApi.js` gains `staffComplaintDetail`, `resolve`,
`raisePriority`, `addNote` and `openChat`; `workOrdersApi.assign` takes `force`
through unchanged.

**Only `staffComplaintDetail` exists on the running backend**, and its guard
widens with this amendment's migration; the other four calls and the snapshot's
fifth array are hand-applied with it. Until then they 404 and each card or modal
renders its failure line. 49 new tests: `SupervisorDashboard.test.jsx` (five
sections, furthest-stage rendering, the universal trio on all eight fixture
cards, the chat POST and the dock event, the note flow, the raise deep link, the
resolve confirm and its verbatim 409, the priority button at High, the honest
force-assign, monitor-only sections), `ComplaintDetailModal.test.jsx`,
`AssignPickerModal.test.jsx`, `ChatDock.test.jsx` and `triageDisplay.test.js`.

## The supervisor's chrome, and the archive of ended work

Amendment 3 of `docs/plans/SUPERVISOR_TRIAGE_SPEC.md` (2026-08-23), frontend
only: the data layer it reads existed already and nothing in it writes.

- **Leadership loses the marketplace chrome** (ruling B1). Five NAV entries in
  `WorkerLayout.jsx` — Calendar, Availability, Communities, Messages, Profile —
  gain `marketplaceOnly: true`, the mirror of the existing `supervisorOnly`
  flag, and the filter is symmetric: leadership never sees the marketplace
  items, nobody else sees the supervisor's. The discriminator is the leadership
  rank alone (`supervisedEngagement` of the snapshot the layout already
  fetches), because the model is simplified for now: supervisors and managers
  are hired from outside the marketplace and hold no provider row. The
  leadership rail reads Dashboard, Complaints, Work orders, Completed work,
  Settings.
- **Hiding the nav item is never the guard** (portal convention). `Calendar.jsx`
  was the gap — it fired `GET /worker/calendar` *and* `GET /worker/communities`
  unconditionally, and the second 404s at anybody with no provider row, the
  exact defect handoff §18 ruled against on the landing page. Both queries now
  wait on the deduplicated `['worker-snapshot']` read and stay `enabled: false`
  for leadership, who get a refusal in the page's own words. `Messages.jsx` —
  the marketplace hiring inbox, where no department ever opens a thread at
  somebody already on the payroll — gains the same refusal and points at the
  floating Messages dock, where a supervisor's conversations actually live.
  Availability, Profile, Settings and Communities already discriminated and are
  untouched.
- **The branding names the rank** (ruling B3). The two hard-coded "Service
  Partner" strings — sidebar eyebrow and header title — render the caller's
  roster rank for leadership, "Supervisor" or "Manager" via the same
  `rankLabel` every roster screen uses, read from the first active leadership
  engagement. Everybody else keeps "Service Partner".
- **Completed work, the read-only archive** (ruling B2). New page
  `src/pages/WorkerDashboard/CompletedWork.jsx` on `/worker/completed`: every
  complaint of the supervised department that ended. The read is
  `GET /departments/{id}/complaints` with **no** status parameter — it takes
  one at most and the archive wants three — and the rows with status
  `resolved`, `closed` or `cancelled` are kept client-side, ordered by
  `resolvedAt` descending with `createdAt` as the fallback key. Filter chips:
  Everything · Resolved · Closed · Cancelled. **On this screen only** the three
  end conditions are labelled distinctly — "Resolved — awaiting the resident",
  "Closed — confirmed", "Cancelled" — a deliberate, display-only departure from
  `complaintStatusLabel`'s closed→Resolved folding, kept local to the page
  because distinguishing end conditions is this screen's entire point. The one
  interaction is the eye, which opens the existing `ComplaintDetailModal` with
  a new `readOnly` prop (default false, so the dashboard's mount is
  byte-identical) that unmounts the `NoteComposer`; no `actions` node is
  passed. The full timeline, internal notes included, still renders — the
  look-back is what the screen is for. The endpoint is unpaginated and the
  notes RPC has no server-side write-freeze on ended complaints; both recorded
  as backlog in the amendment (W1, W2), not worked around.
- **Two riders in passing.** `DepartmentComplaintList.jsx`'s `STATUS_TONES`
  learns `acknowledged`, `closed` and `cancelled` (they rendered an untinted
  pill), and ended rows lose the "Not our department"/move controls — nobody
  can act on a transfer of work that is over. And the possessive marketplace
  fallbacks a supervisor could still meet (`'your community'` in
  `Complaints.jsx`, `'Your community'` in `SupervisorDashboard.jsx`) become the
  neutral "the community"; the actual community name the snapshot carries was
  already preferred.

15 new tests: `WorkerLayout.test.jsx` (the symmetric nav split in both
directions, the rank branding in both places, Service Partner kept for the
marketplace), `CompletedWork.test.jsx` (ended-only filtering with no status
parameter, the distinct labels, the end-stamp ordering, the chips, the
read-only popup with nothing writable in it, the technician refusal),
`ComplaintDetailModal.test.jsx` (`readOnly` unmounts the composer, the default
keeps it), `LeadershipScreens.test.jsx` (the Calendar and Messages refusals,
with neither marketplace read attempted).

## The open-jobs board

The product rulings of 2026-08-23 (`docs/COMPLAINT_ENGINE_HANDOFF.md` §22):
live testing found a freshly hired plumber opening their portal to nothing,
because in the model on record a worker sees only what a supervisor has
offered them. The board is the other half of that model — every unclaimed job
on the caller's department rosters, claimable on the spot, first come first
served. The frozen build spec, adjudications included, is
`docs/plans/OPEN_JOBS_BOARD_SPEC.md`.

- **A new page, `OpenJobs.jsx`, at `/worker/open-jobs`.** One read
  (`GET /worker/open-jobs`, query key `['worker-open-jobs']`) fills the grid;
  each card carries the complaint title, department and community, the trade
  chip, the urgent badge for high priority, and either the slot or a "Time to
  be set" marker — ruling C3 puts unscheduled jobs on the board rather than
  hiding exactly the job the owner raised in testing.
- **The claim is a two-step press, and the second step says what it costs.**
  Ruling C2 makes taking a job instant — no approval sits between the tap and
  the commitment — so the confirm wording carries the whole of it: the job is
  theirs immediately, and the supervisor is told. On success both
  `['worker-open-jobs']` and `['worker-snapshot']` are invalidated, because
  the job left the board and landed on the dashboard in the same moment.
- **Losing the race is the ordinary case, not the edge one.** Two technicians
  reading one board will sometimes press the same card; the server settles it
  under a row lock and answers the loser in a sentence — "Somebody has already
  taken this job." — which the card prints verbatim before the refetch takes
  the card away, because the truthful board no longer has that job on it.
- **A nav entry "Open jobs", directly after Dashboard, `marketplaceOnly`.**
  The same flag as the five marketplace entries, with the direction reversed:
  technicians and marketplace pros claim work here, and leadership *hands out*
  work from the queue — showing a supervisor a board they dispatch onto would
  be the mirror of showing a technician the dispatcher's console.
- **Two empty states, told apart by the snapshot the layout already fetched.**
  No roster rows: "Jobs appear here once a community hires you." A roster and
  nothing open: "Nothing is waiting right now." Neither is an error, and the
  page never interprets one as such.

`workerApi` gains `openJobs()` and `claimJob(id)`. 9 new tests:
`OpenJobs.test.jsx` (the C3 marker drawn from the null slot, the urgent badge,
the two-step claim and its confirm wording, backing out without claiming, the
lost-race sentence and refetch, both empty states, the read failure) and
`WorkerLayout.test.jsx` (the entry's place directly after Dashboard, plus
"Open jobs" joining the marketplace list the two symmetric-nav tests already
walk in both directions).

## The resident sets the time

Product rulings F1–F3 (2026-08-23, recorded in
`docs/COMPLAINT_ENGINE_HANDOFF.md` §23); frozen interface and the orchestrator's
adjudications in `docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`. Three surfaces
change, and the through-line is that **nobody on the staff side picks the hour
any more**.

- **The raise form stops asking "when", for everybody.**
  `AdminDashboard/WorkOrderTriage.jsx`'s `CreateForm` loses its start and end
  `datetime-local` inputs and the `halfASlot` guard that policed them, and the
  payload carries neither `scheduledStartAt` nor `scheduledEndAt` — absent, not
  null, because the server forks on presence (adjudication G1) and a null is a
  different request from an omission. The explainer under the form is now
  subject-aware, and it is the only place a supervisor learns who answers:
  a resident job says the resident picks the time and that the system books the
  first free hour after 24 hours of silence; a common-area job says nobody
  confirms it and the system books it once urgent home visits are covered. The
  old three-way sentence — the one about a slotless raise staying a draft
  nobody is notified about — is gone with the fields it described.
- **The resident's visit card asks one of two questions, and the server says
  which.** `ResidentDashboard/Complaints.jsx`'s `ProposedVisit` branches on the
  `mode` field of `GET /complaints/{id}/schedule-request`. `approve` is the
  card exactly as it was: a proposed hour, "That time works" and "It does not".
  `pick` is new: the heading becomes **"Pick a time for this visit"**, two
  required `datetime-local` inputs collect the start and the end, an end that
  is not after the start is refused in the browser before the round trip, and
  the submit posts `{ startAt, endAt }` (ISO, stamped with the browser's own
  zone) to the new `POST /complaints/{id}/schedule-time`. Under it: *"If you
  have not picked a time within 24 hours, the association books the first
  available hour."* There is **no decline** in pick-mode (ruling F3) — there is
  no proposal to send back, and silence is already answered. The discriminator
  is `mode === 'pick'` and never "the times are null", so a backend that has
  not shipped the field renders the old card rather than a form it would
  refuse. Both writes surface the server's `409` sentences verbatim on the
  card, and both refresh the same three queries: the schedule request, the
  complaint thread, and the complaint list.
- **A sixth section on the supervisor dashboard.**
  `WorkerDashboard/SupervisorDashboard.jsx` gains
  `<Section id="triage-awaiting-resident">`, **"Awaiting resident response"**,
  between "Taken up by you" and "Open job requests" — where it is in the
  journey: raised, and not yet anybody's to claim. It is fed by the snapshot's
  new `awaitingResident` array, rendered with the existing `orderCard` and
  re-bucketed by nothing (the array defaults to `[]`, because the key arrives
  with the hand-applied migration). The rows carry no verb and the eye popup
  offers one navigation action only — the deep link into the work-order queue
  at `?tab=queue&job=…` — because the answer belongs to the resident and the
  24-hour timer belongs to the engine.

`residentApi` gains `scheduleTime(complaintId, { startAt, endAt })`, and the
stale `/** Accept a slot or propose a time */` comment above `schedule` is
replaced: proposing a time was never something that call did, and now that
proposing one is real it had to stop claiming the wrong endpoint does it.
`workOrdersApi.create`'s docstring drops the old slot fork for G1's.

14 new tests: `ProposedVisit.test.jsx` (a new file — pick-mode's picker,
caption and absent decline; the ISO payload; the client-side range refusal; the
`409` verbatim; approve-mode's two buttons and absent picker; a response with
no `mode` at all; the 404 that draws nothing), `WorkOrders.test.jsx` (no
`datetime-local` anywhere on the raise form, both explainer sentences, and a
wire body asserted not to contain the two slot keys) and
`SupervisorDashboard.test.jsx` (the sixth bucket rendered with its status chip,
its place in the DOM order of the six sections, and the no-verb popup). The
work-order vocabulary needed nothing: `awaiting_resident` has read *"Waiting on
the resident"* since the day the queue shipped.

## Retired client code

The following categories were removed after an import-graph audit:

- fixture data for dashboard users, complaints, visitors, payments, amenities,
  bookings, notices, departments, administrators, and requests;
- three unused amenity `localStorage` persistence adapters;
- the unused local invitation/token/redeem slice and its self-check;
- unused default Vite image assets; and
- password/OTP/direct-Supabase authentication components and routes.

Static onboarding metadata, admin designation options, and resident FAQs remain
in `src/data` because their current components import them as application
configuration or help content rather than tenant records.

## Validation

- `npm run build` validates the production Vite bundle.
- `npm run lint` runs the configured frontend lint check.
- Runtime validation requires a signed-in member: use the browser Network panel
  to confirm a 200 snapshot request and a long-lived SSE request. A new
  community legitimately starts with empty database collections rather than
  fixture data.
