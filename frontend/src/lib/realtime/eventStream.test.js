import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  __resetStreamForTests,
  isStreamLive,
  STREAM_TOPICS,
  subscribeToStream,
  subscribeToStreamState,
} from './eventStream.js';

// What is worth testing here is not "does EventSource work" — it is the two
// claims this module makes to the rest of the app: that a tab holds exactly one
// connection however many things listen, and that a frame reaches every
// listener as a hint rather than as data.

let instances;

class FakeEventSource {
  static CONNECTING = 0;

  static OPEN = 1;

  static CLOSED = 2;

  constructor(url) {
    this.url = url;
    this.closed = false;
    this.readyState = FakeEventSource.CONNECTING;
    this.listeners = new Map();
    instances.push(this);
  }

  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  /** Drive the fake the way the browser would. */
  fire(type, data) {
    for (const listener of this.listeners.get(type) || []) {
      listener(data === undefined ? { type } : { type, data });
    }
  }

  /** The handshake succeeded. */
  succeed() {
    this.readyState = FakeEventSource.OPEN;
    this.fire('open');
  }

  /**
   * What an HTTP error *response* does: one `error`, `readyState` parked at
   * CLOSED, and the browser never retries. This is the 403 seen live.
   */
  fail() {
    this.readyState = FakeEventSource.CLOSED;
    this.fire('error');
  }

  /** A dropped connection the browser will retry by itself. */
  drop() {
    this.readyState = FakeEventSource.CONNECTING;
    this.fire('error');
  }
}

beforeEach(() => {
  instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
});

afterEach(() => {
  __resetStreamForTests();
  vi.unstubAllGlobals();
});

describe('the shared stream', () => {
  it('opens one connection for many listeners and closes it with the last one', () => {
    const a = vi.fn();
    const b = vi.fn();

    const stopA = subscribeToStream(a);
    const stopB = subscribeToStream(b);

    expect(instances).toHaveLength(1);
    expect(instances[0].url).toBe('/api/v1/events');

    instances[0].fire('notification.created', '{"kind":"complaint.resolved"}');
    expect(a).toHaveBeenCalledOnce();
    expect(b).toHaveBeenCalledOnce();

    stopA();
    expect(instances[0].closed).toBe(false);
    stopB();
    expect(instances[0].closed).toBe(true);
  });

  it('counts two identical callbacks as two listeners', () => {
    const same = vi.fn();
    const stopOne = subscribeToStream(same);
    const stopTwo = subscribeToStream(same);
    stopOne();
    expect(instances[0].closed).toBe(false);
    stopTwo();
    expect(instances[0].closed).toBe(true);
  });

  it('reopens after the last listener has gone', () => {
    subscribeToStream(vi.fn())();
    subscribeToStream(vi.fn());
    expect(instances).toHaveLength(2);
  });

  it('hands out the topic, the kind and the resync flag, and nothing else', () => {
    const seen = [];
    subscribeToStream((frame) => seen.push(frame));

    instances[0].fire('notification.created', '{"kind":"work_order.claimed","id":"n1"}');
    instances[0].fire('stream.resync', '{"resync":true}');
    instances[0].fire('work_order.changed', 'not json at all');
    instances[0].fire('message');

    expect(seen).toEqual([
      { topic: 'notification.created', kind: 'work_order.claimed', resync: false },
      { topic: 'stream.resync', kind: undefined, resync: true },
      { topic: 'work_order.changed', kind: undefined, resync: false },
      // The unnamed frame keeps the browser's own name for it, which is what
      // every map treats as "topic unknown, answer with the cheap read".
      { topic: 'message', kind: undefined, resync: false },
    ]);
  });

  it('registers every topic the server can emit, including the new three', () => {
    subscribeToStream(vi.fn());
    for (const topic of STREAM_TOPICS) {
      expect(instances[0].listeners.has(topic)).toBe(true);
    }
    expect(STREAM_TOPICS).toContain('work_order.changed');
    expect(STREAM_TOPICS).toContain('amenity.changed');
    expect(STREAM_TOPICS).toContain('message.created');
  });

  it('does not let one listener throwing cost the others their frame', () => {
    const good = vi.fn();
    subscribeToStream(() => {
      throw new Error('mapper blew up');
    });
    subscribeToStream(good);
    instances[0].fire('dashboard.refresh', '{}');
    expect(good).toHaveBeenCalledOnce();
  });
});

