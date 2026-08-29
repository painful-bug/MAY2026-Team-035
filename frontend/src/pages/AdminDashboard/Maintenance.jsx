import React, { useState } from 'react';
// Modal renders through a portal to document.body. In place, it sat inside
// AdminLayout's `<main class="animate-fade-in">` — a fill-forwards opacity
// animation keeps <main> a stacking context forever, so `z-[999]` was trapped
// at <main>'s own level and the sticky header's `z-40` painted above it. Same
// fix as the departments modals (Departments.jsx).
import { createPortal } from 'react-dom';
import { useMutation } from '@tanstack/react-query';
import { useApp } from '../../store/useApp';
import {
  CreditCard, Search, CheckCircle, Clock, Plus, BadgeIndianRupee, X, BookMarked,
} from 'lucide-react';
import { moneyApi } from '../../features/money/moneyApi';
import { getDashboardSnapshot } from '../../lib/dashboard/dashboardApi';

const INVOICE_TYPES = ['maintenance', 'amenity', 'penalty', 'misc'];
const PAYMENT_METHODS = ['Cash', 'UPI', 'Credit Card', 'Net Banking', 'Cheque', 'Bank Transfer'];

const fieldClass = 'w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold';

function Modal({ title, icon: Icon, onClose, children }) {
  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4"
    >
      <div className="bg-white rounded-3xl border border-slate-100 max-w-lg w-full p-6 space-y-5 animate-slide-up max-h-[calc(100vh-2rem)] overflow-y-auto">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-extrabold text-slate-900 flex items-center gap-2">
            {Icon ? <Icon className="w-5 h-5 text-indigo-600" /> : null}
            {title}
          </h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-650">
            <X className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  );
}

