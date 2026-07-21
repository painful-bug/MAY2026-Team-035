import React from 'react';
import { getBookingTypeLabel } from '../../constants/bookingFormOptions.js';
import {
  formatLedgerCurrency,
  formatLedgerDate,
} from '../../utils/amenityLedger.js';
import BookingStatusBadge from '../booking/BookingStatusBadge.jsx';
import FormSection from '../booking/FormSection.jsx';
import ModalLayout from '../booking/ModalLayout.jsx';
import PaymentStatusBadge from './PaymentStatusBadge.jsx';
import AuditTimeline from './AuditTimeline.jsx';
import TransactionHistory from './TransactionHistory.jsx';

function DetailValue({ label, value, children }) {
  return (
    <div className="space-y-1 rounded-xl bg-slate-50 px-3.5 py-3">
      <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      {children ?? (
        <p className="text-xs font-bold text-slate-700">{value || '—'}</p>
      )}
    </div>
  );
}

export default function TransactionDetailsPanel({
  transaction,
  amenityName,
  onClose,
}) {
  return (
    <ModalLayout
      title="Transaction Details"
      description={`Booking ${transaction.bookingId}`}
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <div className="space-y-5">
        <FormSection title="Resident information">
          <div className="grid gap-3 sm:grid-cols-3">
            <DetailValue label="Resident" value={transaction.residentName} />
            <DetailValue label="Flat" value={transaction.residentFlat} />
            <DetailValue
              label="Resident ID"
              value={transaction.residentId}
            />
          </div>
        </FormSection>

        <FormSection title="Booking information">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <DetailValue label="Amenity" value={amenityName} />
            <DetailValue
              label="Booking Date"
              value={formatLedgerDate(transaction.bookingDate)}
            />
            <DetailValue
              label="Booking Type"
              value={getBookingTypeLabel(transaction.bookingType)}
            />
            <DetailValue label="Booking Status">
              <span className="inline-flex pt-0.5">
                <BookingStatusBadge status={transaction.bookingStatus} />
              </span>
            </DetailValue>
            <DetailValue label="Payment Status">
              <span className="inline-flex pt-0.5">
                <PaymentStatusBadge status={transaction.paymentStatus} />
              </span>
            </DetailValue>
            <DetailValue
              label="Payment Reference"
              value={transaction.paymentReference}
            />
          </div>
        </FormSection>

        <FormSection title="Payment summary">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <DetailValue
              label="Deposit Amount"
              value={formatLedgerCurrency(transaction.depositAmount)}
            />
            <DetailValue
              label="Booking Charges"
              value={formatLedgerCurrency(transaction.bookingCharges)}
            />
            <DetailValue
              label="Additional Charges"
              value={formatLedgerCurrency(transaction.additionalCharges)}
            />
            <DetailValue
              label="Total Amount"
              value={formatLedgerCurrency(transaction.totalAmount)}
            />
            <DetailValue
              label="Amount Paid"
              value={formatLedgerCurrency(transaction.amountPaid)}
            />
            <DetailValue
              label="Pending Deposit"
              value={formatLedgerCurrency(transaction.outstandingDeposit)}
            />
            <DetailValue
              label="Refunded Amount"
              value={formatLedgerCurrency(transaction.refundAmount)}
            />
            <DetailValue
              label="Damage Deductions"
              value={formatLedgerCurrency(transaction.damageAmount)}
            />
            <DetailValue
              label="Remaining Refund"
              value={formatLedgerCurrency(transaction.remainingRefund)}
            />
          </div>
        </FormSection>

        <FormSection title="Internal notes">
          <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs font-semibold leading-relaxed text-slate-600">
            {transaction.internalNotes || 'No internal notes recorded.'}
          </p>
        </FormSection>

        <TransactionHistory transaction={transaction} />

        <FormSection title="Audit timeline">
          <AuditTimeline entries={transaction.auditTrail} />
        </FormSection>

        <div className="flex justify-end border-t border-slate-100 pt-5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700"
          >
            Close
          </button>
        </div>
      </div>
    </ModalLayout>
  );
}
