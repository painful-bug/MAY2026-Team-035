// D15 — a community's colour is derived from its id, never stored.
//
// A stable hash indexes a fixed palette, so the same society is the same colour
// on every device with no column, no migration, no admin setting and no field
// in any API response. Nothing has to stay in sync because nothing is written
// down.
//
// The classes are spelled out in full on purpose. Tailwind scans source text,
// so a composed `bg-${name}-500` would be scanned as nothing and the swatch
// would render transparent.

const PALETTE = Object.freeze([
  { name: 'sky', dot: 'bg-sky-500', chip: 'bg-sky-50 text-sky-700 border-sky-200', bar: 'border-l-sky-500' },
  { name: 'emerald', dot: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-700 border-emerald-200', bar: 'border-l-emerald-500' },
  { name: 'amber', dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-700 border-amber-200', bar: 'border-l-amber-500' },
  { name: 'violet', dot: 'bg-violet-500', chip: 'bg-violet-50 text-violet-700 border-violet-200', bar: 'border-l-violet-500' },
  { name: 'rose', dot: 'bg-rose-500', chip: 'bg-rose-50 text-rose-700 border-rose-200', bar: 'border-l-rose-500' },
  { name: 'teal', dot: 'bg-teal-500', chip: 'bg-teal-50 text-teal-700 border-teal-200', bar: 'border-l-teal-500' },
  { name: 'indigo', dot: 'bg-indigo-500', chip: 'bg-indigo-50 text-indigo-700 border-indigo-200', bar: 'border-l-indigo-500' },
  { name: 'orange', dot: 'bg-orange-500', chip: 'bg-orange-50 text-orange-700 border-orange-200', bar: 'border-l-orange-500' },
]);

const NEUTRAL = Object.freeze({
  name: 'slate',
  dot: 'bg-slate-400',
  chip: 'bg-slate-50 text-slate-600 border-slate-200',
  bar: 'border-l-slate-400',
});

/** Stable per-community colour. Same id, same swatch, on every device. */
export function communityColor(communityId) {
  if (!communityId) return NEUTRAL;
  let hash = 0;
  for (let i = 0; i < communityId.length; i += 1) {
    hash = (hash * 31 + communityId.charCodeAt(i)) | 0;
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}