// Issue one invoice against one flat. `POST /invoices` -- the flat is created
// on first reference, so there is no separate flat-picker step.
function CreateInvoiceModal({ onClose, onCreated }) {
  const [title, setTitle] = useState('');
  const [flat, setFlat] = useState('');
  const [invoiceType, setInvoiceType] = useState('maintenance');
  const [dueDate, setDueDate] = useState('');
  const [taxPercent, setTaxPercent] = useState('');
  const [notes, setNotes] = useState('');
  const [lineItems, setLineItems] = useState([{ description: '', quantity: 1, unitAmount: '' }]);

  const create = useMutation({
    mutationFn: (payload) => moneyApi.createInvoice(payload),
    onSuccess: onCreated,
  });

  const updateLine = (index, field, value) => {
    setLineItems((rows) => rows.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  };
  const addLine = () => setLineItems((rows) => [...rows, { description: '', quantity: 1, unitAmount: '' }]);
  const removeLine = (index) => setLineItems((rows) => rows.filter((_, i) => i !== index));

  const handleSubmit = (event) => {
    event.preventDefault();
    if (create.isPending) return;
    const cleanLines = lineItems
      .filter((row) => row.description.trim() && Number(row.unitAmount) > 0)
      .map((row) => ({
        description: row.description.trim(),
        quantity: Number(row.quantity) || 1,
        unitAmount: Number(row.unitAmount),
      }));
    if (!title.trim() || !flat.trim() || cleanLines.length === 0) return;
    create.mutate({
      title: title.trim(),
      flat: flat.trim(),
      invoiceType,
      lineItems: cleanLines,
      dueDate: dueDate || null,
      taxPercent: taxPercent === '' ? null : Number(taxPercent),
      notes: notes.trim() || null,
    });
  };

  const total = lineItems.reduce(
    (sum, row) => sum + (Number(row.quantity) || 0) * (Number(row.unitAmount) || 0), 0
  );

  return (
    <Modal title="Issue an invoice" icon={BadgeIndianRupee} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Title</span>
            <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Clubhouse Event Charge" className={fieldClass} />
          </label>
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Flat</span>
            <input required value={flat} onChange={(e) => setFlat(e.target.value)} placeholder="e.g. B-1204" className={fieldClass} />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Invoice type</span>
            <select value={invoiceType} onChange={(e) => setInvoiceType(e.target.value)} className={fieldClass}>
              {INVOICE_TYPES.map((type) => (
                <option key={type} value={type}>{type[0].toUpperCase() + type.slice(1)}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Due date</span>
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={fieldClass} />
          </label>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Line items</span>
            <button type="button" onClick={addLine} className="text-[11px] font-bold text-indigo-600 flex items-center gap-1">
              <Plus className="w-3.5 h-3.5" />Add line
            </button>
          </div>
          {lineItems.map((row, index) => (
            <div key={index} className="grid grid-cols-[1fr_4.5rem_5.5rem_auto] gap-2 items-center">
              <input
                required
                placeholder="Description"
                value={row.description}
                onChange={(e) => updateLine(index, 'description', e.target.value)}
                className={fieldClass}
              />
              <input
                type="number"
                min="1"
                placeholder="Qty"
                value={row.quantity}
                onChange={(e) => updateLine(index, 'quantity', e.target.value)}
                className={fieldClass}
              />
              <input
                type="number"
                min="0.01"
                step="0.01"
                required
                placeholder="Amount"
                value={row.unitAmount}
                onChange={(e) => updateLine(index, 'unitAmount', e.target.value)}
                className={fieldClass}
              />
              <button
                type="button"
                onClick={() => removeLine(index)}
                disabled={lineItems.length === 1}
                className="text-slate-400 hover:text-rose-600 disabled:opacity-30"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Tax percent (optional)</span>
            <input type="number" min="0" max="99.99" step="0.01" value={taxPercent} onChange={(e) => setTaxPercent(e.target.value)} className={fieldClass} />
          </label>
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Line total</span>
            <p className="text-sm font-extrabold text-slate-800 py-2.5">₹{total.toLocaleString()}</p>
          </div>
        </div>

        <label className="space-y-1 block">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Notes (optional)</span>
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className={fieldClass} />
        </label>

        {create.error ? (
          <p role="alert" className="text-xs font-semibold text-rose-600">{create.error.message}</p>
        ) : null}

        <button
          type="submit"
          disabled={create.isPending}
          className="w-full py-3 bg-indigo-650 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 text-xs flex items-center justify-center gap-1.5 disabled:opacity-60"
        >
          {create.isPending ? 'Issuing…' : 'Issue invoice'}
        </button>
      </form>
    </Modal>
  );
}

// Record money already received against one invoice. **Not a checkout.**
// `POST /invoices/{id}/payments` marks the invoice settled based on payment
// taken outside the app -- the copy below says so on purpose, so nobody reads
// this as a resident-facing "pay now" button.
function RecordPaymentModal({ invoice, onClose, onRecorded }) {
  const [amount, setAmount] = useState(String(invoice.amount ?? ''));
  const [method, setMethod] = useState('Cash');
  const [reference, setReference] = useState('');
  const [paidAt, setPaidAt] = useState('');
  const [notes, setNotes] = useState('');

  const record = useMutation({
    mutationFn: (payload) => moneyApi.recordPayment(invoice.id, payload),
    onSuccess: onRecorded,
  });

  const handleSubmit = (event) => {
    event.preventDefault();
    if (record.isPending) return;
    const numeric = Number(amount);
    if (!(numeric > 0)) return;
    record.mutate({
      amount: numeric,
      method,
      reference: reference.trim() || null,
      paidAt: paidAt ? new Date(paidAt).toISOString() : null,
      notes: notes.trim() || null,
    });
  };

  return (
    <Modal title="Record a payment received" icon={BookMarked} onClose={onClose}>
      <div className="rounded-xl bg-amber-50 border border-amber-100 p-3 text-[11px] font-semibold text-amber-800 leading-relaxed">
        This records money the community has <strong>already received</strong> outside the
        app -- cash in hand, a bank transfer confirmed by phone, and so on. It settles{' '}
        <strong>{invoice.title}</strong> ({invoice.flat ? `Flat ${invoice.flat}` : 'this invoice'}).
        It does not charge the resident and is not a payment gateway.
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Amount received</span>
            <input
              type="number"
              min="0.01"
              step="0.01"
              required
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={fieldClass}
            />
          </label>
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Method</span>
            <select value={method} onChange={(e) => setMethod(e.target.value)} className={fieldClass}>
              {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Reference (optional)</span>
            <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="e.g. TXN-88213" className={fieldClass} />
          </label>
          <label className="space-y-1">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Received on (optional)</span>
            <input type="date" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} className={fieldClass} />
          </label>
        </div>
        <label className="space-y-1 block">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Notes (optional)</span>
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className={fieldClass} />
        </label>

        {record.error ? (
          <p role="alert" className="text-xs font-semibold text-rose-600">{record.error.message}</p>
        ) : null}

        <button
          type="submit"
          disabled={record.isPending}
          className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl transition-all shadow-md shadow-emerald-100 text-xs flex items-center justify-center gap-1.5 disabled:opacity-60"
        >
          {record.isPending ? 'Recording…' : 'Record payment received'}
        </button>
      </form>
    </Modal>
  );
}

export default function Maintenance() {
  const payments = useApp((state) => state.payments);
  const users = useApp((state) => state.users);
  const hydrateDashboard = useApp((state) => state.hydrateDashboard);
  const showToast = useApp((state) => state.showToast);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('All');
  const [creating, setCreating] = useState(false);
  const [recordingFor, setRecordingFor] = useState(null);

  const refreshDashboard = async () => {
    const snapshot = await getDashboardSnapshot();
    hydrateDashboard(snapshot);
  };

  // Stats Calculations
  const paidPayments = payments.filter(p => p.status === 'Paid');
  const unpaidPayments = payments.filter(p => p.status === 'Unpaid');
  const totalCollected = paidPayments.reduce((acc, curr) => acc + curr.amount, 0);
  const totalOutstanding = unpaidPayments.reduce((acc, curr) => acc + curr.amount, 0);
  const collectionRatio = totalCollected + totalOutstanding > 0
    ? Math.round((totalCollected / (totalCollected + totalOutstanding)) * 100)
    : 0;

  // Filtered Payments Table
  const filteredPayments = payments.filter((pay) => {
    const user = users.find(u => u.id === pay.userId);
    const residentName = user ? user.name : 'Unknown';
    const matchSearch = residentName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          pay.flat.toLowerCase().includes(searchTerm.toLowerCase());

    const matchStatus = filterStatus === 'All' || pay.status === filterStatus;
    return matchSearch && matchStatus;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Maintenance collections</h1>
          <p className="text-xs font-semibold text-slate-400 mt-1">Review society ledger, invoices outstanding, and online fee collection logs.</p>
        </div>
        <div className="flex items-center gap-3 self-start sm:self-auto">
          <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 px-3 py-1.5 border border-slate-200 rounded-lg text-slate-500">
            Collection Efficiency: {collectionRatio}%
          </span>
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all shadow-md shadow-indigo-100 flex items-center gap-1.5"
          >
            <Plus className="w-4 h-4" />
            Issue invoice
          </button>
        </div>
      </div>

      {/* Stats Summary Panel */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white border border-slate-100 p-5 rounded-2xl shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">Total Collections Received</span>
            <p className="text-2xl font-extrabold text-emerald-600">₹{totalCollected.toLocaleString()}</p>
            <span className="text-[10px] text-slate-400 font-semibold block">{paidPayments.length} transactions paid</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <CheckCircle className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white border border-slate-100 p-5 rounded-2xl shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">Outstanding Receivables</span>
            <p className="text-2xl font-extrabold text-rose-650">₹{totalOutstanding.toLocaleString()}</p>
            <span className="text-[10px] text-slate-400 font-semibold block">{unpaidPayments.length} bills pending</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
            <Clock className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white border border-slate-100 p-5 rounded-2xl shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">Total Billed Dues</span>
            <p className="text-2xl font-extrabold text-slate-800">₹{(totalCollected + totalOutstanding).toLocaleString()}</p>
            <span className="text-[10px] text-slate-400 font-semibold block">{payments.length} ledger sheets</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-indigo-50 text-indigo-650 flex items-center justify-center">
            <CreditCard className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Filter and Search */}
      <div className="bg-white p-4.5 border border-slate-100 rounded-2xl shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative max-w-sm w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by resident name or flat..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
          />
        </div>

        <div className="flex gap-2 bg-slate-50 border border-slate-200/60 p-1 rounded-xl text-xs font-bold self-start sm:self-auto">
          {['All', 'Paid', 'Unpaid'].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                filterStatus === status
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Payments Table */}
      <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          {filteredPayments.length === 0 ? (
            <div className="text-center py-12 text-xs text-slate-400 font-semibold">
              No ledger records found.
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-3.5">Resident</th>
                  <th className="px-6 py-3.5">Flat location</th>
                  <th className="px-6 py-3.5">Bill Invoice</th>
                  <th className="px-6 py-3.5">Amount</th>
                  <th className="px-6 py-3.5">Due Date</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 text-xs font-semibold text-slate-600">
                {filteredPayments.map((pay) => {
                  const user = users.find(u => u.id === pay.userId);
                  return (
                    <tr key={pay.id} className="hover:bg-slate-50/20 transition-colors">
                      <td className="px-6 py-4 font-bold text-slate-805">
                        {user ? user.name : 'Resident'}
                      </td>
                      <td className="px-6 py-4 font-mono font-bold text-slate-500">
                        Tower {pay.tower} • Flat {pay.flat}
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <p>{pay.title}</p>
                          <p className="text-[10px] text-slate-400 font-semibold mt-0.5">{pay.billPeriod}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4 font-bold text-slate-805">₹{pay.amount.toLocaleString()}</td>
                      <td className="px-6 py-4">{pay.dueDate}</td>
                      <td className="px-6 py-4">
                        <span className={`text-[9px] font-extrabold px-2.5 py-1 rounded-full uppercase tracking-wider border ${
                          pay.status === 'Paid'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                            : 'bg-rose-50 text-rose-750 border-rose-100'
                        }`}>
                          {pay.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {pay.status === 'Unpaid' ? (
                          <button
                            type="button"
                            onClick={() => setRecordingFor(pay)}
                            className="inline-flex items-center gap-1.5 text-[11px] font-bold text-indigo-600 hover:text-indigo-800"
                          >
                            <BookMarked className="w-3.5 h-3.5" />
                            Record payment
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {creating ? (
        <CreateInvoiceModal
          onClose={() => setCreating(false)}
          onCreated={async () => {
            await refreshDashboard();
            showToast('Invoice issued', 'success');
            setCreating(false);
          }}
        />
      ) : null}

      {recordingFor ? (
        <RecordPaymentModal
          invoice={recordingFor}
          onClose={() => setRecordingFor(null)}
          onRecorded={async () => {
            await refreshDashboard();
            showToast('Payment recorded', 'success');
            setRecordingFor(null);
          }}
        />
      ) : null}
    </div>
  );
}
