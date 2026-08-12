import React, { useRef, useState } from 'react';
import {
  Ban,
  Eye,
  MoreHorizontal,
  Plus,
  ReceiptText,
  RotateCcw,
  Wallet,
} from 'lucide-react';
import { LEDGER_ACTION } from '../../constants/ledgerStatuses.js';
import { getLedgerMenuActions } from '../../utils/amenityLedger.js';

const ACTION_META = {
  [LEDGER_ACTION.VIEW]: { label: 'View Details', icon: Eye },
  [LEDGER_ACTION.REFUND]: { label: 'Refund Deposit', icon: RotateCcw },
  [LEDGER_ACTION.DAMAGE]: {
    label: 'Deduct Damage Charges',
    icon: ReceiptText,
  },
  [LEDGER_ACTION.FORCE_CANCEL]: {
    label: 'Force Cancel Booking',
    icon: Ban,
  },
  // Money in, then money owed. Two different sentences about the same booking,
  // and the menu says which is which so nobody records a receipt when they
  // meant to raise a bill.
  [LEDGER_ACTION.PAYMENT]: { label: 'Record Payment Received', icon: Wallet },
  [LEDGER_ACTION.CHARGE]: { label: 'Add Charge', icon: Plus },
};

export default function LedgerActionsMenu({ transaction, onAction }) {
  const containerRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);

  const handleBlur = (event) => {
    if (!containerRef.current?.contains(event.relatedTarget)) {
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} onBlur={handleBlur} className="relative">
      <button
        type="button"
        aria-label={`Actions for ${transaction.bookingId}`}
        aria-expanded={isOpen}
        onClick={(event) => {
          event.stopPropagation();
          setIsOpen((current) => !current);
        }}
        className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition-colors hover:bg-white hover:text-indigo-700"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {isOpen && (
        <div className="absolute right-0 z-30 mt-2 w-56 rounded-xl border border-slate-100 bg-white p-1.5 shadow-lg shadow-slate-100">
          {getLedgerMenuActions(transaction).map((action) => {
            const meta = ACTION_META[action];

            if (!meta) {
              return null;
            }

            const Icon = meta.icon;
            const isDestructive = action === LEDGER_ACTION.FORCE_CANCEL;

            return (
              <button
                key={action}
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  setIsOpen(false);
                  onAction(action, transaction);
                }}
                className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-xs font-bold transition-colors ${
                  isDestructive
                    ? 'text-rose-600 hover:bg-rose-50'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-800'
                }`}
              >
                <Icon className="h-4 w-4" />
                {meta.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
