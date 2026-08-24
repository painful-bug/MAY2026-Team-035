import { afterEach, describe, expect, it, vi } from 'vitest';
import { fromISODate, localTodayISO, todayISO } from './dates.js';

// `todayISO()` is UTC's today, and screens that mean "the day the reader is
// having" were using it: east of UTC the amenity day timeline flipped to
// tomorrow's (empty) schedule at 05:30 local and stayed there (issue #48 D4).

afterEach(() => {
  vi.useRealTimers();
});

describe('localTodayISO', () => {
  it('names the day the reader is having, for any instant', () => {
    // `en-CA` formats as YYYY-MM-DD in the runner's own zone, which is the
    // definition being pinned. In +05:30 this instant is 23:30 on the 23rd; in
    // UTC-5 it is 13:00 on the 23rd; at 20:00 UTC it would be the 24th in
    // India and still the 23rd in New York — and each reader gets their own.
    const instant = new Date('2026-08-23T18:00:00.000Z');

    expect(localTodayISO(instant)).toBe(instant.toLocaleDateString('en-CA'));
  });

  it('reads the system clock when given nothing', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-08-23T18:00:00.000Z'));

    expect(localTodayISO()).toBe(
      new Date('2026-08-23T18:00:00.000Z').toLocaleDateString('en-CA')
    );
  });

  it('reports the local day of an explicit date, not its UTC day', () => {
    // Local midnight on the 23rd: `toISOString()` would say the 22nd anywhere
    // west of UTC and the 23rd anywhere east of it.
    expect(localTodayISO(new Date(2026, 7, 23, 0, 0, 0))).toBe('2026-08-23');
    expect(localTodayISO(new Date(2026, 0, 5, 23, 59, 0))).toBe('2026-01-05');
  });

  it('pads month and day so the value is a valid date-input value', () => {
    expect(localTodayISO(new Date(2026, 0, 1))).toBe('2026-01-01');
  });

  it('is the UTC day only when the reader is on UTC', () => {
    vi.useFakeTimers();
    const instant = new Date('2026-08-23T18:00:00.000Z');
    vi.setSystemTime(instant);

    // `todayISO()` answers 2026-08-23 for this instant everywhere on earth;
    // `localTodayISO()` answers the 24th east of UTC+6.
    expect(todayISO()).toBe('2026-08-23');
    expect(localTodayISO() === todayISO()).toBe(
      instant.toLocaleDateString('en-CA') === '2026-08-23'
    );
  });
});

describe('fromISODate', () => {
  it('reads a date-input value as local midnight', () => {
    const parsed = fromISODate('2026-08-23');

    expect(parsed.getFullYear()).toBe(2026);
    expect(parsed.getMonth()).toBe(7);
    expect(parsed.getDate()).toBe(23);
    expect(parsed.getHours()).toBe(0);
  });

  it('round-trips with localTodayISO', () => {
    expect(localTodayISO(fromISODate('2026-02-01'))).toBe('2026-02-01');
  });

  it('is an invalid date for an empty or malformed value', () => {
    expect(Number.isNaN(fromISODate('').getTime())).toBe(true);
    expect(Number.isNaN(fromISODate(undefined).getTime())).toBe(true);
  });
});