describe('connection state', () => {
  it('is degraded until open and again after an error', () => {
    const watcher = vi.fn();
    subscribeToStreamState(watcher);
    subscribeToStream(vi.fn());

    expect(isStreamLive()).toBe(false);

    instances[0].fire('open');
    expect(isStreamLive()).toBe(true);
    expect(watcher).toHaveBeenCalledTimes(1);

    instances[0].fire('error');
    expect(isStreamLive()).toBe(false);
    expect(watcher).toHaveBeenCalledTimes(2);
  });

  it('tells nobody about a state that did not change', () => {
    const watcher = vi.fn();
    subscribeToStreamState(watcher);
    subscribeToStream(vi.fn());
    instances[0].fire('error');
    expect(watcher).not.toHaveBeenCalled();
  });

  it('reports degraded on a browser with no EventSource at all', () => {
    __resetStreamForTests();
    vi.stubGlobal('EventSource', undefined);
    const stop = subscribeToStream(vi.fn());
    expect(isStreamLive()).toBe(false);
    stop();
  });
});

// Proven live on 2026-08-27: a signed-in-but-not-yet-approved session opened
// `GET /api/v1/events`, got a 403, and the tab's realtime was dead until every
// subscriber unmounted and remounted — so the approval seconds later never
// arrived. An HTTP error response parks `readyState` at CLOSED and the browser
// does not retry; that is the one case this module has to retry for itself.
describe('reopening after a fatal close', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('opens a new connection five seconds after an error that closed the stream', () => {
    subscribeToStream(vi.fn());
    expect(instances).toHaveLength(1);

    instances[0].fail();
    expect(instances).toHaveLength(1);

    vi.advanceTimersByTime(4999);
    expect(instances).toHaveLength(1);

    vi.advanceTimersByTime(1);
    expect(instances).toHaveLength(2);
    expect(instances[1].url).toBe('/api/v1/events');
    // The dead handle is let go of, not left holding a listener set.
    expect(instances[0].closed).toBe(true);
  });

  it('doubles the wait on each repeated fatal close and stops doubling at a minute', () => {
    subscribeToStream(vi.fn());

    // 5 s, 10 s, 20 s, 40 s, then the 60 s cap twice over.
    for (const [attempt, delay] of [5_000, 10_000, 20_000, 40_000, 60_000, 60_000].entries()) {
      instances[instances.length - 1].fail();
      vi.advanceTimersByTime(delay - 1);
      expect(instances).toHaveLength(attempt + 1);
      vi.advanceTimersByTime(1);
      expect(instances).toHaveLength(attempt + 2);
    }
  });

  it('starts the backoff over once a connection has actually opened', () => {
    subscribeToStream(vi.fn());

    instances[0].fail();
    vi.advanceTimersByTime(5_000);
    expect(instances).toHaveLength(2);

    // Without the reset this second outage would wait 10 s.
    instances[1].succeed();
    expect(isStreamLive()).toBe(true);

    instances[1].fail();
    expect(isStreamLive()).toBe(false);
    vi.advanceTimersByTime(4_999);
    expect(instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(instances).toHaveLength(3);
  });

  it('drops the pending reopen when the last listener goes', () => {
    const stop = subscribeToStream(vi.fn());
    instances[0].fail();

    stop();

    vi.advanceTimersByTime(120_000);
    expect(instances).toHaveLength(1);
  });

  it('keeps the reopen for the listeners that are still there', () => {
    const stop = subscribeToStream(vi.fn());
    subscribeToStream(vi.fn());
    instances[0].fail();

    stop();

    vi.advanceTimersByTime(5_000);
    expect(instances).toHaveLength(2);
  });

  it('schedules nothing for a transient error the browser retries itself', () => {
    subscribeToStream(vi.fn());

    instances[0].drop();
    expect(isStreamLive()).toBe(false);

    vi.advanceTimersByTime(120_000);
    expect(instances).toHaveLength(1);
    expect(instances[0].closed).toBe(false);
  });
});
