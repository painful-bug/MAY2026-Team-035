import { CloudOff, X } from 'lucide-react';
import { VERDICT_LABELS, VERDICT_STYLES, shortDateTime } from './vocabulary';

/**
 * The answer to a scan.
 *
 * `provisional` is the offline case and it is not cosmetic. A device holding a
 * cached bundle can check a hash and a validity window; it cannot know how many
 * of a four-guest party are already inside, or that the resident cancelled the
 * pass after the bundle was cut. So an offline *admitted* is a decision the
 * guard is making with partial information, and the card says exactly that
 * rather than looking like the server agreed.
 */
export default function VerdictCard({ verdict, onDismiss, provisional = false }) {
  if (!verdict) return null;
  const tone = VERDICT_STYLES[verdict.verdict] || 'border-slate-200 bg-slate-50 text-slate-700';
  const label = VERDICT_LABELS[verdict.verdict] || verdict.verdict;

  return (
    <div className={`rounded-2xl border p-4 ${tone}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-extrabold tracking-tight">{label}</p>
          <p className="mt-0.5 text-xs font-semibold opacity-90">{verdict.detail}</p>
        </div>
        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss"
            className="rounded-full bg-white/60 p-1.5"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      {provisional ? (
        <p className="mt-3 flex items-start gap-2 rounded-xl bg-white/70 p-3 text-[11px] font-bold">
          <CloudOff className="mt-px h-4 w-4 shrink-0" />
          <span>
            Provisional — decided on this device from the cached pass list. The server has
            not seen it yet and will record its own verdict when the gate is back online.
          </span>
        </p>
      ) : null}

      {verdict.visitorName ? (
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[11px] font-semibold">
          <Detail label="Visitor" value={verdict.visitorName} />
          <Detail label="Guests" value={verdict.guestCount ?? '—'} />
          <Detail label="Flat" value={verdict.unitCode || '—'} />
          <Detail label="Resident" value={verdict.residentName || '—'} />
          {verdict.validFrom || verdict.validUntil ? (
            <div className="col-span-2">
              <dt className="text-[9px] font-bold uppercase tracking-wider opacity-70">Valid</dt>
              <dd>
                {shortDateTime(verdict.validFrom)} — {shortDateTime(verdict.validUntil)}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : null}
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-[9px] font-bold uppercase tracking-wider opacity-70">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
