import { queriesForFrame } from '../../lib/realtime/frameQueries.js';
import { useLiveUpdates } from '../../lib/realtime/useLiveUpdates.js';

// Live updates for the resident portal, and the query keys they invalidate.
//
// The transport, the ref-counted single `EventSource` and the pure frame →
// keys mapper all moved to `lib/realtime/` when the worker and manager portals
// needed the same three things (C2). What is left here is the part that was
// only ever about residents: `residentKeys`, and the map that says which of
// them a frame stales. The pure-mapper / hook split survives the move —
// `queriesForEvent` below is still a pure function and still the unit under
// test, it just delegates the generic half.
//
// **A resident never receives `dashboard.refresh`.** That frame means "re-read
// the admin snapshot", which a resident would be refused; it is named in the
// map anyway, so a mis-audienced row degrades to a re-read rather than to
// nothing. What actually arrives here is `notification.created` (audience
// `member`, one row addressed to this person), the two community-audience
// topics `work_order.changed` and `amenity.changed`, and `stream.resync` (this
// connection fell behind). The payload is a hint and never truth — every
// branch below re-reads.

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
  /** The three amenity reads on the booking screen. */
  amenitiesAvailable: () => ['resident', 'amenities-available'],
  amenityBookings: () => ['resident', 'amenity-bookings'],
  /** Prefix: the conflicts query keys itself by amenity, dates and slots. */
  amenityConflicts: () => ['resident', 'amenity-booking-conflicts'],
};

// The bell's key, which lives in `features/notifications`. Named here rather
// than imported so this module has one job; if the bell ever renames its key
// this is the line that has to move with it.
const NOTIFICATIONS = ['notifications'];

/**
 * The resident portal's frame → query-key map.
 *
 * Every notification changes the badge and the activity strip, so the snapshot
 * and the bell are on every branch (`always`). What the topic or the `kind`
 * decides is the *extra* read: a complaint event also stales the list, a
 * work-order event also stales the proposed visit, an amenity event stales the
 * three reads behind the booking form. An unrecognised topic or kind still
 * refreshes the snapshot — the feed is on it, so a kind added by a later build
 * step is visible without a change here.
 *
 * @type {import('../../lib/realtime/frameQueries.js').PortalEventMap}
 */
export const RESIDENT_EVENT_MAP = Object.freeze({
  always: [residentKeys.snapshot(), NOTIFICATIONS],
  resync: [residentKeys.all, NOTIFICATIONS],
  topics: {
    // See the header: a resident should never see this one, and if one arrives
    // the honest reading of it is the resync reading.
    'dashboard.refresh': [residentKeys.all, NOTIFICATIONS],
    // Community-audience. A work order is a visit on a complaint: both the
    // thread and the proposal the resident is being asked about can have moved.
    'work_order.changed': [residentKeys.complaintList(), residentKeys.scheduleAll()],
    // Community-audience, and the reason the booking screen's dead
    // `homebandhu:dashboard-refresh` listener could be deleted: somebody else
    // taking the 6pm slot is exactly this frame.
    'amenity.changed': [
      residentKeys.amenitiesAvailable(),
      residentKeys.amenityBookings(),
      residentKeys.amenityConflicts(),
    ],
  },
  kinds: {
    complaint: [residentKeys.complaintList()],
    work_order: [residentKeys.complaintList(), residentKeys.scheduleAll()],
    amenity: [
      residentKeys.amenitiesAvailable(),
      residentKeys.amenityBookings(),
      residentKeys.amenityConflicts(),
    ],
  },
});

/**
 * Which queries one frame makes stale, for a resident. Pure, and the unit
 * under test.
 *
 * @param {{topic?: string, kind?: string, resync?: boolean}} frame
 * @returns {Array<Array<string>>} query keys, each an invalidation prefix
 */
export function queriesForEvent(frame = {}) {
  return queriesForFrame(frame, RESIDENT_EVENT_MAP);
}

/**
 * Keep the resident's screens current while the portal is open.
 *
 * Mounted once, by `ResidentLayout`. It used to be mounted per page — by
 * `DashboardHome` and `Complaints` — which meant every other resident screen
 * (visitors, amenities, payments, notices) sat on a stream nobody had opened,
 * and a navigation between the two closed one connection to open another.
 */
export function useResidentLiveUpdates() {
  useLiveUpdates(RESIDENT_EVENT_MAP);
}
