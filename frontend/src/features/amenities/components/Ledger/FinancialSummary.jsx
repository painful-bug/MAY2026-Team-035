import React from 'react';
import {
  CircleCheckBig,
  CircleDollarSign,
  IndianRupee,
  ReceiptText,
  RotateCcw,
  ShieldAlert,
  WalletCards,
  WalletMinimal,
} from 'lucide-react';
import { formatLedgerCurrency } from '../../utils/amenityLedger.js';
import LedgerSummaryCard from './LedgerSummaryCard.jsx';

export default function FinancialSummary({ summary }) {
  const cards = [
    {
      label: 'Total Bookings',
      value: summary.totalBookings,
      caption: 'Transactions recorded',
      icon: ReceiptText,
      iconClasses: 'bg-indigo-50 text-indigo-600',
    },
    {
      label: 'Total Revenue',
      value: formatLedgerCurrency(summary.totalRevenue),
      caption: 'Payments collected',
      icon: IndianRupee,
      iconClasses: 'bg-emerald-50 text-emerald-600',
    },
    {
      label: 'Pending Deposits',
      value: formatLedgerCurrency(summary.pendingDeposits),
      caption: 'Deposit balance due',
      icon: WalletCards,
      iconClasses: 'bg-amber-50 text-amber-600',
    },
    {
      label: 'Refund Pending',
      value: summary.refundPending,
      caption: 'Transactions awaiting refund',
      icon: RotateCcw,
      iconClasses: 'bg-blue-50 text-blue-600',
    },
    {
      label: 'Refund Completed',
      value: formatLedgerCurrency(summary.refundCompleted),
      caption: 'Deposits refunded',
      icon: CircleDollarSign,
      iconClasses: 'bg-emerald-50 text-emerald-600',
    },
    {
      label: 'Damage Deductions',
      value: formatLedgerCurrency(summary.damageDeductions),
      caption: 'Deposit deductions recorded',
      icon: ShieldAlert,
      iconClasses: 'bg-rose-50 text-rose-600',
    },
    {
      label: 'Outstanding Refunds',
      value: formatLedgerCurrency(summary.outstandingRefunds),
      caption: 'Refundable amount pending',
      icon: WalletMinimal,
      iconClasses: 'bg-amber-50 text-amber-600',
    },
    {
      label: 'Completed Transactions',
      value: summary.completedTransactions,
      caption: 'Paid and completed',
      icon: CircleCheckBig,
      iconClasses: 'bg-slate-100 text-slate-600',
    },
  ];

  return (
    <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <LedgerSummaryCard key={card.label} {...card} />
      ))}
    </section>
  );
}
