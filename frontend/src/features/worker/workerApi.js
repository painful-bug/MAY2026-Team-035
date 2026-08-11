import { api } from '../../lib/api/client';

// Every endpoint the worker portal touches, in one thin file.
//
// The same shape as `features/registration/registrationApi.js`: no state, no
// caching, no error translation. Caching is react-query's job and it is already
// mounted; a second cache here would be a second thing to invalidate.
//
// §4.20 in the progress journal is why there is no zustand slice beside this.
// The slices in `store/slices/` are the demo half of the app -- they mint their
// own ids -- and every page that talks to the real backend uses react-query.

const range = (from, to) => `from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

export const workerApi = {
  // --- the one call that fills the screen ------------------------------------
  snapshot: () => api('/worker/snapshot'),

  // --- identity --------------------------------------------------------------
  skills: () => api('/skills'),
  register: (payload) => post('/service-providers', payload),
  profile: () => api('/service-providers/me'),
  updateProfile: (payload) => api('/service-providers/me', { method: 'PATCH', body: JSON.stringify(payload) }),
  setSkills: (skillIds) => api('/service-providers/me/skills', { method: 'PUT', body: JSON.stringify({ skillIds }) }),
  setAvailable: (isAvailable) =>
    api('/service-providers/me/availability', { method: 'PATCH', body: JSON.stringify({ isAvailable }) }),

  // --- work ------------------------------------------------------------------
  jobs: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
    ).toString();
    return api(`/worker/jobs${query ? `?${query}` : ''}`);
  },
  job: (workOrderId) => api(`/worker/jobs/${workOrderId}`),
  acceptJob: (workOrderId) => post(`/worker/jobs/${workOrderId}/accept`),
  declineJob: (workOrderId, reason) => post(`/worker/jobs/${workOrderId}/decline`, { reason: reason || null }),
  startJob: (workOrderId) => post(`/worker/jobs/${workOrderId}/start`),
  completeJob: (workOrderId, notes) => post(`/worker/jobs/${workOrderId}/complete`, { notes: notes || null }),
  reportJobFailure: (workOrderId, reason) => post(`/worker/jobs/${workOrderId}/unable`, { reason }),

  // --- time ------------------------------------------------------------------
  calendar: (from, to) => api(`/worker/calendar?${range(from, to)}`),
  unavailability: (from, to) => api(from && to ? `/worker/unavailability?${range(from, to)}` : '/worker/unavailability'),
  addUnavailability: (payload) => post('/worker/unavailability', payload),
  removeUnavailability: (blockId) => api(`/worker/unavailability/${blockId}`, { method: 'DELETE' }),
  availabilityRules: () => api('/worker/availability-rules'),
  setAvailabilityRules: (rules) =>
    api('/worker/availability-rules', { method: 'PUT', body: JSON.stringify({ rules }) }),

  // --- where I work ----------------------------------------------------------
  myCommunities: () => api('/worker/communities'),
  searchCommunities: ({ query = '', limit = 20 } = {}) =>
    api(`/worker/communities/search?q=${encodeURIComponent(query)}&limit=${limit}`),
  myApplications: () => api('/worker/applications'),
  apply: (payload) => post('/worker/applications', payload),
  withdrawApplication: (applicationId) => api(`/worker/applications/${applicationId}`, { method: 'DELETE' }),
  decideInvitation: (applicationId, decision, note = null) =>
    post(`/worker/applications/${applicationId}/decision`, { decision, note }),

  // --- leaving ---------------------------------------------------------------
  // Keyed on the roster row and not on the community, because somebody hired by
  // three societies is leaving exactly one of them and nothing in the session
  // says which. `myCommunities` already carries the open request per row, so
  // neither of these needs a read of its own.
  // `effectiveAt` is the day they want to stop; omitted means immediately.
  requestDeparture: (staffId, reason, effectiveAt) =>
    post(`/worker/communities/${staffId}/departure`, {
      reason: reason || null,
      effectiveAt: effectiveAt || null,
    }),
  cancelDeparture: (staffId) =>
    api(`/worker/communities/${staffId}/departure`, { method: 'DELETE' }),

  // --- talking to a department ----------------------------------------------
  conversations: () => api('/conversations'),
  conversation: (conversationId) => api(`/conversations/${conversationId}`),
  sendMessage: (conversationId, body) => post(`/conversations/${conversationId}/messages`, { body }),
};
