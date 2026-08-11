import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';

// Live updates for the resident portal, and the query keys they invalidate.
//
// `GET /api/v1/events` is server-sent events over the browser's own
// `EventSource` (API.md §5.1). The session is the cookie `client.js` already
// sends on every call — same origin, so `EventSource` carries it without being
// told to, and no token reaches the browser. That is why this file opens the
// stream directly instead of going through `api()`, which parses JSON and would
// try to decode a stream that never ends.
//
// **A resident never receives `dashboard.refresh`.** That frame means "re-read
// the admin snapshot", which a resident would be refused, so the two frames that
// actually arrive here are `notification.created` (audience `member`, one row
// addressed to this person) and `stream.resync` (this connection fell behind).
// The payload is a hint and never truth — every branch below re-reads.

export const residentKeys = {
  all: ['resident'],
  snapshot: () => ['resident', 'snapshot'],
  /** The whole complaint list, whatever filters are on it. */
  complaintList: () => ['resident', 'complaints'],
  complaints: (params = {}) => ['resident', 'complaints', params],
  complaint: (complaintId) => ['resident', 'complaint', complaintId],
  /** Every proposed visit; react-query matches this as a prefix. */
  scheduleAll: () => ['resident', 'schedule'],
  schedule: (complaintId) => ['resident', 'schedule', complaintId],
  directory: () => ['resident', 'directory'],
};

// The bell's key, which lives in `features/notifications`. Named here rather
// than imported so this module has one import and one job; if the bell ever
// renames its key this is the line that has to move with it.
const NOTIFICATIONS = ['notifications'];

/**
 * Which queries one frame makes stale. Pure, and the unit under test.
 *
 * Every notification changes the badge and the activity strip, so the snapshot
 * is on every branch. What the `kind` decides is the *extra* read: a complaint
 * event also stales the list, a work-order event also stales the proposed
 * visit. An unrecognised kind still refreshes the snapshot — the feed is on it,
 * so a kind added by a later build step is visible without a change here.
 *
 * @param {{topic?: string, kind?: string, resync?: boolean}} frame
 * @returns {Array<Array<string>>} query keys, each an invalidation prefix
 */
export function queriesForEvent(frame = {}) {
  const { topic, kind, resync } = frame;

  // "You have a gap, re-read everything." The only frame that can arrive with
  // no preceding domain event, and the one every client must handle.
  if (resync || topic === 'stream.resync' || topic === 'dashboard.refresh') {
    return [residentKeys.all, NOTIFICATIONS];
  }

  const keys = [residentKeys.snapshot(), NOTIFICATIONS];

  if (topic && topic !== 'notification.created') {
    // A topic this portal was not written for. The snapshot is still the
    // honest answer: it carries the feed, and re-reading it is cheap.
    return keys;
  }

  const family = String(kind || '').split('.')[0];
  if (family === 'complaint') {
    keys.push(residentKeys.complaintList());
  } else if (family === 'work_order') {
    // A work order is a visit on a complaint: both the thread and the proposal
    // the resident is being asked about can have moved.
    keys.push(residentKeys.complaintList(), residentKeys.scheduleAll());
  }

  return keys;
}

/**
 * Keep the resident's screen current while it is open.
 *
 * Mounted per page rather than in the layout, because only one resident page
 * renders at a time and a hook in the layout would be a second file the two
 * phase-6 wiring tasks both edit. Closing the stream on unmount is what stops a
 * navigation leaving a connection behind.
 *
 * The stream failing is not an error state on screen: the queries below it have
 * their own, and a browser with no backend at all should show the page's empty
 * state rather than a banner about a transport.
 */
export function useResidentLiveUpdates() {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (typeof EventSource === 'undefined') return undefined;

    let source;
    try {
      source = new EventSource('/api/v1/events');
    } catch {
      return undefined;
    }

    const apply = (frame) => {
      for (const queryKey of queriesForEvent(frame)) {
        queryClient.invalidateQueries({ queryKey });
      }
    };

    const handle = (event) => {
      let payload = {};
      try {
        payload = JSON.parse(event.data || '{}');
      } catch {
        payload = {};
      }
      apply({ topic: event.type, kind: payload.kind, resync: payload.resync });
    };

    source.addEventListener('notification.created', handle);
    source.addEventListener('stream.resync', handle);
    // A named frame does not also arrive as `message`; this catches an unnamed
    // one, which is what a proxy that strips the event name leaves behind.
    source.addEventListener('message', handle);

    return () => source.close();
  }, [queryClient]);
}
