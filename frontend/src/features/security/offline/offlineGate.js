// The gate keeps working when the network does not. `US-3.5`.
//
// ---------------------------------------------------------------------------
// THIS FILE IS A DELIBERATE EXCEPTION TO A STANDING RULE
// ---------------------------------------------------------------------------
// `store/appStore.js` states it plainly: *browser state is a render cache only;
// localStorage is deliberately never a source of domain truth.* Every other
// screen in this project obeys that, and `public/sw.js` refuses to cache
// `/api/*` for the same reason.
//
// This module breaks it on purpose, in one direction, for one screen. A barrier
// whose network has dropped still has people standing at it, and the choice is
// between recording what happened and losing it. So the scan queue below is
// durable client-owned write state — the first in this codebase.
//
// What keeps that safe is not the storage, it is `POST /security/offline-reconcile`:
//   * The bundle carries **hashes only**. There is no plaintext code in the
//     database to leak, and a device holding the file learns nothing it was not
//     already authorised to admit.
//   * The bundle is **unsigned**, and `0040`'s docstring explains why a
//     signature would be theatre — the same person who can edit the cache can
//     delete the check beside it, because both are JavaScript on their machine.
//   * So every offline verdict is **provisional**. The server re-runs the real
//     verification on reconcile and records its own answer beside the device's
//     claim, in a log the community's admins can read. That, not the cache, is
//     the security property.
//
// Consequently `verifyLocal` below is honest about being a guess: it can check
// a hash and a validity window, and it cannot know how many of a four-guest
// party are already inside, or that the resident cancelled the pass an hour
// after the bundle was cut.

// Module-private on purpose. Nothing outside this file should read or write
// either key directly — the functions below are what keeps a half-written value
// from reaching a caller, and an exported key is an invitation to skip them.
const BUNDLE_KEY = 'hb.security.offlineBundle.v1';
const QUEUE_KEY = 'hb.security.offlineQueue.v1';

/** The server caps a reconcile submission at 200 entries. */
const RECONCILE_BATCH = 200;

// --------------------------------------------------------------------------
// Storage — every read tolerates junk, because a half-written key is a thing
// that happens on a device that lost power at the gate.
// --------------------------------------------------------------------------

function readJson(key, fallback) {
  try {
    const raw = globalThis.localStorage?.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    globalThis.localStorage?.setItem(key, JSON.stringify(value));
  } catch {
    // A full or disabled store is not a reason to fail the scan in front of
    // the guard. They still get their verdict; it just will not survive a
    // reload, and the banner already tells them the gate is offline.
  }
}

export function saveBundle(bundle) {
  writeJson(BUNDLE_KEY, { fetchedAt: new Date().toISOString(), bundle });
}

export function loadBundle() {
  return readJson(BUNDLE_KEY, null);
}

export function loadQueue() {
  const queue = readJson(QUEUE_KEY, []);
  return Array.isArray(queue) ? queue : [];
}

export function saveQueue(queue) {
  writeJson(QUEUE_KEY, queue);
}

// --------------------------------------------------------------------------
// Verification
// --------------------------------------------------------------------------

/** SHA-256 hex — the same digest `0040` compares against, via Web Crypto. */
export async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

/** Is the cached bundle still inside the window the server issued it for? */
export function bundleUsable(cached, now = Date.now()) {
  const expiresAt = cached?.bundle?.expiresAt;
  if (!expiresAt) return false;
  const expiry = new Date(expiresAt).getTime();
  return Number.isFinite(expiry) && expiry > now;
}

/**
 * Decide locally what the server would probably say.
 *
 * Mirrors `verify_gate_credential`'s window rules and stops there. It cannot
 * mirror the guest-count arithmetic (which needs prior `visitor_events`) and
 * so **never returns `departed`** — an offline second scan reads as another
 * admission, and reconcile sorts out which it really was.
 */
export async function verifyLocal(credential, bundle, now = Date.now()) {
  const passes = bundle?.passes || [];
  const hex = await sha256Hex(credential);
  const match = passes.find((pass) => pass.codeHash === hex || pass.passHash === hex);

  if (!match) {
    return {
      verdict: 'not_found',
      detail: 'That code is not in the cached pass list for this gate.',
    };
  }

  const from = match.validFrom ? new Date(match.validFrom).getTime() : null;
  const until = match.validUntil ? new Date(match.validUntil).getTime() : null;

  if (from && from > now) {
    return {
      verdict: 'not_yet_valid',
      detail: 'This pass is not valid yet.',
      ...passFields(match),
    };
  }
  if (until && until < now) {
    return {
      verdict: 'expired',
      detail: 'This pass has expired.',
      ...passFields(match),
    };
  }
  return {
    verdict: 'admitted',
    detail: 'Valid in the cached list. Recorded for confirmation.',
    ...passFields(match),
  };
}

function passFields(pass) {
  return {
    passId: pass.passId,
    visitorName: pass.visitorName,
    guestCount: pass.guestCount,
    unitCode: pass.unitCode,
    validFrom: pass.validFrom,
    validUntil: pass.validUntil,
  };
}

// --------------------------------------------------------------------------
// The queue
// --------------------------------------------------------------------------

/**
 * Add one offline scan.
 *
 * `sourceClientId` is the server's idempotency key: unique per community, and a
 * replay returns the stored verdict untouched rather than re-verifying. That
 * last part matters more here than anywhere else in the feature, because
 * re-verifying a replay would check the visitor *out* — a second scan is a
 * departure.
 */
export function enqueueScan(queue, { credential, verdict, presentedAt }) {
  return [
    ...queue,
    {
      sourceClientId: crypto.randomUUID(),
      credential,
      presentedAt: presentedAt || new Date().toISOString(),
      claimedVerdict: verdict.verdict,
      visitorName: verdict.visitorName || null,
      status: 'pending',
    },
  ];
}

export function pendingEntries(queue) {
  return queue.filter((entry) => entry.status === 'pending');
}

/** What `POST /security/offline-reconcile` accepts — nothing local travels. */
export function toReconcilePayload(entries) {
  return entries.slice(0, RECONCILE_BATCH).map((entry) => ({
    sourceClientId: entry.sourceClientId,
    credential: entry.credential,
    presentedAt: entry.presentedAt,
    claimedVerdict: entry.claimedVerdict,
  }));
}

/**
 * Fold the server's answer back into the queue.
 *
 * **Accepted and replayed entries leave; rejected ones stay.** An entry the
 * server refused is a person the guard let in that the server says should not
 * have been — the single most important thing this whole mechanism can tell
 * anybody, and clearing it silently would throw it away. It stays on screen,
 * with the server's own words, until the guard dismisses it one at a time.
 */
export function applyOutcomes(queue, outcomes) {
  const byId = new Map((outcomes || []).map((outcome) => [outcome.sourceClientId, outcome]));
  return queue.flatMap((entry) => {
    const outcome = byId.get(entry.sourceClientId);
    if (!outcome) return [entry];

    const settled = outcome.wasReplay || ['admitted', 'departed'].includes(outcome.serverVerdict);
    if (settled) return [];

    return [
      {
        ...entry,
        status: 'rejected',
        serverVerdict: outcome.serverVerdict,
        serverDetail: outcome.detail || null,
      },
    ];
  });
}

export function dismissEntry(queue, sourceClientId) {
  return queue.filter((entry) => entry.sourceClientId !== sourceClientId);
}
