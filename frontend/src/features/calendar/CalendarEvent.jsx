import { communityColor } from '../../lib/communityColor';

const time = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });

// `CalendarEntry.kind` is `job` or `unavailable`, and the two are drawn
// differently on purpose: one is work somebody is expecting you at, the other is
// time you have taken back. Leave carries no communityId — it belongs to the
// person, not to any of the societies employing them — so it gets the striped
// neutral treatment rather than a society's colour.

export default function CalendarEvent({ entry, onSelect, compact = false }) {
  const leave = entry.kind === 'unavailable';
  const colour = communityColor(entry.communityId);
  const at = entry.startsAt ? time.format(new Date(entry.startsAt)) : '';
  const interactive = Boolean(onSelect) && !leave;

  return (
    <button
      type="button"
      disabled={!interactive}
      onClick={interactive ? () => onSelect(entry) : undefined}
      title={`${at} ${entry.title}${entry.communityName ? ` · ${entry.communityName}` : ''}`}
      className={`w-full rounded-lg border-l-4 px-2 py-1 text-left transition-colors ${
        leave
          ? 'border-l-slate-300 bg-[repeating-linear-gradient(45deg,#f8fafc,#f8fafc_5px,#f1f5f9_5px,#f1f5f9_10px)] text-slate-500'
          : `${colour.bar} bg-white text-slate-800 shadow-sm ${interactive ? 'hover:bg-slate-50' : ''}`
      } ${interactive ? 'cursor-pointer' : 'cursor-default'}`}
    >
      <p className={`truncate font-bold ${compact ? 'text-[10px]' : 'text-xs'}`}>
        {at && <span className="font-extrabold tabular-nums">{at} </span>}
        {entry.title}
      </p>
      {!compact && entry.subtitle && (
        <p className="truncate text-[10px] font-medium text-slate-500">{entry.subtitle}</p>
      )}
      {!compact && entry.communityName && (
        <span className="mt-1 inline-flex items-center gap-1 text-[10px] font-semibold text-slate-500">
          <span className={`h-1.5 w-1.5 rounded-full ${colour.dot}`} />
          {entry.communityName}
        </span>
      )}
    </button>
  );
}
