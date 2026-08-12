// The gate's closed vocabularies, in one place.
//
// Every list here is validated server-side in `security_service.py` and again
// by a CHECK constraint in `0040`. Sending a word that is not in one of these
// is a 422 naming the accepted set, deliberately — a typed category that
// quietly became `Other` would be a report with a hole in it. So the forms pick
// from these arrays rather than accepting free text, and the arrays are the
// same order the API documents.

/** Wire *and* display form: the API translates to `security_concern` itself. */
export const INCIDENT_CATEGORIES = [
  'Security concern',
  'Medical emergency',
  'Fire alarm',
  'Unauthorized access',
  'Property damage',
  'Other',
];

export const SEVERITIES = ['low', 'medium', 'high', 'critical'];
export const INCIDENT_STATUSES = ['open', 'acknowledged', 'resolved'];
export const DIRECTIONS = ['inward', 'outward'];

/** The four `GET /security/exports/{dataset}` accepts. */
export const EXPORT_DATASETS = [
  ['material-movements', 'Material register'],
  ['water-tankers', 'Tanker log'],
  ['incidents', 'Incidents'],
  ['shifts', 'Shifts'],
];

export const SEVERITY_STYLES = {
  low: 'bg-slate-100 text-slate-600',
  medium: 'bg-sky-100 text-sky-700',
  high: 'bg-amber-100 text-amber-800',
  critical: 'bg-rose-100 text-rose-700',
};

export const INCIDENT_STATUS_STYLES = {
  open: 'bg-rose-100 text-rose-700',
  acknowledged: 'bg-amber-100 text-amber-800',
  resolved: 'bg-emerald-100 text-emerald-700',
};

export const SHIFT_STATUS_STYLES = {
  scheduled: 'bg-indigo-100 text-indigo-700',
  active: 'bg-emerald-100 text-emerald-700',
  completed: 'bg-slate-100 text-slate-600',
  cancelled: 'bg-slate-100 text-slate-500',
  missed: 'bg-rose-100 text-rose-700',
};

export const DIRECTION_STYLES = {
  inward: 'bg-emerald-100 text-emerald-700',
  outward: 'bg-indigo-100 text-indigo-700',
};

// The six verdicts `POST /security/gate/verify` can answer with. Only the first
// two are a barrier that opens, which is why they are the only green ones — a
// guard glancing at this card in the dark should not have to read the word.
export const VERDICT_STYLES = {
  admitted: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  departed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  refused: 'border-rose-200 bg-rose-50 text-rose-800',
  not_yet_valid: 'border-amber-200 bg-amber-50 text-amber-900',
  expired: 'border-amber-200 bg-amber-50 text-amber-900',
  not_found: 'border-rose-200 bg-rose-50 text-rose-800',
};

export const VERDICT_LABELS = {
  admitted: 'Admitted',
  departed: 'Checked out',
  refused: 'Refused',
  not_yet_valid: 'Not yet valid',
  expired: 'Expired',
  not_found: 'Not recognised',
};

/** The shared input class, the same literal the converted pages already use. */
export const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

export const labelClass =
  'block text-[10px] font-bold uppercase tracking-wider text-slate-400';

/** `2026-08-11T22:00:00Z` → `11 Aug, 22:00`. No date library in this project. */
export function shortDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function shortTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

/** `datetime-local` wants `YYYY-MM-DDTHH:mm` with no zone and no seconds. */
export function toLocalInput(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}
