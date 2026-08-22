import { Eye, MessageCircle, StickyNote, X } from 'lucide-react';

// The pieces every triage surface shares: the chip, the section frame, the
// empty and failure lines, the modal shell, and the three icon buttons that sit
// on every card in every section.
//
// **Why they left `SupervisorDashboard.jsx`.** Amendment 2 put two popups and a
// note composer beside the page, and all three draw the same chip and the same
// refusal line as the cards behind them. Copying a `Chip` into a modal is how a
// screen ends up with two chip vocabularies; importing one is how the frozen
// chip rules stay one rule.
//
// There is no shared `Modal` in this codebase and this file does not invent
// one — `ModalShell` is `JobDetailModal.jsx`'s own shell, lifted verbatim
// (fixed inset overlay, a sheet that is a bottom sheet on a phone and a card on
// a desktop, `max-h-[90vh]`, a sticky header, a Close button with an
// `aria-label`) so the supervisor's popups and the worker's are the same object
// on the same portal.

const when = new Intl.DateTimeFormat(undefined, {
  day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
});

export const whenText = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : when.format(date);
};

export function Chip({ className = 'bg-slate-100 text-slate-600 ring-slate-200', children }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ring-1 ring-inset ${className}`}
    >
      {children}
    </span>
  );
}

export function Section({ id, title, count, blurb, children }) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <div>
        <h2
          id={id}
          className="flex items-baseline gap-2 text-xs font-extrabold uppercase tracking-wider text-slate-500"
        >
          {title}
          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] tabular-nums text-slate-600">
            {count}
          </span>
        </h2>
        <p className="mt-1 text-[11px] font-semibold text-slate-400">{blurb}</p>
      </div>
      {children}
    </section>
  );
}

// Empty states say what an empty list *means* here, because in four of the five
// sections empty is the good outcome and in one of them it is the whole job.
// "No data" would read as a broken screen in all five.
export function Empty({ icon: Icon, children }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-6">
      <Icon className="h-5 w-5 shrink-0 text-slate-300" />
      <p className="text-xs font-semibold text-slate-500">{children}</p>
    </div>
  );
}

export function Failure({ error }) {
  if (!error) return null;
  const details = Array.isArray(error.details) ? error.details : [];
  return (
    <p role="alert" className="text-xs font-semibold text-rose-600">
      {error.message}
      {details.map((detail) => (
        <span key={`${detail.field}:${detail.message}`} className="block font-normal">
          {detail.field ? `${detail.field}: ` : ''}{detail.message}
        </span>
      ))}
    </p>
  );
}

// Every icon-only control on this surface goes through here, so that "it has a
// name and it shows its focus" is a property of the component rather than a
// thing six call sites each remembered. `title` doubles the label for a mouse;
// `aria-label` is the one a screen reader and the tests read.
export function IconButton({ label, icon: Icon, onClick, disabled, pending, tone = 'slate' }) {
  const tones = {
    slate: 'text-slate-500 hover:bg-slate-100 hover:text-slate-700',
    indigo: 'text-indigo-600 hover:bg-indigo-50',
  };
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled || pending}
      onClick={onClick}
      className={`rounded-xl p-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 ${tones[tone]}`}
    >
      <Icon className={`h-4 w-4 ${pending ? 'animate-pulse' : ''}`} />
    </button>
  );
}

/**
 * The three verbs a supervisor holds over *any* row on this page.
 *
 * Amendment 2 puts them on every card in every section, including the two
 * monitor-only ones — looking, asking and recording are not stage-specific, and
 * a supervisor who can only ask a question about work that has not started yet
 * is a supervisor who telephones instead.
 *
 * `complaintId` can be null: `TriageWorkOrder.complaintId` is nullable in the
 * frozen DTO, and a job raised against no complaint has no timeline to show, no
 * resident to chat to and nothing to note. The buttons stay drawn and disabled,
 * with the reason in their title, rather than disappearing on one card in a row
 * of otherwise identical ones.
 */
export function CardActions({ subject, complaintId, onOpen, onChat, onNote, chatPending }) {
  const orphan = !complaintId;
  const reason = orphan ? ' — this job has no complaint behind it' : '';
  return (
    <div className="flex items-center gap-0.5">
      <IconButton
        label={`View details of ${subject}${reason}`}
        icon={Eye}
        disabled={orphan}
        onClick={onOpen}
      />
      <IconButton
        label={`Chat about ${subject}${reason}`}
        icon={MessageCircle}
        disabled={orphan}
        pending={chatPending}
        onClick={onChat}
      />
      <IconButton
        label={`Add an internal note to ${subject}${reason}`}
        icon={StickyNote}
        disabled={orphan}
        onClick={onNote}
      />
    </div>
  );
}

export function ModalShell({ title, subtitle, onClose, children, footer }) {
  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center bg-slate-900/50 p-0 backdrop-blur-sm sm:items-center sm:p-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-3xl bg-white sm:rounded-3xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 bg-white px-5 py-4">
          <div className="min-w-0">
            <p className="truncate text-base font-extrabold text-slate-900">{title}</p>
            {subtitle ? (
              <p className="mt-0.5 truncate text-xs font-semibold text-slate-500">{subtitle}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">{children}</div>
        {footer ? <div className="border-t border-slate-100 px-5 py-3">{footer}</div> : null}
      </div>
    </div>
  );
}
