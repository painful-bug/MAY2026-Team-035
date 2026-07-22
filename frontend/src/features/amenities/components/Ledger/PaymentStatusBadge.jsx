import React from 'react';
import {
  PAYMENT_STATUS,
  PAYMENT_STATUS_LABELS,
} from '../../constants/ledgerStatuses.js';

const STATUS_CLASSES = {
  [PAYMENT_STATUS.PAID]:
    'border-emerald-100 bg-emerald-50 text-emerald-700',
  [PAYMENT_STATUS.PENDING]: 'border-amber-100 bg-amber-50 text-amber-700',
  [PAYMENT_STATUS.PARTIALLY_PAID]:
    'border-blue-100 bg-blue-50 text-blue-700',
  [PAYMENT_STATUS.REFUND_PENDING]:
    'border-indigo-100 bg-indigo-50 text-indigo-700',
  [PAYMENT_STATUS.REFUNDED]:
    'border-emerald-100 bg-emerald-50 text-emerald-700',
  [PAYMENT_STATUS.CANCELLED]:
    'border-slate-200 bg-slate-50 text-slate-600',
};

export default function PaymentStatusBadge({ status }) {
  const label = PAYMENT_STATUS_LABELS[status];
  const classes = STATUS_CLASSES[status];

  if (!label || !classes) {
    return null;
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-[10px] font-extrabold ${classes}`}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}
