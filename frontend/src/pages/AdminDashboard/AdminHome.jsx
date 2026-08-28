import React from 'react';
import { useApp } from '../../store/useApp';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  UserPlus,
  AlertTriangle,
  IndianRupee,
  Activity,
  ChevronRight,
  TrendingUp,
  Building2
} from 'lucide-react';

// "+N this week", from the snapshot's `weeklyNew` counts (items created in the
// trailing 7 days). This replaces a literal "+2 this week" that shipped with
// the demo and survived into the live app. Defensive on purpose: the backend
// field lands in parallel, so `weeklyNew` may be missing entirely — and a
// missing field, a zero, or garbage all render nothing rather than a fake
// trend.
// Snapshot pendingRequests rows are snake_case view rows (applicant_name,
// requested_unit_code, requested_building_text, requested_unit_text) — the
// demo-era `req.name` / `req.flat` / `req.tower` keys never existed on them,
// so this card used to render "Flat undefined • Tower undefined". Prefer the
// resolved unit code, then the applicant's free-text claim, then a dash.
function residenceLabel(req) {
  if (req.requested_unit_code) return req.requested_unit_code;
  const building = (req.requested_building_text || '').trim();
  const unit = (req.requested_unit_text || '').trim();
  if (building && unit) return `Tower ${building} · Flat ${unit}`;
  if (unit) return unit;
  return '—';
}

function TrendChip({ count }) {
  const value = Number(count);
  if (!Number.isFinite(value) || value <= 0) return null;
  return (
    <span className="text-[10px] text-emerald-600 font-semibold block flex items-center gap-0.5">
      <TrendingUp className="w-3 h-3" /> +{value} this week
    </span>
  );
}

export default function AdminHome() {
  const { users, pendingRequests, complaints, payments, activities, weeklyNew } = useApp();
  const navigate = useNavigate();

  // Stats Calculations
  const residentsCount = users.filter(u => u.role === 'Resident').length;
  const pendingCount = pendingRequests.length;
  const activeComplaints = complaints.filter(c => c.status !== 'Resolved').length;

  // Collection Calculations
  const paidPayments = payments.filter(p => p.status === 'Paid');
  const unpaidPayments = payments.filter(p => p.status === 'Unpaid');
  const currentCollection = paidPayments.reduce((acc, curr) => acc + curr.amount, 0);
  const targetCollection = currentCollection + unpaidPayments.reduce((acc, curr) => acc + curr.amount, 0);
  const percentCollected = targetCollection > 0 ? Math.round((currentCollection / targetCollection) * 100) : 0;

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Admin Dashboard Overview</h1>
        <p className="text-xs font-semibold text-slate-450 mt-1">Real-time society statistics, pending approvals, and maintenance collection summary.</p>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total Residents */}
        <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">Total Residents</span>
            <p className="text-2xl font-extrabold text-slate-800">{residentsCount}</p>
            <TrendChip count={weeklyNew?.residents} />
          </div>
          <div className="w-11 h-11 rounded-2xl bg-indigo-50 text-indigo-650 flex items-center justify-center">
            <Users className="w-5 h-5" />
          </div>
        </div>

        {/* Pending Requests */}
        <button 
          onClick={() => navigate('/admin/pending')}
          className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm flex items-center justify-between hover:border-indigo-150 hover:shadow-md transition-all text-left w-full group"
        >
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">Pending Requests</span>
            <p className="text-2xl font-extrabold text-slate-800">{pendingCount}</p>
            <span className="text-[10px] text-indigo-600 font-semibold block group-hover:underline">
              Review requests
            </span>
          </div>
          <div className="w-11 h-11 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center">
            <UserPlus className="w-5 h-5" />
          </div>
        </button>

        {/* Active Complaints */}
        <button 
          onClick={() => navigate('/admin/complaints')}
          className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm flex items-center justify-between hover:border-indigo-150 hover:shadow-md transition-all text-left w-full"
        >
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">Active Complaints</span>
            <p className="text-2xl font-extrabold text-slate-800">{activeComplaints}</p>
            <span className="text-[10px] text-amber-600 font-semibold block">
              Awaiting resolutions
            </span>
            <TrendChip count={weeklyNew?.complaints} />
          </div>
          <div className="w-11 h-11 rounded-2xl bg-amber-50 text-amber-605 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </button>

        {/* Monthly Collection */}
        <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">Monthly Collection</span>
            <p className="text-2xl font-extrabold text-slate-800">₹{currentCollection.toLocaleString()}</p>
            <div className="flex items-center gap-1.5 pt-0.5">
              <div className="w-16 bg-slate-100 h-1.5 rounded-full overflow-hidden">
                <div className="bg-indigo-600 h-full rounded-full" style={{ width: `${percentCollected}%` }} />
              </div>
              <span className="text-[10px] text-slate-400 font-bold">{percentCollected}% of goal</span>
            </div>
          </div>
          <div className="w-11 h-11 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
            <IndianRupee className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <button
          onClick={() => navigate('/admin/departments?create=1')}
          className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm flex items-center justify-between hover:border-indigo-150 hover:shadow-md transition-all text-left w-full group"
        >
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">Quick Action</span>
            <p className="text-sm font-extrabold text-slate-800 pt-1">Create Department</p>
            <span className="text-[10px] text-indigo-600 font-semibold block group-hover:underline">
              Set up staff & categories
            </span>
          </div>
          <div className="w-11 h-11 rounded-2xl bg-indigo-50 text-indigo-650 flex items-center justify-center">
            <Building2 className="w-5 h-5" />
          </div>
        </button>
      </div>

      {/* Admin Sub Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Pending approvals quick review */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-100 p-6 space-y-4">
          <div className="flex justify-between items-center pb-2">
            <div className="flex items-center gap-2">
              <UserPlus className="w-5 h-5 text-indigo-650" />
              <h3 className="font-extrabold text-slate-800 text-sm">Recent Approval Requests</h3>
            </div>
            <button
              onClick={() => navigate('/admin/pending')}
              className="text-xs font-bold text-indigo-600 hover:text-indigo-700 flex items-center gap-0.5"
            >
              View all
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {pendingCount === 0 ? (
            <div className="text-center py-8 text-xs text-slate-400 font-semibold border border-slate-100 border-dashed rounded-xl">
              No pending registrations right now.
            </div>
          ) : (
            <div className="space-y-3">
              {pendingRequests.slice(0, 3).map((req) => (
                <div key={req.id} className="p-3.5 bg-slate-50 border border-slate-100 rounded-xl flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-bold text-slate-800">{req.applicant_name}</p>
                    <p className="text-[10px] text-slate-450 font-semibold mt-0.5">{residenceLabel(req)}</p>
                  </div>
                  <button
                    onClick={() => navigate('/admin/pending')}
                    className="px-3.5 py-1.5 bg-white border border-slate-200 hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-200 text-slate-700 text-[10px] font-bold rounded-xl transition-all"
                  >
                    Manage
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* System Activity Timeline */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-100 p-6 space-y-4">
          <div className="flex items-center gap-2 pb-2">
            <Activity className="w-5 h-5 text-indigo-655" />
            <h3 className="font-extrabold text-slate-800 text-sm">Society Activity Log</h3>
          </div>

          <div className="space-y-4 max-h-[220px] overflow-y-auto pr-1">
            {activities.map((act) => (
              <div key={act.id} className="flex gap-3 text-xs font-semibold">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0 mt-1.5" />
                <div className="flex-1">
                  <p className="text-slate-700 leading-normal">{act.text}</p>
                  <p className="text-[9px] text-slate-400 font-bold uppercase tracking-wider mt-0.5">{act.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
