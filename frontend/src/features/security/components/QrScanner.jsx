import { useCallback, useRef, useState } from 'react';
import { Camera, KeyRound, LogIn, ScanLine } from 'lucide-react';
import QrCaptureModal from './QrCaptureModal';
import { visitorCredential } from '../../../lib/visitorQr';

// Only decoded credentials leave this component. Manual entry remains available
// when the browser does not expose the native QR decoder or camera access.

export default function QrScanner({ onScan, busy = false, disabled = false, hint }) {
  const submittingRef = useRef(false);
  const [submitting, setSubmitting] = useState(false);
  const [active, setActive] = useState(false);
  const [message, setMessage] = useState('');
  const [code, setCode] = useState('');

  const stop = useCallback(() => setActive(false), []);
  const blocked = busy || disabled || submitting;

  const start = () => {
    if (blocked || submittingRef.current || active) return;
    setMessage('');
    const BarcodeDetector = globalThis.BarcodeDetector;
    if (!BarcodeDetector || !navigator.mediaDevices?.getUserMedia) {
      setMessage(
        'This browser cannot scan QR codes. Type the six-digit security code instead.'
      );
      return;
    }
    setActive(true);
  };

  const verify = async (raw) => {
    if (blocked || submittingRef.current) return;
    let credential;
    try {
      credential = visitorCredential(raw);
    } catch (error) {
      stop();
      setMessage(error.message);
      return;
    }
    submittingRef.current = true;
    setSubmitting(true);
    setMessage('');
    stop();
    try {
      await onScan(credential);
      setCode('');
    } catch {
      setMessage('The pass could not be verified. Please try again.');
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const submit = (event) => {
    event.preventDefault();
    const trimmed = code.trim();
    if (!trimmed || active) return;
    void verify(trimmed);
  };

  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="rounded-xl bg-indigo-50 p-2.5 text-indigo-600">
          <ScanLine className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-base font-extrabold text-slate-900">Verify a visitor</h2>
          <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
            {hint || 'Scan the resident QR, or enter its six-digit security code.'}
          </p>
        </div>
      </div>

      <div className="mt-5 space-y-4">
        {active ? (
          <QrCaptureModal onClose={stop} onCapture={verify} disabled={blocked} />
        ) : null}
        <button
          type="button"
          onClick={start}
          disabled={blocked}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 py-3 text-xs font-bold text-indigo-700 hover:bg-indigo-100 disabled:opacity-60"
        >
          <Camera className="h-4 w-4" />
          Start QR camera scanner
        </button>

        {message ? (
          <p role="alert" className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-[11px] font-semibold text-amber-800">
            {message}
          </p>
        ) : null}

        <div className="relative flex items-center justify-center">
          <div className="absolute inset-x-0 border-t border-slate-100" />
          <span className="relative bg-white px-3 text-[9px] font-bold uppercase tracking-widest text-slate-400">
            or enter manually
          </span>
        </div>

        <form onSubmit={submit} className="flex gap-2">
          <div className="relative flex-1">
            <KeyRound className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              required
              disabled={blocked || active}
              inputMode="numeric"
              value={code}
              onChange={(event) => setCode(event.target.value.trimStart())}
              placeholder="Security code"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-10 pr-4 font-mono text-sm font-bold tracking-[0.14em] text-slate-800 focus:border-indigo-500 focus:bg-white focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={blocked || active}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            <LogIn className="h-4 w-4" />
            {busy || submitting ? 'Checking…' : 'Verify'}
          </button>
        </form>
      </div>
    </section>
  );
}
