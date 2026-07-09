import React from 'react';
import { useApp } from '../../store/useApp';
import { UserCheck, Mail, Phone, Home, Check, X, ShieldAlert } from 'lucide-react';

export default function PendingRegistrations() {
  const { pendingRequests, acceptRequest, rejectRequest } = useApp();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Pending Registrations</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Approve or reject flat registration requests from new residents.</p>
      </div>

      {pendingRequests.length === 0 ? (
        <div className="bg-white border border-slate-100 p-12 text-center rounded-2xl shadow-sm space-y-3">
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
            <Check className="w-6 h-6" />
          </div>
          <h3 className="font-extrabold text-slate-800 text-sm">All Caught Up!</h3>
          <p className="text-xs font-semibold text-slate-450 max-w-sm mx-auto">
            There are no pending flat registration requests at the moment. All signups have been approved or rejected.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {pendingRequests.map((req) => (
            <div key={req.id} className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm space-y-4 hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-extrabold text-slate-850 text-sm">{req.name}</h3>
                  <span className="text-[10px] font-bold text-slate-400 mt-0.5 block">Requested on {req.date}</span>
                </div>
                <span className="bg-indigo-50 border border-indigo-100 text-indigo-700 text-[10px] font-bold px-2 py-0.5 rounded flex items-center gap-1">
                  <Home className="w-3 h-3" />
                  Flat {req.flat}
                </span>
              </div>

              {/* Resident profile details */}
              <div className="space-y-2.5 pt-3 border-t border-slate-50 text-xs font-semibold text-slate-600">
                <div className="flex items-center gap-2">
                  <Mail className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <span>{req.email}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <span>{req.phone}</span>
                </div>
                <div className="flex items-center gap-2 font-bold text-slate-700">
                  <span className="text-[9px] uppercase tracking-wider text-slate-400 font-extrabold">Tower Location:</span>
                  <span>Tower {req.tower}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-2 gap-3 pt-4 border-t border-slate-50">
                <button
                  onClick={() => acceptRequest(req.id)}
                  className="py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-sm shadow-indigo-100 text-xs flex items-center justify-center gap-1.5"
                >
                  <Check className="w-4 h-4" />
                  Accept Request
                </button>
                <button
                  onClick={() => rejectRequest(req.id)}
                  className="py-2.5 border border-slate-200 hover:bg-rose-50 hover:text-rose-600 hover:border-rose-100 text-slate-600 font-bold rounded-xl transition-all text-xs flex items-center justify-center gap-1.5"
                >
                  <X className="w-4 h-4" />
                  Reject Request
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
