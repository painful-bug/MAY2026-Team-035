import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';

// The module's own header promises it is "safe to call in a browser that
// supports none of it" — callers (Settings.jsx's PushCard) consume
// `{ ok, reason }` and never expect a throw. Before this file, six sites threw
// straight past that contract: `Notification.requestPermission()`,
// `navigator.serviceWorker.ready` (which also never rejects, so a stuck
// browser hung the toggle forever), `existing.unsubscribe()`,
// `pushManager.subscribe()` (real-world `AbortError` on an unreachable push
// service), the unwrapped subscribe-POST, and `disablePush`'s unwrapped
// unregister-POST. Every test below exercises one of those sites and asserts
// a resolved `{ ok: false, reason }` rather than a rejection.

vi.mock('../api/client', () => ({ api: vi.fn() }));

// A real (public, widely-used-in-tutorials) VAPID example key — used only so
// `decodeKey`'s base64url -> Uint8Array conversion has something valid to
// decode; its bytes are never asserted on.
const APPLICATION_SERVER_KEY =
  'BDd3_hVL9fZi9Ybo2UUzA284WG5FZR30_95YeZJsiApwXKpNcF1rRPF3foIiBHXRdJI2Qhumhf6_LFTeZaNndIo';

function installServiceWorker({ register, ready, getRegistration } = {}) {
  Object.defineProperty(window.navigator, 'serviceWorker', {
    configurable: true,
    value: {
      register: register ?? vi.fn().mockResolvedValue({}),
      ready: ready ?? Promise.resolve({}),
      getRegistration: getRegistration ?? vi.fn().mockResolvedValue(undefined),
    },
  });
}

function removeServiceWorker() {
  // `navigator.serviceWorker` does not exist on the jsdom prototype at all,
  // so "removing support" is just not defining the property in the first
  // place — nothing to delete between tests.
  delete window.navigator.serviceWorker;
}

function installFullSupport({ registration, notificationPermission = 'granted', requestPermission } = {}) {
  installServiceWorker({
    register: vi.fn().mockResolvedValue(registration),
    ready: Promise.resolve(registration),
    getRegistration: vi.fn().mockResolvedValue(registration),
  });
  vi.stubGlobal('PushManager', function PushManager() {});
  vi.stubGlobal('Notification', {
    permission: notificationPermission,
    requestPermission: requestPermission ?? vi.fn().mockResolvedValue(notificationPermission),
  });
}

