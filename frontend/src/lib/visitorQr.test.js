// @vitest-environment node
import { createHash } from 'node:crypto';
import { expect, it } from 'vitest';
import { buildVisitorQrPayload, visitorCredential } from './visitorQr';
import { verifyLocal } from '../features/security/offline/offlineGate';

it.each(['123456', 'issued-pass-token'])('preserves a plain credential: %s', (credential) => {
  expect(visitorCredential(` ${credential} `)).toBe(credential);
});

it.each([
  '{broken',
  JSON.stringify({ type: 'other', version: 2, token: 'token' }),
  JSON.stringify({ type: 'homebandhu-visitor-pass', version: 1, token: 'token' }),
  JSON.stringify({ type: 'homebandhu-visitor-pass', version: 2, token: {} }),
])('rejects damaged or unsupported envelopes: %s', (raw) => {
  expect(() => visitorCredential(raw)).toThrow(/visitor QR/);
});

it('matches the stored token hash for an actual resident envelope in offline verification', async () => {
  const pass = { id: 'pass-1', guestCount: 2 };
  const secret = { passToken: 'issued-pass-token', securityCode: '123456' };
  const payload = buildVisitorQrPayload(pass, secret);
  const bundle = { passes: [{
    passId: pass.id,
    passHash: createHash('sha256').update(secret.passToken).digest('hex'),
    validFrom: '2026-09-04T09:00:00Z',
    validUntil: '2026-09-04T11:00:00Z',
    guestCount: 2,
  }] };
  const now = Date.parse('2026-09-04T10:00:00Z');
  expect((await verifyLocal(payload, bundle, now)).verdict).toBe('not_found');
  expect((await verifyLocal(visitorCredential(payload), bundle, now)).verdict).toBe('admitted');
});
