import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import { verifyEmailToken, homeRouteFor } from '../../lib/auth/authService';
import { useAuthStore } from '../../store/authStore';

function confirmationFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token_hash') || window.history.state?.emailConfirmation?.token || '';
  const type = params.get('type') || window.history.state?.emailConfirmation?.type || 'email';
  return { token, type: type === 'signup' ? 'signup' : 'email' };
}

export default function EmailConfirmationPage() {
  const navigate = useNavigate();
  const completeExternalLogin = useAuthStore((state) => state.completeExternalLogin);
  const [{ token, type }] = useState(confirmationFromLocation);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has('token_hash')) {
      window.history.replaceState({ ...window.history.state, emailConfirmation: { token, type } }, '', '/auth/confirm-email');
    }
  }, [token, type]);
  const confirm = async () => { setBusy(true); setError(''); try { await verifyEmailToken(token, type); const result = await completeExternalLogin(); if (!result.success) throw new Error(result.message); navigate(homeRouteFor(result.context), { replace: true }); } catch (reason) { setError(reason.message || 'This verification link is invalid or expired.'); } finally { setBusy(false); } };
  return <AuthCard title="Confirm your email" description="Confirming is an explicit action to protect email links from security scanners."><div className="space-y-4 text-center"><p className="text-sm text-slate-600">Your email is ready to verify.</p>{error ? <p role="alert" className="text-xs font-semibold text-rose-600">{error}</p> : null}<button type="button" disabled={!token || busy} onClick={confirm} className="w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white disabled:opacity-60">{busy ? 'Confirming…' : 'Confirm email'}</button><Link to="/login" className="text-xs font-bold text-indigo-600">Back to sign in</Link></div></AuthCard>;
}
