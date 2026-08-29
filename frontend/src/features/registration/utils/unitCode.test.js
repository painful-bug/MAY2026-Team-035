import { describe, expect, it } from 'vitest';
import { normalizeUnitCode } from './unitCode';

// Mirror of backend/app/domain/units.py::normalize_unit_code — these cases pin
// the JS copy to the Python semantics so the approval panel's match preview
// agrees with what the RPC will actually match or create.
describe('normalizeUnitCode', () => {
  it('returns null for a blank unit', () => {
    expect(normalizeUnitCode('C', '')).toBeNull();
    expect(normalizeUnitCode('C', '   ')).toBeNull();
    expect(normalizeUnitCode('C', null)).toBeNull();
    expect(normalizeUnitCode('C', undefined)).toBeNull();
  });

  it('returns the unit unchanged when there is no building', () => {
    expect(normalizeUnitCode('', '505')).toBe('505');
    expect(normalizeUnitCode(null, 'Villa-17')).toBe('Villa-17');
    expect(normalizeUnitCode('   ', 'C-505')).toBe('C-505');
  });

  it('prefixes a bare flat number with the building', () => {
    expect(normalizeUnitCode('C', '505')).toBe('C-505');
    expect(normalizeUnitCode('A', '302')).toBe('A-302');
    expect(normalizeUnitCode('C', '505B')).toBe('C-505B');
    expect(normalizeUnitCode(' C ', ' 505 ')).toBe('C-505');
  });

  it('never double-prefixes an already-prefixed unit (the C-C-505 hazard)', () => {
    expect(normalizeUnitCode('C', 'C-505')).toBe('C-505');
    expect(normalizeUnitCode('c', 'C-505')).toBe('C-505');
    expect(normalizeUnitCode('C', 'c-505')).toBe('c-505');
  });

  it('leaves structured or unexpected unit text unchanged', () => {
    expect(normalizeUnitCode('C', 'Villa-17')).toBe('Villa-17');
    expect(normalizeUnitCode('C', '123456')).toBe('123456');
    expect(normalizeUnitCode('C', '5th floor')).toBe('5th floor');
  });
});
