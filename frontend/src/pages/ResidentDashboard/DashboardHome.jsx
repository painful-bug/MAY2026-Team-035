import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { useNavigate } from 'react-router-dom';
import { 
  UserPlus, 
  AlertTriangle, 
  CalendarPlus, 
  CreditCard, 
  TrendingUp, 
  Users, 
  Clock, 
  Calendar,
  Megaphone,
  CheckCircle2,
  ChevronRight,
  ArrowRight,
  ShieldAlert,
  DollarSign
} from 'lucide-react';

export default function DashboardHome() {
  const { 
    currentUser, 
    complaints, 
    notices, 
    visitors, 
    bookings, 
    payments, 
    amenities,
    activities,
    preapproveVisitor,
    raiseComplaint,
    bookAmenity,
    payInvoice,
    approveVisitorRequest,
    searchQuery
  } = useApp();

  const navigate = useNavigate();

  // Modals state
  const [visitorModalOpen, setVisitorModalOpen] = useState(false);
  const [complaintModalOpen, setComplaintModalOpen] = useState(false);
  const [amenityModalOpen, setAmenityModalOpen] = useState(false);
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);

  // Form states for modals
  const [visitorForm, setVisitorForm] = useState({ name: '', phone: '', purpose: 'Guest', time: '04:00 PM' });
  const [complaintForm, setComplaintForm] = useState({ title: '', description: '', category: 'Plumbing', urgency: 'Medium' });
  const [amenityForm, setAmenityForm] = useState({ amenityId: 'a1', date: new Date().toISOString().split('T')[0], timeSlot: '07:00 AM - 08:30 AM' });
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  // 1. Calculations based on user specific mock data and search filter
  const filteredNotices = notices.filter(n => 
    n.title.toLowerCase().includes((searchQuery || '').toLowerCase()) ||
    (n.description && n.description.toLowerCase().includes((searchQuery || '').toLowerCase()))
  );

  const userComplaints = complaints.filter(c => c.userId === currentUser?.id);
  const filteredComplaints = userComplaints.filter(c => 
    c.title.toLowerCase().includes((searchQuery || '').toLowerCase()) ||
    (c.description && c.description.toLowerCase().includes((searchQuery || '').toLowerCase()))
  );
  const activeComplaintsCount = filteredComplaints.filter(c => c.status !== 'Resolved').length;

  const userVisitors = visitors.filter(v => v.flat === currentUser?.flat);
  const filteredVisitors = userVisitors.filter(v => 
    v.name.toLowerCase().includes((searchQuery || '').toLowerCase()) ||
    v.purpose.toLowerCase().includes((searchQuery || '').toLowerCase())
  );
  const pendingVisitors = filteredVisitors.filter(v => v.status === 'Pending Approval');
  const expectedVisitorsCount = filteredVisitors.filter(v => v.status === 'Expected').length;
  const checkedInVisitorsCount = filteredVisitors.filter(v => v.status === 'Checked In').length;

  const selectedAmenityForm = amenities.find(a => a.id === amenityForm.amenityId);
  const isAmenityFormMaintenance = selectedAmenityForm?.status === 'Under Maintenance';

  const userBookings = bookings.filter(b => b.userId === currentUser?.id);
  const upcomingBookingsCount = userBookings.filter(b => b.status === 'Confirmed').length;

  const userPayments = payments.filter(p => p.userId === currentUser?.id);
  const unpaidInvoices = userPayments.filter(p => p.status === 'Unpaid');
  const totalUnpaidAmount = unpaidInvoices.reduce((acc, curr) => acc + curr.amount, 0);
  const primaryInvoice = unpaidInvoices[0] || null;

  // Format date
  const getFormattedDate = () => {
    return new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    });
  };

  // Handle Form Submissions
  const handleAddVisitor = (e) => {
    e.preventDefault();
    if (!visitorForm.name || !visitorForm.phone) return;
    preapproveVisitor(visitorForm);
    setVisitorForm({ name: '', phone: '', purpose: 'Guest', time: '04:00 PM' });
    setVisitorModalOpen(false);
  };

  const handleRaiseComplaint = (e) => {
    e.preventDefault();
    if (!complaintForm.title || !complaintForm.description) return;
    raiseComplaint(complaintForm);
    setComplaintForm({ title: '', description: '', category: 'Plumbing', urgency: 'Medium' });
    setComplaintModalOpen(false);
  };

  const handleBookAmenity = (e) => {
    e.preventDefault();
    bookAmenity(amenityForm);
    setAmenityModalOpen(false);
  };

  const handlePay = (e) => {
    e.preventDefault();
    if (!selectedInvoice) return;
    payInvoice(selectedInvoice.id, 'UPI');
    setPaymentModalOpen(false);
  };

  return (
    <div className="space-y-8">
      {/* Welcome Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Good evening, {currentUser?.name.split(' ')[0]} 
          </h1>
          <p className="text-sm font-semibold text-slate-400 mt-1">Here's what's happening in your apartment today.</p>
        </div>
        <div className="text-xs sm:text-sm font-bold text-slate-500 bg-white border border-slate-100 px-4 py-2 rounded-2xl shadow-sm self-start md:self-auto">
          {getFormattedDate()}
        </div>
      </div>

      {/* Quick Action Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <button 
          onClick={() => setVisitorModalOpen(true)}
          className="p-5 bg-white border border-slate-100 hover:border-indigo-200 rounded-2xl text-left transition-all hover:shadow-lg group"
        >
          <div className="w-10 h-10 rounded-xl bg-indigo-55/70 text-indigo-600 flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
            <UserPlus className="w-5 h-5" />
          </div>
          <p className="text-sm font-extrabold text-slate-800">Add Visitor</p>
          <p className="text-[10px] text-slate-400 font-semibold mt-1">Pre-approve a guest</p>
        </button>

        <button 
          onClick={() => setComplaintModalOpen(true)}
          className="p-5 bg-white border border-slate-100 hover:border-rose-200 rounded-2xl text-left transition-all hover:shadow-lg group"
        >
          <div className="w-10 h-10 rounded-xl bg-rose-55/70 text-rose-600 flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <p className="text-sm font-extrabold text-slate-800">Raise Complaint</p>
          <p className="text-[10px] text-slate-400 font-semibold mt-1">Report an issue</p>
        </button>

        <button 
          onClick={() => setAmenityModalOpen(true)}
          className="p-5 bg-white border border-slate-100 hover:border-emerald-200 rounded-2xl text-left transition-all hover:shadow-lg group"
        >
          <div className="w-10 h-10 rounded-xl bg-emerald-55/70 text-emerald-600 flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
            <CalendarPlus className="w-5 h-5" />
          </div>
          <p className="text-sm font-extrabold text-slate-800">Book Amenity</p>
          <p className="text-[10px] text-slate-400 font-semibold mt-1">Gym, Club, Pool</p>
        </button>

        <button 
          onClick={() => {
            if (primaryInvoice) {
              setSelectedInvoice(primaryInvoice);
              setPaymentModalOpen(true);
            } else {
              navigate('/resident/payments');
            }
          }}
          className="p-5 bg-white border border-slate-100 hover:border-amber-200 rounded-2xl text-left transition-all hover:shadow-lg group"
        >
          <div className="w-10 h-10 rounded-xl bg-amber-55/70 text-amber-600 flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
            <CreditCard className="w-5 h-5" />
          </div>
          <p className="text-sm font-extrabold text-slate-800">Pay Maintenance</p>
          <p className="text-[10px] text-slate-400 font-semibold mt-1">
            {primaryInvoice ? `₹${primaryInvoice.amount.toLocaleString()} due` : 'No dues pending'}
          </p>
        </button>
      </div>

      {/* Info Status Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-100 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-rose-500 uppercase tracking-wider block">Active Complaints</span>
            <p className="text-2xl font-extrabold text-slate-800">{activeComplaintsCount}</p>
            <span className="text-[10px] text-slate-400 font-semibold block">1 in progress</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-100 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-indigo-500 uppercase tracking-wider block">Pending Visitors</span>
            <p className="text-2xl font-extrabold text-slate-800">{pendingVisitors.length}</p>
            <span className="text-[10px] text-slate-400 font-semibold block">Awaiting approval</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Users className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-100 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-emerald-500 uppercase tracking-wider block">Upcoming Bookings</span>
            <p className="text-2xl font-extrabold text-slate-800">{upcomingBookingsCount}</p>
            <span className="text-[10px] text-slate-400 font-semibold block">This week</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Calendar className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-100 flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] font-extrabold text-amber-500 uppercase tracking-wider block">Maintenance Due</span>
            <p className="text-2xl font-extrabold text-slate-800">₹{totalUnpaidAmount.toLocaleString()}</p>
            <span className="text-[10px] text-slate-400 font-semibold block">Due in 9 days</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center">
            <CreditCard className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Notices & Complaints */}
        <div className="lg:col-span-8 space-y-6">
          {/* Recent Notices */}
          <div className="bg-white rounded-2xl border border-slate-100 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Megaphone className="w-5 h-5 text-indigo-600" />
                <h3 className="font-extrabold text-slate-800 text-base">Recent Notices</h3>
              </div>
              <button 
                onClick={() => navigate('/resident/notices')}
                className="text-xs font-bold text-indigo-600 hover:text-indigo-700 flex items-center gap-0.5"
              >
                View all
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            <div className="divide-y divide-slate-50">
              {filteredNotices.slice(0, 3).map((notice) => (
                <div key={notice.id} className="py-4 first:pt-0 last:pb-0 flex items-start justify-between gap-4">
                  <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-slate-550 flex-shrink-0 mt-0.5">
                      <Megaphone className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-800">{notice.title}</p>
                      <p className="text-[11px] font-semibold text-slate-400 mt-0.5">{notice.date}</p>
                    </div>
                  </div>
                  <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${
                    notice.urgency === 'High' 
                      ? 'bg-rose-50 text-rose-700' 
                      : notice.urgency === 'Medium'
                      ? 'bg-amber-50 text-amber-700'
                      : 'bg-blue-50 text-blue-700'
                  }`}>
                    {notice.urgency}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* My Complaints */}
          <div className="bg-white rounded-2xl border border-slate-100 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-indigo-650" />
                <h3 className="font-extrabold text-slate-800 text-base">My Complaints</h3>
              </div>
              <button 
                onClick={() => navigate('/resident/complaints')}
                className="text-xs font-bold text-indigo-650 hover:text-indigo-750 flex items-center gap-0.5"
              >
                View all
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {filteredComplaints.length === 0 ? (
              <div className="text-center py-6 text-xs text-slate-400 font-semibold">
                {searchQuery ? 'No matching complaints found.' : 'No complaints filed yet. Click "Raise Complaint" above if you have an issue.'}
              </div>
            ) : (
              <div className="space-y-4">
                {filteredComplaints.slice(0, 2).map((comp) => (
                  <div key={comp.id} className="p-4 bg-slate-50/50 border border-slate-100 rounded-xl space-y-3.5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h4 className="text-sm font-extrabold text-slate-850">{comp.title}</h4>
                        <p className="text-[11px] font-semibold text-slate-450 mt-0.5">{comp.assignee} • {comp.timeAgo}</p>
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        comp.status === 'Resolved' 
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' 
                          : comp.status === 'In Progress'
                          ? 'bg-blue-55/60 text-blue-700 border border-blue-100/50'
                          : 'bg-rose-50 text-rose-700 border border-rose-100'
                      }`}>
                        {comp.status}
                      </span>
                    </div>
                    {comp.status !== 'Resolved' && (
                      <div className="space-y-1.5">
                        <div className="flex justify-between text-[10px] font-bold text-slate-500">
                          <span>Progress</span>
                          <span>{comp.progress}%</span>
                        </div>
                        <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                          <div 
                            className="bg-indigo-600 h-full rounded-full transition-all duration-500" 
                            style={{ width: `${comp.progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Visitors Today & Pay Banner */}
        <div className="lg:col-span-4 space-y-6">
          {/* Visitors Today Card */}
          <div className="bg-white rounded-2xl border border-slate-100 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-indigo-600" />
                <h3 className="font-extrabold text-slate-800 text-sm">Visitors Today</h3>
              </div>
              <button 
                onClick={() => setVisitorModalOpen(true)}
                className="text-xs font-bold text-indigo-600 hover:underline"
              >
                + Add
              </button>
            </div>

            {/* Counters */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-slate-50/50 p-2.5 rounded-xl border border-slate-100/50">
                <p className="text-base font-extrabold text-slate-850">{expectedVisitorsCount}</p>
                <p className="text-[9px] text-slate-400 font-bold uppercase mt-0.5">Expected</p>
              </div>
              <div className="bg-emerald-50/20 p-2.5 rounded-xl border border-emerald-100/30">
                <p className="text-base font-extrabold text-emerald-700">{checkedInVisitorsCount}</p>
                <p className="text-[9px] text-emerald-650 font-bold uppercase mt-0.5">In</p>
              </div>
              <div className="bg-indigo-50/20 p-2.5 rounded-xl border border-indigo-100/30">
                <p className="text-base font-extrabold text-indigo-700">{pendingVisitors.length}</p>
                <p className="text-[9px] text-indigo-650 font-bold uppercase mt-0.5">Pending</p>
              </div>
            </div>

            {/* Pending approvals requests */}
            {pendingVisitors.length > 0 ? (
              <div className="space-y-3">
                <p className="text-[10px] font-extrabold text-indigo-655 uppercase tracking-wide bg-indigo-50/55 p-2 rounded-lg border border-indigo-100/30">
                  ⚠️ {pendingVisitors.length} visitor requests awaiting your approval:
                </p>
                <div className="space-y-2.5">
                  {pendingVisitors.slice(0, 3).map((vis) => (
                    <div key={vis.id} className="p-3 bg-slate-50 border border-slate-100 rounded-xl space-y-2.5">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-xs font-bold text-slate-800">{vis.name}</p>
                          <p className="text-[10px] text-slate-450 font-semibold">{vis.purpose} • {vis.eta}</p>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => approveVisitorRequest(vis.id)}
                          className="py-1 bg-indigo-600 hover:bg-indigo-750 text-white text-[10px] font-bold rounded-lg transition-colors"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => {}} // Reject logic can be just local removing
                          className="py-1 border border-slate-200 hover:bg-slate-100 text-slate-600 text-[10px] font-bold rounded-lg transition-colors"
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-xs text-slate-400 font-semibold border border-dashed border-slate-200 rounded-xl">
                No pending requests.
              </div>
            )}
          </div>

          {/* Maintenance Due Blue Banner */}
          {primaryInvoice && (
            <div className="bg-indigo-600 text-white rounded-2xl p-6 space-y-4 shadow-lg shadow-indigo-150 relative overflow-hidden">
              {/* Background abstract circles */}
              <div className="absolute right-0 bottom-0 translate-x-1/4 translate-y-1/4 w-32 h-32 bg-white/10 rounded-full" />
              
              <div className="space-y-1">
                <span className="text-[9px] font-extrabold uppercase tracking-widest text-indigo-200">Maintenance Due</span>
                <p className="text-3xl font-extrabold">₹{primaryInvoice.amount.toLocaleString()}</p>
                <p className="text-[10px] text-indigo-150 font-semibold">Due {primaryInvoice.dueDate}</p>
              </div>

              <button 
                onClick={() => {
                  setSelectedInvoice(primaryInvoice);
                  setPaymentModalOpen(true);
                }}
                className="w-full bg-white/20 hover:bg-white/35 text-white font-bold py-2.5 rounded-xl text-xs transition-colors backdrop-blur-sm z-10 relative"
              >
                Pay Now
              </button>
            </div>
          )}
        </div>
      </div>

      {/* --- MODALS --- */}

      {/* Visitor Pre-Approval Modal */}
      {visitorModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl border border-slate-100 max-w-md w-full p-6 space-y-6 animate-slide-up">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-extrabold text-slate-900">Pre-approve a Guest</h3>
              <button 
                onClick={() => setVisitorModalOpen(false)}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                Cancel
              </button>
            </div>

            <form onSubmit={handleAddVisitor} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Visitor Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Rahul Verma"
                  value={visitorForm.name}
                  onChange={(e) => setVisitorForm({ ...visitorForm, name: e.target.value })}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Mobile Number</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. +91 98765 43210"
                  value={visitorForm.phone}
                  onChange={(e) => setVisitorForm({ ...visitorForm, phone: e.target.value })}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Purpose</label>
                  <select
                    value={visitorForm.purpose}
                    onChange={(e) => setVisitorForm({ ...visitorForm, purpose: e.target.value })}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  >
                    <option value="Guest">Guest</option>
                    <option value="Delivery">Delivery</option>
                    <option value="Service">Service</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Expected Time</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 04:00 PM"
                    value={visitorForm.time}
                    onChange={(e) => setVisitorForm({ ...visitorForm, time: e.target.value })}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-750 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 mt-2 text-sm"
              >
                Generate Entry Code
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Raise Complaint Modal */}
      {complaintModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl border border-slate-100 max-w-md w-full p-6 space-y-6 animate-slide-up">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-extrabold text-slate-900">Raise Complaint</h3>
              <button 
                onClick={() => setComplaintModalOpen(false)}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                Cancel
              </button>
            </div>

            <form onSubmit={handleRaiseComplaint} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Issue Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Leaking kitchen tap"
                  value={complaintForm.title}
                  onChange={(e) => setComplaintForm({ ...complaintForm, title: e.target.value })}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Category</label>
                  <select
                    value={complaintForm.category}
                    onChange={(e) => setComplaintForm({ ...complaintForm, category: e.target.value })}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  >
                    <option value="Plumbing">Plumbing</option>
                    <option value="Electrical">Electrical</option>
                    <option value="Infrastructure">Infrastructure</option>
                    <option value="Cleaning">Cleaning</option>
                    <option value="Security">Security</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Urgency</label>
                  <select
                    value={complaintForm.urgency}
                    onChange={(e) => setComplaintForm({ ...complaintForm, urgency: e.target.value })}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  >
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Description</label>
                <textarea
                  required
                  rows={3}
                  placeholder="Describe the issue in detail..."
                  value={complaintForm.description}
                  onChange={(e) => setComplaintForm({ ...complaintForm, description: e.target.value })}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-755 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 mt-2 text-sm"
              >
                Submit Complaint
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Book Amenity Modal */}
      {amenityModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl border border-slate-100 max-w-md w-full p-6 space-y-6 animate-slide-up">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-extrabold text-slate-900">Book Society Amenity</h3>
              <button 
                onClick={() => setAmenityModalOpen(false)}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                Cancel
              </button>
            </div>

            <form onSubmit={handleBookAmenity} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Select Amenity</label>
                <select
                  value={amenityForm.amenityId}
                  onChange={(e) => setAmenityForm({ ...amenityForm, amenityId: e.target.value })}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                >
                  {amenities.map(a => (
                    <option key={a.id} value={a.id} disabled={a.status === 'Under Maintenance'}>
                      {a.name} ({a.timing}) {a.status === 'Under Maintenance' ? '(Under Maintenance)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Date</label>
                  <input
                    type="date"
                    required
                    value={amenityForm.date}
                    onChange={(e) => setAmenityForm({ ...amenityForm, date: e.target.value })}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Time Slot</label>
                  <select
                    value={amenityForm.timeSlot}
                    onChange={(e) => setAmenityForm({ ...amenityForm, timeSlot: e.target.value })}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  >
                    <option value="07:00 AM - 08:30 AM">07:00 AM - 08:30 AM</option>
                    <option value="09:00 AM - 10:30 AM">09:00 AM - 10:30 AM</option>
                    <option value="04:00 PM - 05:30 PM">04:00 PM - 05:30 PM</option>
                    <option value="06:00 PM - 07:30 PM">06:00 PM - 07:30 PM</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={isAmenityFormMaintenance}
                className={`w-full py-3 text-white font-bold rounded-xl transition-all mt-2 text-sm ${
                  isAmenityFormMaintenance
                    ? 'bg-slate-300 cursor-not-allowed shadow-none'
                    : 'bg-indigo-600 hover:bg-indigo-755 shadow-md shadow-indigo-100'
                }`}
              >
                {isAmenityFormMaintenance ? 'Under Maintenance' : 'Confirm Booking'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Pay Maintenance Due Modal */}
      {paymentModalOpen && selectedInvoice && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl border border-slate-100 max-w-md w-full p-6 space-y-6 animate-slide-up">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-extrabold text-slate-900">Simulate Payment</h3>
              <button 
                onClick={() => setPaymentModalOpen(false)}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                Cancel
              </button>
            </div>

            <div className="bg-indigo-50/50 border border-indigo-100/50 rounded-2xl p-4.5 space-y-2">
              <span className="text-[9px] font-extrabold uppercase tracking-wide text-indigo-500">Invoice Details</span>
              <p className="text-sm font-bold text-slate-805">{selectedInvoice.title}</p>
              <div className="flex justify-between items-baseline pt-2">
                <span className="text-xs text-slate-450 font-bold">Total Amount:</span>
                <span className="text-xl font-extrabold text-slate-900">₹{selectedInvoice.amount.toLocaleString()}</span>
              </div>
            </div>

            <form onSubmit={handlePay} className="space-y-4">
              <div className="space-y-2">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Payment Method</label>
                <div className="grid grid-cols-2 gap-3 text-center">
                  <div className="p-3 border border-indigo-500 bg-indigo-50/20 text-indigo-950 rounded-xl text-xs font-bold cursor-pointer">
                    UPI (Simulated)
                  </div>
                  <div className="p-3 border border-slate-150 text-slate-500 hover:bg-slate-50 rounded-xl text-xs font-bold cursor-not-allowed">
                    Credit Card
                  </div>
                </div>
              </div>

              <div className="text-[10px] text-slate-400 font-semibold text-center leading-relaxed">
                Clicking pay will mark the maintenance invoice status as **Paid** in context memory and update your dashboard stats.
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-indigo-650 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 text-sm flex items-center justify-center gap-1.5"
              >
                <DollarSign className="w-4 h-4" />
                Pay ₹{selectedInvoice.amount.toLocaleString()}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
