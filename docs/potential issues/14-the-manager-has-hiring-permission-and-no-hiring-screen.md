# 14 — The manager has hiring permission and no hiring screen

**Found** 2026-08-11, building the `/manager` portal · **✅ Fixed 2026-08-11, same day** ·
**Ours to fix**

| | |
|---|---|
| **Severity** | Medium. A capability that exists in the API, is deliberately granted, and cannot be used. |
| **Blast radius** | Every department manager, and every security-department manager. Nobody has one yet — `staff_provisioning` mints the first. |
| **Fix size** | Turned out to be one hook, one new page, one new endpoint and a routing fragment. No migration. |

---

## The short version

**A department manager may hire, and had no screen to hire from.**

`department_hiring.py` is guarded by `require_admin_or_manager` with
`can_manage_department` inside every RPC — that pairing exists *specifically* so a manager can run
their own department's hiring without being an administrator. All fourteen operations accept them.

The `/manager` portal shipped with Overview, Skills and Team, and **no Hiring tab**. So the
permission was real and unreachable.

## It was worse than one missing tab

Three things came out of the audit that ran before the fix, and only the first was known when this
file was written.

**1. The security-department manager had the same gap.** `_portal_for` routes a `manager` whose
department `kind` is `security` to `/security-manager`, and `SecurityLayout.jsx` carried a comment
saying so outright: *"No 'Manage Staff' entry: hiring, ranks and departures live in the admin
portal's department screens."* Same `membership_role`, same two guards, same absence.

**2. The application notification was a dead link for exactly the person it is for.**
`apply_to_department` (`0035` §7) notifies `array['admin', 'manager']` — so a manager *was* told when
a service person applied — and the link resolved to
`/admin/departments/{id}/hiring?tab=applications` (`notifications_service.py`). For a manager,
`ProtectedRoute requiredRole="Admin"` does not show a 403; it redirects to their own overview. A
click that appears to do nothing.

**3. There was no way to open a candidate at all.** Every route into the hiring surface — a candidate
tile, an application card, that notification — is about somebody **not yet on a roster**, and the
only person-detail read was `GET /departments/{id}/staff/{staffId}`, which needs a
`staff_assignments` row. The screens could list people and never open one.

**What was never true:** that any of this belonged to a *supervisor*. A supervisor holds a `worker`
membership with a `supervisor` roster rank; `require_admin_or_manager` checks the membership role and
refuses them, and `can_manage_department` does not mention rank at all. Supervisors have work-order
triage and departure handover, never hiring. Rank and role are separate axes and only role is checked
here.

## What was built

| Piece | Where |
|---|---|
| `usePortalScope()` — base path, department id, `canHire` | `frontend/src/features/hiring/usePortalScope.js` |
| `DepartmentHiring` and `EmployeeDetail` de-hardcoded | five `/admin/…` links now come from `base` |
| `CandidateDetail` — the person before they work here | `frontend/src/pages/AdminDashboard/CandidateDetail.jsx` |
| `GET /service-providers/{id}` — the read behind it | `service_providers.py`, admin-or-manager |
| `JoinRequests` — accept/reject on the dashboard | `features/hiring/components/JoinRequests.jsx` |
| `portalNotificationUrl()` — the bell's link, per reader | `features/notifications/portalUrl.js` |
| `HIRING_ROUTES` — one fragment, three mounts | `App.jsx` |

**Three details worth carrying forward.**

The routes keep the admin's `:departmentId` shape under every portal, even though a manager's
session already names their department. One shape means one implementation and no branch that only
one portal exercises — and typing somebody else's id is not a way in, because `can_manage_department`
refuses it in Postgres. That is the posture `department_hiring.py` states: *an id arriving in a URL
is never an authorization decision.*

The nav entry is gated on **`accessRole`**, not `role`. `/security-manager` is home to two different
people — the department's manager and a senior guard — who share a display label and do not share
this permission. `accessRole` is the membership role, which is the guard the API actually applies.

