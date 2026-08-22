import { SESSION_STATUS, useAuthStore } from '../../store/authStore';

export default function SessionRestorationState() {
  const ready = useAuthStore((state) => state.isAuthReady);
  const status = useAuthStore((state) => state.sessionStatus);
  const message = useAuthStore((state) => state.authError);
  const retry = useAuthStore((state) => state.initializeAuth);

  if (!ready) {
    return (
      <div
        aria-live="polite"
        className="flex min-h-screen items-center justify-center bg-slate-50 text-sm font-semibold text-slate-500"
      >
        Restoring your session…
      </div>
    );
  }

  if (status !== SESSION_STATUS.ERROR) return null;
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div role="alert" className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <h1 className="text-lg font-bold text-slate-900">We could not restore your session</h1>
        <p className="mt-2 text-sm text-slate-600">{message || 'Check your connection and try again.'}</p>
        <button
          type="button"
          onClick={() => void retry()}
          className="mt-5 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-bold text-white"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
