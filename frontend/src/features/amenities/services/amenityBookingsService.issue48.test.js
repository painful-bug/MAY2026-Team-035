import { beforeEach, describe, expect, it, vi } from 'vitest';

// Acceptance test for GitHub issue #48 D5 — the resident slot validator reads
// the ADMIN/MANAGER-guarded `GET /dashboard/snapshot`, so for the resident
// actually looking at the booking form the read 403s. The whole validation
// used to reject with it, which left the booking form stuck on "Checking
// availability..." for good. The 403 is now an unverified check rather than a
// failure: the answer is optimistic, and the booking write — which holds an
// advisory lock and answers a clash with a 409 — remains the authority.

const mocks = vi.hoisted(() => ({ getDashboardSnapshot: vi.fn() }));

vi.mock('../../../lib/dashboard/dashboardApi.js', () => ({
  getDashboardSnapshot: mocks.getDashboardSnapshot,
}));

import { ApiError } from '../../../lib/api/client.js';
import { validateBookingSlot } from './amenityBookingsService.js';

beforeEach(() => {
  mocks.getDashboardSnapshot.mockReset();
});

describe('issue #48 D5: slot validation for a resident caller', () => {
  it(
    'resolves to a boolean when the snapshot read is forbidden (403)',
    async () => {
      mocks.getDashboardSnapshot.mockRejectedValue(
        new ApiError({
          status: 403,
          code: 'forbidden',
          message: 'Administrators only.',
        })
      );

      const result = await validateBookingSlot({
        amenityId: 'a1',
        date: '2026-08-30',
        startTime: '07:00',
        endTime: '08:00',
        openingTime: '06:00',
        closingTime: '22:00',
      });

      expect(typeof result).toBe('boolean');
    }
  );
});
