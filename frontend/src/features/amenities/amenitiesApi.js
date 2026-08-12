import { api } from '../../lib/api/client.js';
import { getDashboardSnapshot } from '../../lib/dashboard/dashboardApi.js';

// The admin amenity surface, in one place.
//
// Same shape as `features/hiring/hiringApi.js` and
// `features/resident/residentApi.js`: no state, no caching, no error
// translation. react-query owns all three, and the four amenity screens above
// are its only callers.
//
// It sits beside `services/amenitiesService.js` rather than inside it. That
// module is the *catalogue* — create, update, delete, settings — and it is
// already wired to `POST/PUT/DELETE /dashboard/amenities`. This one is the
// booking, approval, ledger and report surface that migration `0016` shipped
// and that nothing called until now.
//
// ---------------------------------------------------------------------------
// The four money verbs, because three of them look interchangeable and are not
// (docs/API.md §10). Getting these the wrong way round moves the wrong money.
//
//   payments — money the community RECEIVED, recorded against one existing
//              charge (`booking` | `deposit` | `additional` |
//              `late_cancellation`). It settles a debt; it never creates one.
//              Idempotent on `paymentReference`, and an overpayment is a `409`
//              rather than a clamp.
//
//   charges  — money the resident now OWES that nobody had billed yet:
//              housekeeping after the event, a late-cancellation fee. It adds
//              to `additionalCharges`, and a second charge of a kind ADDS to
//              the first rather than replacing it.
//
//   damage   — money taken OUT of the deposit already held. Not a charge: it
//              reduces what is refundable rather than raising what is owed,
//              and Postgres caps it at what is left.
//
//   refund   — giving the rest of the deposit back. **No amount**: it is
//              deposit paid − damage taken − already refunded, computed by the
//              database, because a refund whose size the caller chooses is a
//              refund somebody can ask to be bigger.
//
// None of these is the resident's `POST /amenity-bookings/{id}/pay`, which is
// the payment simulator (§14) and belongs to the resident portal. That one is
// a resident initiating a payment against their own booking through a gateway;
// these are an administrator recording what already happened at the desk. They
// deliberately do not share an endpoint, and nothing on an admin screen calls
// the simulator — which is why no `idempotencyKey` and no `PaymentOutcome`
// branch appears anywhere in this module.
// ---------------------------------------------------------------------------

const post = (path, body = {}) =>
  api(path, { method: 'POST', body: JSON.stringify(body) });

const query = (params) => {
  const pairs = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== ''
  );
  const search = new URLSearchParams(pairs).toString();
  return search ? `?${search}` : '';
};

