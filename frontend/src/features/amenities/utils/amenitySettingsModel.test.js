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

// `openingHours` is the display string the amenity cards render verbatim. It
// used to be composed from the settings-form DEFAULTS laid over the record, so
// an amenity whose hours were never stored (the hosted snapshot's rows carry
// no hours at all) read "6:00 AM - 10:00 PM" on every card. It must now be
// composed only from hours the record really carries — '' otherwise, which
// the cards render as no hours line.

const BASE = {
  id: 'a1',
  name: 'Pool',
  description: '',
  category: 'Recreation',
  status: 'Active',
  isActive: true,
};

describe('normalizeAmenityRecord display hours', () => {
  it('leaves openingHours empty when the record carries no hours', () => {
    const record = normalizeAmenityRecord(BASE);

    expect(record.openingHours).toBe('');
    // The settings form still gets its editable seed values.
    expect(record.operatingHours.openingTime).toBe('06:00');
    expect(record.operatingHours.closingTime).toBe('22:00');
  });

  it('treats the null-hours wire spelling ("00:00"/"00:00") as no hours', () => {
    const record = normalizeAmenityRecord({
      ...BASE,
      openingTime: '00:00',
      closingTime: '00:00',
    });

    expect(record.openingHours).toBe('');
  });

  it('formats real stored hours', () => {
    const flat = normalizeAmenityRecord({
      ...BASE,
      openingTime: '06:00',
      closingTime: '22:00',
    });
    const nested = normalizeAmenityRecord({
      ...BASE,
      operatingHours: { openingTime: '07:30', closingTime: '21:00' },
    });

    expect(flat.openingHours).toBe('6:00 AM - 10:00 PM');
    expect(nested.openingHours).toBe('7:30 AM - 9:00 PM');
  });
});
