// Client-side ID generation. Was `${prefix}_${Date.now()}` scattered across the
// old context; centralised here + a random suffix so IDs minted in the same
// millisecond (e.g. several phones added to one flat in a loop) don't collide.
export const genId = (prefix = 'id') =>
  `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
