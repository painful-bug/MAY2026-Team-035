import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { getVisitorSecurityCode } from '../../lib/visitorPasses';
import { useNavigate } from 'react-router-dom';
import QRCode from 'qrcode';
import { 
  UserPlus, 
  AlertTriangle, 
  CalendarPlus, 
  CreditCard, 
  Users, 
  Megaphone,
  ChevronRight,
  DollarSign,
  Download,
  QrCode,
  Copy,
  ShieldCheck
} from 'lucide-react';

export default function DashboardHome() {
  const { 
    currentUser, 
    complaints, 
    notices, 
    visitors, 
    payments, 
    preapproveVisitor,
    payInvoice,
    approveVisitorRequest,
    rejectVisitorRequest,
    searchQuery,
    showToast
  } = useApp();

  const navigate = useNavigate();

  // Modals state
  const [visitorModalOpen, setVisitorModalOpen] = useState(false);
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [visitorQrPass, setVisitorQrPass] = useState(null);
  const [isGeneratingQr, setIsGeneratingQr] = useState(false);
  const [visitorQrError, setVisitorQrError] = useState('');

  // Form states for modals
  const [visitorForm, setVisitorForm] = useState({
    purpose: 'Guest',
    purposeDetails: '',
    time: '16:00',
    date: new Date().toISOString().split('T')[0],
    guestCount: 1,
  });
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
  const userVisitors = visitors.filter(v => v.flat === currentUser?.flat);
  const filteredVisitors = userVisitors.filter(v => 
    (v.name || '').toLowerCase().includes((searchQuery || '').toLowerCase()) ||
    (v.purpose || '').toLowerCase().includes((searchQuery || '').toLowerCase()) ||
    (v.purposeDetails || '').toLowerCase().includes((searchQuery || '').toLowerCase())
  );
  const pendingVisitors = filteredVisitors.filter(v => v.status === 'Pending Approval');
  const expectedVisitorsCount = filteredVisitors
    .filter(v => ['Expected', 'Approved'].includes(v.status))
    .reduce((count, visitor) => count + Number(visitor.guestCount || 1), 0);
  const checkedInVisitorsCount = filteredVisitors
    .filter(v => v.status === 'Checked In')
    .reduce((count, visitor) => count + Number(visitor.guestCount || 1), 0);

  const userPayments = payments.filter(p => p.userId === currentUser?.id);
  const unpaidInvoices = userPayments.filter(p => p.status === 'Unpaid');
  const primaryInvoice =
    unpaidInvoices.find((invoice) =>
      invoice.title.toLowerCase().includes('maintenance')
    ) ??
    unpaidInvoices[0] ??
    null;

  const formatDueDate = (date) =>
    new Intl.DateTimeFormat('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(new Date(`${date}T00:00:00.000Z`));

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
  const handleAddVisitor = async (e) => {
    e.preventDefault();
    setVisitorQrError('');
    setIsGeneratingQr(true);

    try {
      const visitor = preapproveVisitor(visitorForm);
      const qrDataUrl = await QRCode.toDataURL(visitor.qrPayload, {
        width: 320,
        margin: 2,
        color: {
          dark: '#1e1b4b',
          light: '#ffffff',
        },
        errorCorrectionLevel: 'M',
      });
      setVisitorQrPass({ visitor, qrDataUrl });
    } catch {
      setVisitorQrError('Unable to generate the QR code. Please try again.');
    } finally {
      setIsGeneratingQr(false);
    }
  };

  const closeVisitorModal = () => {
    setVisitorModalOpen(false);
    setVisitorQrPass(null);
    setVisitorQrError('');
    setVisitorForm({
      purpose: 'Guest',
      purposeDetails: '',
      time: '16:00',
      date: new Date().toISOString().split('T')[0],
      guestCount: 1,
    });
  };

  const copyVisitorSecurityCode = async () => {
    const securityCode = getVisitorSecurityCode(visitorQrPass?.visitor);
    if (!securityCode) return;

    await navigator.clipboard.writeText(securityCode);
    showToast('Security code copied', 'success');
  };

  const handlePay = (e) => {
    e.preventDefault();
    if (!selectedInvoice) return;
    payInvoice(selectedInvoice.id, 'UPI');
    setPaymentModalOpen(false);
  };

  return (
    <div className="space-y-6">
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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <button 
          onClick={() => setVisitorModalOpen(true)}
          className="group rounded-2xl border border-slate-100 bg-white p-4 text-left transition-all hover:border-indigo-200 hover:shadow-sm"
        >
          <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <UserPlus className="h-4.5 w-4.5" />
          </div>
          <p className="text-sm font-extrabold text-slate-800">Add Visitor</p>
          <p className="text-[10px] text-slate-400 font-semibold mt-1">Pre-approve a guest</p>
        </button>

        <button 
          onClick={() => navigate('/resident/complaints')}
          className="group rounded-2xl border border-slate-100 bg-white p-4 text-left transition-all hover:border-rose-200 hover:shadow-sm"
        >
          <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
            <AlertTriangle className="h-4.5 w-4.5" />
          </div>
          <p className="text-sm font-extrabold text-slate-800">Raise Complaint</p>
          <p className="text-[10px] text-slate-400 font-semibold mt-1">Report an issue</p>
        </button>

        <button 
          onClick={() => navigate('/resident/amenities')}
          className="group rounded-2xl border border-slate-100 bg-white p-4 text-left transition-all hover:border-emerald-200 hover:shadow-sm"
        >
          <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
            <CalendarPlus className="h-4.5 w-4.5" />
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
          className="group rounded-2xl border border-slate-100 bg-white p-4 text-left transition-all hover:border-amber-200 hover:shadow-sm"
        >
          <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
            <CreditCard className="h-4.5 w-4.5" />
          </div>
          <p className="text-sm font-extrabold text-slate-800">Pay Maintenance</p>
          {primaryInvoice ? (
            <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="text-base font-extrabold text-slate-800">
                ₹{primaryInvoice.amount.toLocaleString('en-IN')}
              </span>
              <span className="text-[10px] font-semibold text-slate-400">
                Due {formatDueDate(primaryInvoice.dueDate)}
              </span>
            </div>
          ) : (
            <p className="mt-1 text-[10px] font-semibold text-emerald-600">
              No maintenance dues
            </p>
          )}
        </button>
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
                onClick={() => navigate('/resident/visitors?view=history')}
                className="text-xs font-bold text-indigo-600 hover:underline"
              >
                History
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
                          onClick={() => rejectVisitorRequest(vis.id)}
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
              <div>
                <h3 className="text-lg font-extrabold text-slate-900">
                  {visitorQrPass ? 'Visitor QR Pass' : 'Pre-approve Visitors'}
                </h3>
                <p className="mt-1 text-[11px] font-semibold text-slate-400">
                  {visitorQrPass
                    ? 'One QR code for the complete visitor group.'
                    : 'Create a shared gate pass for expected visitors.'}
                </p>
              </div>
              <button 
                onClick={closeVisitorModal}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                {visitorQrPass ? 'Done' : 'Cancel'}
              </button>
            </div>

            {visitorQrPass ? (
              <div className="space-y-5">
                <div className="mx-auto w-fit rounded-2xl border border-indigo-100 bg-white p-3 shadow-sm">
                  <img
                    src={visitorQrPass.qrDataUrl}
                    alt="Visitor group QR pass"
                    className="h-56 w-56"
                  />
                </div>
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-extrabold text-slate-800">
                        {visitorQrPass.visitor.purpose === 'Other'
                          ? visitorQrPass.visitor.purposeDetails || 'Other'
                          : visitorQrPass.visitor.purpose}{' '}
                        Group Pass
                      </p>
                      <p className="mt-1 text-[11px] font-semibold text-slate-400">
                        {visitorQrPass.visitor.purpose} ·{' '}
                        {visitorQrPass.visitor.date} at{' '}
                        {visitorQrPass.visitor.expectedTime}
                      </p>
                    </div>
                    <span className="rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-[10px] font-extrabold text-indigo-700">
                      {visitorQrPass.visitor.guestCount} Guest
                      {visitorQrPass.visitor.guestCount === 1 ? '' : 's'}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center gap-2 rounded-xl bg-white p-3 text-[11px] font-semibold text-slate-500">
                    <QrCode className="h-4 w-4 shrink-0 text-indigo-600" />
                    Share this same QR and security code with every guest in the
                    group.
                  </div>
                </div>
                <div className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="rounded-xl bg-white p-2 text-indigo-600 shadow-sm">
                        <ShieldCheck className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                          Security Code
                        </p>
                        <p className="mt-0.5 font-mono text-xl font-extrabold tracking-[0.2em] text-slate-900">
                          {getVisitorSecurityCode(visitorQrPass.visitor)}
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={copyVisitorSecurityCode}
                      className="flex items-center gap-1.5 rounded-xl border border-indigo-100 bg-white px-3 py-2 text-[11px] font-bold text-indigo-700 hover:bg-indigo-50"
                    >
                      <Copy className="h-3.5 w-3.5" />
                      Copy
                    </button>
                  </div>
                  <p className="mt-3 text-[10px] font-semibold leading-relaxed text-slate-500">
                    Security can scan the QR or enter this code manually. It is
                    valid for the complete visitor group.
                  </p>
                </div>
                <a
                  href={visitorQrPass.qrDataUrl}
                  download={`HomeBandhu-${visitorQrPass.visitor.purpose}-Group-QR.png`}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-sm font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700"
                >
                  <Download className="h-4 w-4" />
                  Download QR Code
                </a>
              </div>
            ) : (
              <form onSubmit={handleAddVisitor} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Purpose</label>
                  <select
                    value={visitorForm.purpose}
                    onChange={(e) => setVisitorForm({ ...visitorForm, purpose: e.target.value })}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  >
                    <option value="Guest">Guest</option>
                    <option value="Service">Service</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                {visitorForm.purpose === 'Other' && (
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                      Specify Purpose
                    </label>
                    <input
                      type="text"
                      required
                      value={visitorForm.purposeDetails}
                      onChange={(e) =>
                        setVisitorForm({
                          ...visitorForm,
                          purposeDetails: e.target.value,
                        })
                      }
                      placeholder="e.g. Family event"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Expected Date</label>
                    <input
                      type="date"
                      required
                      min={new Date().toISOString().split('T')[0]}
                      value={visitorForm.date}
                      onChange={(e) => setVisitorForm({ ...visitorForm, date: e.target.value })}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Expected Time</label>
                    <input
                      type="time"
                      required
                      value={visitorForm.time}
                      onChange={(e) => setVisitorForm({ ...visitorForm, time: e.target.value })}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Number of Guests</label>
                  <input
                    type="number"
                    required
                    min="1"
                    max="25"
                    value={visitorForm.guestCount}
                    onChange={(e) =>
                      setVisitorForm({
                        ...visitorForm,
                        guestCount: Number(e.target.value),
                      })
                    }
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  />
                  <p className="text-[10px] font-semibold text-slate-400">
                    The same QR code will be valid for this complete group.
                  </p>
                </div>

                {visitorQrError && (
                  <p className="rounded-xl border border-rose-100 bg-rose-50 p-3 text-xs font-semibold text-rose-700">
                    {visitorQrError}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={isGeneratingQr}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-sm font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  <QrCode className="h-4 w-4" />
                  {isGeneratingQr ? 'Generating QR...' : 'Generate QR Code'}
                </button>
              </form>
            )}
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
