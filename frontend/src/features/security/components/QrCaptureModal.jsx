import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Camera, X } from 'lucide-react';

export default function QrCaptureModal({ onClose, onCapture, disabled }) {
  const dialogRef = useRef(null);
  const videoRef = useRef(null);
  const detectorRef = useRef(null);
  const cancelledRef = useRef(false);
  const capturingRef = useRef(false);
  const [ready, setReady] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [message, setMessage] = useState('');
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    const video = videoRef.current;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = 'hidden';
    let cancelled = false;
    let stream;
    cancelledRef.current = false;

    const release = () => {
      stream?.getTracks().forEach((track) => track.stop());
      video.srcObject = null;
    };
    const cameraEnded = () => {
      if (cancelled) return;
      setReady(false);
      setMessage('The camera disconnected. Close this popup and open it again, or type the code.');
      release();
    };
    const start = async () => {
      try {
        detectorRef.current = new globalThis.BarcodeDetector({ formats: ['qr_code'] });
      } catch {
        setMessage('This browser cannot read QR codes. Close this popup and type the security code.');
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        });
        // Permission may resolve after closing, navigation, or effect cleanup.
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        stream.getTracks().forEach((track) => track.addEventListener('ended', cameraEnded));
        video.srcObject = stream;
        await video.play();
        if (!cancelled) {
          setReady(video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0);
        }
      } catch (error) {
        if (cancelled) return;
        release();
        setReady(false);
        setMessage(
          error.name === 'NotAllowedError'
            ? 'Camera access was denied. Allow camera access and reopen the scanner, or type the code.'
            : 'The camera could not start. Check that it is connected and available, or type the code.'
        );
      }
    };
    void start();

    return () => {
      cancelled = true;
      cancelledRef.current = true;
      stream?.getTracks().forEach((track) => track.removeEventListener('ended', cameraEnded));
      release();
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  const close = () => {
    // Suppress a pending decode immediately, before React unmounts the popup.
    cancelledRef.current = true;
    onClose();
  };

  const capture = async () => {
    const video = videoRef.current;
    if (disabled || !ready || capturingRef.current || cancelledRef.current) return;
    if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
      setReady(false);
      return;
    }
    capturingRef.current = true;
    setCapturing(true);
    setMessage('');
    try {
      // Freeze one frame at the user's click; never decode the moving stream.
      const frame = document.createElement('canvas');
      frame.width = video.videoWidth;
      frame.height = video.videoHeight;
      frame.getContext('2d').drawImage(video, 0, 0, frame.width, frame.height);
      const codes = await detectorRef.current.detect(frame);
      if (cancelledRef.current) return;
      const credential = codes.find((code) => code.rawValue)?.rawValue;
      if (credential) {
        void onCapture(credential);
      } else {
        setMessage('No QR code was found. Hold the pass steady and take another picture.');
      }
    } catch {
      if (!cancelledRef.current) {
        setMessage('That picture could not be read. Try another picture, or type the code.');
      }
    } finally {
      capturingRef.current = false;
      if (!cancelledRef.current) setCapturing(false);
    }
  };

  return createPortal(
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      className="fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-3xl border-0 bg-white p-0 text-slate-900 shadow-2xl backdrop:bg-slate-900/60"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div className="p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={titleId} className="text-base font-extrabold">Scan visitor QR</h2>
            <p id={descriptionId} className="mt-1 text-xs text-slate-500">
              Position the QR code in view, then take a picture to verify the pass.
            </p>
          </div>
          <button type="button" onClick={close} aria-label="Close scanner"
            className="rounded-full bg-slate-100 p-2 text-slate-600 hover:bg-slate-200">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="relative mt-5 overflow-hidden rounded-2xl bg-slate-950">
          <video ref={videoRef} muted playsInline aria-label="Live camera preview"
            onLoadedData={() => {
              const video = videoRef.current;
              setReady(video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0);
            }}
            className="max-h-[55dvh] min-h-48 w-full object-contain" />
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-36 w-36 rounded-2xl border-2 border-white/80" />
          </div>
        </div>
        {!ready && !message ? <p role="status" className="mt-3 text-xs text-slate-500">Starting camera…</p> : null}
        {message ? <p role="alert" className="mt-3 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">{message}</p> : null}
        <button type="button" onClick={() => void capture()} disabled={!ready || capturing || disabled}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-60">
          <Camera className="h-5 w-5" />
          {capturing ? 'Reading picture…' : 'Take picture'}
        </button>
      </div>
    </dialog>,
    document.body
  );
}
