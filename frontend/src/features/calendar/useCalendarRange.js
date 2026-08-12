import { useCallback, useMemo, useState } from 'react';

// The calendar primitive's arithmetic, in one place.
//
// Generalised from the amenity timeline in the sense the plan meant: that code
// (`features/amenities/utils/amenityTimeline.js`) does slot geometry *inside a
// single day*, in `HH:MM` strings, and has no concept of a date at all. Nothing
// in it could be reused for a month grid, so what carries over is its shape --
// pure functions, no component state, `Intl` for every label -- rather than its
// lines.
//
// No date library. `Date` plus `Intl.DateTimeFormat` covers all of it, and the
// one genuinely awkward operation (add a month without 31 January becoming
// 3 March) is handled by setting the day to 1 before moving the month.

const DAY_MS = 86_400_000;

/** Local calendar day as `YYYY-MM-DD`. Never `toISOString`, which is UTC. */
export const dayKey = (value) => {
  const date = value instanceof Date ? value : new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate()
  ).padStart(2, '0')}`;
};

const startOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());

/** Monday-first, because the working week is what this calendar is about. */
const startOfWeek = (date) => {
  const start = startOfDay(date);
  const weekday = (start.getDay() + 6) % 7;
  return new Date(start.getTime() - weekday * DAY_MS);
};

const addDays = (date, count) => new Date(date.getTime() + count * DAY_MS);

const addMonths = (date, count) => new Date(date.getFullYear(), date.getMonth() + count, 1);

const monthLabel = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' });
const dayLabel = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' });
const weekdayLabel = new Intl.DateTimeFormat(undefined, { weekday: 'short' });

export const WEEKDAY_NAMES = Array.from({ length: 7 }, (_, index) =>
  weekdayLabel.format(addDays(startOfWeek(new Date(2026, 0, 5)), index))
);

/**
 * A cursor over the calendar, and the grid it implies.
 *
 * The `from`/`to` pair is exactly what `GET /worker/calendar` takes, and it
 * covers the whole rendered grid rather than the whole month — a month view
 * shows the tail of the previous month, and those days having no entries
 * because nobody asked for them would read as days off.
 */
export function useCalendarRange(initialView = 'month') {
  const [view, setView] = useState(initialView);
  const [cursor, setCursor] = useState(() => startOfDay(new Date()));

  const days = useMemo(() => {
    if (view === 'week') {
      const start = startOfWeek(cursor);
      return Array.from({ length: 7 }, (_, index) => addDays(start, index));
    }
    const start = startOfWeek(new Date(cursor.getFullYear(), cursor.getMonth(), 1));
    // Six rows always. A grid that is five rows one month and six the next
    // makes everything below it jump on every navigation.
    return Array.from({ length: 42 }, (_, index) => addDays(start, index));
  }, [cursor, view]);

  const move = useCallback(
    (direction) =>
      setCursor((current) =>
        view === 'week' ? addDays(current, direction * 7) : addMonths(current, direction)
      ),
    [view]
  );

  const label =
    view === 'week'
      ? `${dayLabel.format(days[0])} – ${dayLabel.format(days[6])}, ${days[6].getFullYear()}`
      : monthLabel.format(cursor);

  return {
    view,
    setView,
    cursor,
    days,
    label,
    from: dayKey(days[0]),
    to: dayKey(addDays(days[days.length - 1], 1)),
    next: () => move(1),
    previous: () => move(-1),
    today: () => setCursor(startOfDay(new Date())),
    isCurrentMonth: (date) => date.getMonth() === cursor.getMonth(),
  };
}

/** Entries bucketed by the local day they start on, for O(1) cell lookup. */
export function groupByDay(entries = []) {
  const grouped = new Map();
  for (const entry of entries) {
    if (!entry?.startsAt) continue;
    const key = dayKey(entry.startsAt);
    const bucket = grouped.get(key);
    if (bucket) bucket.push(entry);
    else grouped.set(key, [entry]);
  }
  for (const bucket of grouped.values()) {
    bucket.sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt));
  }
  return grouped;
}
