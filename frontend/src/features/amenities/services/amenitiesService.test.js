import { beforeEach, describe, expect, it, vi } from 'vitest';

// The write shape of `POST/PUT /dashboard/amenities`, and how many times one
// save costs the whole admin snapshot.
//
// `AmenityWrite` is `extra="forbid"` on the other side, so the body is a
// closed vocabulary: a key too many is a 422 on every save, and a key too few
// is the field silently not being stored — which is how the amenity picture
// and the opening hours went missing (issue #48 D2/D4).

const mocks = vi.hoisted(() => ({
  getDashboardSnapshot: vi.fn(),
  api: vi.fn(),
}));

vi.mock('../../../lib/dashboard/dashboardApi.js', () => ({
  getDashboardSnapshot: mocks.getDashboardSnapshot,
}));

vi.mock('../../../lib/api/client.js', () => ({ api: mocks.api }));

import {
  createAmenity,
  setAmenityActiveStatus,
  updateAmenitySettings,
} from './amenitiesService.js';
import {
  createAmenitySettingsFormValues,
  serializeAmenitySettings,
} from '../utils/amenitySettingsModel.js';

const HOURLESS_AMENITY = {
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

const bodyOf = (call) => JSON.parse(call[1].body);

const lastWrite = (method) =>
  bodyOf(
    [...mocks.api.mock.calls]
      .reverse()
      .find(([, options]) => options?.method === method)
  );

beforeEach(() => {
  mocks.getDashboardSnapshot.mockReset();
  mocks.api.mockReset();
  mocks.api.mockResolvedValue({ id: 'a1' });
});

describe('createAmenity write body', () => {
  const FORM_VALUES = {
    name: 'Gym',
    description: 'Fitness centre',
    category: 'Fitness',
    location: 'Clubhouse',
    capacity: 20,
    bookingMode: 'Shared',
    requireApproval: false,
    hourlyRate: 0,
    isActive: true,
    openingTime: '06:00',
    closingTime: '21:30',
    image: 'data:image/webp;base64,UklGRg==',
  };

  it('sends the form\'s hours and picture, and nothing the model forbids', async () => {
    await createAmenity(FORM_VALUES);

    expect(mocks.api).toHaveBeenCalledTimes(1);
    const [path, options] = mocks.api.mock.calls[0];
    expect(path).toBe('/dashboard/amenities');
    expect(options.method).toBe('POST');
    expect(bodyOf(mocks.api.mock.calls[0])).toEqual({
      name: 'Gym',
      description: 'Fitness centre',
      category: 'Fitness',
      location: 'Clubhouse',
      capacity: 20,
      booking_mode: 'Shared',
      approval_required: false,
      hourly_rate: 0,
      is_active: true,
      image: 'data:image/webp;base64,UklGRg==',
      opening_time: '06:00',
      closing_time: '21:30',
    });
  });

  it('does not read the dashboard snapshot to describe what it just created', async () => {
    const created = await createAmenity(FORM_VALUES);

    expect(mocks.getDashboardSnapshot).not.toHaveBeenCalled();
    expect(created.id).toBe('a1');
    expect(created.name).toBe('Gym');
    expect(created.openingHours).toBe('6:00 AM - 9:30 PM');
  });

  it('sends null rather than an empty string for a missing picture', async () => {
    await createAmenity({ ...FORM_VALUES, image: '' });

    expect(lastWrite('POST').image).toBeNull();
  });

  it('refuses a picture the endpoint cannot accept, in words the admin can act on', async () => {
    await expect(
      createAmenity({ ...FORM_VALUES, image: 'ftp://pictures/pool.png' })
    ).rejects.toThrow(
      'The amenity image must be an uploaded picture or an https:// link.'
    );
    expect(mocks.api).not.toHaveBeenCalled();
  });

  it('refuses a data URL over the column budget instead of posting a 422', async () => {
    await expect(
      createAmenity({
        ...FORM_VALUES,
        image: `data:image/jpeg;base64,${'A'.repeat(140_000)}`,
      })
    ).rejects.toThrow('The amenity image is too large to save.');
    expect(mocks.api).not.toHaveBeenCalled();
  });
});

describe('setAmenityActiveStatus', () => {
  it('flips the switch with one PUT and no snapshot read when handed the record', async () => {
    const updated = await setAmenityActiveStatus('a1', HOURLESS_AMENITY);

    expect(mocks.getDashboardSnapshot).not.toHaveBeenCalled();
    expect(mocks.api).toHaveBeenCalledTimes(1);
    const [path, options] = mocks.api.mock.calls[0];
    expect(path).toBe('/dashboard/amenities/a1');
    expect(options.method).toBe('PUT');
    expect(bodyOf(mocks.api.mock.calls[0]).is_active).toBe(false);
    expect(updated.isActive).toBe(false);
    expect(updated.status).toBe('Inactive');
  });

  it('reads the snapshot exactly once when it has to find the record itself', async () => {
    mocks.getDashboardSnapshot.mockResolvedValue({
      amenities: [HOURLESS_AMENITY],
    });

    await setAmenityActiveStatus('a1');

    expect(mocks.getDashboardSnapshot).toHaveBeenCalledTimes(1);
    expect(mocks.api).toHaveBeenCalledTimes(1);
  });

  it('does not invent opening hours for an amenity that has none', async () => {
    // `normalizeAmenityRecord` seeds 06:00-22:00 so the settings form has
    // something to edit. Writing those back would make a status toggle decide
    // when the clubhouse opens.
    await setAmenityActiveStatus('a1', HOURLESS_AMENITY);

    const body = lastWrite('PUT');
    expect(body.opening_time).toBeNull();
    expect(body.closing_time).toBeNull();
  });

  it('carries real stored hours through untouched', async () => {
    await setAmenityActiveStatus('a1', {
      ...HOURLESS_AMENITY,
      openingTime: '07:00',
      closingTime: '21:00',
    });

    const body = lastWrite('PUT');
    expect(body.opening_time).toBe('07:00');
    expect(body.closing_time).toBe('21:00');
  });
});

describe('updateAmenitySettings', () => {
  it('reads the snapshot once and writes the submitted hours', async () => {
    mocks.getDashboardSnapshot.mockResolvedValue({
      amenities: [HOURLESS_AMENITY],
    });
    await updateAmenitySettings(
      'a1',
      serializeAmenitySettings({
        ...createAmenitySettingsFormValues(HOURLESS_AMENITY),
        openingTime: '05:30',
        closingTime: '23:00',
      })
    );

    expect(mocks.getDashboardSnapshot).toHaveBeenCalledTimes(1);
    expect(mocks.api).toHaveBeenCalledTimes(1);
    const body = lastWrite('PUT');
    expect(body.opening_time).toBe('05:30');
    expect(body.closing_time).toBe('23:00');
  });
});
