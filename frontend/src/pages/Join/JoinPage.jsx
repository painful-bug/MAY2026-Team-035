import { useEffect, useRef, useState } from 'react';
import { Building, Loader2 } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { prepareInvitation } from '../../lib/auth/authService';
import { AUTH_ROUTES, getDashboardRouteForRole } from '../../routes/authRoutes';
import { useAuthStore } from '../../store/authStore';

export default function JoinPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const prepared = useRef(false);
  const currentUser = useAuthStore((state) => state.currentUser);
  const isAuthReady = useAuthStore((state) => state.isAuthReady);
  const beginGoogleSignIn = useAuthStore((state) => state.beginGoogleSignIn);
  const redeemInvite = useAuthStore((state) => state.redeemInvite);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [working, setWorking] = useState(Boolean(token));

  const prepare = async (artifact) => {
    setError(''); setWorking(true);
    try {
      await prepareInvitation(artifact);
      prepared.current = true;
      if (currentUser) {
        const result = await redeemInvite();
        if (result.success) navigate(getDashboardRouteForRole(result.user.role), { replace: true });
        else setError(result.message);
      } else {
        beginGoogleSignIn('/join');
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'This invitation cannot be used.');
    } finally { setWorking(false); }
  };

  useEffect(() => {
    if (token && !prepared.current) void prepare({ token });
  // The link token is intentionally consumed into an HTTP-only pending-invite cookie.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token && isAuthReady && currentUser && !prepared.current) {
      setWorking(true);
      redeemInvite().then((result) => {
        if (result.success) navigate(getDashboardRouteForRole(result.user.role), { replace: true });
        else setError(result.message);
      }).finally(() => setWorking(false));
    }
  }, [currentUser, isAuthReady, navigate, redeemInvite, token]);

  const submitCode = (event) => {
    event.preventDefault();
    if (code.trim()) void prepare({ code: code.trim() });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12 font-sans">
      <div className="w-full max-w-md space-y-6 rounded-3xl border border-slate-100 bg-white p-8 text-center shadow-xl shadow-slate-100 animate-slide-up">
        <div className="inline-flex items-center justify-center gap-2"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white"><Building className="h-5 w-5" /></div><span className="font-extrabold tracking-tight text-slate-900">HomeBandhu</span></div>
        <div className="space-y-1"><h1 className="text-xl font-extrabold text-slate-900">Activate your invitation</h1><p className="text-xs font-semibold text-slate-400">Only the invited, verified Google email can activate this membership.</p></div>
        {error && <p role="alert" className="rounded-xl border border-rose-100 bg-rose-50 p-3 text-xs font-semibold text-rose-700">{error}</p>}
        {token || working ? <div className="flex justify-center py-4 text-xs font-semibold text-slate-500"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Preparing secure invitation…</div> : (
          <form onSubmit={submitCode} className="space-y-3 text-left"><label htmlFor="invite-code" className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Invitation code</label><input id="invite-code" value={code} onChange={(event) => setCode(event.target.value)} placeholder="Enter invitation code" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-500 focus:bg-white" /><button type="submit" className="w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white">Continue with Google</button></form>
        )}
        <Link to={AUTH_ROUTES.LOGIN} className="block text-xs font-bold text-indigo-600 hover:underline">Back to sign in</Link>
      </div>
    </div>
  );
}
