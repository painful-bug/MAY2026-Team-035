import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../../lib/api/client.js';
import { getDashboardSnapshot } from '../../../lib/dashboard/dashboardApi.js';
import { setAmenityActiveStatus } from './amenitiesService.js';

vi.mock('../../../lib/api/client.js', () => ({ api: vi.fn() }));
vi.mock('../../../lib/dashboard/dashboardApi.js', () => ({
  getDashboardSnapshot: vi.fn(),
}));

const AMENITY = {
  id: 'amenity-1',
  name: 'Clubhouse',
  description: 'Community hall',
  category: 'Recreation',
  location: 'Ground floor',
  capacity: 40,
  bookingMode: 'Exclusive',
  requireApproval: false,
  hourlyRate: 0,
  isActive: true,
  openingTime: '06:00',
  closingTime: '22:00',
};

describe('setAmenityActiveStatus', () => {
  beforeEach(() => {
    api.mockReset();
    getDashboardSnapshot.mockReset();
  });

  it('uses the amenity already on the card and refreshes the snapshot once', async () => {
    api.mockResolvedValueOnce({ id: AMENITY.id });
    getDashboardSnapshot.mockResolvedValueOnce({
      amenities: [{ ...AMENITY, isActive: false, status: 'Inactive' }],
    });

    await expect(setAmenityActiveStatus(AMENITY)).resolves.toMatchObject({
      id: AMENITY.id,
      isActive: false,
    });

    expect(api).toHaveBeenCalledWith(
      `/dashboard/amenities/${AMENITY.id}`,
      expect.objectContaining({ method: 'PUT' })
    );
    expect(getDashboardSnapshot).toHaveBeenCalledTimes(1);
  });
});
