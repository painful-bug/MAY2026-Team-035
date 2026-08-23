// One vocabulary for department staff, replacing three lists that disagreed.
//
// Before this file, `STAFF_ROLES` existed three times:
//
//   Departments.jsx            Technician · Security Guard · Gate Officer ·
//                              Supervisor · Manager · Coordinator
//   CreateDepartment.jsx       Technician · Manager · Supervisor (page since
//                              deleted — its route was already a redirect)
//   the security manager demo   Security Guard · Gate Officer · Supervisor
//                               (that screen was replaced 2026-08-11; the
//                                roster it edited locally now lives only in
//                                the admin portal's department screens)
//
// They disagreed because they were answering two different questions with one
// list. `Manager` and `Supervisor` say where somebody sits in a department;
// `Technician`, `Security Guard`, `Gate Officer` and `Coordinator` say what they
// do. Every screen was picking whichever subset it needed, so no two agreed and
// none of them matched what the database stores.
//
// The database has kept the two apart since 0019 and 0035 settled the values:
//
//   staff_assignments.rank       text, checked against manager|supervisor|member
//   staff_assignments.job_title  text, no constraint at all
//   staff_assignments.shift      text, checked against the five below
//
// So this file has three exports, and their *kinds* differ deliberately.

/**
 * Where somebody sits. A closed set, because the database closes it.
 *
 * `member` is the stored value and "Team member" is what a person reads —
 * showing somebody the word `member` beside "Manager" and "Supervisor" reads
 * like a missing label rather than a rank.
 *
 * One manager per department is enforced by a partial unique index, not here.
 * The screen offers the option and the database refuses the second one, which
 * is the right way round: a client-side check would go stale the moment two
 * managers were promoted in different tabs.
 */
export const STAFF_RANKS = Object.freeze([
  { value: 'manager', label: 'Manager' },
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'member', label: 'Team member' },
]);

export const rankLabel = (rank) =>
  STAFF_RANKS.find((entry) => entry.value === String(rank || '').toLowerCase())?.label
  || 'Team member';

/**
 * The two ranks that are *hired into a department* rather than *found in the
 * marketplace*, and the reason they need a name of their own.
 *
 * `staff_invitations_rank_check` (20260812090200:103) admits exactly these two:
 * an administrator types a name and an email, and that person is a manager or a
 * supervisor the first time they sign in. `member` is unreachable that way — it
 * is what a registered service provider becomes when a department hires them.
 *
 * So this is the predicate for "does this person's work arrive through a
 * department". A manager or supervisor never registered, has no
 * `service_providers` row and never needs one: skills and coordinates exist for
 * distance matching, and nobody is matching distance to somebody already on the
 * payroll. The worker portal gates its marketplace registration form on this.
 */
export const LEADERSHIP_RANKS = Object.freeze(['manager', 'supervisor']);

export const isLeadershipRank = (rank) =>
  LEADERSHIP_RANKS.includes(String(rank || '').toLowerCase());

/**
 * True when any of these engagements is a live leadership posting.
 *
 * Takes the `communities[]` of `GET /worker/snapshot`, which carries one row
 * per roster the caller is on with its `rank` — the only place the session can
 * learn a rank at all, since nothing on `sessionContext` carries one.
 */
export const holdsLeadershipEngagement = (engagements) =>
  (engagements ?? []).some(
    (engagement) => engagement?.status === 'active' && isLeadershipRank(engagement?.rank),
  );

/**
 * The same question asked for its answer rather than for a yes/no: *which*
 * roster row makes this person a supervisor.
 *
 * `holdsLeadershipEngagement` is enough to decide a nav item; a screen scoped to
 * a department needs the row, because `departmentId` is on it and nowhere else
 * the browser can reach — `GET /departments` is admin-only, so a supervisor
 * cannot look their own department up.
 *
 * **The first such row, and that is a decision.** Somebody supervising two
 * departments in two societies is possible and rare, and a portal-wide
 * department switcher is a bigger idea than any one screen: it would want
 * `communities[]` in a shared context that every worker page reads. Recorded
 * here rather than half-built, and the department id stays in the URL under
 * every portal, so the second department is reachable by link the day that
 * switcher exists.
 *
 * Lives beside `isLeadershipRank` rather than in the two pages that ask, so the
 * set of ranks that may supervise is stated once. It was written twice for one
 * day — `WorkerDashboard/Complaints.jsx` had its own copy — which is the
 * three-disagreeing-lists failure at the head of this file, in miniature.
 */
export const supervisedEngagement = (engagements) =>
  (engagements ?? []).find(
    (engagement) => engagement?.status === 'active' && isLeadershipRank(engagement?.rank),
  ) || null;

/**
 * What somebody does. **Suggestions on a free-text field, not a select.**
 *
 * `job_title` is `text` with no check constraint, so a closed list here would be
 * a screen inventing a rule the database does not have — and the first society
 * with a gardener, a lift technician or a pool attendant would need a migration
 * to hire one. These are the union of what the three old lists offered, minus
 * the two that were ranks.
 */
export const JOB_TITLES = Object.freeze([
  'Technician',
  'Electrician',
  'Plumber',
  'Carpenter',
  'Housekeeping',
  'Gardener',
  'Security Guard',
  'Gate Officer',
  'Coordinator',
]);

/**
 * When somebody works. Closed, and matching `staff_assignments_shift_check`
 * exactly.
 *
 * `Full Day` is the one the security screen was missing — it has been a legal
 * value since 0035 and no screen could express it, which is a gap nobody
 * reports because it looks like a shift the society does not run.
 */
export const SHIFTS = Object.freeze([
  'Day',
  'Evening',
  'Night',
  'Full Day',
  'Rotating',
]);
