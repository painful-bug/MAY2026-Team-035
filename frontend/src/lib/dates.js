// Date formatting helpers — replace the repeated inline Date wrangling the old
// context did in every action.

// UTC's today. Correct for anything the server keys by UTC; WRONG for "what
// day is it where the reader is", which east of UTC flips to tomorrow after
// 05:30 IST and west of it stays on yesterday until midnight. Screens that ask
// the second question want `localTodayISO`.
export const todayISO = () => new Date().toISOString().split('T')[0];

// The reader's own calendar day as `YYYY-MM-DD`. Built from the local
// components rather than `toISOString()`, which converts to UTC first — the
// bug that made the amenity day timeline open on tomorrow's (empty) schedule
// for every Indian admin after 5:30 in the morning.
export const localTodayISO = (date = new Date()) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate()
  ).padStart(2, '0')}`;

// `YYYY-MM-DD` → a Date at local midnight. `new Date('2026-08-23')` is parsed
// as UTC and renders as the previous day west of UTC, so date-picker values
// are read back through this instead.
export const fromISODate = (value) => {
  const [year, month, day] = String(value ?? '')
    .split('-')
    .map(Number);
  return Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)
    ? new Date(year, month - 1, day)
    : new Date(Number.NaN);
};

export const longDate = (d = new Date()) =>
  d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

export const shortTime = (d = new Date()) =>
  d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
