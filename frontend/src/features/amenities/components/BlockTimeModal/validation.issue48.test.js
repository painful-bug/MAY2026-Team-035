import { describe, expect, it } from 'vitest';
import { getInitialBlockTime } from './validation.js';

// Acceptance test for GitHub issue #48 D3 — the Block Time modal's initial
// times.
//
// An amenity whose hours were never stored reaches this function as
// `openingTime: ''` / `closingTime: ''`. `timeToMinutes('')` is NaN, so the
// modal used to seed `startTime: ''` and `endTime: 'NaN:NaN'` — an
// unsubmittable form, with a blank end-time input, before the admin had
// touched anything. Both fields are a real `HH:MM` now.

describe('issue #48 D3: block-time defaults for an amenity without hours', () => {
  it(
    'derives usable HH:MM defaults when the amenity carries no stored hours',
    () => {
      const initial = getInitialBlockTime(
        { openingTime: '', closingTime: '' },
        null
      );

      expect(initial.startTime).toMatch(/^\d{2}:\d{2}$/);
      expect(initial.endTime).toMatch(/^\d{2}:\d{2}$/);
    }
  );
});