export const amenitiesApi = {
  // --- the day timeline ------------------------------------------------------
  /**
   * One amenity's occupied days. `timelineOnly` (default true on the server)
   * drops pending, rejected and cancelled days so the timeline paints only what
   * actually holds the room.
   *
   * The cleaning buffer is NOT in the response: `amenityTimeline` synthesises
   * buffers at render time from each booking's end and the amenity's buffer,
   * and a server-sent buffer would give one block two sources.
   */
  bookings: (amenityId, params = {}) =>
    api(`/amenities/${amenityId}/bookings${query(params)}`),

  /**
   * The admin's Create Booking modal. Confirmed on creation, never pending.
   *
   * `membershipId` names the resident and is the MEMBERSHIP id, not the profile
   * id — the flat is resolved from their residency rather than sent, so the
   * ledger charges a unit that exists. `chargeOverride` replaces the booking
   * fee and nothing else: a waived fee does not waive the deposit, which is
   * coming back. `null` means "use the amenity's fee"; `0` means "free".
   *
   * Opening hours, closed days and the advance window are deliberately not
   * applied — an admin booking the hall out of hours is doing their job — but
   * the conflict rules are, so a taken slot is a `409`.
   */
  createBooking: (amenityId, payload) =>
    post(`/amenities/${amenityId}/bookings`, payload),

  /** Reserve a slot for maintenance. Always exclusive, no flat, no charges. */
  blockSlot: (amenityId, payload) => post(`/amenities/${amenityId}/blocks`, payload),

  /**
   * Cancel selected days. Serves residents and admins from one route: which of
   * the two you are is read from the token, so there is nothing in the body to
   * lie about. All-or-nothing — one ineligible day fails the whole call.
   */
  cancelDays: (payload) => post('/amenity-bookings/cancel', payload),

  /**
   * Override a booking the resident still wants. Distinct from an ordinary
   * cancellation because the ledger records who did it and why, and because the
   * deposit becomes refundable as a result — which the ledger derives.
   */
  forceCancel: (occurrenceId, payload) =>
    post(`/amenity-bookings/${occurrenceId}/force-cancel`, payload),

  // --- approvals -------------------------------------------------------------
  /**
   * The approvals queue — **one row per request, not per day**. `dayCount` and
   * `dates` say how much one decision covers.
   *
   * `outstandingDues` on a row is the FLAT's balance, not the person's: our
   * invoices attach to the unit and carry no person (DECISIONS_NEEDED E18).
   */
  approvals: (amenityId, params = {}) =>
    api(`/amenities/${amenityId}/approvals${query(params)}`),

  /**
   * Approve or reject a whole request. **The id is `bookingSeriesId`, not the
   * row's `id`** — the row is one day and the decision is the request's. Days
   * the resident already withdrew keep their cancellation.
   */
  approve: (seriesId) => post(`/amenity-bookings/${seriesId}/approve`),
  reject: (seriesId, payload) => post(`/amenity-bookings/${seriesId}/reject`, payload),

  // --- the ledger ------------------------------------------------------------
  /**
   * One amenity's transactions. Every figure is derived from the charges and
   * the append-only event stream — nothing stores a balance — and
   * `availableActions` is computed from the same rules the write endpoints
   * enforce, so a button drawn from it is a button the API will honour.
   */
  ledger: (amenityId, params = {}) =>
    api(`/amenities/${amenityId}/ledger${query(params)}`),
  /**
   * The eight cards above the table, aggregated by Postgres over EVERY
   * transaction for the amenity — so they do not change when the table pages,
   * which is exactly what a client-side reduce over the current page got wrong.
   */
  ledgerSummary: (amenityId) => api(`/amenities/${amenityId}/ledger/summary`),

  /** Money received. `{ amount, chargeType, method?, paymentReference?, notes? }`. */
  recordPayment: (occurrenceId, payload) =>
    post(`/amenity-bookings/${occurrenceId}/payments`, payload),
  /** Money now owed. `{ amount, chargeType, description? }` — adds, never replaces. */
  addCharge: (occurrenceId, payload) =>
    post(`/amenity-bookings/${occurrenceId}/charges`, payload),
  /** Money out of the deposit. `{ amount, reason, notes? }` — capped in Postgres. */
  deductDamage: (occurrenceId, payload) =>
    post(`/amenity-bookings/${occurrenceId}/damage`, payload),
  /** The deposit back. `{ reason?, notes? }` — **no amount**, see the note above. */
  refundDeposit: (occurrenceId, payload) =>
    post(`/amenity-bookings/${occurrenceId}/refund`, payload),

  // --- reports ---------------------------------------------------------------
  /**
   * `rows` is a page; `kpis` is a database aggregate over every matching row.
   * That split is the point — a KPI that describes one page is not a KPI, and
   * one of these is labelled "Total Revenue". `options.bookingStatuses` is the
   * lifecycle's fixed vocabulary, so a filter option does not vanish the moment
   * nothing currently has that status.
   */
  report: (params = {}) => api(`/amenity-reports${query(params)}`),

  // --- the resident picker ---------------------------------------------------
  /**
   * Who the Create Booking modal may book for.
   *
   * Read from `GET /dashboard/snapshot` because there is no `GET /residents`:
   * §6 of docs/API.md says so explicitly — the snapshot's `users[]` is that
   * list, and it carries the role the filter needs. The snapshot is
   * ADMIN/MANAGER-guarded, which is fine here and would not be on a resident
   * screen.
   *
   * **`membershipId`, not `id`.** The snapshot's `id` is the PROFILE id;
   * `AdminBookingRequest.membershipId` and `BookingSummary.residentId` are both
   * the membership id. Sending the profile id books nobody and 409s on "the
   * resident has no active flat".
   */
  bookableResidents: async () => {
    const snapshot = await getDashboardSnapshot();
    return (snapshot.users || [])
      .filter((user) => user.role === 'Resident' && user.status === 'Active')
      .map((user) => ({
        id: user.membershipId,
        name: user.name,
        flat: user.flat,
        phone: user.phone,
      }));
  },
};
