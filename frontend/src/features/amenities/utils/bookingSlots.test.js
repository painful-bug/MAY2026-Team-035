import { describe, expect, it } from 'vitest';
import {
  createBookingSlots,
  hasBookableHours,
  minutesToTime,
  timeToMinutes,
} from './bookingSlots.js';

// The NULL-hours case: the hosted `amenities` rows can hold NULL
// opening/closing times, and `GET /amenities/available` reports those as
// "00:00"/"00:00". The slot builder must yield nothing for it (it does — the
// window is zero minutes wide), and `hasBookableHours` is the name the dialog
// uses to say so instead of showing an empty dropdown.

const amenityWith = (openingTime, closingTime) => ({
  openingTime,
  closingTime,
  bookingSlotDuration: 60,
  availabilitySettings: {
    minimumBookingDurationMinutes: 30,
    maximumBookingDurationMinutes: 240,
  },
});

describe('hasBookableHours', () => {
  it('is false for the null-hours wire spelling ("00:00"/"00:00")', () => {
    expect(hasBookableHours(amenityWith('00:00', '00:00'))).toBe(false);
  });

  it('is false when either clock is missing or the window is inverted', () => {
    expect(hasBookableHours(undefined)).toBe(false);
    expect(hasBookableHours(amenityWith('', ''))).toBe(false);
    expect(hasBookableHours(amenityWith('06:00', ''))).toBe(false);
    expect(hasBookableHours(amenityWith('22:00', '06:00'))).toBe(false);
  });

  it('is true for a real window', () => {
    expect(hasBookableHours(amenityWith('06:00', '22:00'))).toBe(true);
  });
});

describe('createBookingSlots', () => {
  it('yields no slots when opening equals closing', () => {
    expect(createBookingSlots(amenityWith('00:00', '00:00'))).toEqual([]);
  });

  it('yields no slots when hours are absent', () => {
    expect(createBookingSlots(amenityWith('', ''))).toEqual([]);
    expect(createBookingSlots(undefined)).toEqual([]);
  });

  it('generates the normal hourly slots for real hours, unchanged', () => {
    const slots = createBookingSlots(amenityWith('06:00', '10:00'));
    expect(slots.map((slot) => slot.value)).toEqual([
      '06:00-07:00',
      '07:00-08:00',
      '08:00-09:00',
      '09:00-10:00',
    ]);
    expect(slots[0].label).toBe('6:00 am - 7:00 am');
  });
});

describe('time helpers', () => {
  it('round-trips minutes and clock strings', () => {
    expect(timeToMinutes('06:30')).toBe(390);
    expect(minutesToTime(390)).toBe('06:30');
  });
});
