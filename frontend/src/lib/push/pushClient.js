import { api } from '../api/client';

// Web Push, from the browser side. The server half has existed since the
// resident build -- `0030` stores the subscriptions and `app/core/push.py`
// sends -- and the only missing piece was `public/sw.js` and this file.
//
// Every function here is safe to call in a browser that supports none of it.
// Push is a permission the user may simply never grant, so no caller should
// have to guard before asking.

const SW_URL = '/sw.js';

export const pushSupported = () =>
  typeof navigator !== 'undefined' &&
  'serviceWorker' in navigator &&
  typeof window !== 'undefined' &&
  'PushManager' in window &&
  'Notification' in window;

/** Register the service worker. Resolves to null when the browser has none. */
export async function registerServiceWorker() {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return null;
  try {
    return await navigator.serviceWorker.register(SW_URL);
  } catch {
    // A failed registration costs push and an offline reload, and nothing else.
    // It must never take the application down with it.
    return null;
  }
}

// VAPID keys travel as base64url; PushManager.subscribe wants raw bytes.
function decodeKey(base64url) {
  const padded = base64url.padEnd(base64url.length + ((4 - (base64url.length % 4)) % 4), '=');
  const binary = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

/**
 * Ask for permission, subscribe, and register the subscription with the server.
 *
 * Returns `{ ok, reason }` rather than throwing, because every failure here is
 * a thing to tell the user calmly: an unsupported browser, a denied prompt, or
 * a server that has no VAPID key configured.
 */
// `navigator.serviceWorker.ready` never rejects — a service worker that fails
// to activate (or a browser that quietly wedges the registration) leaves that
// promise pending forever, which would hang `enablePush` and the toggle's
// spinner with it. Race it against a bound so a stuck browser still resolves
// `{ ok: false, reason }` like every other failure here.
const READY_TIMEOUT_MS = 10_000;
function withTimeout(promise, ms, reason) {
  let timer;
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => resolve({ __timedOut: true, reason }), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

export async function enablePush() {
  if (!pushSupported()) return { ok: false, reason: 'This browser cannot receive push notifications.' };

  let permission;
  try {
    permission = await Notification.requestPermission();
  } catch {
    return { ok: false, reason: 'Could not ask for notification permission.' };
  }
  if (permission !== 'granted') {
    return { ok: false, reason: 'Notifications are blocked. Allow them in your browser settings.' };
  }

  const registration = await registerServiceWorker();
  if (!registration) return { ok: false, reason: 'Could not start the background worker.' };

  const ready = await withTimeout(
    navigator.serviceWorker.ready,
    READY_TIMEOUT_MS,
    'The background worker took too long to start.'
  );
  if (ready?.__timedOut) return { ok: false, reason: ready.reason };

  let publicKey;
  try {
    ({ publicKey } = await api('/push/vapid-key'));
  } catch {
    return { ok: false, reason: 'Push is not configured on this server yet.' };
  }
  if (!publicKey) return { ok: false, reason: 'Push is not configured on this server yet.' };

  try {
    // A subscription is bound to the key that created it and the protocol has
    // no dual-key period, so a rotated key means an existing subscription is
    // dead rather than stale. Drop it and take a new one.
    const existing = await registration.pushManager.getSubscription();
    if (existing) await existing.unsubscribe();

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: decodeKey(publicKey),
    });

    // Posted exactly as the Push API handed it over. Transcribing the key pair
    // by hand is where `auth` ends up in the `p256dh` field, and that failure
    // looks like a push that silently never decrypts.
    await api('/push/subscriptions', {
      method: 'POST',
      body: JSON.stringify({ ...subscription.toJSON(), userAgent: navigator.userAgent }),
    });
    return { ok: true };
  } catch (error) {
    // `pushManager.subscribe` throws `AbortError` when the push service is
    // unreachable (common on Chromium without a live network path to it), and
    // `getSubscription`/`unsubscribe`/the register call above can each fail
    // in their own way. All of it is the same story to the user: the toggle
    // did not turn on.
    return {
      ok: false,
      reason: error?.name === 'AbortError'
        ? 'The push service could not be reached. Try again shortly.'
        : 'Could not turn on notifications.',
    };
  }
}

/** Stop pushing to this browser. Idempotent — no subscription is success. */
export async function disablePush() {
  if (!pushSupported()) return { ok: true };
  try {
    const registration = await navigator.serviceWorker.getRegistration(SW_URL);
    const subscription = await registration?.pushManager.getSubscription();
    if (!subscription) return { ok: true };
    await api('/push/subscriptions/unregister', {
      method: 'POST',
      body: JSON.stringify({ endpoint: subscription.endpoint }),
    });
    await subscription.unsubscribe();
    return { ok: true };
  } catch {
    // Same contract as enablePush: never throw past this module, even on the
    // way out.
    return { ok: false, reason: 'Could not turn off notifications.' };
  }
}

/** Whether this browser currently holds a subscription. */
export async function pushEnabled() {
  try {
    if (!pushSupported() || Notification.permission !== 'granted') return false;
    const registration = await navigator.serviceWorker.getRegistration(SW_URL);
    return Boolean(await registration?.pushManager.getSubscription());
  } catch {
    return false;
  }
}
