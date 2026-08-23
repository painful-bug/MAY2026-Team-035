import { AUTH_ROUTES } from '../../routes/authRoutes';

/**
 * Where a notification should actually land for *this* reader.
 *
 * ## The problem
 *
 * Notification urls are written in SQL, and SQL does not know who will read
 * them. Several are addressed to `array['admin', 'manager']` — a service
 * person applied (`apply_to_department`, `0035`), somebody wants to leave
 * (`0043`, `0045`), an incident was raised (`0040`) — and every one of them
 * spells its url `/admin/…`, because when they were written the admin portal
 * was the only one with the screens.
 *
 * So a department manager has been receiving notifications whose link
 * `ProtectedRoute requiredRole="Admin"` bounces straight back to `/manager`.
 * Not a 403 page: a redirect, which reads as a click that did nothing. That is
 * the half of `docs/potential issues/14` you cannot see from the sweep, because
 * the operation *is* reached — by the admin.
 *
 * **It is not only managers** (2026-08-21). A service department's supervisor
 * holds a `worker` membership — rank is not role — so `_portal_for` sends them
 * to `/worker`, and until this date `PORTAL_BASES` did not have a `worker` key
 * at all. Every `/admin/…` link they were sent came back unrewritten and
 * bounced them home in exactly the same silent way. Two families of
 * notification reach them: the five work-order kinds keyed to
 * `work_orders.supervisor_membership_id`, and the complaint staff notices that
 * `notify_complaint_staff` widened to supervisor-rank roster holders.
 *
 * ## Why the fix is here and not in the database
 *
 * The database would have to know the reader's portal, which means the
 * notification sender re-deriving what `_portal_for` already computes — a
 * second implementation of a rule that decides where people live. `portal` is
 * on the session, computed once by the backend, and the browser already holds
 * it. Rewriting at the point of the click reuses that answer rather than
 * duplicating its derivation.
 *
 * ## What is deliberately *not* rewritten
 *
 * Only paths with a real destination under the reader's own portal. A rewrite
 * to a route that does not exist would turn a link that visibly fails into one
 * that fails confusingly, which is worse. That doctrine is why the rules below
 * are per-portal rather than one list applied to everybody: `/worker` mounts a
 * work-orders screen and no hiring, staff or candidates screen, so a worker's
 * allow-list is one entry where a manager's is four.
 *
 * `/admin/amenities?booking=…` is the one left. There is no manager amenities
 * screen and there should not be — no department owns an amenity — so `0033`
 * was corrected instead to notify admins only, and a manager no longer receives
 * it at all. The rule stays here for rows written before that.
 *
 * ## What changed on 2026-08-21
 *
 * `worker` joined `PORTAL_BASES`, and the rule table became per-portal to let
 * it in without lying about the screens that portal has:
 *
 * * department **work-orders** is rewritten — `/worker/departments/:id/
 *   work-orders` was mounted the same day, and the departure-continuity trigger
 *   re-stamps `supervisor_membership_id` on removal, so those five work-order
 *   notifications are guaranteed a live worker-portal reader.
 * * **hiring, staff and candidates are not**, because `/worker` mounts none of
 *   them. A visible bounce beats a confusing one; see above.
 * * **complaints** and **messages** are rewritten — both screens exist, and
 *   `/worker/complaints` reads `?complaint=` as of the same day, so the link
 *   lands on the row rather than merely on the queue.
 * * the **department root** is rewritten too, on the product owner's ruling
 *   later the same day. It was left out first, on the grounds that a worker's
 *   base is a jobs dashboard rather than a department overview — which
 *   describes the screens correctly and answers the wrong question. See
 *   `DEPARTMENT_ROOT_PORTALS`: the guard sends that reader to `/worker`
 *   whatever this module does, so the only choice on offer is between doing it
 *   deliberately and doing it as a click that appeared to fail.
 *
 * A rank-`member` technician also has portal `worker`, and a rewritten
 * work-orders link lands them on the triage wrapper's in-page refusal panel
 * rather than silently home — visible and self-explaining, which is the
 * improvement. This module keys on portal only: rank is not on the session, and
 * putting it there to sharpen a link rewrite would be the tail wagging the dog.
 *
 * ## What changed on 2026-08-12
 *
 * Two of the three exceptions this file used to list were closed at the source
 * rather than here, which is the better fix in both cases:
 *
 * * `/admin/complaints?complaint=…` **is** rewritten now, because
 *   `/manager/complaints` exists. `complaint_department_routing` gave a complaint a department, so the
 *   notification goes to *that* department's manager instead of all of them,
 *   and it has somewhere to land.
 * * `/admin/security/incidents` used to reach every manager in the community —
 *   a plumbing manager told about gate incidents. `0040` was corrected to
 *   notify admins and *security-department* managers, which is exactly the set
 *   `_portal_for` gives `/security-manager` to. The rewrite below is now for
 *   people who all have the screen.
 */

const PORTAL_BASES = {
  manager: AUTH_ROUTES.MANAGER_DASHBOARD,
  'security-manager': AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD,
  // The service department's supervisor, and every technician beside them:
  // `_portal_for` upgrades only a `security`-role membership by roster rank, so
  // a `worker`-role supervisor stays `worker`.
  worker: AUTH_ROUTES.WORKER_DASHBOARD,
};

