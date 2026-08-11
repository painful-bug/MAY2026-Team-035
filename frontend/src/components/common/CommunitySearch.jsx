import { Loader2, Search } from 'lucide-react';

export default function CommunitySearch({
  inputId = 'community-search',
  label,
  value,
  onChange,
  onSubmit,
  placeholder,
  submitLabel,
  hint,
  isLoading,
  error,
  items = [],
  showEmpty,
  emptyMessage,
  resultsClassName = '',
  resultsRole,
  renderResult,
}) {
  const controls = (
    <>
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          id={inputId}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm font-medium outline-none focus:border-indigo-500"
        />
      </div>
      {submitLabel ? (
        <button type="submit" className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white hover:bg-slate-800">
          {submitLabel}
        </button>
      ) : null}
    </>
  );

  return (
    <div className="space-y-2">
      {label ? <label htmlFor={inputId} className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</label> : null}
      {onSubmit ? (
        <form onSubmit={(event) => { event.preventDefault(); onSubmit(); }} className="flex gap-2">{controls}</form>
      ) : (
        <div className="flex gap-2">{controls}</div>
      )}
      {hint}
      {isLoading ? <p className="inline-flex items-center gap-2 text-xs font-medium text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />Searching communities…</p> : null}
      {error ? <p role="alert" className="text-xs font-semibold text-rose-600">{error}</p> : null}
      {showEmpty ? <p className="rounded-xl border border-dashed border-slate-300 px-4 py-6 text-center text-xs font-semibold text-slate-500">{emptyMessage}</p> : null}
      {items.length > 0 ? (
        <div role={resultsRole} className={resultsClassName}>
          {items.map(renderResult)}
        </div>
      ) : null}
    </div>
  );
}
