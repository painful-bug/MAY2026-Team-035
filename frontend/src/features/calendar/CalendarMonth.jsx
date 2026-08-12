import { useMemo } from 'react';
import CalendarEvent from './CalendarEvent';
import { WEEKDAY_NAMES, dayKey, groupByDay } from './useCalendarRange';

// The month answers one question: which days am I working. It shows at most two
// entries a cell and counts the rest, because a cell that grows with its
// contents makes the whole grid jump and nobody reads the fourth line anyway.

const MAX_PER_CELL = 2;

export default function CalendarMonth({ days, entries, onSelect, isCurrentMonth }) {
  const grouped = useMemo(() => groupByDay(entries), [entries]);
  const today = dayKey(new Date());

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50">
        {WEEKDAY_NAMES.map((name) => (
          <div key={name} className="px-2 py-2 text-center text-[10px] font-extrabold uppercase tracking-wider text-slate-500">
            {name}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {days.map((day) => {
          const key = dayKey(day);
          const cell = grouped.get(key) ?? [];
          const outside = isCurrentMonth && !isCurrentMonth(day);
          return (
            <div
              key={key}
              className={`min-h-24 border-b border-r border-slate-100 p-1.5 ${outside ? 'bg-slate-50/60' : 'bg-white'}`}
            >
              <div className="mb-1 flex items-center justify-between">
                <span
                  className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold tabular-nums ${
                    key === today
                      ? 'bg-indigo-600 text-white'
                      : outside
                        ? 'text-slate-300'
                        : 'text-slate-600'
                  }`}
                >
                  {day.getDate()}
                </span>
                {cell.length > MAX_PER_CELL && (
                  <span className="text-[9px] font-bold text-slate-400">{cell.length}</span>
                )}
              </div>
              <div className="space-y-1">
                {cell.slice(0, MAX_PER_CELL).map((entry) => (
                  <CalendarEvent key={`${entry.kind}-${entry.id}`} entry={entry} onSelect={onSelect} compact />
                ))}
                {cell.length > MAX_PER_CELL && (
                  <p className="px-1 text-[9px] font-bold text-slate-400">
                    +{cell.length - MAX_PER_CELL} more
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
