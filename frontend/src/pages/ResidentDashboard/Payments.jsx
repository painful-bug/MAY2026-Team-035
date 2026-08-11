import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle, Clock, Check, Receipt, ShieldCheck, CalendarClock } from 'lucide-react';
import { residentApi } from '../../features/resident/residentApi';

// Wired to `docs/API.md` §14 / `backend/app/api/v1/routers/resident_money.py`.
//
// Two independent bills a resident can owe: maintenance invoices
// (`GET /invoices/mine`, `POST /invoices/{id}/pay`) and amenity booking
// charges (`GET /amenity-bookings/mine`, `POST /amenity-bookings/{id}/pay`).
// The demo only ever had the first; the second section below is new.
//
// **The gateway is a simulator, and every screen has to say so.** `provider =
// 'simulator'` is written on every row it creates -- §14.1. A decline is a
// `200`, not a thrown error (§14.2): `PaymentOutcome.status` is `succeeded` or
// `failed`, and the client branches on it rather than on the HTTP status.
//
// This screen renders UPI as the only method and sends no instrument at all,
// which is the one row of the simulator's table that always succeeds (§14.3
// last row) -- so the decline branch below is real code, reachable the day a
// VPA field or the card fields get built, but not reachable from this screen
// today. That gap is the API's own note, not an omission here.
const money = (value) =>
  `₹${Number(value ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const formatDate = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};

const mintIdempotencyKey = () =>
  `pay-${typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;

export default function Payments() {
  const queryClient = useQueryClient();
  const [payTarget, setPayTarget] = useState(null); // { kind: 'invoice' | 'booking', item }
  const [idempotencyKey, setIdempotencyKey] = useState(null);
  const [outcome, setOutcome] = useState(null);

  const invoicesQuery = useQuery({
    queryKey: ['resident', 'invoices'],
    queryFn: () => residentApi.invoices(),
  });
  const bookingsQuery = useQuery({
    queryKey: ['resident', 'amenity-bookings'],
    queryFn: () => residentApi.amenityBookings(),
  });

  const invalidateForKind = (kind) => {
    queryClient.invalidateQueries({ queryKey: ['resident', kind === 'invoice' ? 'invoices' : 'amenity-bookings'] });
  };

  const pay = useMutation({
    mutationFn: ({ kind, item }) => {
      const body = {
        amount: item.outstandingAmount,
        idempotencyKey,
        method: 'upi',
        upi: { vpa: '' },
      };
      return kind === 'invoice'
        ? residentApi.payInvoice(item.id, body)
        : residentApi.payAmenityBooking(item.id, body);
    },
    onSuccess: (result, { kind }) => {
      setOutcome(result);
      invalidateForKind(kind);
      if (result.status !== 'succeeded') {
        // A new attempt needs a new key -- reusing the one that just failed
        // would replay the same decline forever (docs/API.md §14.4).
        setIdempotencyKey(mintIdempotencyKey());
      }
    },
  });

  const openPay = (kind, item) => {
    setPayTarget({ kind, item });
    setIdempotencyKey(mintIdempotencyKey());
    setOutcome(null);
  };

  const closeModal = () => {
    setPayTarget(null);
    setIdempotencyKey(null);
    setOutcome(null);
    pay.reset();
  };

  const invoices = invoicesQuery.data?.items || [];
  const unpaidInvoices = invoices.filter((inv) => inv.status === 'Unpaid');
  const paidInvoices = invoices.filter((inv) => inv.status === 'Paid');

  const bookings = bookingsQuery.data?.items || [];
  const payableBookings = bookings.filter((b) => b.isPayable && Number(b.outstandingAmount) > 0);
  const settledBookings = bookings.filter((b) => !(b.isPayable && Number(b.outstandingAmount) > 0));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Maintenance & Dues</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Manage society maintenance charges, amenity booking dues, and view historical invoices.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white p-5 border border-slate-100 rounded-2xl flex items-center justify-between shadow-sm">
            <h3 className="font-extrabold text-slate-800 text-sm flex items-center gap-2 text-rose-650">
              <Clock className="w-5 h-5 text-rose-500" />
              Pending Invoices
            </h3>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-rose-50 px-2.5 py-1 border border-rose-100 rounded-lg text-rose-700">
              {unpaidInvoices.length} Unpaid
            </span>
          </div>

          {invoicesQuery.isLoading ? (
            <div className="bg-white p-12 text-center text-xs text-slate-400 font-semibold border border-slate-100 rounded-2xl">
              Loading invoices…
            </div>
          ) : invoicesQuery.error ? (
            <div role="alert" className="bg-white p-6 text-center text-xs text-rose-600 font-semibold border border-rose-100 rounded-2xl">
              {invoicesQuery.error.message || 'Could not load invoices.'}
            </div>
          ) : unpaidInvoices.length === 0 ? (
            <div className="bg-white p-12 text-center text-xs text-slate-400 font-semibold border border-slate-100 rounded-2xl">
              All dues cleared! No pending maintenance bills.
            </div>
          ) : (
            <div className="space-y-4">
              {unpaidInvoices.map((inv) => (
                <div key={inv.id} className="bg-white border border-slate-100 p-6 rounded-2xl shadow-sm space-y-4 hover:border-indigo-100 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="text-sm font-extrabold text-slate-850">{inv.title}</h4>
                      <p className="text-[10px] text-slate-450 font-semibold mt-1">
                        {inv.invoiceNumber ? `#${inv.invoiceNumber}` : 'Not yet numbered'}
                      </p>
                    </div>
                    <p className="text-lg font-extrabold text-slate-900">{money(inv.outstandingAmount)}</p>
                  </div>

                  <div className="flex justify-between items-center pt-2 border-t border-slate-50">
                    <span className="text-[10px] text-rose-600 bg-rose-50/50 border border-rose-100 px-2 py-0.5 rounded-md font-bold">
                      Due On: {formatDate(inv.dueOn)}
                    </span>
                    <button
                      onClick={() => openPay('invoice', inv)}
                      disabled={!inv.isPayable}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4.5 py-2 rounded-xl transition-all shadow-md shadow-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      Pay Bill
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white p-5 border border-slate-100 rounded-2xl flex items-center justify-between shadow-sm">
            <h3 className="font-extrabold text-slate-800 text-sm flex items-center gap-2 text-emerald-700">
              <CheckCircle className="w-5 h-5 text-emerald-600" />
              Payment History
            </h3>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-50 px-2.5 py-1 border border-emerald-100 rounded-lg text-emerald-800">
              {paidInvoices.length} Paid
            </span>
          </div>

          {paidInvoices.length === 0 ? (
            <div className="bg-white p-12 text-center text-xs text-slate-400 font-semibold border border-slate-100 rounded-2xl">
              No payment history records found.
            </div>
          ) : (
            <div className="space-y-4">
              {paidInvoices.map((inv) => (
                <div key={inv.id} className="bg-white border border-slate-150 p-6 rounded-2xl shadow-sm space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="text-sm font-extrabold text-slate-850">{inv.title}</h4>
                      <p className="text-[10px] text-slate-450 font-semibold mt-1">
                        {inv.invoiceNumber ? `#${inv.invoiceNumber}` : 'Not yet numbered'}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-base font-extrabold text-slate-800">{money(inv.totalAmount)}</p>
                      <span className="text-[9px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-100/50 px-1.5 py-0.5 rounded uppercase tracking-wider mt-1 inline-block">
                        Paid
                      </span>
                    </div>
                  </div>

                  <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 flex items-center justify-between text-[11px] font-semibold text-slate-500">
                    <span>Method: **{inv.instrumentLabel || inv.paymentMethod || 'unknown'}**</span>
                    <span>Paid On: {formatDate(inv.paidAt)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4">
        <div className="bg-white p-5 border border-slate-100 rounded-2xl flex items-center justify-between shadow-sm">
          <h3 className="font-extrabold text-slate-800 text-sm flex items-center gap-2 text-indigo-700">
            <CalendarClock className="w-5 h-5 text-indigo-600" />
            Amenity Booking Dues
          </h3>
          <span className="text-[10px] font-bold uppercase tracking-wider bg-indigo-50 px-2.5 py-1 border border-indigo-100 rounded-lg text-indigo-700">
            {payableBookings.length} Awaiting Payment
          </span>
        </div>

        {bookingsQuery.isLoading ? (
          <div className="bg-white p-12 text-center text-xs text-slate-400 font-semibold border border-slate-100 rounded-2xl">
            Loading amenity bookings…
          </div>
        ) : bookingsQuery.error ? (
          <div role="alert" className="bg-white p-6 text-center text-xs text-rose-600 font-semibold border border-rose-100 rounded-2xl">
            {bookingsQuery.error.message || 'Could not load amenity bookings.'}
          </div>
        ) : bookings.length === 0 ? (
          <div className="bg-white p-12 text-center text-xs text-slate-400 font-semibold border border-slate-100 rounded-2xl">
            You have no amenity bookings.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[...payableBookings, ...settledBookings].map((booking) => (
              <div key={booking.id} className="bg-white border border-slate-100 p-6 rounded-2xl shadow-sm space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-sm font-extrabold text-slate-850">{booking.amenityName}</h4>
                    <p className="text-[10px] text-slate-450 font-semibold mt-1">
                      {formatDate(booking.startsAt)} · {booking.status}
                    </p>
                  </div>
                  <p className="text-base font-extrabold text-slate-900">
                    {money(booking.isPayable ? booking.outstandingAmount : booking.totalAmount)}
                  </p>
                </div>
                {booking.isPayable && Number(booking.outstandingAmount) > 0 ? (
                  <button
                    onClick={() => openPay('booking', booking)}
                    className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4.5 py-2 rounded-xl transition-all shadow-md shadow-indigo-100"
                  >
                    Pay {money(booking.outstandingAmount)}
                  </button>
                ) : (
                  <span className="inline-flex text-[9px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-100/50 px-1.5 py-0.5 rounded uppercase tracking-wider">
                    {Number(booking.outstandingAmount) === 0 ? 'Settled' : booking.status}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {payTarget && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl border border-slate-100 max-w-md w-full p-6 space-y-6 animate-slide-up">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-extrabold text-slate-900">Society Payment Gateway</h3>
              <button
                onClick={closeModal}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                Close
              </button>
            </div>

            <div className="bg-indigo-50/50 border border-indigo-100/30 rounded-2xl p-4.5 space-y-2">
              <span className="text-[9px] font-extrabold uppercase tracking-wide text-indigo-500">
                {payTarget.kind === 'invoice' ? 'Payment Invoice' : 'Amenity Booking'}
              </span>
              <p className="text-sm font-bold text-slate-805">
                {payTarget.kind === 'invoice' ? payTarget.item.title : payTarget.item.amenityName}
              </p>
              <div className="flex justify-between items-baseline pt-2">
                <span className="text-xs text-slate-450 font-bold">Total Payable:</span>
                <span className="text-xl font-extrabold text-slate-900">{money(payTarget.item.outstandingAmount)}</span>
              </div>
            </div>

            {outcome ? (
              outcome.status === 'succeeded' ? (
                <div className="space-y-4 text-center">
                  <CheckCircle className="mx-auto h-10 w-10 text-emerald-600" />
                  <p className="text-sm font-bold text-slate-800">Payment successful.</p>
                  <p className="text-xs font-semibold text-slate-400">
                    Settled via {outcome.instrumentLabel} · {money(outcome.amount)}
                  </p>
                  <button
                    onClick={closeModal}
                    className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all text-sm"
                  >
                    Done
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div role="alert" className="rounded-xl border border-rose-100 bg-rose-50 p-4 text-center">
                    <p className="text-sm font-bold text-rose-700">Payment declined.</p>
                    <p className="mt-1 text-[11px] font-semibold text-rose-500">{outcome.failureCode || 'The gateway declined this attempt.'}</p>
                  </div>
                  <button
                    onClick={() => pay.mutate(payTarget)}
                    disabled={pay.isPending}
                    className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all text-sm disabled:opacity-60"
                  >
                    Try again
                  </button>
                </div>
              )
            ) : (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Payment Options</label>
                  <div className="grid grid-cols-2 gap-3 text-center">
                    <div className="p-3.5 border border-indigo-500 bg-indigo-50/20 text-indigo-950 rounded-xl text-xs font-bold cursor-pointer flex flex-col items-center justify-center gap-1">
                      <ShieldCheck className="w-5 h-5 text-indigo-650" />
                      <span>UPI Payment</span>
                    </div>
                    <div className="p-3.5 border border-slate-150 text-slate-400 hover:bg-slate-50 rounded-xl text-xs font-bold cursor-not-allowed flex flex-col items-center justify-center gap-1">
                      <Receipt className="w-5 h-5 text-slate-400" />
                      <span>Cards/Netbanking</span>
                    </div>
                  </div>
                </div>

                <div className="text-[10px] text-slate-400 font-semibold text-center leading-relaxed">
                  This runs against the simulated gateway (`docs/API.md` §14.1). No money moves;
                  every payment it settles is written with `provider = simulator`.
                </div>

                {pay.error && (
                  <p role="alert" className="text-[11px] font-semibold text-rose-600 text-center">
                    {pay.error.message}
                  </p>
                )}

                <button
                  onClick={() => pay.mutate(payTarget)}
                  disabled={pay.isPending}
                  className="w-full py-3 bg-indigo-600 hover:bg-indigo-755 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 text-sm flex items-center justify-center gap-1.5 disabled:opacity-60"
                >
                  <Check className="w-4 h-4" />
                  {pay.isPending ? 'Processing…' : `Confirm Payment of ${money(payTarget.item.outstandingAmount)}`}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
