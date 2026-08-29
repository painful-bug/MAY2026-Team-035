// The tab's ONE connection to `GET /api/v1/events`.
//
// Before this module there were two openers — `features/resident/residentEvents.js`
// (mounted per resident page) and `lib/dashboard/dashboardApi.js` (mounted by
// `DashboardDataBootstrap` in the admin portal) — and the C2/C3 wiring would
// have added a third and a fourth, because `NotificationBell` and `ChatDock`
// mount in *every* portal including admin. Four `EventSource` objects is four
// server-side asyncio tasks and four outbox fan-outs per open tab, for one
// stream of frames that every listener wants a slice of.
//
// So: one lazily-opened, ref-counted `EventSource`, and a fan-out in the
// browser. The stream opens on the first subscriber and closes on the last, so
// a signed-out tab (nothing mounted) still holds nothing open.
//
// `EventSource` is used directly rather than through `api()` for the reason
// `residentEvents.js` gave: the session is the same-origin cookie `client.js`
// already sends, `EventSource` carries it without being told to, and `api()`
// would try to JSON-decode a stream that never ends.
//
// **A frame is a hint, never truth** (docs/ARCHITECTURE.md). Delivery is
// at-most-once. Nothing here returns a payload for rendering: a subscriber gets
// `{ topic, kind, resync }` — enough to decide *which read is stale*, and
// nothing that could be mistaken for the read itself.

export const STREAM_URL = '/api/v1/events';

// `EventSource` only routes a *named* frame to a listener registered for that
// exact name; a named frame does NOT also arrive as `message`. So every topic
// the server can emit has to be listed here or it is silently dropped.
//
// Topics and audiences, from docs/ARCHITECTURE.md §Live updates:
//   dashboard.refresh        role {admin, manager}
//   access_request.created   role {admin, manager}
//   access_request.decided   role {admin, manager}
//   notification.created     the one recipient (member)
//   work_order.changed       community
//   amenity.changed          community
//   message.created          the recipient membership (member)
//   stream.resync            the affected connection — "you have a gap"
export const STREAM_TOPICS = Object.freeze([
  'dashboard.refresh',
  'access_request.created',
  'access_request.decided',
  'notification.created',
  'work_order.changed',
  'amenity.changed',
  'message.created',
  'stream.resync',
]);

/**
 * Reopen backoff, for the one error `EventSource` does not retry itself.
 *
 * An HTTP error *response* (403 for a signed-in-but-unapproved session, any
 * 5xx) is fatal to an `EventSource`: the browser fires `error` once, parks
 * `readyState` at `CLOSED`, and never tries again. Before this the tab's
 * realtime simply died there — the membership approval that arrives seconds
 * later has nowhere to land, and only a full unmount/remount of every
 * subscriber would have rebuilt the connection.
 */
const REOPEN_BASE_MS = 5_000;
const REOPEN_CAP_MS = 60_000;

/** Subscriptions, as wrapper objects so two identical callbacks still count twice. */
const subscribers = new Set();
/** Connection-state watchers, for `useSseFallbackInterval`. */
const stateWatchers = new Set();

let source = null;
let live = false;
let reopenTimer = null;
let reopenDelay = REOPEN_BASE_MS;

function setLive(next) {
  if (live === next) return;
  live = next;
  for (const watcher of [...stateWatchers]) {
    try {
      watcher.fn();
    } catch {
      // A watcher that throws must not stop the others from being told.
    }
  }
}

/**
 * Turn one raw SSE event into the frame subscribers see.
 *
 * `topic` comes from the registration rather than `event.type` so that a
 * listener invoked with no event object at all (a stub, a polyfill that passes
 * only data) still reports the topic it was registered under.
 */
function toFrame(topic, event) {
  let payload = {};
  try {
    payload = JSON.parse(event?.data || '{}');
  } catch {
    payload = {};
  }
  return {
    topic: topic || event?.type,
    kind: payload?.kind,
    resync: payload?.resync === true,
  };
}

function deliver(topic, event) {
  const frame = toFrame(topic, event);
  for (const subscriber of [...subscribers]) {
    try {
      subscriber.fn(frame);
    } catch {
      // One portal's mapper throwing must not cost every other listener its
      // frame — and the frame is only a hint, so swallowing is survivable.
    }
  }
}

