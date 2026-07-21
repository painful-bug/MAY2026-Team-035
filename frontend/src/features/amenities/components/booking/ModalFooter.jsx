import React from 'react';

export default function ModalFooter({
  onCancel,
  isSubmitting,
  submitLabel,
  submittingLabel,
  onSecondaryAction,
  secondaryLabel,
  submitTone = 'primary',
}) {
  const submitClasses =
    submitTone === 'danger'
      ? 'bg-rose-600 text-white shadow-md shadow-rose-100 hover:bg-rose-700'
      : 'bg-indigo-600 text-white shadow-md shadow-indigo-100 hover:bg-indigo-700';

  return (
    <div className="flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
      {onSecondaryAction ? (
        <button
          type="button"
          onClick={onSecondaryAction}
          disabled={isSubmitting}
          className="rounded-xl px-4 py-2.5 text-xs font-bold text-rose-600 transition-colors hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {secondaryLabel}
        </button>
      ) : (
        <span />
      )}
      <div className="flex flex-col-reverse gap-2 sm:flex-row">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className={`rounded-xl px-4 py-2.5 text-xs font-bold transition-colors disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none ${submitClasses}`}
        >
          {isSubmitting ? submittingLabel : submitLabel}
        </button>
      </div>
    </div>
  );
}