The candidate read is **narrower than the provider's own profile**: no coordinates, no profile id.
`service_providers_read` is `auth.uid() is not null`, so the view would have handed a home coordinate
to anybody signed in; `distanceKm` from the candidate list answers the real question, measured from
the community's own point.

## What was still not fixed — and was, on 2026-08-12

This section listed three notification links left bouncing a manager, on the grounds that rewriting
them to routes that do not exist would turn a visible failure into a confusing one. All three are
closed, and **none of them was closed by adding a rewrite rule**. Each was wrong at the source.

| Was | Now |
|---|---|
| `/admin/complaints?complaint=…` — no manager complaints screen | `complaint_department_routing` gives a complaint a department, so it goes to *that* department's manager, and `/manager/complaints` is where they land. The screen reads `?complaint=` and rings the row |
| `/admin/amenities?booking=…` — likewise | `0033` corrected: **admins only**. No department owns an amenity, so no manager should have been told |
| `/admin/security/incidents` for a non-security manager | `0040` corrected: admins and **security-department** managers, the same predicate `_portal_for` uses to hand out `/security-manager` |

The pattern is worth keeping. Two of the three looked like routing problems and were audience
problems; the third looked like a missing screen and was a missing *column* — a complaint had no
department, so there was nobody better to tell than everybody. **A link with no good destination is
often a notification with no good recipient.**

## It came back on 2026-08-12, from the other side

Worth recording, because the recurrence is more instructive than the original.

The service-professional branch replaced the hiring guard. `can_hire_for_department` gives hiring to
the department's own active manager — **by membership role or by an active `staff_assignments` row
of rank `manager`** — and admits community admins as the fallback *only while it has neither*. It is
a better rule than `can_manage_department` and it is not disputed here.

It broke both frontend gates, in opposite directions.

| | Was | Became |
|---|---|---|
| A security department's roster manager | hidden — `accessRole === 'MANAGER'`, and they hold `'security'` | **this file's exact bug**: real permission, no tab |
| An admin, on a department that has a manager | full hiring screen | applications empty (RLS), candidates `HB403` — a screen that looks broken |

**The fix is that the question stopped having a role-shaped answer**, and the frontend kept asking it
role-shaped. The same admin may hire for one department and not the next one down the list. So
`GET /departments/{id}` now carries `canHire`, computed by calling that exact function, and
`DepartmentHiring.jsx` hides the two hiring tabs and says *who* decides instead. `usePortalScope`
lost its `canHire` — which no caller ever read — and its docstring now says why no such value can
exist.

Nav items stay coarse on purpose: a supervisor can still open the hiring screen and be told it is
not theirs. That costs one click. Hiding it from somebody who *does* hold the permission costs them
the permission, which is what this file is about.

## What is still not fixed

- **A supervisor's complaint screen shows one department.** `WorkerDashboard/Complaints.jsx` picks
  the first roster row where the caller ranks supervisor or manager. Supervising two departments in
  two societies is legal and rare; a portal-wide department switcher wants `communities[]` in a
  shared context every worker page reads, which is a bigger idea than this screen.
- **`complaint_department_routing` is unapplied.** Everything through `0047` is on the hosted
  project; the four `20260812…` files are not. The routing rule is statically parsed and the
  API is repository-mocked, so nothing in this repository proves that a "Water leakage" complaint
  reaches Plumbing.

## How to confirm the original

```bash
cd backend && python scripts/frontend_api_sweep.py
```

The fourteen `department_hiring.py` operations showed as *reached* — because the **admin** screen
reached them. The sweep cannot see that one of two permitted roles has no path to them, which is
worth knowing about the sweep as much as about this gap: **reachability is not the same as
reachability by everyone who is allowed.**

## Related

- [`docs/design/STAFF_PROVISIONING_DESIGN.md`](../design/STAFF_PROVISIONING_DESIGN.md) — how a manager comes to exist at all
- [`10-api-operations-with-no-frontend-consumer.md`](10-api-operations-with-no-frontend-consumer.md) — the sibling problem, one role along
- [`12-notification-parameters-no-screen-reads.md`](12-notification-parameters-no-screen-reads.md) — the other half of the notification-link story
