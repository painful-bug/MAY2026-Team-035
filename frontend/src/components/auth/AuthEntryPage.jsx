import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Navigate, useNavigate } from 'react-router-dom';
import AuthCard from './AuthCard';
import {
  getAuthMethods, homeRouteFor, signInWithPassword, signUpWithPassword,
} from '../../lib/auth/authService';
import { AUTH_FLOW_STATE, useAuthStore } from '../../store/authStore';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import TurnstileChallenge from './TurnstileChallenge';

export default function AuthEntryPage() {
  const navigate = useNavigate();
  const beginOAuth = useAuthStore((state) => state.beginOAuth);
  const completeExternalLogin = useAuthStore((state) => state.completeExternalLogin);
  const authFlowState = useAuthStore((state) => state.authFlowState);
  const sessionContext = useAuthStore((state) => state.sessionContext);
  const isAuthReady = useAuthStore((state) => state.isAuthReady);
  const [methods, setMethods] = useState(null);
  const [error, setError] = useState('');
  // Set when sign-in was refused for an unconfirmed address, so the error can
  // carry the way out of it instead of just naming the problem.
  const [needsConfirmation, setNeedsConfirmation] = useState(false);
  const [mode, setMode] = useState('sign-in');
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm: '', captcha_token: '' });
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState('');
  const setCaptcha = useCallback((captcha_token) => setForm((current) => ({ ...current, captcha_token })), []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getAuthMethods({ signal: controller.signal })
      .then((configuredMethods) => {
        if (active) setMethods(configuredMethods);
      })
      .catch((requestError) => {
        // React Strict Mode intentionally cleans up the first effect before
        // re-running it in development. That cancellation is not an auth
        // failure and must not overwrite the second request's UI state.
        const wasAborted = controller.signal.aborted
          || requestError?.name === 'AbortError'
          || requestError?.message === 'Fetch is aborted';
        if (active && !wasAborted) {
          setError(requestError.message || 'Authentication is unavailable.');
        }
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  if (isAuthReady && sessionContext?.identity) return <Navigate to={homeRouteFor(sessionContext)} replace />;

  const redirecting = authFlowState === AUTH_FLOW_STATE.REDIRECTING;
  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault();
    setError(''); setNotice(''); setNeedsConfirmation(false);
    if (mode === 'sign-up' && form.password !== form.confirm) {
      setError('Passwords do not match.'); return;
    }
    setSubmitting(true);
    try {
      if (mode === 'sign-up') {
        await signUpWithPassword({ full_name: form.full_name, email: form.email, password: form.password, captcha_token: form.captcha_token || null });
        setNotice('Check your email to confirm your account before continuing.');
      } else {
        await signInWithPassword({ email: form.email, password: form.password, captcha_token: form.captcha_token || null });
        const result = await completeExternalLogin();
        if (!result.success) throw new Error(result.message);
        navigate(homeRouteFor(result.context), { replace: true });
      }
    } catch (requestError) {
      setError(requestError.message || 'Unable to continue. Please try again.');
      setNeedsConfirmation(requestError.code === 'email_not_confirmed');
    } finally { setSubmitting(false); }
  };

  const primary = methods?.primary;
  const ordered = methods?.methods || [];
  return (
    <AuthCard title="Welcome to HomeBandhu" description="Sign in or create an account, then join or create your community.">
      <div className="space-y-4">
        {methods === null && !error ? <div className="flex justify-center py-3"><Loader2 className="h-5 w-5 animate-spin text-indigo-600" /></div> : null}
        {ordered.map((method) => method.id === 'google' ? (
          <button key={method.id} type="button" onClick={() => beginOAuth(method.id, AUTH_ROUTES.AUTH_CALLBACK)} disabled={redirecting} className={`flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-3 font-bold shadow-sm transition-all disabled:cursor-wait disabled:opacity-60 ${primary === method.id ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'}`}>
            {redirecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className={primary === method.id ? 'text-white' : 'text-[#4285F4]'}>G</span>}
            {redirecting ? 'Redirecting…' : method.label}
          </button>
        ) : null)}
        {ordered.some((method) => method.id === 'email_password') ? (
          <form onSubmit={submit} className="space-y-3 rounded-2xl border border-slate-100 bg-slate-50 p-4">
            <div className="flex rounded-lg bg-white p-1 text-xs font-bold">
              {['sign-in', 'sign-up'].map((nextMode) => <button key={nextMode} type="button" onClick={() => { setMode(nextMode); setError(''); setNotice(''); }} className={`flex-1 rounded-md px-3 py-2 ${mode === nextMode ? 'bg-indigo-600 text-white' : 'text-slate-500'}`}>{nextMode === 'sign-in' ? 'Sign in' : 'Create account'}</button>)}
            </div>
            {mode === 'sign-up' ? <input value={form.full_name} onChange={update('full_name')} required autoComplete="name" placeholder="Full name" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm" /> : null}
            <input value={form.email} onChange={update('email')} required type="email" autoComplete="email" placeholder="Email" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm" />
            <input value={form.password} onChange={update('password')} required type="password" minLength="15" maxLength="256" autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'} placeholder="Password" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm" />
            {mode === 'sign-up' ? <input value={form.confirm} onChange={update('confirm')} required type="password" autoComplete="new-password" placeholder="Confirm password" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm" /> : null}
            <TurnstileChallenge onToken={setCaptcha} />
            <button type="submit" disabled={submitting} className={`w-full rounded-xl px-4 py-3 text-sm font-bold text-white disabled:opacity-60 ${primary === 'email_password' ? 'bg-indigo-600' : 'bg-slate-800'}`}>{submitting ? 'Please wait…' : mode === 'sign-in' ? 'Continue with email' : 'Create account'}</button>
            <button type="button" onClick={() => navigate('/auth/forgot-password')} className="w-full text-xs font-bold text-indigo-600">Forgot password?</button>
          </form>
        ) : null}
        {notice ? <p className="text-center text-xs font-semibold text-emerald-700">{notice}</p> : null}
        {error ? <p role="alert" className="text-center text-xs font-semibold text-rose-600">{error}</p> : null}
        {needsConfirmation ? (
          <button type="button" onClick={() => navigate(AUTH_ROUTES.CONFIRM_EMAIL)} className="w-full text-xs font-bold text-indigo-600">
            Send me a new confirmation link
          </button>
        ) : null}
      </div>
    </AuthCard>
  );
}
