import { describe, expect, it } from 'vitest';
import { normalizeAmenityRecord } from './amenitySettingsModel.js';

describe('normalizeAmenityRecord', () => {
  it('defaults pendingRequests and outstandingDues to 0 when the snapshot omits them', () => {
    const amenity = normalizeAmenityRecord({ id: 'a1', name: 'pool' });

    expect(amenity.pendingRequests).toBe(0);
    expect(amenity.outstandingDues).toBe(0);
  });

  it('keeps real counts and coerces numeric strings', () => {
    const amenity = normalizeAmenityRecord({
      id: 'a1',
      name: 'pool',
      pendingRequests: 3,
      outstandingDues: '450',
    });

    expect(amenity.pendingRequests).toBe(3);
    expect(amenity.outstandingDues).toBe(450);
  });
});
