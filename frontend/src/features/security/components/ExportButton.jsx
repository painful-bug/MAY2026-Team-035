import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { securityApi } from '../securityApi';
import { ErrorText } from './Primitives';

/**
 * One register as CSV. `US-3.6`.
 *
 * Not a react-query mutation, because nothing is cached and nothing invalidates
 * — the result of pressing this is a file on the guard's device, which react-
 * query has no opinion about. Local state is the honest model.
 *
 * The range is whatever the screen is already filtered to. `US-3.6` asks for
 * *"six months, one year, or longer"* and gets it from `from`/`to` rather than
 * from a retention policy, because nothing here is ever aged out.
 */
export default function ExportButton({ dataset, from, to, label = 'Export CSV' }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      await securityApi.exportCsv(dataset, { from, to });
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={run}
        disabled={busy}
        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
        {label}
      </button>
      <ErrorText error={error} />
    </div>
  );
}
