/* HomeBandhu service worker.
 *
 * It exists for one reason: a browser cannot receive a Web Push message
 * without one. `0030` has stored push subscriptions and `app/core/push.py` has
 * been able to send since the resident build; US-2.7 was stuck here, on a file
 * that did not exist.
 *
 * WHAT THIS DELIBERATELY IS NOT. There is no build-time precache manifest and
 * no Workbox. Vite emits content-hashed asset names, so a hand-written manifest
 * is wrong on the next build, and a generated one is a versioning and
 * invalidation problem nobody asked to have. Instead every successful
 * same-origin GET is cached as it happens and the cache is read only when the
 * network fails. The claim that makes is small and true: a reload with no
 * connectivity still boots the app. It is not an offline-first application.
 */

const CACHE = 'homebandhu-runtime-v1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  // Never cache anything that is not a plain same-origin read. An API response
  // served from cache would show a worker yesterday's jobs and call them today's.
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          void caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        // A single-page app asked for a route it has never loaded. The shell is
        // what answers every route, so the shell is the right fallback.
        if (request.mode === 'navigate') {
          const shell = await caches.match('/index.html');
          if (shell) return shell;
        }
        return Response.error();
      })
  );
});

self.addEventListener('push', (event) => {
  // The sender's payload shape is app/core/push.py's; a push with no body at
  // all is still shown, because a silent push is worse than a vague one.
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { body: event.data ? event.data.text() : '' };
  }
  const title = payload.title || 'HomeBandhu';
  event.waitUntil(
    self.registration.showNotification(title, {
      body: payload.body || '',
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      tag: payload.tag || undefined,
      data: { url: payload.url || '/' },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = event.notification.data?.url || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      // Focus a tab that is already open rather than opening a second one.
      for (const client of windows) {
        if (client.url.includes(target) && 'focus' in client) return client.focus();
      }
      const open = windows.find((client) => 'focus' in client);
      if (open) {
        void open.focus();
        return open.navigate ? open.navigate(target) : undefined;
      }
      return self.clients.openWindow(target);
    })
  );
});
