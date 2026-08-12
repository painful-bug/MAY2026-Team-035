import { api } from '../../lib/api/client';

// The resident's whole API surface, in one place.
//
// Same shape as `features/hiring/hiringApi.js`: no state, no caching, no error
// translation — react-query owns all three. This module is a FROZEN INTERFACE
// while the two phase-6 wiring tasks run in parallel: both consume it, neither
// edits it. A missing wrapper is reported to the orchestrator, not added here.
//
// Every operation below is resident-scoped on the server: the community and the
// caller come from the session, never from an argument, which is why nothing
// here takes a communityId.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

const query = (params) => {
  const pairs = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== ''
  );
  const search = new URLSearchParams(pairs).toString();
  return search ? `?${search}` : '';
};

export const residentApi = {
  // --- the front page --------------------------------------------------------
  /** Everything the dashboard shows, in one read. Fetch this before anything. */
  snapshot: () => api('/resident/snapshot'),

  // --- complaints ------------------------------------------------------------
  complaints: (params = {}) => api(`/complaints${query(params)}`),
  complaint: (complaintId) => api(`/complaints/${complaintId}`),
  /**
   * `{ title, description, categoryId?, departmentId?, ... }` — `departmentId`
   * is the routing picker's answer and **null means "Not sure"**, which lets
   * `raise_complaint` route by category instead. Sending a department the
   * resident guessed wrong is worse than sending nothing.
   */
  createComplaint: (payload) => post('/complaints', payload),
  skills: () => api('/skills'),
  cancelComplaintWork: (complaintId, payload) => post(`/complaints/${complaintId}/cancel`, payload),
  /** Mark the thread read; clears the unread badge, nothing else. */
  markComplaintRead: (complaintId) => post(`/complaints/${complaintId}/read`),
  reopenComplaint: (complaintId, payload = {}) =>
    post(`/complaints/${complaintId}/reopen`, payload),
  /**
   * Confirm a resolution: `{ rating: 1-5, feedback? }`. There is no dispute
   * payload — disputing a resolution IS `reopenComplaint`, which is why the
   * two sit next to each other here.
   */
  resolveComplaint: (complaintId, payload) =>
    post(`/complaints/${complaintId}/resolution`, payload),
  /** Reply on the thread. `{ message, visibility: 'resident' }` is the wire shape. */
  addComplaintComment: (complaintId, payload) =>
    post(`/complaints/${complaintId}/comments`, payload),

  // --- complaint scheduling --------------------------------------------------
  /** The visit the department proposed, if any. 404 means nothing proposed. */
  scheduleRequest: (complaintId) => api(`/complaints/${complaintId}/schedule-request`),
  /** Accept a slot or propose a time: see API.md §resident scheduling. */
  schedule: (complaintId, payload) => post(`/complaints/${complaintId}/schedule`, payload),

  // --- visitor passes --------------------------------------------------------
  visitorPasses: (params = {}) => api(`/visitor-passes${query(params)}`),
  visitorPass: (passId) => api(`/visitor-passes/${passId}`),
  createVisitorPass: (payload) => post('/visitor-passes', payload),
  approveVisitorPass: (passId) => post(`/visitor-passes/${passId}/approve`),
  rejectVisitorPass: (passId) => post(`/visitor-passes/${passId}/reject`),
  cancelVisitorPass: (passId) => post(`/visitor-passes/${passId}/cancel`),

  // --- money -----------------------------------------------------------------
  invoices: (params = {}) => api(`/invoices/mine${query(params)}`),
  /** The simulator: `{ method }`. There is no real gateway anywhere behind this. */
  payInvoice: (invoiceId, payload) => post(`/invoices/${invoiceId}/pay`, payload),
  amenityBookings: (params = {}) => api(`/amenity-bookings/mine${query(params)}`),
  payAmenityBooking: (bookingId, payload) =>
    post(`/amenity-bookings/${bookingId}/pay`, payload),

  // --- home ------------------------------------------------------------------
  notices: (params = {}) => api(`/notices${query(params)}`),
  household: () => api('/me/household'),
  addHouseholdPhone: (payload) => post('/me/household/phones', payload),
  /**
   * Served from `departments`, so it is also the complaint form's routing
   * picker: resident-readable names for who does what. The admin department
   * list 403s a resident; this is the read that does not.
   */
  directoryContacts: () => api('/directory/contacts'),

  // --- amenities -------------------------------------------------------------
  availableAmenities: (params = {}) => api(`/amenities/available${query(params)}`),
};
