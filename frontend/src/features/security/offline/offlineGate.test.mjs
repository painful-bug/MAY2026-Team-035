import assert from 'node:assert/strict';

// The offline gate is the one piece of `US-3.5` that can be proven without a
// server, so it is proven here: the verdict rules, the expiry honesty, and the
// queue transition that decides what a guard is still shown after a sync.
//
// The rules under test are the ones a reader would most plausibly get wrong:
//   * a rejected entry SURVIVES reconcile — it is the security event
//   * a replayed entry does NOT — it was already recorded, and re-verifying it
//     server-side would have checked the visitor out
//   * an expired bundle refuses to guess rather than admitting on a stale list

// `globalThis.crypto` is Web Crypto on Node 18+ and in every browser this ships
// to, so `crypto.subtle.digest` and `crypto.randomUUID` need no shim.

const store = new Map();
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, String(value)),
  removeItem: (key) => store.delete(key),
};

const {
  applyOutcomes,
  bundleUsable,
  dismissEntry,
  enqueueScan,
  loadQueue,
  pendingEntries,
  saveBundle,
  saveQueue,
  sha256Hex,
  toReconcilePayload,
  verifyLocal,
} = await import('./offlineGate.js');

const HOUR = 60 * 60 * 1000;
const now = Date.UTC(2026, 7, 11, 12, 0, 0);

const codeHash = await sha256Hex('483920');
const futureHash = await sha256Hex('111111');
const staleHash = await sha256Hex('222222');

const bundle = {
  generatedAt: new Date(now - HOUR).toISOString(),
  expiresAt: new Date(now + 11 * HOUR).toISOString(),
  communityId: 'community-with-the-gate',
  hashAlgorithm: 'sha256',
  passes: [
    {
      passId: 'pass-live',
      codeHash,
      passHash: null,
      visitorName: 'Anil',
      guestCount: 2,
      unitCode: 'B-204',
      validFrom: new Date(now - HOUR).toISOString(),
      validUntil: new Date(now + HOUR).toISOString(),
    },
    {
      passId: 'pass-future',
      codeHash: futureHash,
      visitorName: 'Later',
      guestCount: 1,
      validFrom: new Date(now + 3 * HOUR).toISOString(),
      validUntil: new Date(now + 5 * HOUR).toISOString(),
    },
    {
      passId: 'pass-stale',
      codeHash: staleHash,
      visitorName: 'Yesterday',
      guestCount: 1,
      validFrom: new Date(now - 5 * HOUR).toISOString(),
      validUntil: new Date(now - 3 * HOUR).toISOString(),
    },
  ],
};

// --- verdict rules ---------------------------------------------------------

assert.equal((await verifyLocal('483920', bundle, now)).verdict, 'admitted');
assert.equal((await verifyLocal('111111', bundle, now)).verdict, 'not_yet_valid');
assert.equal((await verifyLocal('222222', bundle, now)).verdict, 'expired');
assert.equal((await verifyLocal('000000', bundle, now)).verdict, 'not_found');

const admitted = await verifyLocal('483920', bundle, now);
assert.equal(admitted.visitorName, 'Anil', 'the card can name who is at the barrier');
assert.equal(admitted.unitCode, 'B-204');

// The plaintext code is never what we compare — the digest is.
assert.equal(codeHash.length, 64);
assert.notEqual(codeHash, '483920');

// --- bundle expiry ---------------------------------------------------------

assert.equal(bundleUsable({ bundle }, now), true);
assert.equal(
  bundleUsable({ bundle }, now + 12 * HOUR),
  false,
  'past expiresAt the device must refuse to guess'
);
assert.equal(bundleUsable(null, now), false);
assert.equal(bundleUsable({ bundle: { passes: [] } }, now), false, 'no expiry is not usable');

// --- the queue -------------------------------------------------------------

saveBundle(bundle);
saveQueue([]);

let queue = enqueueScan(loadQueue(), { credential: '483920', verdict: admitted });
queue = enqueueScan(queue, {
  credential: '000000',
  verdict: await verifyLocal('000000', bundle, now),
});
queue = enqueueScan(queue, { credential: '222222', verdict: await verifyLocal('222222', bundle, now) });
saveQueue(queue);

assert.equal(loadQueue().length, 3, 'every offline scan is queued, including not_found');
assert.equal(pendingEntries(queue).length, 3);
assert.equal(
  new Set(queue.map((entry) => entry.sourceClientId)).size,
  3,
  'each entry carries its own idempotency key'
);

const payload = toReconcilePayload(queue);
assert.deepEqual(
  Object.keys(payload[0]).sort(),
  ['claimedVerdict', 'credential', 'presentedAt', 'sourceClientId'],
  'nothing local travels to the server'
);

// One accepted, one replayed, one rejected — the three cases the server returns.
const settled = applyOutcomes(queue, [
  { sourceClientId: queue[0].sourceClientId, serverVerdict: 'admitted', wasReplay: false },
  { sourceClientId: queue[1].sourceClientId, serverVerdict: 'admitted', wasReplay: true },
  {
    sourceClientId: queue[2].sourceClientId,
    serverVerdict: 'refused',
    detail: 'That pass was cancelled.',
    wasReplay: false,
  },
]);

assert.equal(settled.length, 1, 'accepted and replayed entries leave the queue');
assert.equal(settled[0].status, 'rejected');
assert.equal(settled[0].serverVerdict, 'refused');
assert.equal(settled[0].serverDetail, 'That pass was cancelled.');

// A replay counts as settled even when the server verdict is not an admission —
// it means the row already exists, which is exactly why it must not be re-sent.
const replayOnly = applyOutcomes([queue[0]], [
  { sourceClientId: queue[0].sourceClientId, serverVerdict: 'expired', wasReplay: true },
]);
assert.equal(replayOnly.length, 0);

// An entry with no outcome (a batch of 200 cut short) stays pending.
const untouched = applyOutcomes(queue, []);
assert.equal(untouched.length, 3);
assert.equal(untouched.every((entry) => entry.status === 'pending'), true);

assert.equal(dismissEntry(settled, settled[0].sourceClientId).length, 0);

console.log('offlineGate: all assertions passed');