const ADMIN_PREFIX = '/admin';

/**
 * The department sub-screens each portal actually mounts:
 * `/departments/{id}/hiring…`, `/staff/{id}…`, `/candidates/{id}…` or
 * `/work-orders…`.
 *
 * `work-orders` joined the manager lists on 2026-08-12, with the migration that
 * gave the seven work-order notifications a screen to land on. The route is
 * mounted under both manager bases by the same `App.jsx` fragment idiom the
 * hiring routes use, so it carries over here for exactly the reason they do —
 * and without it the reader those notifications are most for, a department
 * manager told a visit failed and was never rebooked, would have been
 * redirected home.
 *
 * **Per-portal since 2026-08-21.** One shared list was true while the only
 * readers were the two manager portals, which mount the whole hiring sub-tree.
 * `/worker` mounts `work-orders` and nothing else from this list, so it gets
 * that one entry: rewriting a supervisor's hiring link to `/worker/departments/
 * {id}/hiring` would send them to the catch-all, which is the failure this
 * module exists to prevent rather than a smaller version of it.
 */
const DEPARTMENT_SUBSCREEN = {
  manager: /^\/departments\/[^/?#]+\/(hiring|staff\/|candidates\/|work-orders)/,
  'security-manager': /^\/departments\/[^/?#]+\/(hiring|staff\/|candidates\/|work-orders)/,
  worker: /^\/departments\/[^/?#]+\/(work-orders)/,
};

/** `/departments/{id}` exactly — the admin's department screen, with no query. */
const DEPARTMENT_ROOT = /^\/departments\/[^/?#]+(?:[?#].*)?$/;

/**
 * Who may be sent to their own base in place of the admin's department screen.
 *
 * Both manager portals, because a manager's portal *is* one department and
 * their overview is that screen said differently.
 *
 * **And `worker` since 2026-08-21**, on the product owner's ruling, reversing
 * the day's earlier reading. The argument for leaving it out was that a
 * worker's base is a jobs dashboard rather than a department's roster, so the
 * substitution that is exact for a manager would be a non-sequitur. True about
 * the *screens* and beside the point about the *reader*: `/admin/departments/
 * {id}` is Admin-guarded, so a worker-portal reader who follows it is
 * redirected to `/worker` by `ProtectedRoute` regardless. The choice was never
 * between two destinations — it was between arriving at their portal home
 * deliberately and arriving there via a click that appeared to do nothing.
 * Rewriting picks the first.
 *
 * They receive such links for a real reason rather than by the blind
 * every-portal check in the Python mirror: `notify_department_leadership`
 * (`0043_staff_departures.sql` §419–436) includes supervisor-rank roster
 * holders, who hold portal `worker`, and `staff_invitation.blocked`
 * (`20260821170000`) carries `/admin/departments/{id}`.
 *
 * This is the one rule in this file that does not point at a screen the portal
 * mounts, and it does not weaken the doctrine above: the doctrine forbids
 * rewriting to a route that *does not exist*, and every portal's base exists.
 */
const DEPARTMENT_ROOT_PORTALS = new Set(['manager', 'security-manager', 'worker']);

/**
 * Who has a complaints screen.
 *
 * `manager` since 2026-08-12 and `worker` since 2026-08-21, when
 * `notify_complaint_staff` widened to supervisor-rank roster holders and
 * `/worker/complaints` was already there to receive them. Still not
 * `security-manager`: a gate department's work arrives as incidents and shift
 * entries rather than as resident complaints, so that portal has no such screen
 * and sending it a link to one is the thing this module is here to prevent.
 */
const COMPLAINTS_PORTALS = new Set(['manager', 'worker']);

export function portalNotificationUrl(url, portal) {
  if (!url || !url.startsWith(`${ADMIN_PREFIX}/`)) return url;

  const base = PORTAL_BASES[portal];
  if (!base) return url;

  const rest = url.slice(ADMIN_PREFIX.length);

  // A department sub-screen this portal mounts is mounted at the same shape it
  // has under `/admin`, so the whole path after the base carries over unchanged
  // — including the query string, which is what makes `?tab=departures`,
  // `?departure=…` and the work-order `?job=…` keep working.
  const subscreen = DEPARTMENT_SUBSCREEN[portal];
  if (subscreen && subscreen.test(rest)) return base + rest;

  // The hiring conversation, mounted under every portal in the table — the
  // worker's `/worker/messages` included, which is why this rule needed no
  // portal list of its own when `worker` was added.
  if (rest === '/messages' || rest.startsWith('/messages?')) return base + rest;

  // The admin's department screen, for the portals that have an equivalent.
  if (DEPARTMENT_ROOT_PORTALS.has(portal) && DEPARTMENT_ROOT.test(rest)) {
    return base;
  }

  // The security manager's incidents screen. Same screen, different mount.
  if (rest === '/security/incidents' && portal === 'security-manager') {
    return `${base}/incidents`;
  }

  // The department manager's — and now the supervisor's — complaints screen.
  // See `COMPLAINTS_PORTALS` for who is on that list and who is not.
  if (
    COMPLAINTS_PORTALS.has(portal)
    && (rest === '/complaints' || rest.startsWith('/complaints?'))
  ) {
    return base + rest;
  }

  return url;
}