/**
 * `EventSource.CLOSED` — read off the global so a polyfill that renumbers the
 * states is still understood, with the spec's 2 as the fallback.
 *
 * The fallback matters for the negative case as much as the positive one: a
 * stub or a polyfill that carries no `readyState` at all must read as "not
 * fatal", never as "equal to undefined".
 */
function closedReadyState() {
  const declared = typeof EventSource === 'undefined' ? undefined : EventSource.CLOSED;
  return typeof declared === 'number' ? declared : 2;
}

/** Cancel a scheduled reopen. Safe to call when nothing is pending. */
function cancelReopen() {
  if (reopenTimer === null) return;
  clearTimeout(reopenTimer);
  reopenTimer = null;
}

/** Let go of a dead handle without touching the reopen schedule. */
function discardSource() {
  if (!source) return;
  try {
    source.close();
  } catch {
    // Already dead. Nothing to do.
  }
  source = null;
  setLive(false);
}

/**
 * Queue the reopen the browser will not do.
 *
 * Only while something is listening: a signed-out tab holds nothing open, and
 * that promise would be worth little if a fatal 403 on the way out left a timer
 * behind to reopen the stream nobody wants.
 */
function scheduleReopen() {
  if (reopenTimer !== null) return;
  if (subscribers.size === 0) return;

  const delay = reopenDelay;
  reopenDelay = Math.min(reopenDelay * 2, REOPEN_CAP_MS);
  reopenTimer = setTimeout(() => {
    reopenTimer = null;
    if (subscribers.size === 0) return;
    open();
  }, delay);
}

function open() {
  if (source) return;
  if (typeof EventSource === 'undefined') {
    // jsdom, an old browser, a locked-down webview. Not an error state on
    // screen: the queries underneath have their own, and `sseFallbackInterval`
    // below turns this into the degraded poll.
    setLive(false);
    return;
  }
  try {
    source = new EventSource(STREAM_URL);
  } catch {
    source = null;
    setLive(false);
    return;
  }

  // The handle this listener set belongs to. A dead connection can fire a late
  // `error` after it has been replaced; that one must not close the live one.
  const instance = source;

  instance.addEventListener('open', () => {
    if (source !== instance) return;
    // A connection that got as far as `open` is a working one, so the next
    // fatal close starts its backoff from 5 s again rather than from wherever
    // the last outage climbed to.
    reopenDelay = REOPEN_BASE_MS;
    setLive(true);
  });
  instance.addEventListener('error', () => {
    if (source !== instance) return;
    setLive(false);
    // Transient: `EventSource` retries on its own; `readyState` goes back to
    // CONNECTING and `open` fires again. Until it does the tab is degraded,
    // which is exactly what the fallback poll is for.
    if (instance.readyState !== closedReadyState()) return;
    // Fatal: an HTTP error response. The browser is done with this handle, so
    // drop it and build a new one after the backoff.
    discardSource();
    scheduleReopen();
  });

  for (const topic of STREAM_TOPICS) {
    instance.addEventListener(topic, (event) => deliver(topic, event));
  }
  // The unnamed frame — what a proxy that strips the event name leaves behind.
  instance.addEventListener('message', (event) => deliver(undefined, event));
}

function close() {
  cancelReopen();
  reopenDelay = REOPEN_BASE_MS;
  discardSource();
}

/**
 * Listen to the shared stream.
 *
 * @param {(frame: {topic?: string, kind?: string, resync?: boolean}) => void} fn
 * @returns {() => void} unsubscribe; the connection closes with the last one.
 */
export function subscribeToStream(fn) {
  const entry = { fn };
  subscribers.add(entry);
  if (subscribers.size === 1) open();
  return () => {
    if (!subscribers.delete(entry)) return;
    if (subscribers.size === 0) close();
  };
}

/**
 * Watch whether the stream is currently carrying frames.
 * Shaped for `useSyncExternalStore`: the callback takes no argument.
 *
 * @param {() => void} fn
 * @returns {() => void} unsubscribe
 */
export function subscribeToStreamState(fn) {
  const entry = { fn };
  stateWatchers.add(entry);
  return () => stateWatchers.delete(entry);
}

/** True only between `open` and the next `error`/`close`. */
export function isStreamLive() {
  return live;
}

/**
 * Test seam: forget the connection and every listener.
 *
 * `close()` carries the rest of the state with it — the pending reopen timer is
 * cancelled and the backoff goes back to 5 s — so one test's outage cannot set
 * the next one's delay.
 */
export function __resetStreamForTests() {
  subscribers.clear();
  stateWatchers.clear();
  close();
  live = false;
}
