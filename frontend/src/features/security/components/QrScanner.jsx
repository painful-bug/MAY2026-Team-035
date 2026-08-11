import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, KeyRound, LogIn, ScanLine, X } from 'lucide-react';

// The camera half of the gate, carried over from the demo dashboard unchanged
// in substance — `BarcodeDetector` + `getUserMedia` is real browser code and was
// the one part of that file worth keeping. What changed is the seam: it used to
// call the zustand store directly, and now it hands the raw scanned string to
// `onScan` and knows nothing about what happens next.
//
// **The manual code path is not a fallback, it is the primary path on most
// devices.** `BarcodeDetector` ships in Chromium and nowhere else; a guard on an
// iPhone will type every code they ever verify. So the input is always visible
// rather than hidden behind a "scanning didn't work" state.

export default function QrScanner({ onScan, busy = false, disabled = false, hint }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const scanBusyRef = useRef(false);
  const [active, setActive] = useState(false);
  const [message, setMessage] = useState('');
  const [code, setCode] = useState('');

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setActive(false);
    scanBusyRef.current = false;
  }, []);

  // The camera must be released when the guard navigates away. Without this the
  // light stays on until the tab closes.
  useEffect(() => stop, [stop]);

  const start = async () => {
    setMessage('');
    const BarcodeDetector = globalThis.BarcodeDetector;
    if (!BarcodeDetector || !navigator.mediaDevices?.getUserMedia) {
      setMessage(
        'This browser cannot scan QR codes. Type the six-digit security code instead.'
      );
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      });
      streamRef.current = stream;
      setActive(true);
      await new Promise((resolve) => setTimeout(resolve, 0));
      if (!videoRef.current) {
        stop();
        return;
      }
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      const detector = new BarcodeDetector({ formats: ['qr_code'] });

      timerRef.current = setInterval(async () => {
        if (scanBusyRef.current || !videoRef.current || videoRef.current.readyState < 2) {
          return;
        }
        scanBusyRef.current = true;
        try {
          const codes = await detector.detect(videoRef.current);
          if (codes[0]?.rawValue) {
            stop();
            onScan(codes[0].rawValue);
          }
        } catch {
          setMessage('That QR could not be read. Hold it steady, or type the code.');
        } finally {
          scanBusyRef.current = false;
        }
      }, 500);
    } catch {
      stop();
      setMessage('Camera permission was refused. Type the code instead.');
    }
  };

  const submit = (event) => {
    event.preventDefault();
    const trimmed = code.trim();
    if (!trimmed) return;
    stop();
    onScan(trimmed);
    setCode('');
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
          <div className="relative overflow-hidden rounded-2xl bg-slate-950">
            <video ref={videoRef} muted playsInline className="aspect-video w-full object-cover" />
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="h-36 w-36 rounded-2xl border-2 border-white/80 shadow-[0_0_0_999px_rgba(15,23,42,0.35)]" />
            </div>
            <button
              type="button"
              onClick={stop}
              aria-label="Stop scanning"
              className="absolute right-3 top-3 rounded-full bg-slate-950/70 p-2 text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={start}
            disabled={disabled}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 py-3 text-xs font-bold text-indigo-700 hover:bg-indigo-100 disabled:opacity-60"
          >
            <Camera className="h-4 w-4" />
            Start QR camera scanner
          </button>
        )}

        {message ? (
          <p className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-[11px] font-semibold text-amber-800">
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
              inputMode="numeric"
              value={code}
              onChange={(event) => setCode(event.target.value.trimStart())}
              placeholder="Security code"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-10 pr-4 font-mono text-sm font-bold tracking-[0.14em] text-slate-800 focus:border-indigo-500 focus:bg-white focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={busy || disabled}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            <LogIn className="h-4 w-4" />
            {busy ? 'Checking…' : 'Verify'}
          </button>
        </form>
      </div>
    </section>
  );
}
