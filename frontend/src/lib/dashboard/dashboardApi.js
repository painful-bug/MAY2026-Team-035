import { api } from '../api/client.js';
import { subscribeToStream } from '../realtime/eventStream.js';

export const getDashboardSnapshot = () => api('/dashboard/snapshot');

// Which frames mean "the admin projection may have moved". Everything else on
// the stream is addressed elsewhere: `notification.created` to the bell,
// `message.created` to the chat dock, and re-snapshotting the whole admin
// dashboard for either would be a large read for a change it does not show.
const SNAPSHOT_TOPICS = new Set([
  'dashboard.refresh',
  'access_request.created',
  'access_request.decided',
  'work_order.changed',
  'amenity.changed',
  // The unnamed frame — a proxy that stripped the event name. Unclassifiable,
  // so it is treated as the broad case.
  'message',
]);

/**
 * The admin portal's listener, kept in its own shape because
 * `DashboardDataBootstrap` hydrates a zustand projection rather than a React
 * Query cache, and is the one live-update consumer that is not an invalidation.
 *
 * It no longer opens its own `EventSource`: it subscribes to the tab's shared
 * one, so an admin who also has the bell and the chat dock mounted holds one
 * connection rather than three.
 */
export function subscribeToDashboard(onChange) {
  return subscribeToStream((frame) => {
    if (frame.resync || SNAPSHOT_TOPICS.has(frame.topic)) onChange(frame);
  });
}
