import { api } from '../../lib/api/client';

// Which department owns a complaint.
//
// Same shape as `features/hiring/hiringApi.js` and `features/departments`:
// no state, no caching, no error translation. react-query owns all three.
//
// **This is a separate module from `departmentsApi` on purpose.** Its three
// populations are different — an admin allotting, a manager moving, a
// supervisor asking — and its endpoints live behind their own router with its
// own guard. Folding them into the departments feature would have suggested
// they share an audience with skills and staff invitations, which are
// admin-and-manager only.
//
// The routing rule itself is nowhere in this file. It is
// `resolve_complaint_department` (`complaint_department_routing`) and it runs when the complaint is
// raised: the category first, the resident's own guess second, the triage queue
// third. Nothing in the browser gets to re-decide it.

const patch = (path, body = {}) => api(path, { method: 'PATCH', body: JSON.stringify(body) });
const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

const query = (params) => {
  const pairs = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== ''
  );
  return pairs.length ? `?${new URLSearchParams(pairs)}` : '';
};

export const complaintRoutingApi = {
  /**
   * One department's complaints. Read by its manager *and* its supervisors —
   * the API admits both, because both act on the same rows.
   */
  departmentComplaints: (departmentId, params = {}) =>
    api(`/departments/${departmentId}/complaints${query(params)}`),

  /**
   * The admin's triage queue.
   *
   * Not `/complaints/unassigned`: `GET /complaints/{id}` already exists and
   * would have swallowed it, reading "unassigned" as a complaint id. The path
   * is a sibling rather than a child so nothing added later can capture it.
   */
  unassigned: () => api('/unassigned-complaints'),

  /**
   * Id, name and kind of every active department, for a destination picker.
   *
   * Not `/departments`: that one is admin-only and carries roster counts,
   * categories, hours and skills. This endpoint exists so drawing a dropdown
   * did not become a reason to widen that read.
   */
  departmentOptions: () => api('/department-options'),

  /** Open "this isn't ours" requests waiting on a manager's answer. */
  changeRequests: (departmentId) =>
    api(`/departments/${departmentId}/complaint-department-requests`),

  /**
   * Allot an unrouted complaint, or move a routed one.
   *
   * One call for both, because they are the same write — which one you are
   * performing is decided in Postgres from what the complaint currently holds,
   * not from anything sent here.
   */
  assignDepartment: (complaintId, departmentId) =>
    patch(`/complaints/${complaintId}/department`, { departmentId }),

  /** A supervisor asking their manager to move it. The destination is optional. */
  requestChange: (complaintId, payload) =>
    post(`/complaints/${complaintId}/department-requests`, payload),

  /** The manager's answer: `accept` or `reject`. */
  decideChange: (complaintId, requestId, payload) =>
    patch(`/complaints/${complaintId}/department-requests/${requestId}`, payload),
};
