import { beforeEach, describe, expect, it, vi } from 'vitest';

// The acceptance battery for GitHub issue #48 — the amenities catalogue
// service half. Both cases were `it.fails` repros; both are fixed and
// promoted, and they now pin the behaviour against regression.

const mocks = vi.hoisted(() => ({
  getDashboardSnapshot: vi.fn(),
  api: vi.fn(),
}));

vi.mock('../../../lib/dashboard/dashboardApi.js', () => ({
  getDashboardSnapshot: mocks.getDashboardSnapshot,
}));

vi.mock('../../../lib/api/client.js', () => ({
  api: mocks.api,
}));

import {
  createAmenity,
  setAmenityActiveStatus,
} from './amenitiesService.js';

const AMENITY = {
  id: 'a1',
  name: 'Clubhouse',
  description: 'Community hall',
  category: 'Recreation',
  location: 'Ground Floor',
  status: 'Active',
  isActive: true,
  capacity: 40,
  bookingMode: 'Shared',
  requireApproval: false,
  hourlyRate: 0,
  pendingRequests: 0,
  outstandingDues: 0,
};

beforeEach(() => {
  mocks.getDashboardSnapshot.mockReset();
  mocks.api.mockReset();
});

describe('issue #48 amenity catalogue service', () => {
  // D1: it used to read the snapshot three times to flip one boolean — once
  // here, once inside `updateAmenity`, once more for the `getAmenityById`
  // read-back — and each read is the WHOLE admin snapshot: users, complaints,
  // visitors, bookings, payments, notices. One read finds the record; the PUT
  // is built from it, and the merged record is the answer.
  it(
    'D1: toggling an amenity refetches the dashboard snapshot at most once',
    async () => {
      mocks.getDashboardSnapshot.mockResolvedValue({ amenities: [AMENITY] });
      mocks.api.mockResolvedValue({});

      await setAmenityActiveStatus('a1');

      expect(
        mocks.getDashboardSnapshot.mock.calls.length
      ).toBeLessThanOrEqual(1);
    }
  );

  // D2: the Add Amenity form collects an image and `toAmenityWrite` used to
  // drop it — the POST body carried no `image` key at all, so the picture
  // vanished without a word. It is on the wire now (contract §A/§E).
  it(
    'D2: createAmenity sends the image in the POST /dashboard/amenities body',
    async () => {
      mocks.getDashboardSnapshot.mockResolvedValue({ amenities: [] });
      mocks.api.mockResolvedValue({ id: 'new-1' });

      await createAmenity({
        name: 'Gym',
        description: 'Fitness centre',
        category: 'Fitness',
        location: 'Clubhouse',
        capacity: 20,
        bookingMode: 'Shared',
        requireApproval: false,
        hourlyRate: 0,
        isActive: true,
        image: 'data:image/png;base64,x',
      });

      const createCall = mocks.api.mock.calls.find(
        ([path, options]) =>
          path === '/dashboard/amenities' && options?.method === 'POST'
      );
      expect(createCall).toBeDefined();
      const body = JSON.parse(createCall[1].body);
      expect(body).toHaveProperty('image');
    }
  );
});