function makeRegistration({ subscription, subscribe, unsubscribe } = {}) {
  const sub = subscription === undefined
    ? {
      endpoint: 'https://push.example/abc',
      toJSON: () => ({ endpoint: 'https://push.example/abc', keys: { p256dh: 'k', auth: 'a' } }),
      unsubscribe: unsubscribe ?? vi.fn().mockResolvedValue(true),
    }
    : subscription;
  return {
    pushManager: {
      getSubscription: vi.fn().mockResolvedValue(sub),
      subscribe: subscribe ?? vi.fn().mockResolvedValue({
        toJSON: () => ({ endpoint: 'https://push.example/new', keys: { p256dh: 'k', auth: 'a' } }),
      }),
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  removeServiceWorker();
  vi.useRealTimers();
});

describe('pushSupported', () => {
  it('is false with no serviceWorker/PushManager/Notification on the page', async () => {
    const { pushSupported } = await import('./pushClient');
    expect(pushSupported()).toBe(false);
  });

  it('is true once every piece of the API is present', async () => {
    installFullSupport({ registration: makeRegistration() });
    const { pushSupported } = await import('./pushClient');
    expect(pushSupported()).toBe(true);
  });
});

describe('registerServiceWorker', () => {
  it('resolves null, not a rejection, when register() throws', async () => {
    installServiceWorker({ register: vi.fn().mockRejectedValue(new Error('nope')) });
    const { registerServiceWorker } = await import('./pushClient');
    await expect(registerServiceWorker()).resolves.toBeNull();
  });

  it('resolves null when there is no serviceWorker at all', async () => {
    removeServiceWorker();
    const { registerServiceWorker } = await import('./pushClient');
    await expect(registerServiceWorker()).resolves.toBeNull();
  });
});

describe('enablePush', () => {
  it('never rejects and resolves { ok: false } for an unsupported browser', async () => {
    const { enablePush } = await import('./pushClient');
    await expect(enablePush()).resolves.toEqual({
      ok: false,
      reason: expect.any(String),
    });
  });

  it('resolves { ok: false } when the permission prompt throws', async () => {
    installFullSupport({
      registration: makeRegistration(),
      requestPermission: vi.fn().mockRejectedValue(new Error('blocked by policy')),
    });
    const { enablePush } = await import('./pushClient');
    await expect(enablePush()).resolves.toEqual({ ok: false, reason: expect.any(String) });
  });

  it('resolves { ok: false } when permission is denied, without calling the API', async () => {
    installFullSupport({ registration: makeRegistration(), notificationPermission: 'denied' });
    vi.mocked(api).mockResolvedValue({});
    const { enablePush } = await import('./pushClient');

    const result = await enablePush();
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/blocked/i);
    expect(api).not.toHaveBeenCalled();
  });

  it('resolves { ok: false } instead of hanging forever when serviceWorker.ready never settles', async () => {
    vi.useFakeTimers();
    installServiceWorker({
      register: vi.fn().mockResolvedValue({}),
      ready: new Promise(() => {}), // never resolves — the real defect this guards.
    });
    vi.stubGlobal('PushManager', function PushManager() {});
    vi.stubGlobal('Notification', {
      permission: 'granted',
      requestPermission: vi.fn().mockResolvedValue('granted'),
    });
    const { enablePush } = await import('./pushClient');

    const pending = enablePush();
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(pending).resolves.toEqual({ ok: false, reason: expect.any(String) });
  });

  it('resolves { ok: false } when the vapid-key fetch throws', async () => {
    installFullSupport({ registration: makeRegistration() });
    vi.mocked(api).mockRejectedValue(new Error('network down'));
    const { enablePush } = await import('./pushClient');

    await expect(enablePush()).resolves.toEqual({
      ok: false,
      reason: 'Push is not configured on this server yet.',
    });
  });

  it('resolves { ok: false } when the server has no vapid key configured', async () => {
    installFullSupport({ registration: makeRegistration() });
    vi.mocked(api).mockResolvedValue({ publicKey: null });
    const { enablePush } = await import('./pushClient');

    await expect(enablePush()).resolves.toEqual({
      ok: false,
      reason: 'Push is not configured on this server yet.',
    });
  });

  it('resolves { ok: false } when an existing subscription refuses to unsubscribe', async () => {
    const registration = makeRegistration({
      unsubscribe: vi.fn().mockRejectedValue(new Error('gone')),
    });
    installFullSupport({ registration });
    vi.mocked(api).mockResolvedValue({ publicKey: APPLICATION_SERVER_KEY });
    const { enablePush } = await import('./pushClient');

    await expect(enablePush()).resolves.toEqual({ ok: false, reason: expect.any(String) });
  });

  it('gives a specific reason for AbortError from an unreachable push service', async () => {
    const abortError = Object.assign(new Error('unreachable'), { name: 'AbortError' });
    const registration = makeRegistration({
      subscription: null,
      subscribe: vi.fn().mockRejectedValue(abortError),
    });
    installFullSupport({ registration });
    vi.mocked(api).mockResolvedValue({ publicKey: APPLICATION_SERVER_KEY });
    const { enablePush } = await import('./pushClient');

    await expect(enablePush()).resolves.toEqual({
      ok: false,
      reason: expect.stringMatching(/push service/i),
    });
  });

  it('resolves { ok: false } when the subscribe-POST to the server throws', async () => {
    const registration = makeRegistration({ subscription: null });
    installFullSupport({ registration });
    vi.mocked(api)
      .mockResolvedValueOnce({ publicKey: APPLICATION_SERVER_KEY }) // /push/vapid-key
      .mockRejectedValueOnce(new Error('server error')); // POST /push/subscriptions
    const { enablePush } = await import('./pushClient');

    await expect(enablePush()).resolves.toEqual({ ok: false, reason: expect.any(String) });
  });

  it('resolves { ok: true } on the full happy path', async () => {
    const registration = makeRegistration({ subscription: null });
    installFullSupport({ registration });
    vi.mocked(api)
      .mockResolvedValueOnce({ publicKey: APPLICATION_SERVER_KEY })
      .mockResolvedValueOnce({ ok: true });
    const { enablePush } = await import('./pushClient');

    await expect(enablePush()).resolves.toEqual({ ok: true });
  });
});

describe('disablePush', () => {
  it('resolves { ok: true } for an unsupported browser', async () => {
    const { disablePush } = await import('./pushClient');
    await expect(disablePush()).resolves.toEqual({ ok: true });
  });

  it('resolves { ok: true } when there is no subscription to remove', async () => {
    installFullSupport({ registration: makeRegistration({ subscription: null }) });
    const { disablePush } = await import('./pushClient');
    await expect(disablePush()).resolves.toEqual({ ok: true });
  });

  it('resolves { ok: false } instead of throwing when the unregister-POST fails', async () => {
    installFullSupport({ registration: makeRegistration() });
    vi.mocked(api).mockRejectedValue(new Error('server error'));
    const { disablePush } = await import('./pushClient');

    await expect(disablePush()).resolves.toEqual({ ok: false, reason: expect.any(String) });
  });

  it('resolves { ok: false } when getRegistration itself throws', async () => {
    installServiceWorker({ getRegistration: vi.fn().mockRejectedValue(new Error('boom')) });
    vi.stubGlobal('PushManager', function PushManager() {});
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission: vi.fn() });
    const { disablePush } = await import('./pushClient');

    await expect(disablePush()).resolves.toEqual({ ok: false, reason: expect.any(String) });
  });
});

describe('pushEnabled', () => {
  it('resolves false, never rejects, for an unsupported browser', async () => {
    const { pushEnabled } = await import('./pushClient');
    await expect(pushEnabled()).resolves.toBe(false);
  });

  it('resolves false when the registration lookup throws', async () => {
    installServiceWorker({ getRegistration: vi.fn().mockRejectedValue(new Error('boom')) });
    vi.stubGlobal('PushManager', function PushManager() {});
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission: vi.fn() });
    const { pushEnabled } = await import('./pushClient');

    await expect(pushEnabled()).resolves.toBe(false);
  });

  it('resolves true when a subscription exists', async () => {
    installFullSupport({ registration: makeRegistration() });
    const { pushEnabled } = await import('./pushClient');

    await expect(pushEnabled()).resolves.toBe(true);
  });
});
