import { useEffect } from 'react';
import { X } from 'lucide-react';

// The pieces every gate screen repeats. Lifted from the two demo dashboards,
// which each carried their own byte-identical copy of `MetricCard` — the
// duplication that made a change to one of them a change to neither.

const TONES = {
  indigo: 'bg-indigo-50 text-indigo-600',
  amber: 'bg-amber-50 text-amber-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  rose: 'bg-rose-50 text-rose-600',
  slate: 'bg-slate-100 text-slate-500',
};

export function MetricCard({ icon: Icon, label, value, detail, tone = 'indigo' }) {
  return (
    <article className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`rounded-xl p-2.5 ${TONES[tone] || TONES.indigo}`}>
          <Icon className="h-5 w-5" />
        </div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
          {label}
        </p>
      </div>
      <p className="mt-4 text-3xl font-extrabold tracking-tight text-slate-900">{value}</p>
      {detail ? (
        <p className="mt-1 text-[11px] font-semibold text-slate-400">{detail}</p>
      ) : null}
    </article>
  );
}

export function Pill({ children, className = '' }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold ${
        className || 'bg-slate-100 text-slate-600'
      }`}
    >
      {children}
    </span>
  );
}

export function PageHeading({ title, description, action }) {
  return (
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{title}</h1>
        {description ? (
          <p className="mt-1 text-xs font-semibold text-slate-400">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function Empty({ children }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 px-5 py-10 text-center text-sm font-semibold text-slate-500">
      {children}
    </div>
  );
}

export function Loading({ children = 'Loading…' }) {
  return <p className="text-sm font-semibold text-slate-500">{children}</p>;
}

/**
 * Any failure, rendered where the thing that failed is.
 *
 * `community_role_required` gets its own sentence because the raw message —
 * *Only gate staff may use this* — reads like a bug to somebody who was handed
 * a gate login, and the actual cause is a membership that has not been given a
 * gate role in *this* community.
 */
export function ErrorText({ error }) {
  if (!error) return null;
  const message =
    error.code === 'community_role_required'
      ? 'Your account holds no gate role in this community, so this screen has nothing to show. Ask an admin to add you to the security department.'
      : error.message;
  return (
    <p role="alert" className="text-sm font-semibold text-rose-600">
      {message}
    </p>
  );
}

/** A centred sheet. Escape closes, the backdrop closes, the body stops scrolling. */
export function GateModal({ title, description, onClose, children, wide = false }) {
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className={`max-h-[90vh] w-full overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl ${
          wide ? 'max-w-2xl' : 'max-w-lg'
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-extrabold text-slate-900">{title}</h2>
            {description ? (
              <p className="mt-0.5 text-[11px] font-semibold text-slate-400">{description}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}

/** A segmented pill bar. Wide targets, horizontally scrollable — a gate is a phone. */
export function TabBar({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1">
      {tabs.map(([id, label]) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={`shrink-0 rounded-lg px-4 py-2 text-xs font-bold ${
            active === id ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
