import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import { resendEmailConfirmation, verifyEmailToken } from '../../lib/auth/authService';
import { authIntentFromSearch, destinationAfterAuth } from '../../routes/authRoutes';
import { useAuthStore } from '../../store/authStore';
import { recordServiceSignupEvent } from '../../lib/telemetry/serviceSignupTelemetry';

const BUTTON = 'w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white disabled:opacity-60';

/**
 * Spends the one-time hash from a confirmation email.
 *
 * Confirming is an explicit click rather than something that happens on page
 * load, so a mail-security scanner following the link cannot burn the hash
 * before the person does.
 *
 * The page can also be reached with no hash to spend -- an already-used link, or
 * a Supabase template still on GoTrue's default `{{ .ConfirmationURL }}`, which
 * verifies at the provider and redirects here empty-handed. That used to leave a
 * greyed-out button and no explanation. Now it says which of those happened and
 * offers the way out of both.
 */
export default function EmailConfirmationPage() {
  const navigate = useNavigate();
  const completeExternalLogin = useAuthStore((state) => state.completeExternalLogin);
  const [token, setToken] = useState('');
  const [type, setType] = useState('email');
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [intent, setIntent] = useState(null);

  useEffect(() => {
    const saved = window.history.state?.emailConfirmation;
    const params = new URLSearchParams(window.location.search);
    const value = saved?.token || params.get('token_hash') || '';
    const nextIntent = saved?.intent || authIntentFromSearch(window.location.search);
    const nextType = saved?.type || (params.get('type') === 'signup' ? 'signup' : 'email');
    setToken(value);
    setType(nextType);
    setIntent(nextIntent);
    setReady(true);
    // Keep the hash out of history and out of anything that reads the URL bar.
    if (value) {
      window.history.replaceState(
        { ...window.history.state, emailConfirmation: { token: value, type: nextType, intent: nextIntent } },
        '',
        `/auth/confirm-email${nextIntent ? `?intent=${nextIntent}` : ''}`,
      );
    }
  }, []);

  const confirm = async () => {
    setBusy(true);
    setError('');
    try {
      await verifyEmailToken(token, type);
      const result = await completeExternalLogin();
      if (!result.success) throw new Error(result.message);
      if (intent) void recordServiceSignupEvent('auth_completed');
      navigate(destinationAfterAuth(result.context, intent), { replace: true });
    } catch (reason) {
      setError(reason.message || 'This verification link is invalid or expired.');
    } finally {
      setBusy(false);
    }
  };

  const resend = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await resendEmailConfirmation(email, intent);
      // Deliberately the same answer whether or not that address has an
      // unconfirmed account, so this cannot be used to discover who registered.
      setNotice('If an unconfirmed account exists for that address, a new link is on its way.');
    } catch (reason) {
      setError(reason.message || 'Could not send a new link. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  if (!ready) return null;
  const loginPath = `/login${intent ? `?intent=${intent}` : ''}`;

  if (token) {
    return (
      <AuthCard
        title="Confirm your email"
        description="Confirming is an explicit action to protect email links from security scanners."
      >
        <div className="space-y-4 text-center">
          <p className="text-sm text-slate-600">Your email is ready to verify.</p>
          {error ? <p role="alert" className="text-xs font-semibold text-rose-600">{error}</p> : null}
          <button type="button" disabled={busy} onClick={confirm} className={BUTTON}>
            {busy ? 'Confirming…' : 'Confirm email'}
          </button>
          <Link to={loginPath} className="text-xs font-bold text-indigo-600">Back to sign in</Link>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="This link has nothing left to confirm" description="It was already used, or it arrived without its verification token.">
      <form onSubmit={resend} className="space-y-4">
        <p className="text-sm text-slate-600">
          If you have just clicked the link in your email, your address may already be confirmed —
          try signing in first. Otherwise, send yourself a fresh link.
        </p>
        <label className="block space-y-1">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Email address</span>
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm"
          />
        </label>
        {error ? <p role="alert" className="text-xs font-semibold text-rose-600">{error}</p> : null}
        {notice ? <p role="status" className="text-xs font-semibold text-emerald-600">{notice}</p> : null}
        <button type="submit" disabled={busy} className={BUTTON}>
          {busy ? 'Sending…' : 'Send a new link'}
        </button>
        <div className="text-center">
          <Link to={loginPath} className="text-xs font-bold text-indigo-600">Back to sign in</Link>
        </div>
      </form>
    </AuthCard>
  );
}
