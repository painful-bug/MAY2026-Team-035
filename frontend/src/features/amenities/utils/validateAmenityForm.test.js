import { describe, expect, it } from 'vitest';
import { validateAmenityForm } from './validateAmenityForm.js';

const VALUES = {
  name: 'Gym',
  description: 'Fitness centre',
  openingTime: '06:00',
  closingTime: '21:00',
  bookingMode: 'Exclusive',
  capacity: '',
  cleaningBuffer: '0',
  maxBookingsPerResident: '',
};

describe('validateAmenityForm hours', () => {
  it('accepts a real window', () => {
    expect(validateAmenityForm(VALUES)).toEqual({});
  });

  it('requires both ends', () => {
    expect(validateAmenityForm({ ...VALUES, openingTime: '' })).toHaveProperty(
      'openingTime',
      'Opening time is required.'
    );
    expect(validateAmenityForm({ ...VALUES, closingTime: '' })).toHaveProperty(
      'closingTime',
      'Closing time is required.'
    );
  });

  it('refuses closing at or before opening, which the column constraint would reject', () => {
    // The hours are stored now: `amenities_hours_check` and the write model's
    // validator both refuse this, so catching it here saves a round trip that
    // could only ever come back a 422.
    expect(
      validateAmenityForm({ ...VALUES, openingTime: '21:00', closingTime: '06:00' })
    ).toHaveProperty(
      'closingTime',
      'Closing time must be later than opening time.'
    );
    expect(
      validateAmenityForm({ ...VALUES, openingTime: '06:00', closingTime: '06:00' })
    ).toHaveProperty(
      'closingTime',
      'Closing time must be later than opening time.'
    );
  });
});
