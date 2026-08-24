import { api } from '../../lib/api/client';

// The resident's whole API surface, in one place.
//
// Same shape as `features/hiring/hiringApi.js`: no state, no caching, no error
// translation — react-query owns all three. This module was a FROZEN INTERFACE
// while the two phase-6 wiring tasks ran in parallel: both consumed it, neither
// edited it. That freeze is over; it thaws one endpoint at a time, on an
// orchestrator's say-so, and never because a screen wanted a wrapper.
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
  /**
   * The visit request on this complaint, if any. 404 means there is none.
   *
   * `mode` says which of the two questions is being asked: `approve` is the
   * department proposing an hour for the resident to confirm or decline;
   * `pick` is the department asking the resident to name the hour themselves
   * (ruling F1), and its proposed times are null because nobody has proposed
   * one. The two have different writes below.
   */
  scheduleRequest: (complaintId) => api(`/complaints/${complaintId}/schedule-request`),
  /**
   * Answer a proposed hour (`approve`-mode): `{ response: 'confirmed' |
   * 'declined', note? }`. Declining clears the time and sends it back to the
   * supervisor; it is not a counter-proposal, which is why there is no time in
   * this payload.
   */
  schedule: (complaintId, payload) => post(`/complaints/${complaintId}/schedule`, payload),
  /**
   * Name the hour (`pick`-mode): `{ startAt, endAt }`, both ISO and both
   * required. Silence is answered by the system 24 hours after the raise
   * (ruling F2), so there is no decline to send here — see API.md §resident
   * scheduling.
   */
  scheduleTime: (complaintId, payload) =>
    post(`/complaints/${complaintId}/schedule-time`, payload),

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
