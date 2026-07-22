import React from 'react';

export default function SettingsFooter({
  isDirty,
  isSaving,
  error,
  onReset,
}) {
  return (
    <footer className="sticky bottom-4 z-10 rounded-2xl border border-slate-100 bg-white/95 p-4 shadow-sm backdrop-blur sm:flex sm:items-center sm:justify-between sm:px-5">
      <div>
        <p className="text-xs font-extrabold text-slate-700">
          {isDirty ? 'You have unsaved changes.' : 'Settings are up to date.'}
        </p>
        {error && (
          <p role="alert" className="mt-1 text-[11px] font-semibold text-rose-600">
            {error}
          </p>
        )}
      </div>
      <div className="mt-3 flex gap-3 sm:mt-0">
        <button
          type="button"
          disabled={!isDirty || isSaving}
          onClick={onReset}
          className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none"
        >
          Reset Changes
        </button>
        <button
          type="submit"
          disabled={!isDirty || isSaving}
          className="flex-1 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none sm:flex-none"
        >
          {isSaving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </footer>
  );
}
