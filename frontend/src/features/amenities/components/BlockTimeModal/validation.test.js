import { describe, expect, it } from 'vitest';
import { getInitialBlockTime, validateBlockedSlot } from './validation.js';

describe('getInitialBlockTime', () => {
  it('opens on the slot the admin clicked when there is one', () => {
    expect(
      getInitialBlockTime(
        { openingTime: '06:00', closingTime: '22:00' },
        { startTime: '14:00', endTime: '15:00' }
      )
    ).toEqual({ startTime: '14:00', endTime: '15:00' });
  });

  it('opens on the first hour of the amenity when it has hours', () => {
    expect(
      getInitialBlockTime({ openingTime: '06:00', closingTime: '22:00' }, null)
    ).toEqual({ startTime: '06:00', endTime: '07:00' });
  });

  it('never runs past a closing time less than an hour away', () => {
    expect(
      getInitialBlockTime({ openingTime: '21:30', closingTime: '22:00' }, null)
    ).toEqual({ startTime: '21:30', endTime: '22:00' });
  });

  it('falls back to a working hour when the amenity carries no hours', () => {
    expect(getInitialBlockTime({}, null)).toEqual({
      startTime: '09:00',
      endTime: '10:00',
    });
  });

  it('never returns a time past the end of the day', () => {
    expect(
      getInitialBlockTime({ openingTime: '23:30', closingTime: '' }, null)
    ).toEqual({ startTime: '23:30', endTime: '23:59' });
  });
});

describe('validateBlockedSlot', () => {
  const VALUES = {
    reason: 'Deep clean',
    department: 'Housekeeping',
    startTime: '09:00',
    endTime: '10:00',
  };

  it('accepts a complete block', () => {
    expect(validateBlockedSlot(VALUES)).toEqual({});
  });

  it('refuses an end time at or before the start', () => {
    expect(validateBlockedSlot({ ...VALUES, endTime: '09:00' })).toEqual({
      endTime: 'End time must be later than start time.',
    });
  });
});
