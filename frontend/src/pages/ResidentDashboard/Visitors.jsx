import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { getVisitorSecurityCode } from '../../lib/visitorPasses';
import { useSearchParams } from 'react-router-dom';
import QRCode from 'qrcode';
import {
  Users,
  UserPlus,
  CheckCircle,
  QrCode,
  Download,
  X,
  Copy,
  ShieldCheck,
} from 'lucide-react';

export default function Visitors() {
  const {
    visitors,
    currentUser,
    preapproveVisitor,
    approveVisitorRequest,
    rejectVisitorRequest,
    showToast,
  } = useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [purpose, setPurpose] = useState('Guest');
  const [purposeDetails, setPurposeDetails] = useState('');
  const [time, setTime] = useState('16:00');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [guestCount, setGuestCount] = useState(1);
  const [generatedPass, setGeneratedPass] = useState(null);
  const [isGeneratingQr, setIsGeneratingQr] = useState(false);

  const userVisitors = visitors.filter(v => v.flat === currentUser?.flat);
  const today = new Date().toISOString().split('T')[0];
  const activeView = searchParams.get('view') === 'history' ? 'history' : 'current';
  const isPastVisitor = (visitor) =>
    ['Checked Out', 'Rejected'].includes(visitor.status) ||
    (visitor.date && visitor.date < today);
  const visibleVisitors = userVisitors
    .filter((visitor) =>
      activeView === 'history' ? isPastVisitor(visitor) : !isPastVisitor(visitor)
    )
    .sort((a, b) =>
      `${b.date || ''} ${b.expectedTime || b.eta || ''}`.localeCompare(
        `${a.date || ''} ${a.expectedTime || a.eta || ''}`
      )
    );
  const getPurposeLabel = (visitor) =>
    visitor.purpose === 'Other'
      ? visitor.purposeDetails || 'Other'
      : visitor.purpose || 'Visitor';

  const showQrPass = async (visitor) => {
    setIsGeneratingQr(true);
    try {
      const payload =
        visitor.qrPayload ??
        JSON.stringify({
          type: 'homebandhu-visitor-pass',
          version: 1,
          passId: visitor.id,
          securityCode: getVisitorSecurityCode(visitor),
          guestCount: visitor.guestCount ?? 1,
        });
      const qrDataUrl = await QRCode.toDataURL(payload, {
        width: 320,
        margin: 2,
        color: { dark: '#2b381a', light: '#fffdf7' },
        errorCorrectionLevel: 'M',
      });
      setGeneratedPass({ visitor, qrDataUrl });
    } finally {
      setIsGeneratingQr(false);
    }
  };

  const copySecurityCode = async (visitor) => {
    const securityCode = getVisitorSecurityCode(visitor);
    if (!securityCode) return;

    await navigator.clipboard.writeText(securityCode);
    showToast('Security code copied', 'success');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const visitor = preapproveVisitor({
      purpose,
      purposeDetails,
      time,
      date,
      guestCount,
    });
    setGuestCount(1);
    setPurposeDetails('');
    await showQrPass(visitor);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Visitor Management</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Create group QR passes and review current or past gate activity.</p>
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
        {/* Pre-approve Form */}
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
                max="25"
                value={guestCount}
                onChange={(e) => setGuestCount(Number(e.target.value))}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
              />
              <p className="text-[10px] font-semibold text-slate-400">
                One shared QR will cover the complete group.
              </p>
            </div>

            <button
              type="submit"
              disabled={isGeneratingQr}
              className="flex w-full items-center justify-center gap-2 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 text-xs disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <QrCode className="h-4 w-4" />
              {isGeneratingQr ? 'Generating QR...' : 'Generate QR Code'}
            </button>
          </form>
          </div>
        )}

        {/* Visitors Log */}
        <div className={`${activeView === 'history' ? 'lg:col-span-12' : 'lg:col-span-8'} bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden flex flex-col justify-between`}>
          <div className="p-6 border-b border-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-650" />
              <h3 className="font-extrabold text-slate-800 text-sm">
                {activeView === 'history' ? 'Visitor History' : 'Current Visitor Passes'}
              </h3>
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-50 px-2.5 py-1 border border-slate-100 rounded-lg text-slate-450">
              {visibleVisitors.length} {activeView === 'history' ? 'Past Visits' : 'Active Passes'}
            </span>
          </div>

          <div className="overflow-x-auto flex-1">
            {visibleVisitors.length === 0 ? (
              <div className="text-center py-12 text-xs text-slate-400 font-semibold">
                {activeView === 'history'
                  ? 'No past visitor activity recorded for this flat.'
                  : 'No current or upcoming visitor passes.'}
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50/55 border-b border-slate-100 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                    <th className="px-6 py-3.5">Security Code</th>
                    <th className="px-6 py-3.5">Purpose</th>
                    <th className="px-6 py-3.5">Group Size</th>
                    <th className="px-6 py-3.5">Expected On</th>
                    <th className="px-6 py-3.5">Gate Activity</th>
                    <th className="px-6 py-3.5">Status</th>
                    <th className="px-6 py-3.5">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 text-xs font-semibold text-slate-600">
                  {visibleVisitors.map((vis) => (
                    <tr key={vis.id} className="hover:bg-slate-50/30 transition-colors">
                      <td className="px-6 py-4.5">
                        <span className="font-mono text-indigo-700 bg-indigo-50 border border-indigo-100/50 px-2 py-0.5 rounded text-[10px] font-bold">
                          {getVisitorSecurityCode(vis)}
                        </span>
                      </td>
                      <td className="px-6 py-4.5">
                        <span className="font-bold text-slate-800">{getPurposeLabel(vis)}</span>
                        {vis.purpose !== 'Other' && vis.purposeDetails && (
                          <span className="mt-0.5 block text-[10px] font-medium text-slate-400">
                            {vis.purposeDetails}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4.5">
                        {vis.guestCount ?? 1} Guest
                        {(vis.guestCount ?? 1) === 1 ? '' : 's'}
                      </td>
                      <td className="px-6 py-4.5">
                        <div>
                          <p>{vis.date}</p>
                          <p className="text-[10px] text-slate-400 font-medium">
                            {vis.expectedTime || vis.eta || 'Not specified'}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 py-4.5">
                        {vis.checkInTime ? (
                          <div>
                            <p>In: {vis.checkInTime}</p>
                            <p className="text-[10px] text-slate-400 font-medium">
                              {vis.checkOutTime
                                ? `Out: ${vis.checkOutTime}`
                                : activeView === 'history'
                                  ? 'Checkout not recorded'
                                  : 'Still inside'}
                            </p>
                          </div>
                        ) : (
                          <span className="text-slate-400">Not checked in</span>
                        )}
                      </td>
                      <td className="px-6 py-4.5">
                        <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${
                          vis.status === 'Checked In' 
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' 
                            : vis.status === 'Checked Out'
                            ? 'bg-slate-100 text-slate-500 border border-slate-200'
                            : vis.status === 'Approved'
                            ? 'bg-blue-50 text-blue-700 border border-blue-100'
                            : vis.status === 'Expected'
                            ? 'bg-amber-50 text-amber-700 border border-amber-100'
                            : 'bg-rose-50 text-rose-700 border border-rose-100'
                        }`}>
                          {vis.status}
                        </span>
                      </td>
                      <td className="px-6 py-4.5">
                        {activeView === 'history' ? (
                          <span className="text-[10px] text-slate-400 flex items-center gap-1 font-bold">
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-600" /> Recorded
                          </span>
                        ) : vis.status === 'Pending Approval' ? (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => approveVisitorRequest(vis.id)}
                              className="bg-indigo-600 hover:bg-indigo-700 text-white text-[10px] font-bold px-3 py-1 rounded-lg transition-colors shadow-sm"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => rejectVisitorRequest(vis.id)}
                              className="border border-slate-200 text-slate-500 hover:bg-slate-50 text-[10px] font-bold px-3 py-1 rounded-lg transition-colors"
                            >
                              Reject
                            </button>
                          </div>
                        ) : ['Expected', 'Approved'].includes(vis.status) ? (
                          <button
                            type="button"
                            onClick={() => showQrPass(vis)}
                            className="text-[10px] text-indigo-600 flex items-center gap-1 font-bold hover:text-indigo-700"
                          >
                            <QrCode className="w-3 h-3" /> View QR
                          </button>
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

      {generatedPass && (
        <div
          className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setGeneratedPass(null);
            }
          }}
        >
          <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-extrabold text-slate-900">
                  Visitor QR Pass
                </h2>
                <p className="mt-1 text-[11px] font-semibold text-slate-400">
                  Shared by the complete visitor group.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setGeneratedPass(null)}
                className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
                aria-label="Close QR pass"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mx-auto mt-5 w-fit rounded-2xl border border-indigo-100 p-3">
              <img
                src={generatedPass.qrDataUrl}
                alt="Visitor group QR pass"
                className="h-56 w-56"
              />
            </div>
            <div className="mt-4 text-center">
              <p className="text-sm font-extrabold text-slate-800">
                {getPurposeLabel(generatedPass.visitor)} Group Pass
              </p>
              <p className="mt-1 text-xs font-semibold text-slate-400">
                Valid for {generatedPass.visitor.guestCount ?? 1} guest
                {(generatedPass.visitor.guestCount ?? 1) === 1 ? '' : 's'} ·{' '}
                {generatedPass.visitor.date} at{' '}
                {generatedPass.visitor.expectedTime ??
                  generatedPass.visitor.eta}
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
                      {getVisitorSecurityCode(generatedPass.visitor)}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => copySecurityCode(generatedPass.visitor)}
                  className="flex items-center gap-1.5 rounded-xl border border-indigo-100 bg-white px-3 py-2 text-[11px] font-bold text-indigo-700 hover:bg-indigo-50"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy
                </button>
              </div>
              <p className="mt-3 text-[10px] font-semibold leading-relaxed text-slate-500">
                Security can scan the QR or enter this code manually. The same
                code is valid for the complete visitor group.
              </p>
            </div>
            <a
              href={generatedPass.qrDataUrl}
              download={`HomeBandhu-${getPurposeLabel(generatedPass.visitor).replaceAll(' ', '-')}-Group-QR.png`}
              className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-xs font-bold text-white hover:bg-indigo-700"
            >
              <Download className="h-4 w-4" />
              Download QR Code
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
