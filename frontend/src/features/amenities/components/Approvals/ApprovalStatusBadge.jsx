import React from 'react';
import {
  BOOKING_STATUS,
  BOOKING_STATUS_LABELS,
} from '../../constants/bookingStatuses.js';

const STATUS_CLASSES = {
  [BOOKING_STATUS.PENDING]: 'border-amber-100 bg-amber-50 text-amber-700',
  [BOOKING_STATUS.APPROVED]:
    'border-emerald-100 bg-emerald-50 text-emerald-700',
  [BOOKING_STATUS.REJECTED]: 'border-rose-100 bg-rose-50 text-rose-700',
  [BOOKING_STATUS.CANCELLED]:
    'border-slate-200 bg-slate-50 text-slate-600',
};

export default function ApprovalStatusBadge({ status }) {
  const label = BOOKING_STATUS_LABELS[status];
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
