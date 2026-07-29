import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

export default function AccountPage() {
  const context = useAuthStore((state) => state.sessionContext);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const leave = async () => { await logout(); navigate('/login', { replace: true }); };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <section className="w-full max-w-lg rounded-3xl border border-slate-100 bg-white p-8 shadow-xl shadow-slate-100">
        <p className="text-xs font-bold uppercase tracking-widest text-indigo-600">HomeBandhu account</p>
        <h1 className="mt-2 text-2xl font-extrabold text-slate-900">Your account is active</h1>
        <p className="mt-3 text-sm font-medium leading-relaxed text-slate-600">You are signed in as {context?.identity?.email}. Your {context?.membership?.role || 'community'} membership does not yet have a dedicated operational portal.</p>
        <button type="button" onClick={leave} className="mt-6 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white">Sign out</button>
      </section>
    </main>
  );
}
