import { describe, expect, it } from 'vitest';
import { queriesForEvent, residentKeys } from './residentEvents';

// The mapping is the only part of the live-update wiring worth a test: the hook
// around it is an `EventSource` and two `addEventListener` calls, and a mock for
// that would test the mock. What can actually be got wrong is which read a frame
// makes stale — and the failure is silent, a screen that quietly stops updating.

const has = (keys, key) =>
  keys.some((entry) => JSON.stringify(entry) === JSON.stringify(key));

describe('queriesForEvent', () => {
  it('re-reads everything on a resync, which is the one frame with no domain event behind it', () => {
    const keys = queriesForEvent({ topic: 'stream.resync', resync: true });
    expect(has(keys, residentKeys.all)).toBe(true);
    expect(has(keys, ['notifications'])).toBe(true);
  });

  it('treats a dashboard.refresh frame as the same instruction', () => {
    expect(has(queriesForEvent({ topic: 'dashboard.refresh' }), residentKeys.all)).toBe(true);
  });

  it('always stales the snapshot and the bell, because every notification is on both', () => {
    const keys = queriesForEvent({ topic: 'notification.created', kind: 'notice.published' });
    expect(has(keys, residentKeys.snapshot())).toBe(true);
    expect(has(keys, ['notifications'])).toBe(true);
    expect(has(keys, residentKeys.complaintList())).toBe(false);
  });

  it('stales the complaint list for a complaint event', () => {
    const keys = queriesForEvent({ topic: 'notification.created', kind: 'complaint.resolved' });
    expect(has(keys, residentKeys.complaintList())).toBe(true);
    expect(has(keys, residentKeys.scheduleAll())).toBe(false);
  });

  it('stales the proposed visit as well for a work-order event', () => {
    const keys = queriesForEvent({
      topic: 'notification.created',
      kind: 'work_order.schedule_requested',
    });
    expect(has(keys, residentKeys.scheduleAll())).toBe(true);
    expect(has(keys, residentKeys.complaintList())).toBe(true);
  });

  it('still refreshes the snapshot for a kind nobody has taught it', () => {
    const keys = queriesForEvent({ topic: 'notification.created', kind: 'something.new' });
    expect(has(keys, residentKeys.snapshot())).toBe(true);
    expect(keys).toHaveLength(2);
  });

  it('survives a frame with no payload at all', () => {
    expect(has(queriesForEvent(), residentKeys.snapshot())).toBe(true);
    expect(has(queriesForEvent({ topic: 'message' }), residentKeys.snapshot())).toBe(true);
  });

  it('scopes a complaint detail under the same prefix the list uses', () => {
    // `['resident','complaint',id]` must not be caught by the list's prefix, or
    // marking one thread read would refetch every open detail on the screen.
    expect(residentKeys.complaint('c1')[1]).not.toBe(residentKeys.complaintList()[1]);
  });
});
