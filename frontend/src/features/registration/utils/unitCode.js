// JS mirror of backend/app/domain/units.py::normalize_unit_code — used only to
// PREVIEW the canonical unit code in the admin approval panel ("Matches
// existing unit C-505" vs "Will create unit C-505"). The backend recomputes the
// canonical code itself from the raw building/unit inputs, so a drift here can
// mislabel the preview but never corrupt data.
//
// Semantics (keep in lockstep with the Python normalizer):
// - blank unit → null
// - no building → unit unchanged
// - unit already prefixed "<building>-" (case-insensitive) → unit unchanged
//   (guards the documented C-C-505 double-prefix hazard)
// - unit looks like a bare flat number (1–5 digits + optional letter) →
//   "<building>-<unit>"
// - anything else (already-structured codes like "Villa-17") → unit unchanged
const BARE_FLAT_NUMBER = /^\d{1,5}[A-Za-z]?$/;

export function normalizeUnitCode(building, unit) {
  const flat = (unit ?? '').trim();
  if (!flat) return null;
  const tower = (building ?? '').trim();
  if (!tower) return flat;
  if (flat.toLowerCase().startsWith(`${tower.toLowerCase()}-`)) return flat;
  if (BARE_FLAT_NUMBER.test(flat)) return `${tower}-${flat}`;
  return flat;
}
