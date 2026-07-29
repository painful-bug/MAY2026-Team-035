import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { CheckCircle, Clock, Check, Receipt, ShieldCheck } from 'lucide-react';

export default function Payments() {
  const { payments, currentUser, payInvoice } = useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  const userPayments = payments.filter(p => p.userId === currentUser?.id);
  const unpaidInvoices = userPayments.filter(p => p.status === 'Unpaid');
  const paidInvoices = userPayments.filter(p => p.status === 'Paid');

  const handlePayClick = (invoice) => {
    setSelectedInvoice(invoice);
    setModalOpen(true);
  };

  const handleConfirmPay = () => {
    if (!selectedInvoice) return;
    payInvoice(selectedInvoice.id, 'UPI');
    setModalOpen(false);
    setSelectedInvoice(null);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Maintenance & Dues</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Manage society maintenance charges, utility bills, and view historical invoices.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Unpaid Invoices */}
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

          {unpaidInvoices.length === 0 ? (
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
                      <p className="text-[10px] text-slate-450 font-semibold mt-1">Period: {inv.billPeriod}</p>
                    </div>
                    <p className="text-lg font-extrabold text-slate-900">₹{inv.amount.toLocaleString()}</p>
                  </div>

                  <div className="flex justify-between items-center pt-2 border-t border-slate-50">
                    <span className="text-[10px] text-rose-600 bg-rose-50/50 border border-rose-100 px-2 py-0.5 rounded-md font-bold">
                      Due On: {inv.dueDate}
                    </span>
                    <button
                      onClick={() => handlePayClick(inv)}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4.5 py-2 rounded-xl transition-all shadow-md shadow-indigo-100"
                    >
                      Pay Bill
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Paid Invoices History */}
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
                      <p className="text-[10px] text-slate-450 font-semibold mt-1">Period: {inv.billPeriod}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-base font-extrabold text-slate-800">₹{inv.amount.toLocaleString()}</p>
                      <span className="text-[9px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-100/50 px-1.5 py-0.5 rounded uppercase tracking-wider mt-1 inline-block">
                        Paid
                      </span>
                    </div>
                  </div>

                  <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 flex items-center justify-between text-[11px] font-semibold text-slate-500">
                    <span>Method: **{inv.paymentMethod}**</span>
                    <span>Paid On: {inv.paidOn}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* simulated Payment modal */}
      {modalOpen && selectedInvoice && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl border border-slate-100 max-w-md w-full p-6 space-y-6 animate-slide-up">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-extrabold text-slate-900">Society Payment Gateway</h3>
              <button 
                onClick={() => setModalOpen(false)}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                Cancel
              </button>
            </div>

            <div className="bg-indigo-50/50 border border-indigo-100/30 rounded-2xl p-4.5 space-y-2">
              <span className="text-[9px] font-extrabold uppercase tracking-wide text-indigo-500">Payment Invoice</span>
              <p className="text-sm font-bold text-slate-805">{selectedInvoice.title}</p>
              <div className="flex justify-between items-baseline pt-2">
                <span className="text-xs text-slate-450 font-bold">Total Payable:</span>
                <span className="text-xl font-extrabold text-slate-900">₹{selectedInvoice.amount.toLocaleString()}</span>
              </div>
            </div>

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
                Clicking confirm simulates a secure mock payment. The status in the application memory state will update instantly.
              </div>

              <button
                onClick={handleConfirmPay}
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-755 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 text-sm flex items-center justify-center gap-1.5"
              >
                <Check className="w-4 h-4" />
                Confirm Payment of ₹{selectedInvoice.amount.toLocaleString()}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
