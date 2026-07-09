import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { CreditCard, Search, CheckCircle, Clock } from 'lucide-react';

export default function Maintenance() {
  const { payments, users } = useApp();
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('All');

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
        <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 px-3 py-1.5 border border-slate-200 rounded-lg text-slate-500 self-start sm:self-auto">
          Collection Efficiency: {collectionRatio}%
        </span>
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
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
