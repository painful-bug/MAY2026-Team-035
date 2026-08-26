import { describe, expect, it } from 'vitest';

import {
  ALL_QUERIES,
  queriesForFrame,
  SSE_FALLBACK_INTERVAL_MS,
  sseFallbackInterval,
} from './frameQueries.js';
import {
  CHAT_EVENT_MAP,
  MANAGER_EVENT_MAP,
  NOTIFICATION_EVENT_MAP,
  WORKER_EVENT_MAP,
} from './portalMaps.js';

// The mapping is the only part of the live-update wiring worth a test: the hook
// around it is `subscribeToStream` and a `for` loop, and a mock for that would
// test the mock. What can actually be got wrong is which read a frame makes
// stale — and the failure is silent, a screen that quietly stops updating.

const has = (keys, key) => keys.some((entry) => JSON.stringify(entry) === JSON.stringify(key));

const WORKER_SNAPSHOT = ['worker-snapshot'];
const OPEN_JOBS = ['worker-open-jobs'];
const TRIAGE = ['supervisor-triage'];
const WORK_ORDERS = ['work-orders'];
const DEPARTMENTS = ['departments'];
const HIRING = ['hiring'];
const NOTIFICATIONS = ['notifications'];
const DM_THREADS = ['dm-threads'];
const DM_THREAD = ['dm-thread'];

describe('queriesForFrame', () => {
  const MAP = {
    always: [['always']],
    resync: [['everything']],
    topics: { 'thing.changed': [['thing']] },
    kinds: { thing: [['thing']], other: [['other']] },
  };

  it('answers a resync with the resync group and nothing else', () => {
    expect(queriesForFrame({ topic: 'stream.resync', resync: true }, MAP)).toEqual([['everything']]);
    expect(queriesForFrame({ topic: 'stream.resync' }, MAP)).toEqual([['everything']]);
    // The flag alone is enough: the server sets it on `dashboard.refresh` for
    // an admin and on `stream.resync` for everybody else.
    expect(queriesForFrame({ topic: 'dashboard.refresh', resync: true }, MAP)).toEqual([
      ['everything'],
    ]);
  });

  it('falls back to `always` for a resync when the map names no resync group', () => {
    expect(queriesForFrame({ resync: true }, { always: [['a']] })).toEqual([['a']]);
  });

  it('adds a named topic to `always`', () => {
    expect(queriesForFrame({ topic: 'thing.changed' }, MAP)).toEqual([['always'], ['thing']]);
  });

  it('costs only `always` for a topic nobody named', () => {
    expect(queriesForFrame({ topic: 'nobody.knows' }, MAP)).toEqual([['always']]);
  });

  it('reads the kind family, and only on the topic that carries one', () => {
    expect(queriesForFrame({ topic: 'notification.created', kind: 'other.happened' }, MAP)).toEqual([
      ['always'],
      ['other'],
    ]);
    // A `kind` riding on a topic that does not carry one is ignored rather
    // than trusted: only `notification.created` has that field.
    expect(queriesForFrame({ topic: 'thing.changed', kind: 'other.happened' }, MAP)).toEqual([
      ['always'],
      ['thing'],
    ]);
  });

  it('survives an unnamed frame, an unknown kind and no frame at all', () => {
    expect(queriesForFrame({ topic: 'message' }, MAP)).toEqual([['always']]);
    expect(queriesForFrame({ topic: 'message', kind: 'other.x' }, MAP)).toEqual([
      ['always'],
      ['other'],
    ]);
    expect(queriesForFrame({ topic: 'notification.created', kind: 'nobody.knows' }, MAP)).toEqual([
      ['always'],
    ]);
    expect(queriesForFrame()).toEqual([]);
    expect(queriesForFrame({}, MAP)).toEqual([['always']]);
  });

  it('never repeats a key, so one frame is never two refetches of one query', () => {
    const map = { always: [['a']], topics: { 't': [['a'], ['b']] }, kinds: {} };
    expect(queriesForFrame({ topic: 't' }, map)).toEqual([['a'], ['b']]);
  });
});

