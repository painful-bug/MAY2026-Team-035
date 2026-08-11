import { api, download } from '../../lib/api/client';

// The gate: posts, shifts, the two registers, incidents, verification, offline
// and the exports. Backed by migrations `0040` and `0047`, documented in
// `docs/API.md` §19.
//
// Same shape as `features/hiring/hiringApi.js`: no state, no caching, no error
// translation — react-query owns all three.
//
// **No community id travels on any call in this file**, and that is the whole
// surface's design rather than an omission here. A register entry, a shift and
// an incident are each a fact about exactly one society, so the backend derives
// the community from the caller's own membership and would refuse an id in a
// body. The client cannot pick which gate it is standing at, because a client
// that could pick would be a client that could pick the wrong one.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });
const patch = (path, body = {}) => api(path, { method: 'PATCH', body: JSON.stringify(body) });

const query = (params) => {
  const pairs = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== ''
  );
  const search = new URLSearchParams(pairs).toString();
  return search ? `?${search}` : '';
};

export const securityApi = {
  // --- posts and the roster --------------------------------------------------
  posts: (params = {}) => api(`/security/posts${query(params)}`),
  /** Security manager only. Omitting a field on edit leaves it alone. */
  createPost: (payload) => post('/security/posts', payload),
  updatePost: (postId, payload) => patch(`/security/posts/${postId}`, payload),

  /**
   * The guards a shift may be given to. Security manager only (`0047`).
   *
   * Deliberately narrower than what the shift write accepts: only staff of
   * departments whose kind is `security`. A picker offering the plumbing roster
   * would be offering a mistake.
   */
  roster: () => api('/security/roster'),

  // --- shifts ----------------------------------------------------------------
  /**
   * `from`/`to` match on **overlap**, not on start — a night shift that began
   * at 22:00 yesterday is the one a guard on duty at 01:00 is looking at.
   */
  shifts: (params = {}) => api(`/security/shifts${query(params)}`),
  createShift: (payload) => post('/security/shifts', payload),
  /**
   * Two permissions behind one route. `{ status }` alone on your *own* shift is
   * any guard — that is End Shift. Any other field, or anybody else's shift, is
   * the security manager's, and the server decides which from the shape of the
   * body rather than from a flag we could get wrong.
   */
  updateShift: (shiftId, payload) => patch(`/security/shifts/${shiftId}`, payload),

  // --- the material register (US-3.3) ----------------------------------------
  movements: (params = {}) => api(`/security/material-movements${query(params)}`),
  /**
   * `sourceClientId` is what makes a retry safe: it is unique per community, so
   * re-sending a queued entry returns the original row instead of writing a
   * second one. Mint it once per form, not once per attempt.
   */
  recordMovement: (payload) => post('/security/material-movements', payload),
  /** Idempotent: pressing *returned* twice is a 200 with the recorded time. */
  returnMovement: (movementId, payload = {}) =>
    post(`/security/material-movements/${movementId}/return`, payload),

  // --- the tanker log (US-3.4) -----------------------------------------------
  tankers: (params = {}) => api(`/security/water-tankers${query(params)}`),
  recordTanker: (payload) => post('/security/water-tankers', payload),
  updateTanker: (logId, payload) => patch(`/security/water-tankers/${logId}`, payload),

  // --- incidents -------------------------------------------------------------
  incidents: (params = {}) => api(`/security/incidents${query(params)}`),
  /** `high` and `critical` notify the community's admins and managers. */
  recordIncident: (payload) => post('/security/incidents', payload),
  updateIncident: (incidentId, payload) =>
    patch(`/security/incidents/${incidentId}`, payload),

  // --- the gate --------------------------------------------------------------
  /**
   * Scan or type a credential.
   *
   * **A refusal is a 200 with a verdict, not an error.** The guard asked a
   * question and got an answer; only `4xx` here is about the guard.
   *
   * **The second scan is the way out** — presenting the same credential again
   * checks the visitor out, which is why there is no separate check-out call.
   */
  verify: (payload) => post('/security/gate/verify', payload),

  /**
   * The passes this gate may need while disconnected. Hashes only — there is no
   * plaintext code in the database to hand out. Doubles as the expected-visitor
   * list, which is the only forward view of visitors a guard has.
   */
  offlineBundle: (hours = 12) => api(`/security/offline-bundle${query({ hours })}`),

  /**
   * Replay what the gate did offline. Idempotent per `sourceClientId`, and that
   * matters more here than anywhere else: re-verifying a replay would check the
   * visitor *out*, because a second scan is a departure. Max 200 entries.
   */
  offlineReconcile: (entries) => post('/security/offline-reconcile', { entries }),

  // --- exports (US-3.6) ------------------------------------------------------
  /** `dataset` is material-movements | water-tankers | incidents | shifts. */
  exportCsv: (dataset, params = {}) =>
    download(`/security/exports/${dataset}${query(params)}`, {
      filename: `${dataset}.csv`,
    }),
};
