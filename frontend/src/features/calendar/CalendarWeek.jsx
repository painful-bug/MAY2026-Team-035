import { useMemo } from 'react';
import CalendarEvent from './CalendarEvent';
import { dayKey, groupByDay } from './useCalendarRange';

// The week answers a different question from the month — not *which days* but
// *what exactly, and when* — so it shows every entry in full rather than
// truncating, and stacks them in time order.
//
// DELIBERATELY NOT A TIME GRID. An hour-ruled column with absolutely positioned
// blocks exists to make overlaps visible, and a worker's accepted jobs cannot
// overlap: `work_order_assignments_no_overlap` in `0036` is a GiST exclusion
// constraint that refuses the write. Drawing a hundred lines of geometry to
// reveal a state the database forbids is geometry for its own sake.

const weekday = new Intl.DateTimeFormat(undefined, { weekday: 'short' });

export default function CalendarWeek({ days, entries, onSelect }) {
  const grouped = useMemo(() => groupByDay(entries), [entries]);
  const today = dayKey(new Date());

  return (
    <div className="grid gap-2 sm:grid-cols-7">
      {days.map((day) => {
        const key = dayKey(day);
        const cell = grouped.get(key) ?? [];
        return (
          <div
            key={key}
            className={`rounded-2xl border p-2 ${
              key === today ? 'border-indigo-200 bg-indigo-50/50' : 'border-slate-200 bg-white'
            }`}
          >
            <div className="mb-2 flex items-baseline justify-between px-1">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">
                {weekday.format(day)}
              </span>
              <span
                className={`text-sm font-extrabold tabular-nums ${
                  key === today ? 'text-indigo-600' : 'text-slate-700'
                }`}
              >
                {day.getDate()}
              </span>
            </div>
            <div className="space-y-1.5">
              {cell.length === 0 ? (
                <p className="px-1 py-3 text-center text-[10px] font-semibold text-slate-300">Free</p>
              ) : (
                cell.map((entry) => (
                  <CalendarEvent key={`${entry.kind}-${entry.id}`} entry={entry} onSelect={onSelect} />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
