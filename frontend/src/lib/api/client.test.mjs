import assert from 'node:assert/strict';

globalThis.document = { cookie: '' };
const calls = [];
let sessionAttempts = 0;
globalThis.fetch = async (url, options = {}) => {
  calls.push({ url, options });
  if (url.endsWith('/auth/csrf')) {
    document.cookie = 'hb_preauth_csrf=preauth-token';
    return Response.json({ message: 'CSRF protection ready.' });
  }
  if (url.endsWith('/auth/session') && sessionAttempts++ === 0) {
    return Response.json({ error: { code: 'token_expired' } }, { status: 401 });
  }
  if (url.endsWith('/signed-out')) {
    return Response.json({ error: { code: 'authentication_error' } }, { status: 401 });
  }
  return Response.json({ ok: true });
};

const { api } = await import('./client.js');
await api('/onboarding/community', { method: 'POST', body: '{}' });

assert.equal(calls[0].url, '/api/v1/auth/csrf');
assert.equal(calls[1].options.headers.get('X-CSRF-Token'), 'preauth-token');

document.cookie = 'hb_csrf=session-token; hb_recovery_csrf=recovery-token; hb_preauth_csrf=preauth-token';
await api('/telemetry/service-signup', { method: 'POST', body: '{}' });
assert.equal(calls[2].options.headers.get('X-CSRF-Token'), 'session-token');

// An idle tab can lose its short-lived access and CSRF cookies while retaining
// the refresh cookie. Bootstrap pre-auth CSRF before attempting the refresh.
document.cookie = '';
await api('/auth/session');
assert.deepEqual(calls.slice(3).map(({ url }) => url), [
  '/api/v1/auth/session',
  '/api/v1/auth/csrf',
  '/api/v1/auth/refresh',
  '/api/v1/auth/session',
]);
assert.equal(calls[5].options.headers['X-CSRF-Token'], 'preauth-token');

const beforeSignedOut = calls.length;
await assert.rejects(api('/signed-out'), ({ code }) => code === 'authentication_error');
assert.deepEqual(calls.slice(beforeSignedOut).map(({ url }) => url), [
  '/api/v1/signed-out',
]);
