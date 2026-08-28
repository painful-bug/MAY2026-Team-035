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
  constructor(url) {
    this.url = url;
    this.closed = false;
    this.listeners = new Map();
    instances.push(this);
  }

  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }

  close() {
    this.closed = true;
  }

  /** Drive the fake the way the browser would. */
  fire(type, data) {
    for (const listener of this.listeners.get(type) || []) {
      listener(data === undefined ? { type } : { type, data });
    }
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
