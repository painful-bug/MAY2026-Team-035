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
