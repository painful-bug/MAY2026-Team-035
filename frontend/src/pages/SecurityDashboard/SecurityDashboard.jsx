import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Camera,
  CheckCircle2,
  ClipboardClock,
  Clock3,
  DoorOpen,
  History,
  KeyRound,
  LifeBuoy,
  LogIn,
  LogOut,
  Phone,
  ScanLine,
  Send,
  UserCheck,
  Users,
  X,
} from 'lucide-react';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useApp } from '../../store/useApp';
import { getVisitorSecurityCode } from '../../lib/visitorPasses';

const todayISO = () => new Date().toISOString().split('T')[0];
const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

const statusClasses = {
  'Pending Approval': 'border-amber-100 bg-amber-50 text-amber-700',
  Approved: 'border-blue-100 bg-blue-50 text-blue-700',
  Expected: 'border-indigo-100 bg-indigo-50 text-indigo-700',
  'Checked In': 'border-emerald-100 bg-emerald-50 text-emerald-700',
  'Checked Out': 'border-slate-200 bg-slate-100 text-slate-600',
  Rejected: 'border-rose-100 bg-rose-50 text-rose-700',
};

const formatVisitTime = (visitor) =>
  visitor.expectedTime || visitor.eta || 'Not specified';

function MetricCard({ icon: Icon, label, value, detail, tone }) {
  const tones = {
    indigo: 'bg-indigo-50 text-indigo-600',
    amber: 'bg-amber-50 text-amber-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    slate: 'bg-slate-100 text-slate-600',
  };

  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            {label}
          </p>
          <p className="mt-2 text-3xl font-extrabold text-slate-900">{value}</p>
          <p className="mt-1 text-[10px] font-semibold text-slate-400">
            {detail}
          </p>
        </div>
        <div className={`rounded-xl p-3 ${tones[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function ResultMessage({ result, onClose }) {
  if (!result) return null;

  return (
    <div
      className={`flex items-start justify-between gap-3 rounded-xl border p-3 text-xs font-semibold ${
        result.ok
          ? 'border-emerald-100 bg-emerald-50 text-emerald-800'
          : 'border-rose-100 bg-rose-50 text-rose-800'
      }`}
    >
      <div className="flex items-start gap-2">
        {result.ok ? (
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
        ) : (
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        )}
        <div>
          <p>
            {result.ok
              ? `${result.visitor?.name || 'Visitor'} may enter. Check-in recorded.`
              : result.message}
          </p>
          {result.ok && result.visitor && (
            <p className="mt-1 text-[10px] font-medium opacity-80">
              Flat {result.visitor.flat} · {result.visitor.guestCount || 1}{' '}
              guest{Number(result.visitor.guestCount || 1) === 1 ? '' : 's'}
            </p>
          )}
        </div>
      </div>
      <button type="button" onClick={onClose} aria-label="Dismiss result">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function SecurityDashboard({ view = 'dashboard' }) {
  const {
    currentUser,
    users,
    visitors,
    activities,
    requestVisitorApproval,
    verifyVisitorPass,
    checkInVisitor,
    checkOutVisitor,
    showToast,
    addActivity,
  } = useApp();
  const navigate = useNavigate();
  const dashboardPath =
    currentUser?.role === 'SecurityManager'
      ? AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD
      : AUTH_ROUTES.SECURITY_DASHBOARD;
  const videoRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const scannerTimerRef = useRef(null);
  const scanBusyRef = useRef(false);
  const [manualCode, setManualCode] = useState('');
  const [verificationResult, setVerificationResult] = useState(null);
  const [scannerActive, setScannerActive] = useState(false);
  const [scannerMessage, setScannerMessage] = useState('');

  const residentOptions = useMemo(() => {
    const byFlat = new Map();
    users
      .filter((user) => user.role === 'Resident' && user.status === 'Active')
      .forEach((user) => {
        if (!byFlat.has(user.flat)) {
          byFlat.set(user.flat, {
            flat: user.flat,
            tower: user.tower,
            residentName: user.name,
          });
        }
      });
    return [...byFlat.values()].sort((a, b) => a.flat.localeCompare(b.flat));
  }, [users]);

  const [requestForm, setRequestForm] = useState(() => ({
    flat: '',
    visitorLabel: '',
    purpose: 'Guest',
    guestCount: 1,
    date: todayISO(),
    time: new Date().toTimeString().slice(0, 5),
  }));
  const [incidentForm, setIncidentForm] = useState({
    type: 'Security concern',
    location: 'Main Gate',
    details: '',
  });

  useEffect(() => {
    if (requestForm.flat || residentOptions.length === 0) return;
    setRequestForm((current) => ({
      ...current,
      flat: residentOptions[0].flat,
    }));
  }, [requestForm.flat, residentOptions]);

  const today = todayISO();
  const pendingVisitors = visitors.filter(
    (visitor) => visitor.status === 'Pending Approval'
  );
  const approvedVisitors = visitors.filter(
    (visitor) => visitor.status === 'Approved'
  );
  const expectedVisitors = visitors.filter(
    (visitor) => visitor.status === 'Expected'
  );
  const checkedInVisitors = visitors.filter(
    (visitor) => visitor.status === 'Checked In'
  );
  const gateHistory = visitors
    .filter(
      (visitor) =>
        ['Checked Out', 'Rejected'].includes(visitor.status) ||
        visitor.checkedInAt
    )
    .sort((a, b) =>
      String(b.checkedOutAt || b.checkedInAt || b.createdAt || b.date).localeCompare(
        String(a.checkedOutAt || a.checkedInAt || a.createdAt || a.date)
      )
    );
  const todayEntries = visitors.filter(
    (visitor) =>
      visitor.checkedInAt?.startsWith(today) ||
      (!visitor.checkedInAt && visitor.date === today && visitor.checkInTime)
  ).length;

  const stopScanner = useCallback(() => {
    if (scannerTimerRef.current) {
      clearInterval(scannerTimerRef.current);
      scannerTimerRef.current = null;
    }
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setScannerActive(false);
    scanBusyRef.current = false;
  }, []);

  useEffect(() => stopScanner, [stopScanner]);

  const verifyCredential = useCallback(
    (credential) => {
      const result = verifyVisitorPass(credential);
      setVerificationResult(result);
      if (result.ok) {
        setManualCode('');
      }
      return result;
    },
    [verifyVisitorPass]
  );

  const startScanner = async () => {
    setScannerMessage('');
    setVerificationResult(null);
    const BarcodeDetector = globalThis.BarcodeDetector;

    if (!BarcodeDetector || !navigator.mediaDevices?.getUserMedia) {
      setScannerMessage(
        'QR camera scanning is not supported by this browser. Enter the security code manually.'
      );
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      });
      cameraStreamRef.current = stream;
      setScannerActive(true);

      await new Promise((resolve) => setTimeout(resolve, 0));
      if (!videoRef.current) {
        stopScanner();
        return;
      }
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      const detector = new BarcodeDetector({ formats: ['qr_code'] });

      scannerTimerRef.current = setInterval(async () => {
        if (
          scanBusyRef.current ||
          !videoRef.current ||
          videoRef.current.readyState < 2
        ) {
          return;
        }
        scanBusyRef.current = true;
        try {
          const codes = await detector.detect(videoRef.current);
          if (codes[0]?.rawValue) {
            stopScanner();
            verifyCredential(codes[0].rawValue);
          }
        } catch {
          setScannerMessage(
            'The QR could not be read. Hold it steady or use the manual code.'
          );
        } finally {
          scanBusyRef.current = false;
        }
      }, 500);
    } catch {
      stopScanner();
      setScannerMessage(
        'Camera access was unavailable. Allow camera permission or enter the code manually.'
      );
    }
  };

  const submitManualCode = (event) => {
    event.preventDefault();
    stopScanner();
    verifyCredential(manualCode);
  };

  const submitApprovalRequest = (event) => {
    event.preventDefault();
    const residence = residentOptions.find(
      (item) => item.flat === requestForm.flat
    );
    if (!residence) return;

    const visitor = requestVisitorApproval({
      ...requestForm,
      tower: residence.tower,
    });
    if (!visitor) return;
    setRequestForm((current) => ({
      ...current,
      visitorLabel: '',
      purpose: 'Guest',
      guestCount: 1,
    }));
  };

  const allowApprovedEntry = (visitorId) => {
    setVerificationResult(checkInVisitor(visitorId));
  };

  const logIncident = (event) => {
    event.preventDefault();
    if (!incidentForm.details.trim()) return;
    addActivity(
      `${currentUser.name} logged ${incidentForm.type.toLowerCase()} at ${incidentForm.location}: ${incidentForm.details.trim()}`,
      'security'
    );
    showToast('Security incident added to the activity log.', 'success');
    setIncidentForm((current) => ({ ...current, details: '' }));
  };

  if (view === 'emergency') {
    return (
      <div className="space-y-6">
        <PageHeading
          title="Emergency Desk"
          description="Quick contacts and incident logging for security operations."
        />
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
            <h2 className="text-base font-extrabold text-slate-900">
              Emergency Contacts
            </h2>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Tap a number from a supported device to call.
            </p>
            <div className="mt-5 space-y-3">
              {[
                ['Society Management Office', '+91 98765 43210'],
                ['Emergency Response', '112'],
                ['Fire Brigade', '101'],
                ['Ambulance', '108'],
              ].map(([label, phone]) => (
                <a
                  key={label}
                  href={`tel:${phone.replaceAll(' ', '')}`}
                  className="flex items-center justify-between rounded-xl border border-slate-100 p-4 hover:border-indigo-200 hover:bg-indigo-50/30"
                >
                  <div>
                    <p className="text-sm font-bold text-slate-800">{label}</p>
                    <p className="mt-1 text-xs font-semibold text-slate-400">
                      {phone}
                    </p>
                  </div>
                  <div className="rounded-xl bg-indigo-50 p-2.5 text-indigo-600">
                    <Phone className="h-4 w-4" />
                  </div>
                </a>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
            <h2 className="text-base font-extrabold text-slate-900">
              Log Security Incident
            </h2>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Record a concise note for management follow-up.
            </p>
            <form onSubmit={logIncident} className="mt-5 space-y-4">
              <Field label="Incident Type">
                <select
                  value={incidentForm.type}
                  onChange={(event) =>
                    setIncidentForm({
                      ...incidentForm,
                      type: event.target.value,
                    })
                  }
                  className={inputClass}
                >
                  <option>Security concern</option>
                  <option>Medical emergency</option>
                  <option>Fire alarm</option>
                  <option>Unauthorized access</option>
                  <option>Property damage</option>
                </select>
              </Field>
              <Field label="Location">
                <input
                  value={incidentForm.location}
                  onChange={(event) =>
                    setIncidentForm({
                      ...incidentForm,
                      location: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </Field>
              <Field label="Incident Details">
                <textarea
                  required
                  rows={5}
                  value={incidentForm.details}
                  onChange={(event) =>
                    setIncidentForm({
                      ...incidentForm,
                      details: event.target.value,
                    })
                  }
                  placeholder="What happened and what action was taken?"
                  className={`${inputClass} resize-none`}
                />
              </Field>
              <button
                type="submit"
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 py-3 text-xs font-bold text-white hover:bg-slate-800"
              >
                <Send className="h-4 w-4" />
                Save Incident
              </button>
            </form>
          </section>
        </div>
      </div>
    );
  }

  if (view === 'history') {
    return (
      <div className="space-y-6">
        <PageHeading
          title="Gate History"
          description="Review visitor check-ins, checkouts, rejected requests, and the security staff involved."
        />
        <GateHistory visitors={gateHistory} />
      </div>
    );
  }

  const isVisitorWorkspace = view === 'visitors';

  return (
    <div className="space-y-6">
      <PageHeading
        title={isVisitorWorkspace ? 'Visitor Access' : 'Security Overview'}
        description={
          isVisitorWorkspace
            ? 'Request resident approval, verify passes, and manage people currently inside.'
            : `Welcome, ${currentUser?.name}. Monitor today’s gate operations from one place.`
        }
        action={
          !isVisitorWorkspace && (
            <button
              type="button"
              onClick={() =>
                navigate(`${dashboardPath}/visitors`)
              }
              className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 hover:bg-indigo-700"
            >
              Open Visitor Access
              <ArrowRight className="h-4 w-4" />
            </button>
          )
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={ClipboardClock}
          label="Awaiting Residents"
          value={pendingVisitors.length}
          detail="Approval requests at the gate"
          tone="amber"
        />
        <MetricCard
          icon={UserCheck}
          label="Approved"
          value={approvedVisitors.length}
          detail="Ready to allow entry"
          tone="indigo"
        />
        <MetricCard
          icon={Users}
          label="Currently Inside"
          value={checkedInVisitors.reduce(
            (sum, visitor) => sum + Number(visitor.guestCount || 1),
            0
          )}
          detail="Guests across all flats"
          tone="emerald"
        />
        <MetricCard
          icon={History}
          label="Today's Entries"
          value={todayEntries}
          detail={`${expectedVisitors.length} pre-approved pass${expectedVisitors.length === 1 ? '' : 'es'} expected`}
          tone="slate"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {isVisitorWorkspace && (
          <ApprovalRequestForm
            form={requestForm}
            setForm={setRequestForm}
            residences={residentOptions}
            onSubmit={submitApprovalRequest}
          />
        )}
        <VerificationPanel
          manualCode={manualCode}
          setManualCode={setManualCode}
          onSubmit={submitManualCode}
          scannerActive={scannerActive}
          scannerMessage={scannerMessage}
          videoRef={videoRef}
          onStartScanner={startScanner}
          onStopScanner={stopScanner}
          result={verificationResult}
          onDismissResult={() => setVerificationResult(null)}
        />
        {!isVisitorWorkspace && (
          <QuickActions
            onVisitors={() =>
              navigate(`${dashboardPath}/visitors`)
            }
            onHistory={() =>
              navigate(`${dashboardPath}/history`)
            }
            onEmergency={() =>
              navigate(`${dashboardPath}/emergency`)
            }
          />
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <ApprovalQueue
          pending={pendingVisitors}
          approved={approvedVisitors}
          onAllowEntry={allowApprovedEntry}
        />
        <InsideNow
          visitors={checkedInVisitors}
          onCheckOut={checkOutVisitor}
        />
      </div>

      {!isVisitorWorkspace && (
        <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-extrabold text-slate-900">
                Recent Security Activity
              </h2>
              <p className="mt-1 text-xs font-semibold text-slate-400">
                Latest visitor and incident updates.
              </p>
            </div>
          </div>
          <div className="mt-5 space-y-3">
            {activities.slice(0, 6).map((activity) => (
              <div
                key={activity.id}
                className="flex items-start gap-3 rounded-xl border border-slate-100 p-3"
              >
                <span className="mt-1.5 h-2 w-2 rounded-full bg-indigo-500" />
                <div>
                  <p className="text-xs font-semibold text-slate-700">
                    {activity.text}
                  </p>
                  <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {activity.time || 'Just now'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function PageHeading({ title, description, action }) {
  return (
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          {title}
        </h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          {description}
        </p>
      </div>
      {action}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">
        {label}
      </span>
      {children}
    </label>
  );
}

function ApprovalRequestForm({ form, setForm, residences, onSubmit }) {
  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="rounded-xl bg-amber-50 p-2.5 text-amber-600">
          <Send className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-base font-extrabold text-slate-900">
            Request Resident Approval
          </h2>
          <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
            Send an unplanned visitor request to the correct flat.
          </p>
        </div>
      </div>
      <form onSubmit={onSubmit} className="mt-5 space-y-4">
        <Field label="Visiting Flat">
          <select
            required
            value={form.flat}
            onChange={(event) => setForm({ ...form, flat: event.target.value })}
            className={inputClass}
          >
            {residences.map((residence) => (
              <option key={residence.flat} value={residence.flat}>
                Flat {residence.flat} · {residence.residentName}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Visitor / Group Label">
            <input
              required
              value={form.visitorLabel}
              onChange={(event) =>
                setForm({ ...form, visitorLabel: event.target.value })
              }
              placeholder="e.g. Courier or Sharma family"
              className={inputClass}
            />
          </Field>
          <Field label="Purpose">
            <select
              value={form.purpose}
              onChange={(event) =>
                setForm({ ...form, purpose: event.target.value })
              }
              className={inputClass}
            >
              <option>Guest</option>
              <option>Delivery</option>
              <option>Service</option>
              <option>Other</option>
            </select>
          </Field>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Date">
            <input
              required
              type="date"
              min={todayISO()}
              value={form.date}
              onChange={(event) => setForm({ ...form, date: event.target.value })}
              className={inputClass}
            />
          </Field>
          <Field label="Time">
            <input
              required
              type="time"
              value={form.time}
              onChange={(event) => setForm({ ...form, time: event.target.value })}
              className={inputClass}
            />
          </Field>
          <Field label="Guests">
            <input
              required
              type="number"
              min="1"
              max="25"
              value={form.guestCount}
              onChange={(event) =>
                setForm({ ...form, guestCount: Number(event.target.value) })
              }
              className={inputClass}
            />
          </Field>
        </div>
        <button
          type="submit"
          disabled={!residences.length}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-amber-500 py-3 text-xs font-bold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          <Send className="h-4 w-4" />
          Send Approval Request
        </button>
      </form>
    </section>
  );
}

function VerificationPanel({
  manualCode,
  setManualCode,
  onSubmit,
  scannerActive,
  scannerMessage,
  videoRef,
  onStartScanner,
  onStopScanner,
  result,
  onDismissResult,
}) {
  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="rounded-xl bg-indigo-50 p-2.5 text-indigo-600">
          <ScanLine className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-base font-extrabold text-slate-900">
            Verify Visitor Pass
          </h2>
          <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
            Scan the resident QR or enter its six-digit security code.
          </p>
        </div>
      </div>

      <div className="mt-5 space-y-4">
        {scannerActive ? (
          <div className="relative overflow-hidden rounded-2xl bg-slate-950">
            <video
              ref={videoRef}
              muted
              playsInline
              className="aspect-video w-full object-cover"
            />
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="h-36 w-36 rounded-2xl border-2 border-white/80 shadow-[0_0_0_999px_rgba(15,23,42,0.35)]" />
            </div>
            <button
              type="button"
              onClick={onStopScanner}
              className="absolute right-3 top-3 rounded-full bg-slate-950/70 p-2 text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={onStartScanner}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 py-3 text-xs font-bold text-indigo-700 hover:bg-indigo-100"
          >
            <Camera className="h-4 w-4" />
            Start QR Camera Scanner
          </button>
        )}

        {scannerMessage && (
          <p className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-[11px] font-semibold text-amber-800">
            {scannerMessage}
          </p>
        )}

        <div className="relative flex items-center justify-center">
          <div className="absolute inset-x-0 border-t border-slate-100" />
          <span className="relative bg-white px-3 text-[9px] font-bold uppercase tracking-widest text-slate-400">
            or enter manually
          </span>
        </div>

        <form onSubmit={onSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <KeyRound className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              required
              inputMode="numeric"
              value={manualCode}
              onChange={(event) =>
                setManualCode(event.target.value.trimStart())
              }
              placeholder="Enter security code"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-10 pr-4 font-mono text-sm font-bold tracking-[0.14em] text-slate-800 focus:border-indigo-500 focus:bg-white focus:outline-none"
            />
          </div>
          <button
            type="submit"
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 text-xs font-bold text-white hover:bg-indigo-700"
          >
            <LogIn className="h-4 w-4" />
            Verify
          </button>
        </form>
        <ResultMessage result={result} onClose={onDismissResult} />
      </div>
    </section>
  );
}

function ApprovalQueue({ pending, approved, onAllowEntry }) {
  const queue = [...approved, ...pending];

  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-extrabold text-slate-900">
            Resident Approval Queue
          </h2>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Updates appear automatically when a resident responds.
          </p>
        </div>
        <span className="rounded-full bg-amber-50 px-3 py-1 text-[10px] font-extrabold text-amber-700">
          {queue.length} OPEN
        </span>
      </div>
      <div className="mt-5 space-y-3">
        {queue.length ? (
          queue.map((visitor) => (
            <div
              key={visitor.id}
              className="rounded-xl border border-slate-100 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-extrabold text-slate-800">
                    {visitor.name}
                  </p>
                  <p className="mt-1 text-[11px] font-semibold text-slate-400">
                    Flat {visitor.flat} · {visitor.purpose} ·{' '}
                    {visitor.guestCount || 1} guest
                    {Number(visitor.guestCount || 1) === 1 ? '' : 's'}
                  </p>
                </div>
                <Status status={visitor.status} />
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-slate-50 pt-3">
                <p className="text-[10px] font-semibold text-slate-400">
                  Requested by {visitor.requestedBy || 'Gate security'} ·{' '}
                  {formatVisitTime(visitor)}
                </p>
                {visitor.status === 'Approved' && (
                  <button
                    type="button"
                    onClick={() => onAllowEntry(visitor.id)}
                    className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-[10px] font-bold text-white hover:bg-emerald-700"
                  >
                    <DoorOpen className="h-3.5 w-3.5" />
                    Allow Entry
                  </button>
                )}
              </div>
            </div>
          ))
        ) : (
          <EmptyState
            icon={CheckCircle2}
            text="No visitor approvals are waiting at the gate."
          />
        )}
      </div>
    </section>
  );
}

function InsideNow({ visitors, onCheckOut }) {
  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-extrabold text-slate-900">
            Visitors Inside
          </h2>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Record checkout when a visitor leaves.
          </p>
        </div>
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-[10px] font-extrabold text-emerald-700">
          {visitors.length} PASSES
        </span>
      </div>
      <div className="mt-5 space-y-3">
        {visitors.length ? (
          visitors.map((visitor) => (
            <div
              key={visitor.id}
              className="flex items-center justify-between gap-4 rounded-xl border border-slate-100 p-4"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-emerald-50 p-2.5 text-emerald-600">
                  <UserCheck className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-extrabold text-slate-800">
                    {visitor.name}
                  </p>
                  <p className="mt-1 text-[10px] font-semibold text-slate-400">
                    Flat {visitor.flat} · In at {visitor.checkInTime} ·{' '}
                    {visitor.guestCount || 1} guest
                    {Number(visitor.guestCount || 1) === 1 ? '' : 's'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onCheckOut(visitor.id)}
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[10px] font-bold text-slate-600 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
              >
                <LogOut className="h-3.5 w-3.5" />
                Check Out
              </button>
            </div>
          ))
        ) : (
          <EmptyState
            icon={Users}
            text="No visitors are currently recorded inside."
          />
        )}
      </div>
    </section>
  );
}

function QuickActions({ onVisitors, onHistory, onEmergency }) {
  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
      <h2 className="text-base font-extrabold text-slate-900">Gate Tools</h2>
      <p className="mt-1 text-xs font-semibold text-slate-400">
        Common security tasks.
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {[
          [Send, 'Request approval', onVisitors, 'bg-amber-50 text-amber-600'],
          [History, 'View history', onHistory, 'bg-indigo-50 text-indigo-600'],
          [LifeBuoy, 'Emergency desk', onEmergency, 'bg-rose-50 text-rose-600'],
        ].map(([Icon, label, onClick, classes]) => (
          <button
            key={label}
            type="button"
            onClick={onClick}
            className="rounded-xl border border-slate-100 p-4 text-left hover:border-indigo-200 hover:shadow-sm"
          >
            <div className={`mb-3 w-fit rounded-lg p-2 ${classes}`}>
              <Icon className="h-4 w-4" />
            </div>
            <p className="text-xs font-bold text-slate-700">{label}</p>
          </button>
        ))}
      </div>
    </section>
  );
}

function Status({ status }) {
  return (
    <span
      className={`whitespace-nowrap rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${
        statusClasses[status] || statusClasses.Expected
      }`}
    >
      {status}
    </span>
  );
}

function EmptyState({ icon: Icon, text }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center">
      <Icon className="h-6 w-6 text-slate-300" />
      <p className="mt-2 text-xs font-semibold text-slate-400">{text}</p>
    </div>
  );
}

function GateHistory({ visitors }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
      {visitors.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50 text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                <th className="px-6 py-4">Visitor</th>
                <th className="px-6 py-4">Residence</th>
                <th className="px-6 py-4">Security Code</th>
                <th className="px-6 py-4">Entry / Exit</th>
                <th className="px-6 py-4">Handled By</th>
                <th className="px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visitors.map((visitor) => (
                <tr key={visitor.id} className="text-xs text-slate-600">
                  <td className="px-6 py-4">
                    <p className="font-extrabold text-slate-800">
                      {visitor.name}
                    </p>
                    <p className="mt-1 text-[10px] font-semibold text-slate-400">
                      {visitor.purpose} · {visitor.guestCount || 1} guest
                      {Number(visitor.guestCount || 1) === 1 ? '' : 's'}
                    </p>
                  </td>
                  <td className="px-6 py-4 font-bold">Flat {visitor.flat}</td>
                  <td className="px-6 py-4 font-mono font-bold text-indigo-700">
                    {getVisitorSecurityCode(visitor) || '—'}
                  </td>
                  <td className="px-6 py-4">
                    <p>In: {visitor.checkInTime || '—'}</p>
                    <p className="mt-1 text-[10px] text-slate-400">
                      Out: {visitor.checkOutTime || '—'}
                    </p>
                  </td>
                  <td className="px-6 py-4">
                    {visitor.checkedInBy || visitor.rejectedBy || '—'}
                  </td>
                  <td className="px-6 py-4">
                    <Status status={visitor.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="p-6">
          <EmptyState
            icon={Clock3}
            text="Gate activity will appear here after the first visitor entry."
          />
        </div>
      )}
    </section>
  );
}
