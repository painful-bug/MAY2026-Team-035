import assert from 'node:assert/strict';

globalThis.document = { cookie: '' };
const calls = [];
globalThis.fetch = async (url, options = {}) => {
  calls.push({ url, options });
  if (url.endsWith('/auth/csrf')) {
    document.cookie = 'hb_preauth_csrf=preauth-token';
    return Response.json({ message: 'CSRF protection ready.' });
  }
  return Response.json({ ok: true });
};

const { api } = await import('./client.js');
await api('/onboarding/community', { method: 'POST', body: '{}' });

assert.equal(calls[0].url, '/api/v1/auth/csrf');
assert.equal(calls[1].options.headers.get('X-CSRF-Token'), 'preauth-token');
