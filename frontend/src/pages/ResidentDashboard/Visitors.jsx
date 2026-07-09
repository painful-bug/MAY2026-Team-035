import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { Users, UserPlus, CheckCircle, Shield, Key } from 'lucide-react';

export default function Visitors() {
  const { visitors, currentUser, preapproveVisitor, approveVisitorRequest } = useApp();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [purpose, setPurpose] = useState('Guest');
  const [time, setTime] = useState('04:00 PM');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);

  const userVisitors = visitors.filter(v => v.flat === currentUser?.flat);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name || !phone) return;
    preapproveVisitor({ name, phone, purpose, time, date });
    setName('');
    setPhone('');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Visitor Management</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Pre-approve guests, delivery agents, or service staff and view gate logs.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Pre-approve Form */}
        <div className="lg:col-span-4 bg-white p-6 border border-slate-100 rounded-2xl h-fit space-y-4 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-50">
            <UserPlus className="w-5 h-5 text-indigo-650" />
            <h3 className="font-extrabold text-slate-805 text-sm">Pre-approve Entry</h3>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Visitor Name</label>
              <input
                type="text"
                required
                placeholder="e.g. John Doe"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Mobile Number</label>
              <input
                type="text"
                required
                placeholder="e.g. +91 99999 88888"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Purpose</label>
              <select
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
              >
                <option value="Guest">Guest / Friend</option>
                <option value="Delivery">Delivery Executive</option>
                <option value="Service">Service Technician</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Date</label>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Expected Time</label>
                <input
                  type="text"
                  placeholder="e.g. 04:00 PM"
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 text-xs"
            >
              Generate Approval Pass
            </button>
          </form>
        </div>

        {/* Visitors Log */}
        <div className="lg:col-span-8 bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden flex flex-col justify-between">
          <div className="p-6 border-b border-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-650" />
              <h3 className="font-extrabold text-slate-800 text-sm">Visitor Entry Log</h3>
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-50 px-2.5 py-1 border border-slate-100 rounded-lg text-slate-450">
              {userVisitors.length} Total Logs
            </span>
          </div>

          <div className="overflow-x-auto flex-1">
            {userVisitors.length === 0 ? (
              <div className="text-center py-12 text-xs text-slate-400 font-semibold">
                No visitor activity recorded for this flat.
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50/55 border-b border-slate-100 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                    <th className="px-6 py-3.5">Pass Code</th>
                    <th className="px-6 py-3.5">Name</th>
                    <th className="px-6 py-3.5">Purpose</th>
                    <th className="px-6 py-3.5">Expected On</th>
                    <th className="px-6 py-3.5">Status</th>
                    <th className="px-6 py-3.5">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 text-xs font-semibold text-slate-600">
                  {userVisitors.map((vis) => (
                    <tr key={vis.id} className="hover:bg-slate-50/30 transition-colors">
                      <td className="px-6 py-4.5">
                        <span className="font-mono text-indigo-700 bg-indigo-50 border border-indigo-100/50 px-2 py-0.5 rounded text-[10px] font-bold">
                          {vis.code}
                        </span>
                      </td>
                      <td className="px-6 py-4.5 font-bold text-slate-800">
                        <div>
                          <p>{vis.name}</p>
                          <p className="text-[10px] text-slate-400 font-medium">{vis.phone}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4.5">{vis.purpose}</td>
                      <td className="px-6 py-4.5">
                        <div>
                          <p>{vis.date}</p>
                          <p className="text-[10px] text-slate-400 font-medium">{vis.eta || vis.checkInTime}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4.5">
                        <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${
                          vis.status === 'Checked In' 
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' 
                            : vis.status === 'Checked Out'
                            ? 'bg-slate-100 text-slate-500 border border-slate-200'
                            : vis.status === 'Expected'
                            ? 'bg-amber-50 text-amber-700 border border-amber-100'
                            : 'bg-rose-50 text-rose-700 border border-rose-100'
                        }`}>
                          {vis.status}
                        </span>
                      </td>
                      <td className="px-6 py-4.5">
                        {vis.status === 'Pending Approval' ? (
                          <button
                            onClick={() => approveVisitorRequest(vis.id)}
                            className="bg-indigo-600 hover:bg-indigo-700 text-white text-[10px] font-bold px-3 py-1 rounded-lg transition-colors shadow-sm"
                          >
                            Approve
                          </button>
                        ) : vis.status === 'Expected' ? (
                          <span className="text-[10px] text-slate-400 flex items-center gap-1 font-bold">
                            <Key className="w-3 h-3 text-amber-600" /> Share Code
                          </span>
                        ) : (
                          <span className="text-[10px] text-slate-400 flex items-center gap-1 font-bold">
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-600" /> Logged
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