describe('the worker portal map', () => {
  it('stales the board, the calendar and the triage queue on work_order.changed', () => {
    const keys = queriesForFrame({ topic: 'work_order.changed' }, WORKER_EVENT_MAP);
    expect(has(keys, OPEN_JOBS)).toBe(true);
    expect(has(keys, TRIAGE)).toBe(true);
    expect(has(keys, WORK_ORDERS)).toBe(true);
    expect(has(keys, WORKER_SNAPSHOT)).toBe(true);
  });

  it('stales the triage queue for a complaint notification', () => {
    const keys = queriesForFrame(
      { topic: 'notification.created', kind: 'complaint.reassigned' },
      WORKER_EVENT_MAP,
    );
    expect(has(keys, TRIAGE)).toBe(true);
    expect(has(keys, WORKER_SNAPSHOT)).toBe(true);
    expect(has(keys, OPEN_JOBS)).toBe(false);
  });

  it('re-reads everything on a resync', () => {
    expect(queriesForFrame({ topic: 'stream.resync' }, WORKER_EVENT_MAP)).toEqual([ALL_QUERIES]);
  });

  it('answers an amenity frame with the snapshot alone — this portal books nothing', () => {
    expect(queriesForFrame({ topic: 'amenity.changed' }, WORKER_EVENT_MAP)).toEqual([
      WORKER_SNAPSHOT,
    ]);
  });
});

describe('the manager portal map', () => {
  it('treats dashboard.refresh as "your department screens moved"', () => {
    const keys = queriesForFrame({ topic: 'dashboard.refresh' }, MANAGER_EVENT_MAP);
    expect(has(keys, DEPARTMENTS)).toBe(true);
    expect(has(keys, WORK_ORDERS)).toBe(true);
    expect(has(keys, HIRING)).toBe(true);
    // Not the whole cache: that is what `stream.resync` is for, and this frame
    // fires on every row change across twelve tables.
    expect(has(keys, ALL_QUERIES)).toBe(false);
  });

  it('re-reads everything on a resync, because its reads are too scattered to list', () => {
    expect(queriesForFrame({ resync: true }, MANAGER_EVENT_MAP)).toEqual([ALL_QUERIES]);
  });

  it('stales hiring on an access-request frame', () => {
    expect(has(queriesForFrame({ topic: 'access_request.created' }, MANAGER_EVENT_MAP), HIRING))
      .toBe(true);
  });
});

describe('the bell and the dock maps', () => {
  it('gives the bell exactly its one key on notification.created', () => {
    expect(queriesForFrame({ topic: 'notification.created' }, NOTIFICATION_EVENT_MAP)).toEqual([
      NOTIFICATIONS,
    ]);
  });

  it('leaves the bell alone on dashboard.refresh, which is other people writing', () => {
    expect(queriesForFrame({ topic: 'dashboard.refresh' }, NOTIFICATION_EVENT_MAP)).toEqual([]);
    expect(queriesForFrame({ topic: 'work_order.changed' }, NOTIFICATION_EVENT_MAP)).toEqual([]);
  });

  it('still re-reads the bell on a resync', () => {
    expect(queriesForFrame({ resync: true }, NOTIFICATION_EVENT_MAP)).toEqual([NOTIFICATIONS]);
  });

  it('stales the mailbox and every open thread on message.created', () => {
    const keys = queriesForFrame({ topic: 'message.created' }, CHAT_EVENT_MAP);
    expect(has(keys, DM_THREADS)).toBe(true);
    // A prefix, so `['dm-thread', id]` is caught whichever thread is open.
    expect(has(keys, DM_THREAD)).toBe(true);
  });

  it('leaves the dock alone on frames that are not about messages', () => {
    expect(queriesForFrame({ topic: 'dashboard.refresh' }, CHAT_EVENT_MAP)).toEqual([]);
    expect(queriesForFrame({ topic: 'amenity.changed' }, CHAT_EVENT_MAP)).toEqual([]);
  });
});

describe('sseFallbackInterval', () => {
  it('disables polling while the stream is live — the frames are the refresh', () => {
    expect(sseFallbackInterval(true)).toBe(false);
  });

  it('polls slowly, and only slowly, while the stream is not', () => {
    expect(sseFallbackInterval(false)).toBe(SSE_FALLBACK_INTERVAL_MS);
    expect(SSE_FALLBACK_INTERVAL_MS).toBe(5 * 60_000);
  });

  it('takes an override, so a caller can be more patient but never faster by accident', () => {
    expect(sseFallbackInterval(false, 90_000)).toBe(90_000);
    expect(sseFallbackInterval(true, 90_000)).toBe(false);
  });
});

describe('ALL_QUERIES', () => {
  it('is the empty prefix, which react-query matches against every key', () => {
    expect(ALL_QUERIES).toEqual([]);
  });
});
