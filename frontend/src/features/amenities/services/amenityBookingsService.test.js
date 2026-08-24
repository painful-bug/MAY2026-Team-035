import { beforeEach, describe, expect, it, vi } from 'vitest';

// The slot hint's two answers: whether the slot looks free, and whether
// anything was actually consulted to say so. The conflict data lives behind
// `GET /dashboard/snapshot`, which 403s the resident looking at the booking
// form, so "we could not check" is a normal outcome and must be reported as
// itself rather than as availability.

const mocks = vi.hoisted(() => ({ getDashboardSnapshot: vi.fn() }));

vi.mock('../../../lib/dashboard/dashboardApi.js', () => ({
  getDashboardSnapshot: mocks.getDashboardSnapshot,
}));

import { ApiError } from '../../../lib/api/client.js';
import {
  checkBookingSlotAvailability,
  validateBookingSlot,
} from './amenityBookingsService.js';

const SLOT = {
  amenityId: 'a1',
  date: '2026-08-30',
  startTime: '07:00',
  endTime: '08:00',
  openingTime: '06:00',
  closingTime: '22:00',
};

const forbidden = () =>
  new ApiError({
    status: 403,
    code: 'forbidden',
    message: 'Administrators only.',
  });

beforeEach(() => {
  mocks.getDashboardSnapshot.mockReset();
});

describe('checkBookingSlotAvailability', () => {
  it('reports an unverified, optimistic answer when the read is forbidden', async () => {
    mocks.getDashboardSnapshot.mockRejectedValue(forbidden());

    expect(await checkBookingSlotAvailability(SLOT)).toEqual({
      available: true,
      verified: false,
    });
  });

  it('still applies the opening-hours window it can compute alone', async () => {
    mocks.getDashboardSnapshot.mockRejectedValue(forbidden());

    expect(
      await checkBookingSlotAvailability({
        ...SLOT,
        startTime: '05:00',
        endTime: '06:00',
      })
    ).toEqual({ available: false, verified: false });
  });

  it('marks the answer verified when the conflict read succeeded', async () => {
    mocks.getDashboardSnapshot.mockResolvedValue({ bookings: [] });

    expect(await checkBookingSlotAvailability(SLOT)).toEqual({
      available: true,
      verified: true,
    });
  });

  it('greys out a slot an existing booking already holds', async () => {
    mocks.getDashboardSnapshot.mockResolvedValue({
      bookings: [
        {
          id: 'b1',
          amenityId: 'a1',
          date: '2026-08-30',
          startTime: '07:00',
          endTime: '08:00',
          status: 'approved',
          state: 'booked',
        },
      ],
    });

    expect(await checkBookingSlotAvailability(SLOT)).toEqual({
      available: false,
      verified: true,
    });
  });

  it('survives a snapshot with no bookings key at all', async () => {
    mocks.getDashboardSnapshot.mockResolvedValue({});

    expect(await checkBookingSlotAvailability(SLOT)).toEqual({
      available: true,
      verified: true,
    });
  });
});

describe('validateBookingSlot', () => {
  it('is the boolean half of the same check', async () => {
    mocks.getDashboardSnapshot.mockRejectedValue(forbidden());

    await expect(validateBookingSlot(SLOT)).resolves.toBe(true);
  });
});
