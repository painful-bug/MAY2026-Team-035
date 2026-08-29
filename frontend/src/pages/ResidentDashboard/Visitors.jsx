import React, { useState } from 'react';
// The QR pass modal renders through a portal to document.body. In place, it
// sat inside ResidentLayout's `<main class="animate-fade-in">` — a
// fill-forwards opacity animation keeps <main> a stacking context forever, so
// `z-[999]` was trapped at <main>'s own level and the sticky header's `z-40`
// painted above it. Same fix as the departments modals
// (AdminDashboard/Departments.jsx).
import { createPortal } from 'react-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import QRCode from 'qrcode';
import { QUERY_POLICIES, PAGINATED } from '../../lib/api/queryClient';
import {
  Users,
  UserPlus,
  CheckCircle,
  QrCode,
  Download,
  X,
  Copy,
  ShieldCheck,
  Info,
} from 'lucide-react';
import { residentApi } from '../../features/resident/residentApi';
import { useAppStore } from '../../store/appStore';

// Wired to `docs/API.md` §13 / `backend/app/api/v1/routers/resident_visitor_passes.py`.
//
// **What changed from the demo.** The demo's Approve/Reject buttons answered a
// visitor request the *frontend itself* invented and raised
// (`createVisitorsSlice.requestVisitorApproval`, called from the Security
// portal): a whole gate conversation simulated entirely in the browser, with
// no backend on either end.
//
// The real `/visitor-passes/{id}/approve` and `/reject` answer something
// narrower and real: a pass the *gate* put in `Pending Approval` because
// somebody arrived unannounced. No endpoint in this codebase creates that
// state yet -- the gate/security app it belongs to does not exist -- so these
// two buttons are wired correctly and, today, practically unreachable. That is
// the router's own stated boundary, not a bug here. The invented
// resident-simulates-the-gate flow is gone; nothing in this file creates a
// `Pending Approval` pass anymore.
const STATUS_STYLES = {
  'Checked In': 'bg-emerald-50 text-emerald-700 border border-emerald-100',
  'Checked Out': 'bg-slate-100 text-slate-500 border border-slate-200',
  Approved: 'bg-blue-50 text-blue-700 border border-blue-100',
  Expected: 'bg-amber-50 text-amber-700 border border-amber-100',
  'Pending Approval': 'bg-indigo-50 text-indigo-700 border border-indigo-100',
  Rejected: 'bg-rose-50 text-rose-700 border border-rose-100',
  Cancelled: 'bg-slate-100 text-slate-500 border border-slate-200',
  Expired: 'bg-slate-100 text-slate-500 border border-slate-200',
};

const CANCELLABLE_STATUSES = ['Expected', 'Pending Approval', 'Approved'];

