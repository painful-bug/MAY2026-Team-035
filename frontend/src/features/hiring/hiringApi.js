import { api } from '../../lib/api/client';

// The manager's side of hiring, and the conversation both sides share.
//
// Same shape as `features/worker/workerApi.js` and
// `features/registration/registrationApi.js`: no state, no caching, no error
// translation. react-query is already mounted and owns all three.
//
// The department id is a path segment on every hiring call rather than an
// implicit "your department", because an admin manages several and the backend
// authorises against the id the resource named — never against whichever
// membership happened to be the caller's default.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

const query = (params) => {
  const pairs = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== ''
  );
  const search = new URLSearchParams(pairs).toString();
  return search ? `?${search}` : '';
};

export const hiringApi = {
  // --- negotiations ----------------------------------------------------------
  applications: (departmentId, params = {}) =>
    api(`/departments/${departmentId}/applications${query(params)}`),

  /**
   * Accept or reject one.
   *
   * `rank`, `jobTitle` and `shift` travel with the *acceptance* rather than with
   * the application, because on an application nobody has offered terms yet —
   * the manager names them at the moment they say yes. On an invitation they are
   * already in the row and this call cannot change them, which is what stops a
   * provider promoting themselves by accepting.
   */
  decide: (departmentId, applicationId, payload) =>
    post(`/departments/${departmentId}/applications/${applicationId}/decide`, payload),

  // --- finding people --------------------------------------------------------
  candidates: (departmentId, params = {}) =>
    api(`/departments/${departmentId}/candidates${query(params)}`),
  invite: (departmentId, payload) =>
    post(`/departments/${departmentId}/invitations`, payload),

  // --- the roster ------------------------------------------------------------
  /**
   * The department's roster, from the departments list rather than a read of
   * its own — there is no `GET /departments/{id}`, and the list already carries
   * `staff[]` because the demo screens were built around it.
   *
   * Not assembled out of accepted applications, which would look equivalent and
   * is not: a roster also holds names somebody typed into the department form,
   * who have no application and never will. `serviceProviderId` (0042) is what
   * tells the two apart, and it is what decides whether a row can be
   * blacklisted at all.
   */
  department: async (departmentId) => {
    const page = await api('/departments?pageSize=100');
    return (page.items || []).find((entry) => entry.id === departmentId) || null;
  },
  /** Off the roster, reapplication still open. */
  removeMember: (departmentId, staffId, reason) =>
    post(`/departments/${departmentId}/members/${staffId}/remove`, { reason: reason || null }),
  /** Barred from the whole community, not just this department. Reason required. */
  blacklist: (departmentId, payload) =>
    post(`/departments/${departmentId}/blacklist`, payload),

  // --- leaving ---------------------------------------------------------------
  /**
   * Open departures, and the settled ones behind them.
   *
   * `openCommitmentCount` on each row is the whole state machine: a pending
   * departure with a non-zero count is a handover in progress, and there is no
   * separate status for that on purpose — a status derived from a count is a
   * status that can disagree with the count.
   */
  departures: (departmentId, params = {}) =>
    api(`/departments/${departmentId}/departures${query(params)}`),
  departure: (departmentId, departureId) =>
    api(`/departments/${departmentId}/departures/${departureId}`),
  /** Start a handover for somebody who has not asked to leave. */
  openDeparture: (departmentId, payload) =>
    post(`/departments/${departmentId}/departures`, payload),
  /**
   * Move one job or shift.
   *
   * Sending no `staffAssignmentId` is the ordinary case and means *take the best
   * candidate the dispatch ranking returns* — the same ranking auto-assignment
   * uses. The screen does not pick a default, because a default here would stop
   * the handover following that ranking.
   */
  reassign: (departmentId, departureId, payload) =>
    post(`/departments/${departmentId}/departures/${departureId}/reassign`, payload),
  /**
   * Approve at a date (the requested one when `effectiveAt` is omitted, a
   * later one at the manager's discretion) or reject. Approval releases the
   * leaver's booked work from that date onward back to the dispatch pool —
   * since 2026-08-10 it is NOT refused for outstanding items.
   */
  decideDeparture: (departmentId, departureId, payload) =>
    post(`/departments/${departmentId}/departures/${departureId}/decide`, payload),
  /** Per conflicting item, who could take it. Zero candidates is an answer. */
  coverage: (departmentId, departureId) =>
    api(`/departments/${departmentId}/departures/${departureId}/coverage`),

  // --- the employee page -----------------------------------------------------
  staffMember: (departmentId, staffId) =>
    api(`/departments/${departmentId}/staff/${staffId}`),
  staffSchedule: (departmentId, staffId, params = {}) =>
    api(`/departments/${departmentId}/staff/${staffId}/schedule${query(params)}`),

  // --- the thread ------------------------------------------------------------
  conversations: (params = {}) => api(`/conversations${query(params)}`),
  conversation: (conversationId) => api(`/conversations/${conversationId}`),
  openConversation: (payload) => post('/conversations', payload),
  sendMessage: (conversationId, body) =>
    post(`/conversations/${conversationId}/messages`, { body }),
};
