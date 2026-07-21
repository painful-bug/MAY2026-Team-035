import React from 'react';
import { formatLedgerCurrency } from '../../utils/amenityLedger.js';
import FormSection from '../booking/FormSection.jsx';

const formatHistoryDate = (timestamp) =>
  new Date(timestamp).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });

function HistorySection({ title, entries, renderSummary }) {
  return (
    <FormSection title={title}>
      {entries.length === 0 ? (
        <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-400">
          No history recorded.
        </p>
      ) : (
        <div className="divide-y divide-slate-50">
          {entries.map((entry) => (
            <div key={entry.id} className="py-3 first:pt-0 last:pb-0">
              <p className="text-xs font-bold text-slate-700">
                {renderSummary(entry)}
              </p>
              <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
                {formatHistoryDate(entry.createdAt)}
              </p>
            </div>
          ))}
        </div>
      )}
    </FormSection>
  );
}

export default function TransactionHistory({ transaction }) {
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <HistorySection
        title="Refund history"
        entries={transaction.refundHistory}
        renderSummary={(entry) =>
          `${formatLedgerCurrency(entry.amount)}${
            entry.reason ? ` · ${entry.reason}` : ''
          }`
        }
      />
      <HistorySection
        title="Damage history"
        entries={transaction.damageHistory}
        renderSummary={(entry) =>
          `${formatLedgerCurrency(entry.amount)} · ${entry.reason}`
        }
      />
      <HistorySection
        title="Cancellation history"
        entries={transaction.cancellationHistory}
        renderSummary={(entry) => entry.reason}
      />
    </div>
  );
}
