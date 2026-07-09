// Framework-free self-check for the two pieces of non-trivial pure logic:
// opaque token minting (tokens.js) and invite redemption (invites.js).
// Run: node src/lib/selfcheck.mjs
import assert from 'node:assert';
import { createInviteToken } from './tokens.js';
import { applyRedeem } from './invites.js';

// --- tokens: opaque, unique, no dashes ---
const t1 = createInviteToken();
const t2 = createInviteToken();
assert.match(t1, /^[a-z0-9]+$/i, 'token is opaque alphanumeric');
assert.notStrictEqual(t1, t2, 'tokens are unique');

// --- applyRedeem ---
const base = () => ({
  users: [
    { id: 'a', phone: '111', apartmentId: 'B-12', status: 'Invited' },
    { id: 'b', phone: '222', apartmentId: 'B-12', status: 'Invited' },
    { id: 'c', phone: '999', apartmentId: 'C-1', status: 'Active' },
  ],
  invitations: [
    { token: 'good', apartmentId: 'B-12', used: false, expiresAt: Date.now() + 1000 },
    { token: 'old', apartmentId: 'B-12', used: false, expiresAt: Date.now() - 1000 },
    { token: 'spent', apartmentId: 'B-12', used: true, expiresAt: Date.now() + 1000 },
  ],
});

assert.strictEqual(applyRedeem(base(), 'nope').reason, 'invalid');
assert.strictEqual(applyRedeem(base(), 'old').reason, 'expired');
assert.strictEqual(applyRedeem(base(), 'spent').reason, 'used');

// happy path: whole flat activated, token consumed, phone selects the member
const r = applyRedeem(base(), 'good', { phone: '222' });
assert.ok(r.ok);
assert.strictEqual(r.user.id, 'b', 'phone selects the right member');
assert.ok(
  r.users.filter((u) => u.apartmentId === 'B-12').every((u) => u.status === 'Active'),
  'whole flat activated'
);
assert.strictEqual(r.users.find((u) => u.id === 'c').status, 'Active', 'other flats untouched');
assert.ok(r.invitations.find((i) => i.token === 'good').used, 'token consumed');

// single-use: redeeming the produced state again fails
const again = applyRedeem({ users: r.users, invitations: r.invitations }, 'good');
assert.strictEqual(again.reason, 'used', 'token is single-use');

console.log('selfcheck OK');
