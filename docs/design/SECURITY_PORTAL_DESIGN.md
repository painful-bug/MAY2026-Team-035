# The security portal — design

Written 2026-08-11, when the gate finally got a frontend (task #93, PO: *"build it"*).
Companion to `API.md` §19, which documents the twenty operations this portal consumes.

## Why this document exists

The gate backend shipped in Phase 1 Step 7 and then sat unconsumed for two phases. That is not a
scheduling anecdote — it is the reason three of the decisions below had to be made at build time
rather than at design time, because an API with no consumer cannot tell you what it is missing.
The roster read in `0047` is the clearest example: the permission gap it closes had existed since
`0040` and was invisible until a form needed it.

## Route map

Two portals over one layout (`layouts/SecurityLayout.jsx`), split by `currentUser.role`.

| Route | Screen | Who |
|---|---|---|
| `/security` | `GateHome` — scan, verdict, expected visitors, offline queue | guard |
| `/security/registers` | `Registers` — `?tab=materials\|tankers` | guard |
| `/security/incidents` | `Incidents` — report + list + export | guard |
| `/security/shifts` | `Shifts` — own roster, start/end shift | guard |
| `/security/emergency` | `Emergency` — national numbers, link to incidents | guard |
| `/security-manager` | `Overview` — four fan-out metrics, today's roster, open incidents | manager |
| `/security-manager/roster` | `Roster` — `?tab=shifts\|posts` | manager |
| `/security-manager/incidents` | `ManagerIncidents` — triage | manager |
| `/security-manager/exports` | `Exports` — all four datasets | manager |
| `/security-manager/{gate,registers,emergency}` | the guard screens, reused | manager |
| `/admin/security/incidents` | `AdminSecurityIncidents` — triage | admin |

**A security manager is not a `manager` membership.** `D3` made rank and role separate axes: the
person who runs the gate roster holds a `security` membership whose `staff_assignments.rank` is
`manager` or `supervisor`. `0040`'s `gate_admin_community_for` is the predicate that decides it, and
every roster-changing call goes through it.

> **Corrected 2026-08-11.** This section previously said `gate_admin_community_for` was the *only*
> predicate that knew the rule, which was true and was the defect: `auth_service.py` derived the
> portal from a `manager` membership instead, and nothing mints one — so this whole portal was
> unreachable by any user the system can create, on the day it shipped. `_portal_for` now asks the
> same question `gate_admin_community_for` asks. See
> [`AUTH_AND_SESSION_DESIGN.md`](AUTH_AND_SESSION_DESIGN.md) §5.6.
>
> A manager is also admitted to `/security/*`, not only `/security-manager/*` — they hold a gate
> role, and two of the notifications below address a guard's URL to somebody who may by then be
> ranked manager.

## Notification URLs are routing contracts

`0040` has emitted its three since Step 7. Two of them pointed at nothing until this portal existed,
which is worth stating plainly: a notification whose `url` 404s is a defect that no test catches
and no user reports twice.

| Event | `url` | Served by |
|---|---|---|
| `shift.scheduled` (to the rostered guard) | `/security/shifts` | `Shifts` |
| high/critical incident (to admins and managers) | `/admin/security/incidents` | `AdminSecurityIncidents` |
| `visitor.checked_in` (to the resident) | `/resident/visitors` | existed already |
| `security_shift.assigned` (`0043`, to the guard a shift was handed to) | `/security/shifts?shift=` | `Shifts` — **corrected 2026-08-11**, it said `/security-manager/shifts`, which is neither a route nor the recipient's portal. `?shift=` honoured the same day; see below |
| `visitor.approved` / `.rejected` / `.cancelled` (`0032`, to the gate) | `/security` | `GateHome` — **corrected 2026-08-11**, it said `/security/visitors`, a route that has never existed |

**A notification from anywhere must name a route that exists on the day it ships**, and that is now
checked rather than asked for: `backend/tests/test_notification_links.py` parses `App.jsx`'s nested
route tree and asserts every `url` literal in every migration resolves against it. Query strings are
dropped before matching, because an ignored parameter is a missing feature and an unroutable path is
a broken link — two different defects, and the same file now answers both.

### The parameter, not just the path

Correcting `security_shift.assigned` to `/security/shifts?shift=` only got the guard to the right
screen. `Shifts` did not read `shift`, so they arrived at a fortnight of rows with nothing marking
the one they had been told about — the link works, so nothing reports it, which is the same class of
silence the path defect had.

`Shifts` now highlights the linked row and scrolls to it. **The row is often not on screen to
highlight**: a handover is driven by `0045`'s scheduled departure, whose date can be weeks out, and
the window this screen queries is a fortnight. Widening it would be worse than useless — the list is
capped at 200 rows ordered by start, so a wider range on a busy gate can truncate away the very row
being looked for. `GET /security/shifts` therefore takes a `shiftId` filter (`API.md` §19): one id,
one row, no window. The screen runs it only when the fortnight did not already contain the shift, and
pins the result above the roster saying so. An empty answer is rendered as *handed on again, or
cancelled* rather than as nothing, because a shift that moved on is a fact the guard needs.

The `(path, parameter)` pairs that no screen reads are recorded in `IGNORED_QUERY_PARAMETERS` in that
same test file and asserted by **equality**, so the list cannot grow quietly and a screen that starts
honouring its parameter has to leave it. It held five when this was written and holds **four** the
same day: `/worker/messages?conversation=` was the only other one in this workstream's code, and it
was the same defect in its cheapest form — the open thread lived in `useState`, which cannot be
linked to. The four that remain all belong to other workstreams and are written up, with the
migration line that emits each and what fixing it would take, in
[`12 — Four notification parameters that no screen reads`](../potential%20issues/12-notification-parameters-no-screen-reads.md).

## Offline operation (`US-3.5`)

`features/security/offline/` — `offlineGate.js` (pure functions + localStorage) and
`useOfflineGate.js` (the hook `GateHome` uses).

**The security property is reconcile, not the cache.** Restated here because it is the thing most
likely to be misunderstood by someone hardening this later:

* The bundle carries **hashes only**. No plaintext code exists in the database to hand out.
* The bundle is **unsigned**, and `0040` explains why signing it would be theatre — the same person
  who can edit the cached file can delete the check beside it, because both are JavaScript on their
  machine.
* Therefore an offline admission is **provisional**. `POST /security/offline-reconcile` re-runs the
  real verification server-side and writes its own verdict beside the device's claim, in
  `offline_reconcile_log`, which the community's admins can read and the submitting guard cannot.

Three consequences the UI must keep honouring:

1. **Every offline verdict is labelled provisional on screen.** The device can check a hash and a
   validity window. It cannot know how many of a four-guest party are already inside, or that the
   resident cancelled the pass after the bundle was cut.
2. **The device never returns `departed`.** That verdict needs the guest-count arithmetic over
   `visitor_events`. An offline second scan reads as another admission and reconcile decides which
   it was — which is also why replays must never be re-verified: re-verifying would check the
   visitor *out*.
3. **Rejected entries survive reconcile and stay on screen until dismissed individually.** An
   admission the server refuses is the single most important thing this mechanism can report.
   Clearing it with the accepted batch would throw it away.

Past the bundle's `expiresAt` the device **refuses to guess**: local verification switches off and
the banner tells the guard to record entries in the registers instead.

### The standing rule this overrides

`store/appStore.js`: *"Browser state is a render cache only… localStorage is deliberately never a
source of domain truth."* `public/sw.js` refuses to cache `/api/*` for the same reason.

The scan queue (`hb.security.offlineQueue.v1`) breaks that, deliberately, in one direction, for one
screen. A barrier whose network has dropped still has people standing at it, and the choice is
between recording what happened and losing it. The exception is scoped to this module and its
header says so; nothing else in the codebase should read it as precedent.

## What this portal deliberately does not do

* **No snapshot endpoint.** `API.md` §19 declined one and the Overview fans out across four list
  reads instead, each rendering independently — one failing leaves the other three on screen.
* **No guard-raised approval requests.** No endpoint exists; the gap is documented at
  `resident_visitor_passes.py:134-140`.
* **No staff management.** Hiring, ranks and departures live in the admin portal's department
  screens. The demo's local staff array here was a second copy that could disagree with the first.
* **No community contact numbers.** Nothing returns them. When community settings grow a contacts
  field, `Emergency.jsx` is where it goes.