const formatWhen = (iso) => {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const buildQrPayload = (pass, secret) =>
  JSON.stringify({
    type: 'homebandhu-visitor-pass',
    version: 2,
    passId: pass.id,
    token: secret.passToken,
    securityCode: secret.securityCode,
    guestCount: pass.guestCount ?? 1,
  });

export default function Visitors() {
  const showToast = useAppStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeView = searchParams.get('view') === 'history' ? 'history' : 'current';

  const [purpose, setPurpose] = useState('Guest');
  const [purposeDetails, setPurposeDetails] = useState('');
  const [time, setTime] = useState('16:00');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [guestCount, setGuestCount] = useState(1);
  const [qrModal, setQrModal] = useState(null);
  const [isGeneratingQr, setIsGeneratingQr] = useState(false);
  // **The one place the security code and pass token ever live on this
  // screen.** `POST /visitor-passes` returns both exactly once, and no later
  // read can return them (docs/API.md §13). This map is this browser tab's
  // memory of what it was just handed -- it does not survive a refresh, and
  // it is not supposed to: the pass is still valid at the gate, this screen
  // just cannot show its QR again. A resident who needs it back issues a new
  // pass, the same trade the invite flow already makes.
  const [secretsByPassId, setSecretsByPassId] = useState({});

  const passesQuery = useQuery({
    queryKey: ['resident', 'visitor-passes', activeView],
    queryFn: () => residentApi.visitorPasses({ view: activeView }),
    ...QUERY_POLICIES.list,
    ...PAGINATED,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['resident', 'visitor-passes'] });

  const renderQr = async (pass, secret) => {
    setIsGeneratingQr(true);
    try {
      const payload = buildQrPayload(pass, secret);
      const qrDataUrl = await QRCode.toDataURL(payload, {
        width: 320,
        margin: 2,
        color: { dark: '#362016', light: '#fffdf7' },
        errorCorrectionLevel: 'M',
      });
      setQrModal({ pass, qrDataUrl, securityCode: secret.securityCode });
    } finally {
      setIsGeneratingQr(false);
    }
  };

  const create = useMutation({
    mutationFn: (payload) => residentApi.createVisitorPass(payload),
    onSuccess: async (created) => {
      const secret = { securityCode: created.securityCode, passToken: created.passToken };
      setSecretsByPassId((prev) => ({ ...prev, [created.id]: secret }));
      setGuestCount(1);
      setPurposeDetails('');
      invalidate();
      showToast?.(`QR pass generated for ${created.guestCount} guest${created.guestCount === 1 ? '' : 's'}`, 'success');
      await renderQr(created, secret);
    },
  });

  const decide = useMutation({
    mutationFn: ({ passId, decision }) => {
      if (decision === 'approve') return residentApi.approveVisitorPass(passId);
      if (decision === 'reject') return residentApi.rejectVisitorPass(passId);
      return residentApi.cancelVisitorPass(passId);
    },
    onSuccess: invalidate,
  });

  const openQr = (pass) => {
    const secret = secretsByPassId[pass.id];
    if (!secret) return;
    renderQr(pass, secret);
  };

  const copySecurityCode = async (code) => {
    if (!code) return;
    await navigator.clipboard.writeText(code);
    showToast?.('Security code copied', 'success');
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    if (purpose === 'Other' && !purposeDetails.trim()) return;
    const expectedAt = new Date(`${date}T${time}:00`).toISOString();
    create.mutate({
      purpose,
      purposeDetails: purpose === 'Other' ? purposeDetails.trim() : '',
      guestCount,
      expectedAt,
    });
  };

  const passes = passesQuery.data?.items || [];
  const getPurposeLabel = (pass) =>
    pass.purpose === 'Other' ? pass.purposeDetails || 'Other' : pass.purpose || 'Visitor';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Visitor Management</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Create QR passes and review current or past gate activity.</p>
        <div className="mt-4 inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
          <button
            type="button"
            onClick={() => setSearchParams({ view: 'current' })}
            className={`rounded-lg px-4 py-2 text-xs font-bold transition-colors ${
              activeView === 'current'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-500 hover:bg-slate-50'
            }`}
          >
            Current Passes
          </button>
          <button
            type="button"
            onClick={() => setSearchParams({ view: 'history' })}
            className={`rounded-lg px-4 py-2 text-xs font-bold transition-colors ${
              activeView === 'history'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-500 hover:bg-slate-50'
            }`}
          >
            History
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {activeView === 'current' && (
          <div className="lg:col-span-4 bg-white p-6 border border-slate-100 rounded-2xl h-fit space-y-4 shadow-sm">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-50">
              <UserPlus className="w-5 h-5 text-indigo-650" />
              <h3 className="font-extrabold text-slate-805 text-sm">Pre-approve Entry</h3>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3.5">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Purpose</label>
                <select
                  value={purpose}
                  onChange={(e) => setPurpose(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                >
                  <option value="Guest">Guest</option>
                  <option value="Service">Service</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              {purpose === 'Other' && (
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Specify Purpose
                  </label>
                  <input
                    type="text"
                    required
                    value={purposeDetails}
                    onChange={(e) => setPurposeDetails(e.target.value)}
                    placeholder="e.g. Family event"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Date</label>
                  <input
                    type="date"
                    min={new Date().toISOString().split('T')[0]}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Expected Time</label>
                  <input
                    type="time"
                    value={time}
                    onChange={(e) => setTime(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Number of Guests</label>
                <input
                  type="number"
                  required
                  min="1"
                  max="50"
                  value={guestCount}
                  onChange={(e) => setGuestCount(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                />
                <p className="text-[10px] font-semibold text-slate-400">
                  One shared QR will cover the complete group.
                </p>
              </div>

              {create.error && (
                <p role="alert" className="text-[11px] font-semibold text-rose-600">
                  {create.error.message}
                </p>
              )}

              <button
                type="submit"
                disabled={create.isPending || isGeneratingQr}
                className="flex w-full items-center justify-center gap-2 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 text-xs disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                <QrCode className="h-4 w-4" />
                {create.isPending || isGeneratingQr ? 'Generating QR...' : 'Generate QR Code'}
              </button>
            </form>
          </div>
        )}

        <div className={`${activeView === 'history' ? 'lg:col-span-12' : 'lg:col-span-8'} bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden flex flex-col justify-between`}>
          <div className="p-6 border-b border-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-650" />
              <h3 className="font-extrabold text-slate-800 text-sm">
                {activeView === 'history' ? 'Visitor History' : 'Current Visitor Passes'}
              </h3>
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-50 px-2.5 py-1 border border-slate-100 rounded-lg text-slate-450">
              {passes.length} {activeView === 'history' ? 'Past Visits' : 'Active Passes'}
            </span>
          </div>

          <div className="overflow-x-auto flex-1">
            {passesQuery.isLoading ? (
              <div className="text-center py-12 text-xs text-slate-400 font-semibold">Loading passes…</div>
            ) : passesQuery.error ? (
              <div role="alert" className="p-6 text-center text-xs font-semibold text-rose-600">
                {passesQuery.error.message || 'Could not load visitor passes.'}
              </div>
            ) : passes.length === 0 ? (
              <div className="text-center py-12 text-xs text-slate-400 font-semibold">
                {activeView === 'history'
                  ? 'No past visitor activity recorded for this flat.'
                  : 'No current or upcoming visitor passes.'}
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50/55 border-b border-slate-100 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                    <th className="px-6 py-3.5">Purpose</th>
                    <th className="px-6 py-3.5">Guests</th>
                    <th className="px-6 py-3.5">Valid Window</th>
                    <th className="px-6 py-3.5">Gate Activity</th>
                    <th className="px-6 py-3.5">Status</th>
                    <th className="px-6 py-3.5">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 text-xs font-semibold text-slate-600">
                  {passes.map((pass) => (
                    <tr key={pass.id} className="hover:bg-slate-50/30 transition-colors">
                      <td className="px-6 py-4.5">
                        <span className="font-bold text-slate-800">{getPurposeLabel(pass)}</span>
                        {pass.isLapsed && (
                          <span className="mt-0.5 block text-[10px] font-bold text-amber-600">Window has passed</span>
                        )}
                      </td>
                      <td className="px-6 py-4.5">
                        {pass.guestCount ?? 1} Guest{(pass.guestCount ?? 1) === 1 ? '' : 's'}
                      </td>
                      <td className="px-6 py-4.5">
                        <div>
                          <p>{formatWhen(pass.validFrom) || 'Not specified'}</p>
                          {pass.validUntil && (
                            <p className="text-[10px] text-slate-400 font-medium">
                              until {formatWhen(pass.validUntil)}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4.5">
                        {pass.checkedInAt ? (
                          <div>
                            <p>In: {formatWhen(pass.checkedInAt)}</p>
                            <p className="text-[10px] text-slate-400 font-medium">
                              {pass.checkedOutAt ? `Out: ${formatWhen(pass.checkedOutAt)}` : 'Still inside'}
                            </p>
                          </div>
                        ) : (
                          <span className="text-slate-400">Not checked in</span>
                        )}
                      </td>
                      <td className="px-6 py-4.5">
                        <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${
                          STATUS_STYLES[pass.status] || 'bg-slate-100 text-slate-500 border border-slate-200'
                        }`}>
                          {pass.status}
                        </span>
                      </td>
                      <td className="px-6 py-4.5">
                        <div className="flex flex-wrap items-center gap-2">
                          {pass.status === 'Pending Approval' ? (
                            <>
                              <button
                                type="button"
                                disabled={decide.isPending}
                                onClick={() => decide.mutate({ passId: pass.id, decision: 'approve' })}
                                className="bg-indigo-600 hover:bg-indigo-700 text-white text-[10px] font-bold px-3 py-1 rounded-lg transition-colors shadow-sm disabled:opacity-60"
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                disabled={decide.isPending}
                                onClick={() => decide.mutate({ passId: pass.id, decision: 'reject' })}
                                className="border border-slate-200 text-slate-500 hover:bg-slate-50 text-[10px] font-bold px-3 py-1 rounded-lg transition-colors disabled:opacity-60"
                              >
                                Reject
                              </button>
                            </>
                          ) : null}
                          {['Expected', 'Approved'].includes(pass.status) ? (
                            secretsByPassId[pass.id] ? (
                              <button
                                type="button"
                                onClick={() => openQr(pass)}
                                className="text-[10px] text-indigo-600 flex items-center gap-1 font-bold hover:text-indigo-700"
                              >
                                <QrCode className="w-3 h-3" /> View QR
                              </button>
                            ) : (
                              <span
                                title="The security code is only shown once, right after the pass is created."
                                className="text-[10px] text-slate-400 flex items-center gap-1 font-bold"
                              >
                                <Info className="w-3 h-3" /> QR not saved
                              </span>
                            )
                          ) : null}
                          {CANCELLABLE_STATUSES.includes(pass.status) ? (
                            <button
                              type="button"
                              disabled={decide.isPending}
                              onClick={() => decide.mutate({ passId: pass.id, decision: 'cancel' })}
                              className="text-[10px] text-rose-600 hover:text-rose-700 font-bold disabled:opacity-60"
                            >
                              Cancel
                            </button>
                          ) : null}
                          {activeView === 'history' && !CANCELLABLE_STATUSES.includes(pass.status) ? (
                            <span className="text-[10px] text-slate-400 flex items-center gap-1 font-bold">
                              <CheckCircle className="w-3.5 h-3.5 text-emerald-600" /> Recorded
                            </span>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {decide.error && (
            <p role="alert" className="px-6 py-3 text-xs font-semibold text-rose-600 border-t border-slate-50">
              {decide.error.message}
            </p>
          )}
        </div>
      </div>

      {qrModal && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Visitor QR pass"
          className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setQrModal(null);
          }}
        >
          <div className="max-h-[calc(100dvh-2rem)] w-full max-w-sm overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-extrabold text-slate-900">Visitor QR Pass</h2>
                <p className="mt-1 text-[11px] font-semibold text-slate-400">
                  Shared by the complete visitor group.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setQrModal(null)}
                className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
                aria-label="Close QR pass"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mx-auto mt-5 w-fit rounded-2xl border border-indigo-100 p-3">
              <img src={qrModal.qrDataUrl} alt="Visitor group QR pass" className="h-56 w-56" />
            </div>
            <div className="mt-4 text-center">
              <p className="text-sm font-extrabold text-slate-800">
                {getPurposeLabel(qrModal.pass)} Group Pass
              </p>
              <p className="mt-1 text-xs font-semibold text-slate-400">
                Valid for {qrModal.pass.guestCount ?? 1} guest{(qrModal.pass.guestCount ?? 1) === 1 ? '' : 's'}
                {formatWhen(qrModal.pass.validFrom) ? ` · from ${formatWhen(qrModal.pass.validFrom)}` : ''}
              </p>
            </div>
            <div className="mt-4 rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4">
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
                      {qrModal.securityCode}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => copySecurityCode(qrModal.securityCode)}
                  className="flex items-center gap-1.5 rounded-xl border border-indigo-100 bg-white px-3 py-2 text-[11px] font-bold text-indigo-700 hover:bg-indigo-50"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy
                </button>
              </div>
              <p className="mt-3 text-[10px] font-semibold leading-relaxed text-slate-500">
                Security can scan the QR or enter this code manually. This is the
                only time it will be shown — write it down or keep this app open
                if you want to read it again later.
              </p>
            </div>
            <a
              href={qrModal.qrDataUrl}
              download={`HomeBandhu-${getPurposeLabel(qrModal.pass).replaceAll(' ', '-')}-Group-QR.png`}
              className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-xs font-bold text-white hover:bg-indigo-700"
            >
              <Download className="h-4 w-4" />
              Download QR Code
            </a>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
