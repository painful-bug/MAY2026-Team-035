import { api } from '../../lib/api/client';

export const registrationApi = {
  searchCommunities: ({ query, limit = 10, signal }) =>
    api(`/communities/search?q=${encodeURIComponent(query)}&limit=${limit}`, { signal }),
  createAccessRequest: (payload) =>
    api('/access-requests', { method: 'POST', body: JSON.stringify(payload) }),
  myAccessRequests: () => api('/access-requests/mine'),
  withdrawAccessRequest: (requestId) =>
    api(`/access-requests/${requestId}/withdraw`, { method: 'POST', body: JSON.stringify({}) }),
  adminAccessRequests: (status = 'pending') =>
    api(`/admin/access-requests?status=${encodeURIComponent(status)}`),
  approveAccessRequest: (requestId, payload = {}) =>
    api(`/admin/access-requests/${requestId}/approve`, { method: 'POST', body: JSON.stringify(payload) }),
  rejectAccessRequest: (requestId, payload) =>
    api(`/admin/access-requests/${requestId}/reject`, { method: 'POST', body: JSON.stringify(payload) }),
  blacklistAccessRequest: (requestId, payload) =>
    api(`/admin/access-requests/${requestId}/blacklist`, { method: 'POST', body: JSON.stringify(payload) }),
  createInvitation: (payload) =>
    api('/admin/invitations', { method: 'POST', body: JSON.stringify(payload) }),
  adminUnits: () => api('/communities/admin/units'),
};
