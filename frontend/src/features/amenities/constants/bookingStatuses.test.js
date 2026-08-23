import { describe, expect, it } from 'vitest';
import {
  BOOKING_STATUS,
  bookingStatusLabel,
  isCancelledBooking,
  normalizeBookingStatus,
} from './bookingStatuses.js';

// The wire sends lowercase machine values — `pending | approved | rejected |
// cancelled | completed | no_show` (issue #48, contract §C) — and the display
// wording is decided here. Screens used to render whichever spelling the
// response happened to carry, so the same status appeared as "Approved" in one
// table and "approved" in another.

describe('normalizeBookingStatus', () => {
  it('maps every spelling of a status onto its machine value', () => {
    expect(normalizeBookingStatus('no_show')).toBe(BOOKING_STATUS.NO_SHOW);
    expect(normalizeBookingStatus('No Show')).toBe(BOOKING_STATUS.NO_SHOW);
    expect(normalizeBookingStatus('NO-SHOW')).toBe(BOOKING_STATUS.NO_SHOW);
    expect(normalizeBookingStatus(' Approved ')).toBe(BOOKING_STATUS.APPROVED);
    expect(normalizeBookingStatus(null)).toBe('');
  });
});

describe('bookingStatusLabel', () => {
  it('labels the six lifecycle statuses the wire can send', () => {
    expect(bookingStatusLabel('pending')).toBe('Pending Approval');
    expect(bookingStatusLabel('approved')).toBe('Approved');
    expect(bookingStatusLabel('rejected')).toBe('Rejected');
    expect(bookingStatusLabel('cancelled')).toBe('Cancelled');
    expect(bookingStatusLabel('completed')).toBe('Completed');
    expect(bookingStatusLabel('no_show')).toBe('No Show');
  });

  it('humanises a status this build has never heard of', () => {
    expect(bookingStatusLabel('awaiting_deposit')).toBe('Awaiting Deposit');
  });

  it('is empty for an absent status rather than printing "Undefined"', () => {
    expect(bookingStatusLabel(undefined)).toBe('');
    expect(bookingStatusLabel('')).toBe('');
  });
});

describe('isCancelledBooking', () => {
  it('recognises a cancelled booking whichever spelling it arrives in', () => {
    expect(isCancelledBooking({ status: 'cancelled' })).toBe(true);
    expect(isCancelledBooking({ status: 'Cancelled' })).toBe(true);
    expect(isCancelledBooking({ status: 'approved' })).toBe(false);
  });
});
