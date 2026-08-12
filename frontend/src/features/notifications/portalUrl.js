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
 * that fails confusingly, which is worse.
 *
 * `/admin/amenities?booking=…` is the one left. There is no manager amenities
 * screen and there should not be — no department owns an amenity — so `0033`
 * was corrected instead to notify admins only, and a manager no longer receives
 * it at all. The rule stays here for rows written before that.
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
};

const ADMIN_PREFIX = '/admin';

/**
 * `/departments/{id}/hiring…`, `/staff/{id}…`, `/candidates/{id}…` or
 * `/work-orders…`.
 *
 * `work-orders` joined the list on 2026-08-12, with the migration that gave the
 * seven work-order notifications a screen to land on. The route is mounted
 * under all three bases by the same `App.jsx` fragment idiom the hiring routes
 * use, so it carries over here for exactly the reason they do — and without
 * this line the reader those notifications are most for, a department manager
 * told a visit failed and was never rebooked, would have been redirected home.
 */
const DEPARTMENT_SUBSCREEN =
  /^\/departments\/[^/?#]+\/(hiring|staff\/|candidates\/|work-orders)/;

/** `/departments/{id}` exactly — the admin's department screen, with no query. */
const DEPARTMENT_ROOT = /^\/departments\/[^/?#]+(?:[?#].*)?$/;

export function portalNotificationUrl(url, portal) {
  if (!url || !url.startsWith(`${ADMIN_PREFIX}/`)) return url;

  const base = PORTAL_BASES[portal];
  if (!base) return url;

  const rest = url.slice(ADMIN_PREFIX.length);

  // The hiring sub-tree is mounted at the same shape under all three portals,
  // so the whole path after the base carries over unchanged — including the
  // query string, which is what makes `?tab=departures` and `?departure=…`
  // keep working.
  if (DEPARTMENT_SUBSCREEN.test(rest)) return base + rest;

  // The hiring conversation, likewise mounted under every portal.
  if (rest === '/messages' || rest.startsWith('/messages?')) return base + rest;

  // The admin's department screen has no per-portal equivalent, and does not
  // need one: a manager's whole portal *is* one department, so their overview
  // is the same destination said differently.
  if (DEPARTMENT_ROOT.test(rest)) return base;

  // The security manager's incidents screen. Same screen, different mount.
  if (rest === '/security/incidents' && portal === 'security-manager') {
    return `${base}/incidents`;
  }

  // The department manager's complaints screen. Only the plain `manager`
  // portal: `/security-manager` has no complaints screen, because a gate
  // department's work arrives as incidents and shift entries rather than as
  // resident complaints. Sending a security manager to a route that does not
  // exist is the thing this whole module is here to prevent.
  if (
    portal === 'manager'
    && (rest === '/complaints' || rest.startsWith('/complaints?'))
  ) {
    return base + rest;
  }

  return url;
}
