import { ALL_QUERIES } from './frameQueries.js';

// The per-portal frame → query-key maps, minus the resident one, which lives
// with `residentKeys` in `features/resident/residentEvents.js` because it is
// written in terms of them. Everything below is a portal whose keys are bare
// literals at their call sites; naming them once here is the closest thing
// those screens have to a key factory.
//
// Two rules the shape below encodes, and the reason each is a rule:
//
//   `stream.resync` is the only broad refetch. The server prepends it when a
//   reconnecting client's `Last-Event-ID` predates the prune horizon, and it
//   means "everything you show may be stale". `dashboard.refresh` is NOT that
//   frame — it fires on every row change across twelve tables — so a map that
//   wants it says so explicitly, and a map that does not (the bell, the dock)
//   ignores it rather than refetching on other people's writes.
//
//   A topic nobody named still costs a re-read of `always`, never nothing. A
//   topic added by a later backend then shows up as a slightly stale-eager
//   snapshot instead of a screen that has quietly stopped updating.

// --- Key groups, as invalidation prefixes -----------------------------------

const NOTIFICATIONS = ['notifications'];
const DM_THREADS = ['dm-threads'];
/** Prefix: catches `['dm-thread', threadId]` for every open thread. */
const DM_THREAD = ['dm-thread'];

const WORKER_SNAPSHOT = ['worker-snapshot'];
const WORKER_OPEN_JOBS = ['worker-open-jobs'];
const WORKER_CALENDAR = ['worker-calendar'];
/** Prefix: `['supervisor-triage', departmentId]`. */
const SUPERVISOR_TRIAGE = ['supervisor-triage'];
/** Prefix: `['work-orders', departmentId, 'queue' | 'department' | ...]`. */
const WORK_ORDERS = ['work-orders'];
/** Prefix: `['departments', departmentId, 'complaints' | 'staff' | ...]`. */
const DEPARTMENTS = ['departments'];
const HIRING = ['hiring'];

// --- The worker portal ------------------------------------------------------
//
// Mounted by `WorkerLayout`, so it covers the technician's dashboard, the open
// jobs board and the supervisor's triage queue at once.
//
// The open-jobs board is the highest-contention read in the app: two
// technicians reading the same board will press the same card, and the loser
// is told by the server. `work_order.changed` is community-audience, so the
// claim that took the card away arrives here — the board stops being a
// twenty-second guess about who else is looking at it.
export const WORKER_EVENT_MAP = Object.freeze({
  // The snapshot is this portal's feed: it carries the day's jobs and is what
  // an unnamed or unrecognised frame can honestly be answered with.
  always: [WORKER_SNAPSHOT],
  resync: [ALL_QUERIES],
  topics: {
    'work_order.changed': [WORKER_OPEN_JOBS, WORKER_CALENDAR, SUPERVISOR_TRIAGE, WORK_ORDERS],
    // A supervisor holds a `manager` membership often enough to be in this
    // frame's role audience, and when they are, it means a table under their
    // queue moved.
    'dashboard.refresh': [SUPERVISOR_TRIAGE],
  },
  kinds: {
    // Reassigned, resolved, escalated: the complaint leaves one section of the
    // triage queue and appears in another, and which is the server's answer.
    complaint: [SUPERVISOR_TRIAGE, DEPARTMENTS],
    work_order: [WORKER_OPEN_JOBS, WORKER_CALENDAR, SUPERVISOR_TRIAGE, WORK_ORDERS],
  },
});

// --- The department manager's portal ----------------------------------------
//
// Managers are in the `dashboard.refresh` role audience and, until this
// change, nobody in this portal was listening: an admin's write moved the
// manager's team, skills and complaint lists with no way for the screen to
// find out.
//
// `resync` is `ALL_QUERIES` rather than an enumeration. This portal's reads are
// spread across `departments`, `work-orders` and `hiring`, several of them
// keyed by ids the map cannot know, and "everything you show may be stale" is
// the literal meaning of the frame — enumerating would be a list that silently
// falls behind the screens.
export const MANAGER_EVENT_MAP = Object.freeze({
  always: [DEPARTMENTS],
  resync: [ALL_QUERIES],
  topics: {
    'dashboard.refresh': [DEPARTMENTS, WORK_ORDERS, HIRING],
    'work_order.changed': [WORK_ORDERS, DEPARTMENTS],
    'access_request.created': [HIRING],
    'access_request.decided': [HIRING],
  },
  kinds: {
    complaint: [DEPARTMENTS, WORK_ORDERS],
    work_order: [WORK_ORDERS, DEPARTMENTS],
    hiring: [HIRING],
  },
});

// --- The notification bell --------------------------------------------------
//
// Not a portal: a component that mounts in admin, resident, manager and worker
// chrome alike, which is why it carries its own map instead of relying on a
// layout's. Deliberately narrow — the bell owns exactly one read, and a bell
// that refetched on every `dashboard.refresh` would poll harder than the 60s
// interval this replaces.
export const NOTIFICATION_EVENT_MAP = Object.freeze({
  always: [],
  resync: [NOTIFICATIONS],
  topics: { 'notification.created': [NOTIFICATIONS] },
  kinds: {},
});

// --- The chat dock ----------------------------------------------------------
//
// Same reasoning as the bell, and the same narrowness. `message.created` is
// addressed to the recipient membership, so this fires for the person being
// written to and nobody else.
export const CHAT_EVENT_MAP = Object.freeze({
  always: [],
  resync: [DM_THREADS, DM_THREAD],
  topics: { 'message.created': [DM_THREADS, DM_THREAD] },
  kinds: { message: [DM_THREADS, DM_THREAD] },
});
