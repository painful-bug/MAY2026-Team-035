import { api } from '../../lib/api/client';

// Skills, complaint categories and leadership provisioning.
//
// Same shape as `features/hiring/hiringApi.js`: no state, no caching, no error
// translation. react-query is already mounted and owns all three.
//
// **Departments themselves are deliberately not here.** Creating, editing and
// deleting one still goes through `store/slices/createDepartmentsSlice.js`,
// which already calls the API and which the whole admin list screen reads from.
// `docs/potential issues/09` is explicit that the slices should not be rewritten
// to call the API from inside zustand, and rewriting the department CRUD onto
// react-query would be that same move wearing a different hat. New surface goes
// through react-query; working surface is left working.
//
// The department id is a path segment on every call rather than an implicit
// "your department", for the reason `hiringApi.js` gives: an admin manages
// several, and the backend authorises against the id the resource named.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });
const put = (path, body = {}) => api(path, { method: 'PUT', body: JSON.stringify(body) });
const patch = (path, body = {}) => api(path, { method: 'PATCH', body: JSON.stringify(body) });
const del = (path) => api(path, { method: 'DELETE' });

const query = (params) => {
  const pairs = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== ''
  );
  const search = new URLSearchParams(pairs).toString();
  return search ? `?${search}` : '';
};

export const departmentsApi = {
  // --- the skill catalogue ---------------------------------------------------
  /**
   * Closest matches for what somebody is typing.
   *
   * Ordering and the `isExact` flag both come from Postgres. `isExact` in
   * particular is **not** recomputed here: it is a case- and
   * whitespace-insensitive comparison, and a second implementation in the
   * browser would disagree with the database on exactly the input that matters
   * — a trailing space, or a different capitalisation — which is the input that
   * decides whether we offer to create a duplicate.
   */
  searchSkills: (q, limit = 8) => api(`/skills${query({ q, limit })}`),

  /** The whole catalogue. What the worker registration grid renders. */
  allSkills: () => api('/skills'),

  /** Add a trade to the global catalogue without attaching it anywhere. */
  createSkill: (payload) => post('/skills', payload),

  // --- a department's claim on it --------------------------------------------
  departmentSkills: (departmentId) => api(`/departments/${departmentId}/skills`),

  /** Replace the whole set. Ids, because by now every one of them exists. */
  setDepartmentSkills: (departmentId, skillIds) =>
    put(`/departments/${departmentId}/skills`, { skillIds }),

  /**
   * The "Add skill" button: create if needed, attach, **one call**.
   *
   * Not `createSkill` followed by `setDepartmentSkills`. Two calls can
   * half-fail, and the half that lands is a skill created and attached to
   * nothing — catalogue litter nobody asked for, produced by the failure that
   * happens on a phone at the end of a long form.
   */
  addDepartmentSkill: (departmentId, name) =>
    post(`/departments/${departmentId}/skills`, { name }),

  removeDepartmentSkill: (departmentId, skillId) =>
    del(`/departments/${departmentId}/skills/${skillId}`),

  // --- complaint categories --------------------------------------------------
  /**
   * This community's categories, each with the trade it resolves to.
   *
   * `skillName: null` is the row worth rendering differently: that category
   * matches no service person in any hiring search, so complaints filed under
   * it reach nobody. It has been true since the category→skill link was built
   * and invisible until this endpoint existed.
   */
  categories: () => api('/complaint-categories'),

  // --- leadership ------------------------------------------------------------
  /**
   * Managers and supervisors created for a department, arrived or not.
   *
   * Nothing is emailed, so a mistyped address produces no bounce and no error —
   * only a row that stays `pending` forever. Rendering this list is the only
   * way anyone finds out.
   */
  staffInvitations: (departmentId, params = {}) =>
    api(`/departments/${departmentId}/staff-invitations${query(params)}`),

  /** `rank` is `manager` or `supervisor`. There is no third option. */
  inviteStaffMember: (departmentId, payload) =>
    post(`/departments/${departmentId}/staff-invitations`, payload),

  /**
   * Correct one that has not been claimed — the answer to a mistyped address.
   *
   * Send only the fields that changed. Omitted means unchanged, so patching the
   * email cannot blank the job title. There is deliberately no `departmentId`:
   * that is what the API authorizes the call against, so moving an invitation is
   * withdraw-and-reissue rather than an edit.
   */
  updateStaffInvitation: (departmentId, invitationId, payload) =>
    patch(`/departments/${departmentId}/staff-invitations/${invitationId}`, payload),

  revokeStaffInvitation: (departmentId, invitationId) =>
    del(`/departments/${departmentId}/staff-invitations/${invitationId}`),
};
